import socket
import sys
import time
import os
import struct

# Configuration
RECEIVER_IP = "localhost"
RECEIVER_PORT = 5001
PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
FILE_PATH = "2024_congestion_control_ecs152a/docker/file.mp3" 
TIMEOUT = 1.0 

def create_packet(seq_id, data):
    # Create packet with sequence ID (4 bytes big endian) + data
    seq_bytes = seq_id.to_bytes(SEQ_ID_SIZE, byteorder='big', signed=True)
    return seq_bytes + data

def main():
    print("Starting Stop-and-Wait Sender...")
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    
    try:
        # TODO: Open file and read data
        # TODO: Implement Stop-and-Wait logic
        # - Send packet
        # - Wait for Ack
        # - Retransmit on timeout
        
        # TODO: Measure and print metrics
        # throughput = ...
        # avg_delay = ...
        # performance = ...
        # print(f"{throughput}, {avg_delay}, {performance}")
        pass
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
