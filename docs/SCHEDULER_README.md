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
Run the app from the project root. The app will auto-start the scheduler daemon if it isn’t already running:
```bash
streamlit run app/app_2.py
```

This will:
1. ✅ Launch the Streamlit app
2. ✅ Start the scheduler daemon automatically (when not in cloud mode)
3. ✅ Keep the scheduler running in the background

### 🔄 **Run refresh now (from the app)**
In the app, open **🔔 Auto-Refresh Scheduler** and click **Run refresh now**. This runs one full refresh (nightly pull → generate pl_daily for all properties), same as the scheduled job. It may take 10–15 minutes; the app shows progress and a short summary when done (e.g. “5 properties refreshed”). Use this when you want updated data without waiting for the next scheduled run, or when the app is deployed without a persistent scheduler (e.g. Streamlit Cloud).

### 🔧 **For Developers**
You can also start components individually:

```bash
# Start the app (scheduler daemon auto-starts when you open the app, or start it manually first)
streamlit run app/app_2.py

# Start just the scheduler daemon (from project root)
./scheduler/start_scheduler.sh

# Check scheduler status
./scheduler/manage_scheduler.sh status

# View scheduler logs
./scheduler/manage_scheduler.sh logs
```

## Management Commands

### 📊 **Check Status**
```bash
./scheduler/manage_scheduler.sh status
```
Shows if the scheduler is running and its process details.

### 📋 **View Logs**
```bash
./scheduler/manage_scheduler.sh logs
```
Shows recent scheduler activity and any errors.

### 🔄 **Restart Scheduler**
```bash
./scheduler/manage_scheduler.sh restart
```
Stops and restarts the scheduler (useful for troubleshooting).

### 🛑 **Stop Scheduler**
```bash
./scheduler/manage_scheduler.sh stop
```
Stops the scheduler (not recommended for normal operation).

## Troubleshooting

### ❌ **Scheduler Not Running**
1. Check if it's running: `./scheduler/manage_scheduler.sh status`
2. View logs: `./scheduler/manage_scheduler.sh logs`
3. Restart: `./scheduler/manage_scheduler.sh restart`

### 🔍 **Check Recent Activity**
```bash
# View recent scheduler logs
tail -20 logs/scheduler_daemon.log

# View auto-scheduler logs
tail -20 logs/auto_scheduler.log
```

### 🔔 **No alert received (Slack / webhook)**
- **Config path:** The scheduler loads `config/scheduler.yaml` from the project root. If the app or daemon runs from another directory, ensure the process’s working directory is the project root (or that paths in code use the project root).
- **Webhook URL:** Set `SCHEDULER_ALERT_WEBHOOK_URL` in the environment where the scheduler runs, or set `scheduler.alerting.webhook_url` in `config/scheduler.yaml`. Ensure `scheduler.alerting.enabled` is `true`.
- **Verify delivery:** From the project root run `python scripts/test_alert_webhook.py`. If that sends a message to Slack, the URL is valid; success/failure alerts use the same webhook.

### ⏳ **Manual refresh seems stuck**
- **Progress:** The scheduler writes progress to `logs/scheduler_status.json`. Check `current_step`, `current_operation`, and `total_progress` to see what’s running.
- **Logs:** Check `logs/scheduler_daemon.log` and `logs/scheduler.log` for errors. A full refresh can take 10–15+ minutes depending on property count and API rate limits.

### 🧪 **How to test alerts without a full refresh**
- Run **`python scripts/test_alert_webhook.py`** from the project root to send one test message.
- In the app, use **Refresh this property** (pick one property) to run nightly pull for all and pl_daily for that property; success or failure will trigger an alert.

### 🚨 **Common Issues**

**Issue**: "Scheduler failed to start"
- **Solution**: Check that the virtual environment is activated
- **Solution**: Ensure `scheduler_daemon.py` exists in the project root

