#!/bin/bash

# Scheduler Daemon Startup Script
# This script starts the scheduler daemon in the background

echo "Starting Pricing Tool Scheduler Daemon..."

# Navigate to the project directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start the scheduler daemon in the background
nohup python scheduler_daemon.py > logs/scheduler_daemon.log 2>&1 &

# Get the process ID
PID=$!
echo "Scheduler daemon started with PID: $PID"
echo "Logs are being written to: logs/scheduler_daemon.log"
echo ""
echo "To stop the scheduler, run: pkill -f scheduler_daemon.py"
echo "To check if it's running: ps aux | grep scheduler_daemon"
echo "To view logs: tail -f logs/scheduler_daemon.log" 