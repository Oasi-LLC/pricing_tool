# Pricing Tool

## Overview
This tool is a dynamic, multi-property hotel and short-term rental rate management system. It generates, reviews, and pushes pricing recommendations for multiple properties, supporting both manual and automated workflows. The tool is designed for property managers and revenue teams to optimize rates, manage minimum stays, and synchronize with external APIs (e.g., PriceLabs).

---

## Key Features
- **Streamlit Web Interface** for interactive rate review, adjustment, and pushing
- **Batch and granular rate/LOS adjustments** with live preview
- **Rules Adjuster System** for automated, rule-based pricing adjustments
- **Advanced Property Rules** with min-stay logic and adjacent day conditions
- **Multi-property support** with flexible configuration
- **Automated data pulls** for nightly overrides and pl_daily data
- **Auto-Refresh Scheduler** for automated data refresh (1 AM & 1 PM Lisbon time)
- **Background Daemon** that runs independently of the Streamlit app
- **Smart refresh logic** that only updates properties that need refreshing
- **Rate limit handling** with retry logic and configurable delays
- **API integration** for live rates and data sync
- **Comprehensive logging and output tracking**
- **Rate Evolution Tracking** with tools to analyze rate changes over time
- **Easy property onboarding** via config and data files

---

## Directory Structure
```
pricing_tool/
├── app/
│   └── app_2.py                    # Streamlit web app (main UI)
├── scheduler/                      # Scheduler daemon and management scripts
│   ├── scheduler_daemon.py         # Background scheduler daemon
│   ├── scheduler_terminal.py       # Terminal scheduler with progress
│   ├── manage_scheduler.sh         # Scheduler management (start/stop/status/logs)
│   ├── manage_scheduler_session.sh # Screen session manager
│   ├── start_scheduler.sh          # Start scheduler daemon
│   └── start_scheduler_session.sh  # Start scheduler in screen session
├── scripts/                        # Data generation and helpers
│   ├── generate_all_properties.py # Batch pl_daily generation
│   ├── generate_pl_daily_comprehensive.py # Comprehensive pl_daily generator
│   ├── auto_recovery.py            # Auto-restart failed services
│   ├── check_system_health.py      # System health checks
│   └── push_flohom12_match_flohom7.py # One-off rate push script
├── docs/                           # Documentation
│   ├── CHANGELOG.md
│   ├── SCHEDULER_README.md
│   └── deployment_guide.md
├── config/
│   ├── properties.yaml             # Property and listing configuration
│   ├── scheduler.yaml              # Scheduler configuration
│   ├── settings.yaml
│   └── date_ranges.yaml
├── data/
│   └── <property>/                 # Data per property (pl_daily, nightly overrides, etc.)
├── src/pricing_engine/             # Core pricing logic
├── utils/                          # Utility modules (backend interface, calendar view, scheduler, etc.)
├── rates/                          # API clients, push/pull scripts
├── run_pricing.py                  # CLI pricing engine
├── logs/                           # Log files
├── requirements.txt                # Python dependencies
├── README.md                       # This file
```

---

## Setup & Installation
1. **Clone the repo:**
   ```bash
   git clone <repo-url>
   cd pricing_tool
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure properties:**
   - Edit `config/properties.yaml` to add/update properties and listings.
   - Place data files in `data/<property>/` as needed.

---

## Rules Adjuster System

The Rules Adjuster is an advanced feature that automatically applies property-specific pricing rules to live rates. It supports:

### Rule Types
- **Rate Adjustments**: Multiplier-based pricing changes based on booking patterns
- **Min-Stay Adjustments**: Intelligent minimum stay modifications with adjacent day logic
- **Conditional Logic**: Complex rules based on adjacent day booking status
- **Reference Rate Logic**: Fallback pricing using nearby dates when primary references are unavailable

### How It Works
1. **Select Properties**: Choose which properties to apply rules to
2. **Apply Rules**: Click "Apply Rules" to process all configured rules
3. **Review Results**: See detailed breakdown of all adjustments made
4. **Push Changes**: Send adjusted rates directly to PriceLabs API

### Rule Configuration
Rules are configured in `config/properties.yaml` for each property, allowing for:
- Target weekday specification (Monday=0, Sunday=6)
- Complex booking conditions (adjacent days, consecutive patterns)
- Multiple action types (price multipliers, min-stay changes)
- Adjacent day minimum stay prerequisites

---

## Logging & Rate Evolution Tracking

The pricing tool now includes comprehensive logging and rate evolution tracking capabilities:

### Logging System
- **Price Update Logs**: Track all rate changes with detailed information
- **Error Logs**: Capture API errors and system failures with context
- **Rule Application Logs**: Log all automatic rule-based adjustments
- **Manual Change Logs**: Track user-initiated rate modifications

### Rate Evolution Tracking
Track how rates evolve over time for any listing and date:

```bash
# List all available dates for a listing
python daily_rate_tracker.py --listing-id 299754 --list-dates

# Track rate evolution for a specific date
python daily_rate_tracker.py --listing-id 299754 --target-date 2025-10-16

# See all listings with rate changes
python rate_evolution_demo.py --list-all