**Issue**: "No logs found"
- **Solution**: Check that the `logs/` directory exists
- **Solution**: Restart the scheduler: `./scheduler/manage_scheduler.sh restart`

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
- `scheduler/scheduler_daemon.py` - Background scheduler daemon
- `scheduler/start_scheduler.sh` - Start the daemon
- `scheduler/manage_scheduler.sh` - Status, logs, restart, stop
- `utils/scheduler.py` - Scheduler logic and refresh orchestration

### 🔧 **Configuration**
The scheduler uses the same configuration as before:
- `config/scheduler.yaml` - Scheduler settings
- `config/properties.yaml` - Property configurations

### 🔔 **Failure alerting (Slack / webhook)**
When a scheduled refresh fails, the scheduler can POST an alert to a webhook. **Alerting is enabled by default** (`alerting.enabled: true`); no message is sent until a webhook URL is configured.

**Security (recommended):** Set the URL via the **`SCHEDULER_ALERT_WEBHOOK_URL`** environment variable so it is not stored in the repo:
```bash
export SCHEDULER_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..."
```
Ensure this env var is set wherever the scheduler daemon runs (e.g. in your shell profile or the script that starts the daemon). Alternatively, you can set `webhook_url` in `config/scheduler.yaml` (less secure if the repo is shared).

### 🧪 **Test alert webhook script**
`scripts/test_alert_webhook.py` sends a single test message to your configured webhook (e.g. Slack) without running any refresh. Use it to confirm that alerts are delivered.

- **When to use:** After setting `webhook_url` or `SCHEDULER_ALERT_WEBHOOK_URL`; when you’re not receiving success/failure alerts and want to verify the webhook.
- **How to run (from project root):**
  ```bash
  # Optional: set URL via env (recommended)
  export SCHEDULER_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/..."
  python scripts/test_alert_webhook.py
  ```
  If the script exits successfully, check your Slack channel (or webhook destination) for the test message. If you see “No webhook URL configured”, set the URL in `config/scheduler.yaml` under `scheduler.alerting.webhook_url` or via the env var above.

**Using Slack**
1. **Create an Incoming Webhook** in Slack:
   - Go to [Slack API – Incoming Webhooks](https://api.slack.com/messaging/webhooks).
   - Click **Create your Slack app** (or use an existing app) → **From scratch** → name it (e.g. “Pricing Tool Alerts”) → choose your workspace.
   - In the app, open **Incoming Webhooks** and turn **Activate Incoming Webhooks** **On**.
   - Click **Add New Webhook to Workspace**, pick the channel where you want alerts (e.g. `#alerts` or a DM), then **Allow**.
   - Copy the **Webhook URL** (looks like `https://hooks.slack.com/services/T…/B…/…`).
2. **Configure the pricing tool**: Set `SCHEDULER_ALERT_WEBHOOK_URL` to that URL (recommended), or set `webhook_url` in `config/scheduler.yaml` under `scheduler.alerting`. Leave both unset/null if you don’t want any alerts.
3. **What you’ll get**: On **success**, the daemon sends one message with the number of properties refreshed and the time. On **failure**, it sends one message per failure with the step name, error text, and timestamp. If the webhook URL is missing or invalid, the scheduler only logs a warning and continues.

**Other webhooks**  
Any HTTP endpoint that accepts a POST body with a `text` (or similar) field will work. Slack’s format is a JSON object `{"text": "your message"}`; other tools may require a different shape—you can extend the code if needed.

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

1. **Stop old scheduler**: `./scheduler/manage_scheduler.sh stop`
2. **Start the app**: `streamlit run app/app_2.py` (daemon auto-starts)
3. **Verify it's working**: `./scheduler/manage_scheduler.sh status`

The new system is backward compatible and will work with existing configurations.

## Future Enhancements

- **Email notifications** for failed refreshes
- **Web dashboard** for monitoring multiple instances
- **Cloud deployment** support for server environments
- **Advanced scheduling** with multiple refresh times 