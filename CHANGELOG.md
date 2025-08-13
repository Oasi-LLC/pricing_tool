# Pricing Tool Changelog

This file documents all significant changes to the pricing tool codebase.

## [v1.9.0] - 2025-01-15

### Added
- **Rules Adjuster System**: Comprehensive rule-based pricing adjustments for live rates
- **Advanced Property Rules**: Sophisticated pricing rules with min-stay adjustments and adjacent day logic
- **Enhanced Scheduler Documentation**: Complete rewrite of scheduler documentation with new auto-scheduler system
- **Property Reconfiguration**: Removed edge1 and pm1 properties, enhanced others with advanced rules
- **Min-Stay Logic**: Advanced logic for checking adjacent weekday minimum stay requirements
- **Rate Adjustment Engine**: Multiplier-based pricing adjustments based on booking patterns
- **Rules UI Integration**: Rules adjuster interface in both table and calendar views

### Changed
- **Property Configuration**: Added extensive adjustment rules to multiple properties (fb1, fb2, pblu1, atx1, sos1, spm1, flo1, melrose1)
- **Scheduler Configuration**: Modified scheduler.yaml (disabled by default, reordered fields)
- **Data Management**: Extended date ranges and added new listing configurations
- **UI Enhancement**: Added rules adjuster expandable sections to main results area

### Removed
- **Properties**: edge1 (Edgecamp) and pm1 (Pamlico) properties completely removed
- **Data Files**: Cleaned up old data files for removed properties
- **Legacy Rules**: Replaced simple rules with advanced, configurable rule system

### Technical Improvements
- **Rules Engine**: New functions for applying property-specific rules to live rates
- **Conditional Logic**: Support for complex booking conditions and adjacent day checks
- **Rate Calculations**: Advanced pricing logic with fallback reference rates
- **Min-Stay Management**: Intelligent minimum stay adjustments based on booking patterns

## [v1.8.0] - 2025-07-29

### Added
- **Comprehensive Error Prevention System**: Implemented multiple safeguards to prevent timezone and variable scope errors
- **System Health Monitoring**: `scripts/check_system_health.py` for monitoring all critical services
- **Auto-Recovery System**: `scripts/auto_recovery.py` for automatically restarting failed services
- **Enhanced Error Handling**: Comprehensive try-catch blocks and graceful failure handling
- **Consecutive Error Tracking**: Prevents infinite error loops with exponential backoff
- **Error Prevention Guide**: `ERROR_PREVENTION_GUIDE.md` with complete documentation of safeguards

### Fixed
- **Critical Timezone Error**: Fixed `"can't subtract offset-naive and offset-aware datetimes"` error that prevented scheduler from running
- **Variable Scope Error**: Fixed `"data_col2 is not defined"` error in Streamlit app scheduler section
- **Scheduler Reliability**: Enhanced scheduler daemon with better error handling and recovery mechanisms
- **App Display Issues**: Fixed indentation errors and variable scope issues in scheduler status display

### Changed
- **Enhanced Scheduler Logic**: Improved timezone handling with proper localization of datetime objects
- **Error Recovery**: Added automatic restart capabilities for failed services
- **Log Management**: Implemented log rotation to prevent log bloat
- **Process Monitoring**: Added health checks for all critical services

### Technical Improvements
- **Timezone Safety**: All datetime objects are now properly timezone-aware before comparison
- **Variable Safety**: Fixed all variable scope issues in the Streamlit app
- **Error Resilience**: System can now self-heal from common failure patterns
- **Monitoring**: Real-time health monitoring with automatic alerting

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