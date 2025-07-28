# Pricing Tool Changelog

This file documents all significant changes to the pricing tool codebase.

## [v1.7.0] - 2025-07-28

### Added
- **Auto-Refresh Scheduler**: Complete automated data refresh system that runs independently of the Streamlit app
- **Background Daemon**: `scheduler_daemon.py` runs continuously to refresh data at scheduled times (1 AM & 1 PM Lisbon time)
- **Smart Refresh Logic**: Only refreshes properties that need updating based on data age or missing files
- **Rate Limit Handling**: Built-in retry logic with configurable delays to handle API rate limits gracefully
- **Management Scripts**: `manage_scheduler.sh` and `start_scheduler.sh` for easy scheduler control
- **Enhanced UI**: Auto-Refresh Scheduler section in Streamlit app with real-time status and controls
- **Comprehensive Documentation**: `SCHEDULER_README.md` with complete setup and usage instructions
- **Individual Property Processing**: Processes properties one by one to avoid API timeouts
- **Timezone Fix**: Fixed critical timezone handling bug that prevented scheduler from running on weekends

### Changed
- **UI Redesign**: Cleaner Auto-Refresh Scheduler interface with status cards and consolidated information
- **Data Management**: Moved data timestamps to scheduler section for better organization
- **Refresh Logic**: "Refresh All Data" now processes only selected properties with dynamic date ranges
- **Configuration**: Added `config/scheduler.yaml` for comprehensive scheduler settings

### Fixed
- **Timezone Bug**: Fixed `can't subtract offset-naive and offset-aware datetimes` error that prevented scheduler operation
- **Rate Limit Issues**: Implemented proper retry logic for properties that hit API rate limits
- **UI Clutter**: Removed redundant information and improved layout for better user experience

## [v1.6.0] - 2025-07-10

### Added
- Enhanced Streamlit UI: live preview for both price and LOS adjustments, batch actions, and improved session state handling
- Support for adding new properties (e.g., FLOHOM 14) via config and data files
- Comprehensive README with setup, usage, and maintenance instructions

### Changed
- All price adjustments now round to whole numbers
- Adjustments (price/LOS) now work sequentially on the same updated data without requiring a refresh
- The "selected rows" table always updates to reflect the current selection
- Data generation and nightly override pulls now fully support new properties

### Removed
- All fallback and dependency on resdata files for occupancy calculation (now only uses pl_daily)
- All resdata_*.csv files from data directories

### Fixed
- NameError and session state bugs in adjustment logic
- UI bugs with stale data after pushing or changing selection

## [v1.5.0] - 2025-04-17

### Added
- New "Friday Orphan Adjustment" rule for both Fredericksburg (fb1) and Wimberley (wb1) properties
- Rule reduces rates for orphaned Fridays (when both Thursday and Saturday are booked)
- Applies a 0.8x multiplier to the rate, using Saturday's tier with Thu-Sun pricing

## [v1.4.0] - 2025-04-17

### Added
- Adjustment rules for Wimberley property (wb1)
- Added same Thursday and Sunday rate adjustment logic that's used for Fredericksburg
- Rules will adjust Thursday rates when Friday is booked and Sunday rates when Saturday is booked

## [v1.3.0] - 2025-04-17

### Changed
- Updated occupancy calculation to use vacant units from pl_daily data instead of reservation data
- Improved accuracy by calculating: (total units - vacant units) / total units × 100
- Added fallback to resdata-based calculation if pl_daily processing fails
- Modified error handling to make occupancy calculation more resilient

## [v1.2.0] - 2025-04-17

### Changed
- Improved occupancy calculation to use total units instead of just counting listings
- Added total_units field to property configuration
- Added units counts for individual listings in wb1 property
- The occupancy percentage will now correctly reflect the total available units

## [v1.1.0] - 2025-04-17

### Changed
- Updated booking status logic to consider a listing "booked" only when all units are occupied (Vacant Units = 0)
- Modified dataloader.py to use the "Vacant Units" column for determining booking status
- Updated comments and documentation to reflect the new "fully booked" requirement
- Changed the log message in dataloader.py to indicate "fully booked entries" instead of "booked/blocked entries"

## [Current Version]

### Features
- Dynamic pricing generation based on property configurations
- Rate table lookups with tier and seasonal adjustments
- Integration with PriceLabs API for live rate data
- Booking status tracking based on pl_daily data
- Web UI for rate visualization and editing

### Dependencies
- Python data processing (Pandas)
- Streamlit for web interface

## [Change History]

### YYYY-MM-DD - Initial Production Release
- Baseline functionality released 