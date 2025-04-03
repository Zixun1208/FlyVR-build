import numpy as np
import socket
from numba import jit

# UDP socket setup
recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_socket.bind(("127.0.0.1", 1317))  # Adjust with your port
send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
send_addr = ("127.0.0.1", 1318)  # Adjust with your target address

# JIT-optimized function for dx, dy calculation
@jit(nopython=True)
def calculate_dx_dy(ds, df, dr, ds_gain, df_gain, dr_gain):
    gain_ds = ds_gain * ds
    gain_df = df_gain * df
    gain_dr = dr_gain * dr
    sin_gain_dr = np.sin(gain_dr)
    cos_gain_dr = np.cos(gain_dr)
    dx = gain_df * sin_gain_dr - gain_ds * cos_gain_dr
    dy = gain_df * cos_gain_dr + gain_ds * sin_gain_dr
    return dx, dy

# Initialize x, y, r
x, y = 0, 5.0
r = 0.0
#Gain parameters
gain_ds = 8.0
gain_df = 8.0
gain_dr = 1.0
# Main loop
while True:
    # Receive data
    data, addr = recv_socket.recvfrom(1024)  # Adjust buffer size as necessary
    try:
        # Parse incoming data assuming CSV format ("ds,df,dr")
        #ds, df, dr = map(float, data.decode().split(','))
        parsed_data = str(data).split(',')
        ds = float(parsed_data[6])
        df = float(parsed_data[7])
        dr = float(parsed_data[8])
    except ValueError:
        continue  # Skip invalid packets
    
    # Compute dx and dy using the JIT-optimized function
    dx, dy = calculate_dx_dy(ds, df, dr, gain_ds, gain_df, gain_dr)
    #print(dx, dy, dr)
    # Update x and y
    x_gain = 0
    y_gain = 1
    r_gain = 0
    x += x_gain * dx
    y += y_gain * dy
    r += r_gain * dr
    print(x,y,r)
    # Send updated x, y as CSV-formatted string
    send_data = f"{x:.1f},{y:.1f},{r:.1f}".encode()
    send_socket.sendto(send_data, send_addr)
