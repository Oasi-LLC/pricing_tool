#!/bin/bash

# Scheduler Daemon Startup Script
# This script starts the scheduler daemon in the background

echo "Starting Pricing Tool Scheduler Daemon..."

# Navigate to the project root (parent of scheduler/)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Activate virtual environment
source venv/bin/activate

# Start the scheduler daemon in the background
nohup python scheduler/scheduler_daemon.py > logs/scheduler_daemon.log 2>&1 &

# Get the process ID
PID=$!
echo "Scheduler daemon started with PID: $PID"
echo "Logs are being written to: logs/scheduler_daemon.log"
echo ""
echo "To stop the scheduler, run: ./scheduler/manage_scheduler.sh stop"
echo "To check if it's running: ps aux | grep scheduler_daemon"
echo "To view logs: tail -f logs/scheduler_daemon.log" 