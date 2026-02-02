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
WINDOW_SIZE = 100 
TIMEOUT = 0.5 

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
    seq_bytes = seq_id.to_bytes(SEQ_ID_SIZE, byteorder='big', signed=True)
    return seq_bytes + data

def send_chunk(sock, addr, seq_id, chunk):
    """
    Sends a specific data chunk with its sequence ID to the address.
    """
    pkt = create_packet(seq_id, chunk)
    sock.sendto(pkt, addr)

def receive_acks(sock, base_idx, seq_ids, acked, packet_ack_times, total_chunks):
    """
    Unpacks arriving ACKs from the socket and advances the window base.
    
    Args:
        sock: The UDP socket.
        base_idx: Current window base index.
        seq_ids: List of all sequence numbers.
        acked: Dictionary mapping seq_id to boolean ack status.
        packet_ack_times: Dictionary to record ACK arrival times.
        total_chunks: Total number of chunks to send.
        
    Returns:
        The updated base_idx.
    """
    # Use select for non-blocking check
    ready = select.select([sock], [], [], 0.01)
    if ready[0]:
        try:
            data, _ = sock.recvfrom(1024)
            if len(data) >= SEQ_ID_SIZE:
                ack_seq_bytes = data[:SEQ_ID_SIZE]
                ack_seq = int.from_bytes(ack_seq_bytes, byteorder='big', signed=True)
                
                now = time.time()
                
                # Check which packets are covered by this Cumulative ACK
                # We iterate from current base forward
                while base_idx < total_chunks:
                    current_seq = seq_ids[base_idx]
                    
                    # If current sequence is strictly less than ACK, it's acknowledged
                    if current_seq < ack_seq:
                        if not acked[current_seq]:
                            acked[current_seq] = True
                            packet_ack_times[current_seq] = now
                        base_idx += 1
                    else:
                        break
        except BlockingIOError:
            pass
            
    return base_idx

def handle_timeout(sock, addr, base_idx, seq_ids, packets_data, packet_last_sent_times):
    """
    Checks if the oldest un-ACKed packet (at base_idx) has timed out. 
    If so, retransmits it.
    """
    base_seq = seq_ids[base_idx]
    
    # Only check if we have sent it at least once
    if base_seq in packet_last_sent_times:
        time_since_last_send = time.time() - packet_last_sent_times[base_seq]
        
        if time_since_last_send > TIMEOUT:
            # Retransmit the base packet
            packet_last_sent_times[base_seq] = time.time()
            send_chunk(sock, addr, base_seq, packets_data[base_seq])

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
    
    # Prepare sequence numbers
    packets_data = {}
    for i, chunk in enumerate(chunks):
        seq_id = i * MESSAGE_SIZE
        packets_data[seq_id] = chunk
        
    seq_ids = sorted(packets_data.keys())
    acked = {seq: False for seq in seq_ids}
    
    # State Variables
    base_idx = 0
    next_seq_idx = 0
    
    # Time Tracking
    packet_send_times = {}       # First send time per packet
    packet_last_sent_times = {}  # Last send time per packet (for re-transmit)
    packet_ack_times = {}        # Ack arrival time per packet
    
    # Setup Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    server_addr = (RECEIVER_IP, RECEIVER_PORT)
        
    # Start Timer
    start_time = time.time()
    
    # Transmission Loop
    while base_idx < total_chunks:
        # Window Filling: Send new packets inside the window
        while next_seq_idx < base_idx + WINDOW_SIZE and next_seq_idx < total_chunks:
            seq_to_send = seq_ids[next_seq_idx]
            current_time = time.time()
            
            # Record first send time
            if seq_to_send not in packet_send_times:
                packet_send_times[seq_to_send] = current_time
            
            # Record last send time
            packet_last_sent_times[seq_to_send] = current_time
            
            # Send Packet
            send_chunk(sock, server_addr, seq_to_send, packets_data[seq_to_send])
            next_seq_idx += 1

        # Handle ACKs: Check socket and move base
        new_base_idx = receive_acks(sock, base_idx, seq_ids, acked, packet_ack_times, total_chunks)
        base_idx = new_base_idx
        
        # Handle Timeouts: Retransmit base if needed
        if base_idx < total_chunks:
            handle_timeout(sock, server_addr, base_idx, seq_ids, packets_data, packet_last_sent_times)

    # Transmission completed
    end_time = time.time()
    
    # Send FINACK multiple times to ensure termination
    fin_packet = create_packet(seq_ids[-1] + MESSAGE_SIZE, b'==FINACK==')
    for _ in range(5):
        sock.sendto(fin_packet, server_addr)
        time.sleep(0.1)
        
    sock.close()
    
    # Create output metrics
    calculate_metrics(start_time, end_time, total_data_size, seq_ids, packet_send_times, packet_ack_times)

if __name__ == "__main__":
    main()
