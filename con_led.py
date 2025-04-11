import nidaqmx
import socket
import logging
import warnings
import argparse
from time import sleep, time

def parse_zone_decay_rates(zones_str):
    """
    Parses a string containing zone:decay_rate pairs separated by commas 
    (e.g., "0:0.02,1:0.01") into a dictionary mapping int(zone) -> float(decay_rate).
    """
    zone_decay_rates = {}
    for zone_pair in zones_str.split(','):
        try:
            zone, decay_rate = zone_pair.split(':')
            zone_decay_rates[int(zone)] = float(decay_rate)
        except ValueError:
            logging.error(f"Invalid zone mapping format for '{zone_pair}'. Expected format zone:decay_rate")
    return zone_decay_rates

# Command-line argument parsing
parser = argparse.ArgumentParser(
    description="UDP to DAQ control script with zone-specific decay rates."
)
parser.add_argument(
    "--zones",
    type=str,
    default="0:0.0,1:0.0",
    help=("Comma-separated list of zone:decay_rate pairs (e.g., '0:0.02,1:0.01') "
          "defining the decay rate for each zone. "
          "If a zone is not found, a default decay rate of 0 (i.e. no decay) is used.")
)
args = parser.parse_args()

# Configuration
DAQ_CHANNEL = "cDAQ1Mod1/port0/line0"
UDP_IP = "127.0.0.1"
UDP_PORT = 1319

FLASH_FREQUENCY = 50.0  # Hz

# Parse zones argument into a dictionary mapping zone -> decay rate.
ZONE_DECAY_RATES = parse_zone_decay_rates(args.zones)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
warnings.filterwarnings("ignore", category=UserWarning, module="nidaqmx")

def udp_daq_control():
    """
    Wait for a first incoming UDP packet to establish a connection, then
    process frames and toggle the DAQ line using zone-specific decay rates.
    """
    # Create and bind a UDP socket, then wait for the first packet.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    logging.info(f"Socket bound on {UDP_IP}:{UDP_PORT}")

    logging.info("Waiting for a client to send any data to establish 'connection'...")

    connected = False

    while not connected:
        try:
            data, addr = sock.recvfrom(512)
            if data:
                logging.info(f"Connection established from {addr}")
                connected = True
        except BlockingIOError:
            pass
        except Exception as e:
            logging.warning(f"Error while waiting for connection: {e}")

    output_state = False
    next_flash_time = time()

    frame_count = 0
    zone = -1

    with nidaqmx.Task() as task:
        task.do_channels.add_do_chan(DAQ_CHANNEL)
        task.start()

        try:
            while True:
                try:
                    data, addr = sock.recvfrom(512)
                    message = data.decode().strip()
                    values = list(map(float, message.split(',')))
                    frame_count = int(values[0])
                    zone = int(values[1])
                except BlockingIOError:
                    # No data available; continue handling flash timing
                    pass
                except (ValueError, IndexError):
                    logging.warning(f"Invalid message received: {data}")
                    continue

                current_time = time()

                if zone == -1:
                    logging.info("Out of reward zone: setting digital output to LOW.")
                    task.write(False)
                else:
                    # Look up the zone-specific decay rate; if not provided, default to 0 (no decay).
                    zone_decay = ZONE_DECAY_RATES.get(zone, 0)
                    # Calculate the new frequency by decaying the base frequency by zone_decay * frame_count.
                    new_flash_freq = FLASH_FREQUENCY - (zone_decay * frame_count)
                    new_flash_freq = max(new_flash_freq, 0)

                    if new_flash_freq == 0:
                        if output_state:
                            logging.info(
                                f"Frequency=0 (frame_count={frame_count}, zone={zone}); setting output LOW."
                            )
                            output_state = False
                            task.write(False)
                    else:
                        flash_interval = 1.0 / new_flash_freq
                        if current_time >= next_flash_time:
                            output_state = not output_state
                            logging.info(
                                f"In reward zone (frame_count={frame_count}, zone={zone}): "
                                f"flashing {'HIGH' if output_state else 'LOW'} at ~{new_flash_freq:.2f} Hz "
                                f"with zone decay rate {zone_decay}."
                            )
                            task.write(output_state)
                            next_flash_time = current_time + flash_interval

        except KeyboardInterrupt:
            logging.info("Interrupted by user. Setting digital output LOW and exiting.")
            task.write(False)
            sleep(2)
        finally:
            task.write(False)
            task.stop()
            sock.close()

if __name__ == "__main__":
    udp_daq_control()

