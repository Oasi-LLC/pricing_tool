#!/usr/bin/env python3
"""
Auto-Recovery Script
Automatically restarts failed services and fixes common issues
"""

import os
import sys
import subprocess
import time
import signal
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def kill_process(pattern):
    """Kill processes matching a pattern"""
    try:
        result = subprocess.run(['pkill', '-f', pattern], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Killed processes matching '{pattern}'")
            time.sleep(2)  # Wait for processes to fully stop
        else:
            print(f"ℹ️ No processes found matching '{pattern}'")
    except Exception as e:
        print(f"❌ Error killing processes: {e}")

def start_scheduler_daemon():
    """Start the scheduler daemon"""
    try:
        # Kill existing scheduler daemon if running
        kill_process('scheduler_daemon.py')
        
        # Start new scheduler daemon
        subprocess.Popen([
            'python', 'scheduler/scheduler_daemon.py'
        ], cwd=project_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ Started scheduler daemon")
        return True
    except Exception as e:
        print(f"❌ Error starting scheduler daemon: {e}")
        return False

def start_streamlit_app():
    """Start the Streamlit app"""
    try:
        # Kill existing Streamlit processes
        kill_process('streamlit')
        
        # Start new Streamlit app
        subprocess.Popen([
            'streamlit', 'run', 'app/app_2.py'
        ], cwd=project_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ Started Streamlit app")
        return True
    except Exception as e:
        print(f"❌ Error starting Streamlit app: {e}")
        return False

def check_and_fix_timezone_issues():
    """Check and fix timezone-related issues in logs"""
    log_file = project_root / "logs" / "scheduler_daemon.log"
    if not log_file.exists():
        return False
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
            if 'offset-naive and offset-aware datetimes' in content:
                print("⚠️ Found timezone issues in logs - this should be fixed now")
                return True
    except Exception as e:
        print(f"❌ Error checking timezone issues: {e}")
    
    return False

def clear_old_logs():
    """Clear very old log entries to prevent log bloat"""
    log_file = project_root / "logs" / "scheduler_daemon.log"
    if not log_file.exists():
        return
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Keep only last 1000 lines
        if len(lines) > 1000:
            with open(log_file, 'w') as f:
                f.writelines(lines[-1000:])
            print("✅ Cleared old log entries")
    except Exception as e:
        print(f"❌ Error clearing logs: {e}")

def main():
    """Run auto-recovery procedures"""
    print("🔄 Running Auto-Recovery...")
    print("=" * 50)
    
    # Check current status
    print("📊 Current Status:")
    
    # Check scheduler daemon
    scheduler_running = False
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        scheduler_running = 'scheduler_daemon.py' in result.stdout
        print(f"{'✅' if scheduler_running else '❌'} Scheduler daemon")
    except:
        print("❌ Scheduler daemon")
    
    # Check Streamlit app
    streamlit_running = False
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        streamlit_running = 'streamlit' in result.stdout and ('app/app_2.py' in result.stdout or 'app_2.py' in result.stdout)
        print(f"{'✅' if streamlit_running else '❌'} Streamlit app")
    except:
        print("❌ Streamlit app")
    
    print("\n🔧 Recovery Actions:")
    
    # Start scheduler if not running
    if not scheduler_running:
        print("🔄 Starting scheduler daemon...")
        start_scheduler_daemon()
    else:
        print("ℹ️ Scheduler daemon is already running")
    
    # Start Streamlit if not running
    if not streamlit_running:
        print("🔄 Starting Streamlit app...")
        start_streamlit_app()
    else:
        print("ℹ️ Streamlit app is already running")
    
    # Check for timezone issues
    check_and_fix_timezone_issues()
    
    # Clear old logs
    clear_old_logs()
    
    print("\n✅ Auto-recovery completed!")
    print("💡 Wait a few seconds for services to fully start")
    print("🌐 Streamlit app should be available at http://localhost:8501")

if __name__ == "__main__":
    main() 