import socket
import sys
import time
import os
import struct
import select

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
RECEIVER_IP = "localhost"
RECEIVER_PORT = 5001
PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
FILE_PATH = "2024_congestion_control_ecs152a/docker/file.mp3" 
TIMEOUT = 1.0 

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def read_file_data(file_path):
    """
    Reads the file at file_path and parses it into chunks of MESSAGE_SIZE.
    Returns a list of binary chunks.
    """
    chunks = []
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(MESSAGE_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        sys.exit(1)
    return chunks

def create_packet(seq_id, data):
    """
    Creates a packet with the 4-byte big-endian sequence ID prepended to data.
    """
    # Convert sequence_id to 4 bytes, big-endian order
    seq_bytes = seq_id.to_bytes(SEQ_ID_SIZE, byteorder='big', signed=True)
    return seq_bytes + data

def send_chunk(sock, addr, seq_id, chunk):
    """
    Sends a specific data chunk with its sequence ID to the address.
    """
    pkt = create_packet(seq_id, chunk)
    sock.sendto(pkt, addr)

def calculate_metrics(start_time, end_time, total_data_size, seq_ids, packet_send_times, packet_ack_times):
    """
    Calculates and prints the required metrics: Throughput, Avg Delay, Performance.
    """
    # Throughput calculation
    duration = end_time - start_time
    throughput = total_data_size / duration if duration > 0 else 0
    
    # Average Delay calculation
    total_delay = 0
    total_samples = 0
    for seq in seq_ids:
        if seq in packet_ack_times and seq in packet_send_times:
            # Delay = Time ACK Received - Time FIRST Sent
            delay = packet_ack_times[seq] - packet_send_times[seq]
            total_delay += delay
            total_samples += 1
            
    avg_delay = total_delay / total_samples if total_samples > 0 else 0
    
    # Performance metric calculation
    # Metric = 0.3 * (Throughput/1000) + 0.7 / AvgDelay
    performance = 0
    if avg_delay > 0:
        performance = (0.3 * (throughput / 1000.0)) + (0.7 / avg_delay)
        
    print(f"{throughput:.7f}, {avg_delay:.7f}, {performance:.7f}")

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
def main():
    # Initialization
    chunks = read_file_data(FILE_PATH)
    total_chunks = len(chunks)
    total_data_size = sum(len(c) for c in chunks)

    seq_ids = range(total_chunks)

    packet_send_times = {}
    packet_last_sent_times = {}
    packet_ack_times = {}

    server_addr = (RECEIVER_IP, RECEIVER_PORT)
    
    # Setup Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.0)

    start_time = time.time()
    
    for i in seq_ids:
        try:
            # -----------------------------------------------------------------
            # 1. Send Packet
            #    Send the current packet to the receiver.
            # -----------------------------------------------------------------
            seq_id = i * MESSAGE_SIZE
            send_chunk(sock, server_addr, seq_id, chunks[i])
            packet_send_times[i] = time.time()
            packet_last_sent_times[i] = time.time()

            # -----------------------------------------------------------------
            # 2. Wait for ACK
            #    Wait for the ACK for the current packet.
            # -----------------------------------------------------------------
            while True:
                ready = select.select([sock], [], [], TIMEOUT)
                if ready[0]:
                    ack, _ = sock.recvfrom(MESSAGE_SIZE)
                    ack_seq_bytes = ack[:SEQ_ID_SIZE]
                    ack_seq = int.from_bytes(ack_seq_bytes, byteorder='big', signed=True)
                    packet_ack_times[i] = time.time()
                    if ack_seq <= seq_id + MESSAGE_SIZE:
                        packet_ack_times[i] = time.time()
                        break
                else:
                    # ---------------------------------------------------------
                    # 3. Timeout / Retransmit
                    #    Retransmit the packet if timeout occurs.
                    # ---------------------------------------------------------
                    send_chunk(sock, server_addr, seq_id, chunks[i])
                    packet_last_sent_times[i] = time.time()
            
        except TimeoutError:
            print("TimeoutError")

    end_time = time.time()
    
    # Send FINACK multiple times to close connection
    fin_packet = create_packet(seq_ids[-1] + MESSAGE_SIZE, b'==FINACK==')
    for _ in range(5):
        sock.sendto(fin_packet, server_addr)
        time.sleep(0.2)
        
    sock.close()
    
    calculate_metrics(start_time, end_time, total_data_size, seq_ids, packet_send_times, packet_ack_times)

if __name__ == "__main__":
    main()
