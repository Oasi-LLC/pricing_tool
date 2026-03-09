#!/usr/bin/env python3
"""
Send a test message to the scheduler alert webhook (e.g. Slack) to verify it works.
Uses SCHEDULER_ALERT_WEBHOOK_URL if set, otherwise config/scheduler.yaml alerting.webhook_url.

Run from project root:
  export SCHEDULER_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/..."
  python scripts/test_alert_webhook.py
"""
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.scheduler import _get_alert_webhook_url

def main():
    webhook_url = _get_alert_webhook_url()
    if not webhook_url:
        print("No webhook URL configured.")
        print("Set SCHEDULER_ALERT_WEBHOOK_URL (recommended) or alerting.webhook_url in config/scheduler.yaml")
        sys.exit(1)

    body = {
        "text": "🧪 *Pricing Tool – test alert*\nThis is a test message. Scheduler failure alerts are working."
    }
    try:
        req = Request(
            webhook_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlopen(req, timeout=10)
        print("Test message sent successfully. Check your Slack channel (or webhook destination).")
    except URLError as e:
        print(f"Failed to send test message: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
