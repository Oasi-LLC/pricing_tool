#!/bin/bash

# Pricing Tool Scheduler - Screen Session Starter
# This script starts the scheduler in a background screen session

echo "🚀 Starting Pricing Tool Scheduler in Screen Session..."

# Check if screen is installed
if ! command -v screen &> /dev/null; then
    echo "❌ Error: 'screen' command not found. Please install screen first."
    echo "   On macOS: brew install screen"
    echo "   On Ubuntu/Debian: sudo apt-get install screen"
    exit 1
fi

# Check if scheduler session already exists
if screen -list | grep -q "pricing-scheduler"; then
    echo "⚠️  Scheduler session already exists!"
    echo "   To view existing session: screen -r pricing-scheduler"
    echo "   To kill existing session: screen -X -S pricing-scheduler quit"
    echo "   To restart: kill existing session first, then run this script again"
    exit 1
fi

# Navigate to project directory
cd "$(dirname "$0")"

# Start the scheduler in a new screen session
echo "📱 Starting scheduler daemon in screen session 'pricing-scheduler'..."
screen -dmS pricing-scheduler bash -c "
    echo '🔄 Starting Pricing Tool Scheduler...'
    echo '📅 Scheduled refreshes: 1:00 AM and 1:00 PM (Lisbon time)'
    echo '💡 To view logs: screen -r pricing-scheduler'
    echo '💡 To detach: Ctrl+A, D'
    echo '💡 To exit: Ctrl+C'
    echo '----------------------------------------'
    source venv/bin/activate
    python scheduler_daemon.py
"

# Check if session was created successfully
if screen -list | grep -q "pricing-scheduler"; then
    echo "✅ Scheduler started successfully in screen session!"
    echo ""
    echo "📋 Useful Commands:"
    echo "   View scheduler logs: screen -r pricing-scheduler"
    echo "   List all sessions: screen -ls"
    echo "   Kill scheduler: screen -X -S pricing-scheduler quit"
    echo ""
    echo "🔍 To check if it's working:"
    echo "   screen -r pricing-scheduler"
    echo "   (Then press Ctrl+A, D to detach)"
    echo ""
    echo "🎯 The scheduler will now run automatically every 12 hours!"
else
    echo "❌ Failed to start scheduler session"
    exit 1
fi


