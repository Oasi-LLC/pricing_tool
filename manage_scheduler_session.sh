#!/bin/bash

# Pricing Tool Scheduler - Session Manager
# This script helps manage the scheduler screen session

SESSION_NAME="pricing-scheduler"

case "${1:-status}" in
    start)
        echo "🚀 Starting scheduler session..."
        ./start_scheduler_session.sh
        ;;
    stop)
        echo "🛑 Stopping scheduler session..."
        if screen -list | grep -q "$SESSION_NAME"; then
            screen -X -S "$SESSION_NAME" quit
            echo "✅ Scheduler stopped"
        else
            echo "ℹ️  No scheduler session found"
        fi
        ;;
    restart)
        echo "🔄 Restarting scheduler session..."
        if screen -list | grep -q "$SESSION_NAME"; then
            screen -X -S "$SESSION_NAME" quit
            sleep 2
        fi
        ./start_scheduler_session.sh
        ;;
    status)
        echo "📊 Scheduler Session Status:"
        echo "----------------------------------------"
        if screen -list | grep -q "$SESSION_NAME"; then
            echo "✅ Status: RUNNING"
            echo "📱 Session: $SESSION_NAME"
            echo "🕐 Started: $(screen -list | grep "$SESSION_NAME" | awk '{print $3, $4}')"
            echo ""
            echo "💡 To view logs: screen -r $SESSION_NAME"
            echo "💡 To stop: ./manage_scheduler_session.sh stop"
        else
            echo "❌ Status: NOT RUNNING"
            echo ""
            echo "💡 To start: ./manage_scheduler_session.sh start"
        fi
        ;;
    logs)
        if screen -list | grep -q "$SESSION_NAME"; then
            echo "📋 Attaching to scheduler session (Ctrl+A, D to detach)..."
            screen -r "$SESSION_NAME"
        else
            echo "❌ No scheduler session found. Start it first with: ./manage_scheduler_session.sh start"
        fi
        ;;
    status-detail)
        echo "📊 Detailed Scheduler Status:"
        echo "----------------------------------------"
        python view_scheduler_status.py
        ;;
    watch)
        echo "🔄 Starting real-time status monitor..."
        python view_scheduler_status.py --watch
        ;;
    *)
        echo "📋 Pricing Tool Scheduler Manager"
        echo "Usage: $0 {start|stop|restart|status|logs|status-detail|watch}"
        echo ""
        echo "Commands:"
        echo "  start         - Start the scheduler in a screen session"
        echo "  stop          - Stop the scheduler session"
        echo "  restart       - Restart the scheduler session"
        echo "  status        - Show current status (default)"
        echo "  logs          - View scheduler logs in real-time"
        echo "  status-detail - Show detailed progress information"
        echo "  watch         - Real-time progress monitoring"
        echo ""
        echo "Examples:"
        echo "  $0 start         # Start scheduler"
        echo "  $0 status        # Check if running"
        echo "  $0 status-detail # Show detailed progress"
        echo "  $0 watch         # Real-time progress monitor"
        echo "  $0 logs          # View live logs"
        echo "  $0 stop          # Stop scheduler"
        ;;
esac


