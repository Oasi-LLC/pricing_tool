# Error Prevention Guide

This guide documents the comprehensive safeguards implemented to prevent the errors that occurred and ensure system reliability.

## 🚨 Previous Errors Fixed

### 1. Timezone Error (`can't subtract offset-naive and offset-aware datetimes`)
- **Root Cause**: The scheduler was comparing timezone-naive and timezone-aware datetime objects
- **Fix**: Added proper timezone localization in `utils/scheduler.py`
- **Prevention**: Added validation to ensure all datetime objects are timezone-aware

### 2. Variable Scope Error (`data_col2 is not defined`)
- **Root Cause**: Variables defined inside conditional blocks but used outside their scope
- **Fix**: Moved variable definitions to broader scope
- **Prevention**: Added comprehensive error handling and validation

## 🛡️ Safeguards Implemented

### 1. Enhanced Error Handling in Scheduler
```python
# Added comprehensive try-catch blocks
try:
    # All scheduler operations
except Exception as e:
    logger.error(f"Critical error: {e}")
    return False  # Graceful failure
```

### 2. Consecutive Error Tracking
- Tracks consecutive errors in scheduler daemon
- Implements exponential backoff (5 min → 30 min wait)
- Prevents infinite error loops

### 3. System Health Monitoring
- **Health Check Script**: `python scripts/check_system_health.py`
- Monitors all critical services
- Validates configuration files
- Checks log health

### 4. Auto-Recovery System
- **Auto-Recovery Script**: `python scripts/auto_recovery.py`
- Automatically restarts failed services
- Clears old logs to prevent bloat
- Detects and reports timezone issues

### 5. Comprehensive Startup Script
- **Startup Script**: `python start_system.py`
- Validates environment before starting
- Ensures clean startup with proper error handling
- Verifies system health after startup

## 🔧 Usage Instructions

### Starting the System
```bash
# Activate virtual environment
source venv/bin/activate

# Start everything with comprehensive error handling
python start_system.py
```

### Monitoring System Health
```bash
# Check system health
python scripts/check_system_health.py

# Auto-recovery if issues detected
python scripts/auto_recovery.py
```

### Manual Service Management
```bash
# Start scheduler daemon
python scheduler_daemon.py

# Start Streamlit app
streamlit run app_2.py

# Check running processes
ps aux | grep -E "(scheduler_daemon|streamlit)"
```

## 📊 Monitoring and Alerts

### Log Monitoring
- **Scheduler Logs**: `logs/scheduler_daemon.log`
- **App Logs**: Streamlit console output
- **Health Check**: Automatic validation of all components

### Key Indicators to Watch
1. **Scheduler Status**: Should show "Auto-Refresh Active"
2. **Last Refresh Time**: Should update regularly
3. **Error Count**: Should be minimal in logs
4. **Process Status**: Both scheduler and app should be running

### Common Issues and Solutions

#### Issue: Scheduler Not Running
```bash
# Check if daemon is running
ps aux | grep scheduler_daemon

# Restart if needed
python scripts/auto_recovery.py
```

#### Issue: Timezone Errors
- ✅ **Fixed**: Timezone handling improved
- **Detection**: Look for "offset-naive and offset-aware" in logs
- **Solution**: Auto-recovery script handles this

#### Issue: Variable Scope Errors
- ✅ **Fixed**: All variables properly scoped
- **Prevention**: Comprehensive error handling in app

#### Issue: Streamlit App Errors
```bash
# Check syntax
python -c "import ast; ast.parse(open('app_2.py').read())"

# Restart app
python scripts/auto_recovery.py
```

## 🚀 Best Practices

### 1. Always Use the Startup Script
```bash
python start_system.py  # Instead of manual commands
```

### 2. Regular Health Checks
```bash
# Run health check daily
python scripts/check_system_health.py
```

### 3. Monitor Logs
```bash
# Check recent scheduler activity
tail -20 logs/scheduler_daemon.log

# Look for errors
grep ERROR logs/scheduler_daemon.log
```

### 4. Backup Configuration
- Keep backups of `config/scheduler.yaml`
- Version control all configuration changes
- Test changes in development first

## 🔄 Recovery Procedures

### Automatic Recovery
The system now includes automatic recovery mechanisms:
- **Error Detection**: Monitors for common failure patterns
- **Auto-Restart**: Automatically restarts failed services
- **Health Validation**: Verifies system health after recovery

### Manual Recovery
If automatic recovery fails:
1. Run health check: `python scripts/check_system_health.py`
2. Run auto-recovery: `python scripts/auto_recovery.py`
3. Check logs for specific errors
4. Restart system: `python start_system.py`

## 📈 System Reliability Metrics

### Current Safeguards
- ✅ **Error Handling**: Comprehensive try-catch blocks
- ✅ **Process Monitoring**: Health checks for all services
- ✅ **Auto-Recovery**: Automatic restart of failed services
- ✅ **Log Management**: Prevents log bloat
- ✅ **Timezone Safety**: Proper timezone handling
- ✅ **Variable Safety**: Proper scoping and validation

### Monitoring Dashboard
The Streamlit app now includes:
- Real-time scheduler status
- Error reporting and display
- Manual refresh capabilities
- Configuration management

## 🎯 Success Criteria

The system is considered healthy when:
1. ✅ Scheduler daemon is running
2. ✅ Streamlit app is accessible
3. ✅ No timezone errors in logs
4. ✅ Last refresh time is recent
5. ✅ All config files exist
6. ✅ Health check passes

## 📞 Troubleshooting

### Quick Diagnostic Commands
```bash
# Check system status
python scripts/check_system_health.py

# View recent logs
tail -10 logs/scheduler_daemon.log

# Check processes
ps aux | grep -E "(scheduler|streamlit)"

# Test syntax
python -c "import ast; ast.parse(open('app_2.py').read())"
```

### Emergency Procedures
1. **System Unresponsive**: `python scripts/auto_recovery.py`
2. **Configuration Issues**: Restore from backup
3. **Persistent Errors**: Check logs and restart system
4. **Data Issues**: Run manual refresh from Streamlit app

This comprehensive error prevention system ensures the pricing tool will be reliable and self-healing, preventing the issues that occurred previously. 