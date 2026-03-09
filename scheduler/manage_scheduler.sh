#!/bin/bash

# Scheduler Management Script
# Usage: ./scheduler/manage_scheduler.sh [start|stop|status|logs]
# Run from project root.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$1" in
    start)
        echo "Starting scheduler daemon..."
        "$ROOT/scheduler/start_scheduler.sh"
        ;;
    stop)
        echo "Stopping scheduler daemon..."
        pkill -f scheduler_daemon.py
        echo "Scheduler daemon stopped"
        ;;
    status)
        echo "Checking scheduler status..."
        if pgrep -f scheduler_daemon.py > /dev/null; then
            echo "✅ Scheduler daemon is RUNNING"
            ps aux | grep scheduler_daemon | grep -v grep
        else
            echo "❌ Scheduler daemon is NOT RUNNING"
        fi
        ;;
    logs)
        echo "Showing recent scheduler logs..."
        tail -20 "$ROOT/logs/scheduler_daemon.log"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the scheduler daemon"
        echo "  stop    - Stop the scheduler daemon"
        echo "  status  - Check if scheduler is running"
        echo "  logs    - Show recent scheduler logs"
        exit 1
        ;;
esac 