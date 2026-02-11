import socket
import sys
import time
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
TIMEOUT = 0.5 

# TCP Reno Specifics
INIT_CWND = 1.0       # Initial Congestion Window
INIT_SSTHRESH = 64    # Initial Slow Start Threshold

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
        
    print(f"{throughput:.6f}, {avg_delay:.6f}, {performance:.6f}")

# -----------------------------------------------------------------------------
# Reno State Management
# -----------------------------------------------------------------------------
class RenoState:
    def __init__(self):
        self.cwnd = INIT_CWND
        self.ssthresh = INIT_SSTHRESH
        self.dup_acks = 0
        self.in_fast_recovery = False

    def on_new_ack(self):
        """
        Called when a new ACK arrives (acknowledging new data).
        """
        # If we experienced a timeout or new data is acked, we exit fast recovery
        if self.in_fast_recovery:
            self.in_fast_recovery = False
            self.cwnd = self.ssthresh  # Deflate window back to ssthresh

        self.dup_acks = 0

        # Congestion Control Logic
        if self.cwnd < self.ssthresh:
            # Slow Start: increase by 1 per ACK
            self.cwnd += 1
        else:
            # Congestion Avoidance: increase by 1/cwnd per ACK (linear growth per RTT)
            self.cwnd += 1.0 / self.cwnd

    def on_dup_ack(self, sock, addr, missing_seq, packets_data, packet_last_sent_times):
        """
        Called when a duplicate ACK arrives.
        Returns True if a packet was retransmitted.
        """
        self.dup_acks += 1
        
        if self.dup_acks == 3:
            # Fast Retransmit
            # Set ssthresh to max(cwnd/2, 2)
            self.ssthresh = max(self.cwnd / 2, 2)
            # Enter Fast Recovery
            self.cwnd = self.ssthresh + 3
            self.in_fast_recovery = True
            
            # Retransmit the missing segment immediately
            if missing_seq in packets_data:
                packet_last_sent_times[missing_seq] = time.time()
                send_chunk(sock, addr, missing_seq, packets_data[missing_seq])
                return True
        elif self.dup_acks > 3:
            # Fast Recovery: Inflate window for each additional dup ACK
            self.cwnd += 1
            
        return False

    def on_timeout(self):
        """
        Called when a timeout occurs.
        """
        self.ssthresh = max(self.cwnd / 2, 2)
        self.cwnd = 1
        self.dup_acks = 0
        self.in_fast_recovery = False

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
def main():
    # State Variables
    base_idx = 0
    next_seq_idx = 0
    reno = RenoState()

    # Initialization
    chunks = read_file_data(FILE_PATH)
    total_chunks = len(chunks)
    total_data_size = sum(len(c) for c in chunks)
    
    packets_data = {}
    for i, chunk in enumerate(chunks):
        seq_id = i * MESSAGE_SIZE
        packets_data[seq_id] = chunk
        
    seq_ids = sorted(packets_data.keys())
    acked = {seq: False for seq in seq_ids}
    
    # Time Tracking
    packet_send_times = {}       # First send time per packet
    packet_last_sent_times = {}  # Last send time per packet (for re-transmit)
    packet_ack_times = {}        # Ack arrival time per packet
    
    # Setup Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    server_addr = (RECEIVER_IP, RECEIVER_PORT)
        
    start_time = time.time()
    
    while base_idx < total_chunks:
        
        # ---------------------------------------------------------------------
        # 1. Transmission Phase
        #    Send packets while the number of in-flight packets is within cwnd.
        # ---------------------------------------------------------------------
        while next_seq_idx < total_chunks:
            # Calculate packets currently in flight
            # In-flight = (next_seq_idx - base_idx)
            # Note: We must compare against cwnd
            if (next_seq_idx - base_idx) < reno.cwnd:
                seq_to_send = seq_ids[next_seq_idx]
                current_time = time.time()
                
                # Record first send time
                if seq_to_send not in packet_send_times:
                    packet_send_times[seq_to_send] = current_time
                
                # Record last send time
                packet_last_sent_times[seq_to_send] = current_time
                
                send_chunk(sock, server_addr, seq_to_send, packets_data[seq_to_send])
                next_seq_idx += 1
            else:
                # Window is full
                break

        # ---------------------------------------------------------------------
        # 2. Acknowledgement Phase
        #    Process all available ACKs to update state and drain buffer.
        # ---------------------------------------------------------------------
        ready = select.select([sock], [], [], 0.01)
        if ready[0]:
            try:
                # Process all available ACKs to drain the buffer and update window quickly
                while True:
                    try:
                        data, _ = sock.recvfrom(1024)
                        if len(data) >= SEQ_ID_SIZE:
                            ack_seq_bytes = data[:SEQ_ID_SIZE]
                            ack_seq = int.from_bytes(ack_seq_bytes, byteorder='big', signed=True)
                            
                            now = time.time()
                            base_seq = seq_ids[base_idx] if base_idx < total_chunks else float('inf')
                            
                            # Analyze ACK
                            # If ack_seq > base_seq, it acked something new
                            if ack_seq > base_seq:
                                # Standard New ACK
                                # It Cumulative ACKs everything before ack_seq
                                
                                # Advance base_idx
                                old_base_idx = base_idx
                                while base_idx < total_chunks and seq_ids[base_idx] < ack_seq:
                                    scurrent = seq_ids[base_idx]
                                    if not acked[scurrent]:
                                        acked[scurrent] = True
                                        packet_ack_times[scurrent] = now
                                    base_idx += 1
                                
                                # If we advanced, it's a "New ACK"
                                if base_idx > old_base_idx:
                                    reno.on_new_ack()

                            elif ack_seq == base_seq:
                                # Duplicate ACK: Receiver is still waiting for base_seq.
                                # Since ack_seq == base_seq, this confirms the receiver has not yet received base_seq.
                                reno.on_dup_ack(sock, server_addr, base_seq, packets_data, packet_last_sent_times)

                            # If ack_seq < base_seq, it's an old ACK, ignore.
                            
                    except BlockingIOError:
                        break
            except Exception:
                pass
        
        # ---------------------------------------------------------------------
        # 3. Timeout Phase
        #    Retransmit the base packet if the timeout interval has passed.
        # ---------------------------------------------------------------------
        if base_idx < total_chunks:
            base_seq = seq_ids[base_idx]
            if base_seq in packet_last_sent_times:
                time_since_last_send = time.time() - packet_last_sent_times[base_seq]
                if time_since_last_send > TIMEOUT:
                    # Timeout occurred
                    reno.on_timeout()
                    
                    # Retransmit base packet
                    packet_last_sent_times[base_seq] = time.time()
                    send_chunk(sock, server_addr, base_seq, packets_data[base_seq])
                    
                    # Reset ssthresh and cwnd, then retransmit base packet.
                    pass

    # Transmission completed
    end_time = time.time()
    
    # Send FINACK multiple times
    if seq_ids:
        fin_packet = create_packet(seq_ids[-1] + MESSAGE_SIZE, b'==FINACK==')
    else:
        fin_packet = create_packet(0, b'==FINACK==')
        
    for _ in range(5):
        sock.sendto(fin_packet, server_addr)
        time.sleep(0.1)
        
    sock.close()
    
    calculate_metrics(start_time, end_time, total_data_size, seq_ids, packet_send_times, packet_ack_times)

if __name__ == "__main__":
    main()