# Create visual graphs of rate evolution
python rate_evolution_tracker.py --listing-id 299754 --target-date 2025-10-16 --output rate_evolution.png
```

### Log Files
- `logs/pricing_updates_*.log` - All rate changes with timestamps and reasons
- `logs/errors_*.log` - System errors and API failures
- `logs/rate_generation_*.log` - Rate calculation and generation logs

### What Gets Logged
- **Rate Pushes**: Every successful rate push to PriceLabs
- **Manual Changes**: All user adjustments made in the frontend
- **Rule Adjustments**: Automatic rule-based rate modifications
- **API Errors**: Failed pushes and connection issues
- **System Events**: Data pulls, refreshes, and configuration changes

---

## Usage
### Web Interface (Recommended)
Run the enhanced Streamlit app (from project root):
```bash
streamlit run app/app_2.py
```
- Select property, date range, and generate rates
- Review, adjust, and push rates/LOS with live preview
- Monitor Auto-Refresh Scheduler status and manage automated data refresh

### Scheduler Management
Start the automated data refresh scheduler (run from project root):
```bash
./scheduler/manage_scheduler.sh start    # Start the scheduler daemon
./scheduler/manage_scheduler.sh status   # Check if scheduler is running
./scheduler/manage_scheduler.sh stop     # Stop the scheduler daemon
./scheduler/manage_scheduler.sh logs     # View recent scheduler logs
```

### Command Line
Run the pricing engine for a property:
```bash
python run_pricing.py --property <property_key>
```

### Data Generation
For each property, you need both the pl_daily data and the nightly pull overrides.

Generate pl_daily data for all properties:
```bash
python scripts/generate_all_properties.py
```
Or for a specific property:
```bash
python scripts/generate_pl_daily_comprehensive.py <property_key>
```

**Nightly Pull Overrides:**
- Make sure to also pull or generate the nightly override files (e.g., `<property_key>_nightly_pulled_overrides.csv`) for each property.
- Place these files in the corresponding `data/<property_key>/` directory.

**Auto-Refresh Scheduler:**
- **Enabled by default.** Automatic data refresh runs at 1 AM and 1 PM Lisbon time.
- **See status in the app:** In the Streamlit app sidebar, open **🔔 Auto-Refresh Scheduler** — you’ll see **🟢 Auto-Refresh Active** or **🔴 Auto-Refresh Inactive** and next/last refresh times.
- **To turn off:** Uncheck **Enable Auto-Refresh** in that section, or set `enabled: false` in `config/scheduler.yaml`.
- Runs independently of the Streamlit app for maximum reliability
- Handles API rate limits with retry logic and configurable delays
- Only refreshes properties that need updating (smart refresh)
- See `docs/SCHEDULER_README.md` for complete documentation

---

## Data Flow & Configuration
- **Configuration:** All properties and listings are defined in `config/properties.yaml`.
- **Data Files:** Each property has its own folder in `data/` containing pl_daily, nightly overrides, rate tables, etc.
- **APIs:** The tool can pull live rates and push updates via external APIs (see `rates/` and `utils/backend_interface.py`).
- **No resdata dependency:** The tool now relies solely on pl_daily for occupancy and does not use resdata files.

---

## Adding a New Property
1. **Update `config/properties.yaml`:**
   - Add a new property block with listings and rate group mapping.
2. **Add data files:**
   - Place pl_daily, nightly overrides (e.g., `<property_key>_nightly_pulled_overrides.csv`), and rate tables in `data/<property_key>/`.
3. **(Optional) Regenerate data:**
   - Use the data generation scripts to create or update pl_daily files.
4. **Verify in UI:**
   - The new property should appear in the Streamlit app for selection and management.

---

## Maintenance & Troubleshooting
- **Logs:** Check `logs/` for detailed run and error logs.
- **Data issues:** Ensure all required data files are present and up to date in each property folder.
- **Config errors:** Validate YAML syntax in `config/properties.yaml`.
- **Dependencies:** Use the provided `requirements.txt` and always activate the virtual environment.
- **Refresh UI:** After making changes to config or data, refresh the Streamlit app.

### Error Prevention & Monitoring
The system now includes comprehensive error prevention and monitoring:

**System Health Check:**
```bash
python scripts/check_system_health.py
```
- Monitors all critical services (scheduler, app, logs)
- Validates configuration files
- Checks for timezone and variable scope errors

**Auto-Recovery:**
```bash
python scripts/auto_recovery.py
```
- Automatically restarts failed services
- Clears old logs to prevent bloat
- Detects and reports common issues

**Error Prevention Features:**
- **Timezone Safety**: All datetime operations are timezone-aware
- **Variable Safety**: Fixed all variable scope issues
- **Error Resilience**: System can self-heal from common failures
- **Process Monitoring**: Real-time health monitoring
- **Consecutive Error Tracking**: Prevents infinite error loops

For detailed error prevention documentation, see `ERROR_PREVENTION_GUIDE.md`.

---

## Contribution Guidelines
- Use feature branches for new work.
- Write clear commit messages and update the changelog.
- Test changes locally before pushing.
- Keep code and config changes well-documented.
- Clean up unused files and dependencies regularly.

---

## Contact & Support
For questions, issues, or contributions, please contact the project maintainer or open an issue in the main repository. 