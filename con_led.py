import nidaqmx
import socket
import logging
import warnings
import argparse
from time import sleep, time

# Command-line argument parsing
parser = argparse.ArgumentParser(description="UDP to DAQ control script with optional no-decay mode.")
parser.add_argument("--no-decay", action="store_true", help="Disable frequency decay over time.")
args = parser.parse_args()

# Configuration
DAQ_CHANNEL = "cDAQ1Mod1/port0/line0"
UDP_IP = "127.0.0.1"
UDP_PORT = 1319

# Base parameters
FLASH_FREQUENCY = 50.0  # Hz
DEFAULT_SCALE = 0.01
NO_DECAY = args.no_decay  # Set via command-line argument

# Define scales for different zones
ZONE_SCALES = {
    0: 0.0055556,
    1: 0.0027778,
    # 2: 0.05,
    # 3: 0.1,
    # Add more zones if needed
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
warnings.filterwarnings("ignore", category=UserWarning, module="nidaqmx")

def udp_daq_control():
    """
    Wait for a first incoming UDP packet. Once that happens,
    consider the 'connection established' and begin processing
    frames & toggling the DAQ line.
    """
    # 1. Create a socket, bind, and wait for first packet
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    logging.info(f"Socket bound on {UDP_IP}:{UDP_PORT}")

    logging.info("Waiting for a client to send any data to establish 'connection'...")

    connected = False
    client_address = None

    while not connected:
        try:
            data, addr = sock.recvfrom(512)
            if data:
                client_address = addr
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
                    pass
                except (ValueError, IndexError):
                    logging.warning(f"Invalid message received: {data}")
                    continue

                current_time = time()

                if zone == -1:
                    logging.info("Out of reward zone: setting digital output to LOW.")
                    task.write(False)

                else:
                    # Get the scale for the current zone
                    scale = ZONE_SCALES.get(zone, DEFAULT_SCALE)

                    if NO_DECAY:
                        new_flash_freq = FLASH_FREQUENCY  # No decay, keep frequency constant
                    else:
                        new_flash_freq = FLASH_FREQUENCY - (scale * frame_count)
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
                                f"using scale={scale}."
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

