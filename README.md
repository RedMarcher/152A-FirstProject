# Congestion Control Project

## Overview
This project implements three congestion control protocols (Stop-and-Wait, Fixed Sliding Window, TCP Reno) over UDP.

## Project Structure
- `sender_stop_and_wait.py`: Sender implementation for Stop-and-Wait.
- `sender_fixed_sliding_window.py`: Sender implementation for Fixed Sliding Window.
- `sender_reno.py`: Sender implementation for TCP Reno.
- `2024_congestion_control_ecs152a/`: Contains the network simulator and receiver code.

## Setup
Clone the required network simulator repository into the project root:
```bash
git clone git@github.com:klvijeth/2024_congestion_control_ecs152a.git
```

## How to Run

### 1. Start the Network Simulator
The simulator must be run from within the `docker` directory of the provided repository.

1. Open a terminal.
2. Navigate to the docker directory:
   ```bash
   cd 2024_congestion_control_ecs152a/docker
   ```
3. Run the simulator script:
   ```bash
   ./start-simulator.sh
   ```
   **Note:** You might need `sudo` depending on your docker configuration.
   
   Wait for the message **"Receiver running"**.

### 2. Run the Sender
Open a **new terminal window** (keep the simulator running in the first one).

Navigate to the project root (where the sender scripts are). Run one of the sender scripts:

**Stop-and-Wait:**
```bash
python3 sender_stop_and_wait.py
```

**Fixed Sliding Window:**
```bash
python3 sender_fixed_sliding_window.py
```

**TCP Reno:**
```bash
python3 sender_reno.py
```

### 3. Verify Transmission
- The receiver will print acknowledgments.
- Upon completion, the received file will be saved to `2024_congestion_control_ecs152a/docker/hdd/file2.mp3`.
- You can compare the sent and received files using `md5sum` or `diff`.

## Configuration
The sender scripts are configured to look for the file at `2024_congestion_control_ecs152a/docker/file.mp3`. If you move the scripts or the file, update the `FILE_PATH` constant in the python files.