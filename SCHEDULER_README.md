# Auto-Scheduler System

## Overview
The pricing tool now includes an **automatic scheduler system** that ensures data refreshes happen reliably without requiring any manual setup or admin privileges. This system works for all users who deploy the tool.

## How It Works

### 🚀 **Automatic Startup**
- **When you start the app**: The scheduler automatically starts in the background
- **No admin required**: Works for all users without system-level installation
- **Cross-platform**: Works on macOS, Linux, and Windows
- **Persistent**: Continues running even if you close the app

### 🔄 **Smart Monitoring**
- **Auto-restart**: If the scheduler crashes, it automatically restarts
- **Background operation**: Runs independently of the Streamlit app
- **Resource efficient**: Minimal CPU and memory usage
- **Logging**: All activity is logged for troubleshooting

### ⏰ **Scheduled Refreshes**
- **Daily at 1:00 PM Lisbon time**: Automatic data refresh
- **Smart refresh logic**: Only updates properties that need refreshing
- **Error handling**: Retries failed operations with exponential backoff
- **Rate limiting**: Respects API limits and avoids overwhelming servers

## Usage

### 🎯 **For End Users (Recommended)**
Simply run the app with the auto-scheduler:
```bash
./start_app_with_scheduler.sh
```

This will:
1. ✅ Start the scheduler automatically
2. ✅ Launch the Streamlit app
3. ✅ Ensure continuous operation

### 🔧 **For Developers**
You can also start components individually:

```bash
# Start just the scheduler
python auto_start_scheduler.py

# Start just the app (scheduler will auto-start)
streamlit run app_2.py

# Check scheduler status
./manage_scheduler.sh status

# View scheduler logs
./manage_scheduler.sh logs
```

## Management Commands

### 📊 **Check Status**
```bash
./manage_scheduler.sh status
```
Shows if the scheduler is running and its process details.

### 📋 **View Logs**
```bash
./manage_scheduler.sh logs
```
Shows recent scheduler activity and any errors.

### 🔄 **Restart Scheduler**
```bash
./manage_scheduler.sh restart
```
Stops and restarts the scheduler (useful for troubleshooting).

### 🛑 **Stop Scheduler**
```bash
./manage_scheduler.sh stop
```
Stops the scheduler (not recommended for normal operation).

## Troubleshooting

### ❌ **Scheduler Not Running**
1. Check if it's running: `./manage_scheduler.sh status`
2. View logs: `./manage_scheduler.sh logs`
3. Restart: `./manage_scheduler.sh restart`

### 🔍 **Check Recent Activity**
```bash
# View recent scheduler logs
tail -20 logs/scheduler_daemon.log

# View auto-scheduler logs
tail -20 logs/auto_scheduler.log
```

### 🚨 **Common Issues**

**Issue**: "Scheduler failed to start"
- **Solution**: Check that the virtual environment is activated
- **Solution**: Ensure `scheduler_daemon.py` exists in the project root

**Issue**: "No logs found"
- **Solution**: Check that the `logs/` directory exists
- **Solution**: Restart the scheduler: `./manage_scheduler.sh restart`

**Issue**: "Permission denied"
- **Solution**: This approach doesn't require admin privileges
- **Solution**: Ensure you're in the project directory and virtual environment is activated

## Technical Details

### 🏗️ **Architecture**
```
User starts app → Auto-scheduler starts → Scheduler daemon runs → Background monitoring
     ↓                    ↓                      ↓                    ↓
Streamlit app      Checks if running    Handles refreshes    Auto-restart on crash
```

### 📁 **Key Files**
- `auto_start_scheduler.py` - Main auto-scheduler logic
- `scheduler_daemon.py` - Background scheduler daemon
- `start_app_with_scheduler.sh` - User-friendly startup script
- `manage_scheduler.sh` - Management and troubleshooting commands

### 🔧 **Configuration**
The scheduler uses the same configuration as before:
- `config/scheduler.yaml` - Scheduler settings
- `config/properties.yaml` - Property configurations

## Benefits

### ✅ **For End Users**
- **Zero setup**: Works immediately for all users
- **No admin required**: No system-level installation needed
- **Reliable**: Automatic restarts and error handling
- **Transparent**: Clear status and logging

### ✅ **For Developers**
- **Easy deployment**: No complex system setup required
- **Cross-platform**: Works on all operating systems
- **Maintainable**: Clear separation of concerns
- **Debuggable**: Comprehensive logging and status commands

### ✅ **For Operations**
- **Self-healing**: Automatically restarts if it crashes
- **Resource efficient**: Minimal system impact
- **Scalable**: Can handle multiple properties and users
- **Monitorable**: Clear status and logging for monitoring

## Migration from Old System

If you were using the old manual scheduler:

1. **Stop old scheduler**: `./manage_scheduler.sh stop`
2. **Start new system**: `./start_app_with_scheduler.sh`
3. **Verify it's working**: `./manage_scheduler.sh status`

The new system is backward compatible and will work with existing configurations.

## Future Enhancements

- **Email notifications** for failed refreshes
- **Web dashboard** for monitoring multiple instances
- **Cloud deployment** support for server environments
- **Advanced scheduling** with multiple refresh times 