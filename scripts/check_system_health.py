#!/usr/bin/env python3
"""
System Health Check Script
Monitors the health of the pricing tool system including scheduler and app status
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_scheduler_daemon():
    """Check if scheduler daemon is running"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'scheduler_daemon.py' in result.stdout:
            return True, "✅ Scheduler daemon is running"
        else:
            return False, "❌ Scheduler daemon is not running"
    except Exception as e:
        return False, f"❌ Error checking scheduler daemon: {e}"

def check_streamlit_app():
    """Check if Streamlit app is running"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'streamlit' in result.stdout and 'app_2.py' in result.stdout:
            return True, "✅ Streamlit app is running"
        else:
            return False, "❌ Streamlit app is not running"
    except Exception as e:
        return False, f"❌ Error checking Streamlit app: {e}"

def check_scheduler_logs():
    """Check recent scheduler logs for errors"""
    log_file = Path("logs/scheduler_daemon.log")
    if not log_file.exists():
        return False, "❌ Scheduler log file not found"
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            if not lines:
                return False, "❌ Scheduler log file is empty"
            
            # Check last 10 lines for errors
            recent_lines = lines[-10:]
            error_count = sum(1 for line in recent_lines if 'ERROR' in line)
            
            if error_count == 0:
                return True, f"✅ Scheduler logs look healthy (last {len(recent_lines)} lines)"
            else:
                return False, f"⚠️ Found {error_count} errors in recent scheduler logs"
    except Exception as e:
        return False, f"❌ Error reading scheduler logs: {e}"

def check_last_refresh():
    """Check when the last refresh occurred"""
    refresh_file = Path("logs/last_scheduler_refresh.txt")
    if not refresh_file.exists():
        return False, "❌ No last refresh record found"
    
    try:
        with open(refresh_file, 'r') as f:
            last_refresh_str = f.read().strip()
            if last_refresh_str:
                return True, f"✅ Last refresh: {last_refresh_str}"
            else:
                return False, "❌ Last refresh record is empty"
    except Exception as e:
        return False, f"❌ Error reading last refresh: {e}"

def check_config_files():
    """Check if required config files exist"""
    config_files = [
        "config/scheduler.yaml",
        "config/properties.yaml",
        "config/settings.yaml"
    ]
    
    missing_files = []
    for config_file in config_files:
        if not Path(config_file).exists():
            missing_files.append(config_file)
    
    if missing_files:
        return False, f"❌ Missing config files: {', '.join(missing_files)}"
    else:
        return True, "✅ All required config files exist"

def main():
    """Run all health checks"""
    print("🔍 Running System Health Check...")
    print("=" * 50)
    
    checks = [
        ("Scheduler Daemon", check_scheduler_daemon),
        ("Streamlit App", check_streamlit_app),
        ("Scheduler Logs", check_scheduler_logs),
        ("Last Refresh", check_last_refresh),
        ("Config Files", check_config_files)
    ]
    
    all_passed = True
    for name, check_func in checks:
        try:
            passed, message = check_func()
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} {name}: {message}")
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"❌ FAIL {name}: Error during check - {e}")
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("🎉 All health checks passed! System is healthy.")
    else:
        print("⚠️ Some health checks failed. Please review the issues above.")
    
    return all_passed

if __name__ == "__main__":
    main() 