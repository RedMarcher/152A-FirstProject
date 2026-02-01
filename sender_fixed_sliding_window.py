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
WINDOW_SIZE = 100 
TIMEOUT = 0.5 

def create_packet(seq_id, data):
    seq_bytes = seq_id.to_bytes(SEQ_ID_SIZE, byteorder='big', signed=True)
    return seq_bytes + data

def main():
    print("Starting Fixed Sliding Window Sender...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    
    try:
        # TODO: Open file and read data
        # TODO: Implement Fixed Sliding Window logic
        # - Maintain window of 100 packets
        # - Handle ACKs and move window
        # - Handle timeouts/retransmissions
        
        # TODO: Calculate metrics
        pass
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
