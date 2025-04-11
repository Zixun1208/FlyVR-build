import numpy as np
import socket
from numba import jit

# UDP socket setup
recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_socket.bind(("127.0.0.1", 1317))  # Listen here
send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
send_addr = ("127.0.0.1", 1318)  # Send updated position here

# JIT-optimized function to convert local movement to global dx, dz without inverting signs
@jit(nopython=True)
def calculate_dx_dz(ds, df, r, ds_gain, df_gain):
    # Apply movement gains without sign inversion
    local_x = ds_gain * ds   # sidestep movement → X
    local_z = df_gain * df   # forward movement → Z

    # Rotate local movement into the global frame using the heading angle r
    cos_r = np.cos(r)
    sin_r = np.sin(r)

    dx = local_x * cos_r - local_z * sin_r
    dz = local_x * sin_r + local_z * cos_r

    return dx, dz

# Initialize position and rotation
x, z = 0.0, 0.0
r = 0.0  # Heading angle in radians

# Gain parameters
gain_ds = 4.0
gain_df = 4.0
gain_dr = 1.0
gain_dx = 0.0
gain_dz = 1.0

# Main loop
while True:
    # Receive data
    data, addr = recv_socket.recvfrom(1024)
    try:
        parsed_data = str(data).split(',')
        ds = float(parsed_data[6])
        df = float(parsed_data[7])
        dr = float(parsed_data[8])
    except (ValueError, IndexError):
        continue  # Skip invalid packets

    # Update rotation
    r += gain_dr * dr

    # Calculate dx, dz using the updated heading r
    dx, dz = calculate_dx_dz(ds, df, r, gain_ds, gain_df)

    # Update x freely
    x = x + gain_dx * dx

    # Update z with clamping
    new_z = z + gain_dz * dz
    if new_z > 100:
        z = 99.9
    elif new_z < 0:
        z = 0.01
    else:
        z = new_z

    # Send updated position and heading as CSV (z, x, Radians)
    send_data = f"{z:.1f},{x:.1f},{r:.1f}".encode()
    send_socket.sendto(send_data, send_addr)

