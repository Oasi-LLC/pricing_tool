# Auto-Refresh Scheduler

The Auto-Refresh Scheduler automatically refreshes your pricing and property data at scheduled times without requiring the Streamlit app to be open.

## 🚀 How It Works

The scheduler runs as an **independent background daemon** that:
- ✅ **Works without the Streamlit app** - No need to keep the web interface open
- ✅ **Runs automatically** - Starts when you run the daemon and continues running
- ✅ **Handles errors gracefully** - Retries failed operations and logs everything
- ✅ **Respects API limits** - Includes delays between operations to avoid rate limits

## 📅 Schedule

By default, the scheduler refreshes data **twice daily**:
- **1:00 AM Lisbon time** - Early morning refresh
- **1:00 PM Lisbon time** - Afternoon refresh

## 🛠️ Management

### Quick Commands

```bash
# Check if scheduler is running
./manage_scheduler.sh status

# Start the scheduler daemon
./manage_scheduler.sh start

# Stop the scheduler daemon
./manage_scheduler.sh stop

# View recent logs
./manage_scheduler.sh logs
```

### Manual Start

```bash
# Start in background
nohup python scheduler_daemon.py > logs/scheduler_daemon.log 2>&1 &

# Or use the startup script
./start_scheduler.sh
```

## 📊 What Gets Refreshed

The scheduler automatically refreshes:

1. **Current Pricing Data** (`*_nightly_pulled_overrides.csv`)
   - Latest rate overrides and changes from PriceLabs API
   - Pulls data for all configured properties

2. **Property Data** (`pl_daily_*.csv`)
   - Daily occupancy, booking patterns, and availability
   - Processes properties individually to avoid API timeouts
   - Uses smart refresh to only update properties that need it

## ⚙️ Configuration

Edit `config/scheduler.yaml` to customize:

```yaml
scheduler:
  enabled: true
  refresh_times: ["01:00", "13:00"]  # Times in 24-hour format
  timezone: "Europe/Lisbon"
  properties: ["fb1", "wb1", "atx1", "edge1", "flo1"]  # Specific properties
  smart_refresh: true  # Only refresh properties that need it
  max_data_age_hours: 24  # How old data can be before refresh
  rate_limiting:
    delay_between_operations: 30  # Seconds between operations
    delay_between_properties: 10  # Seconds between properties
    delay_on_rate_limit: 300  # Seconds to wait on rate limit
```

## 🔍 Monitoring

### Log Files

- **`logs/scheduler_daemon.log`** - Main daemon activity
- **`logs/scheduler.log`** - Refresh attempt results
- **`logs/last_scheduler_refresh.txt`** - Last successful refresh time

### Status Check

The Streamlit app shows:
- ✅ **Auto-Refresh Active/Inactive** status
- 📅 **Next scheduled refresh** time
- 📅 **Last refresh** time
- 📊 **Data file timestamps** (Property Data & Current Pricing)

## 🚨 Troubleshooting

### Scheduler Not Running

```bash
# Check if daemon is running
./manage_scheduler.sh status

# If not running, start it
./manage_scheduler.sh start

# Check logs for errors
./manage_scheduler.sh logs
```

### Data Not Refreshing

1. **Check if scheduler is enabled** in `config/scheduler.yaml`
2. **Verify timezone settings** match your location
3. **Check API credentials** in your configuration
4. **Review logs** for specific error messages

### Rate Limit Issues

The scheduler includes built-in rate limiting:
- Waits between operations to respect API limits
- Retries failed operations with exponential backoff
- Logs all rate limit events for monitoring

## 🔄 Manual Refresh

You can still manually refresh data through the Streamlit app:
- **"Refresh All Data"** button - Refreshes selected properties
- **"Generate Rates"** button - Generates new pricing recommendations

## 📈 Reliability Features

- **Automatic retry logic** for failed operations
- **Rate limit handling** with configurable delays
- **Smart refresh** to only update properties that need it
- **Comprehensive logging** for monitoring and debugging
- **Graceful error handling** to prevent daemon crashes

## 🎯 Best Practices

1. **Start the scheduler daemon** when you set up the system
2. **Monitor logs regularly** to ensure it's working
3. **Configure appropriate delays** for your API limits
4. **Use smart refresh** to minimize unnecessary API calls
5. **Keep the daemon running** for continuous operation

The scheduler is designed to work completely independently of the Streamlit app, ensuring your data stays fresh even when you're not actively using the pricing tool. 