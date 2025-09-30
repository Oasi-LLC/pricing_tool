# Pricing Tool Changelog

This file documents all significant changes to the pricing tool codebase.

## [v1.11.0] - 2025-09-02

### 📊 Change Statistics
- **46 files changed**
- **53,242 insertions**
- **62,412 deletions**
- **Net change: -9,170 lines** (significant cleanup and optimization)

### 🆕 Added

#### **New Files**
- **`utils/date_manager.py`** (10,741 bytes): Centralized date range management system
  - Centralized configuration for all date ranges used throughout the tool
  - Dynamic date calculations for scheduler, nightly pulls, and bulk processing
  - Validation and formatting utilities
  - Backward compatibility functions

- **`config/date_ranges.yaml`** (1,943 bytes): Configuration file for date range management
  - Current year: 2025
  - Full calculation range: 2025-09-01 to 2026-12-31
  - Dynamic calculations for scheduler and bulk processing
  - API operation limits and validation rules

- **`manage_scheduler_session.sh`** (2,511 bytes): Shell script for managing scheduler screen sessions
  - Start/stop/restart scheduler in screen session
  - Status checking and log viewing
  - Session management utilities

- **`start_scheduler_session.sh`** (2,117 bytes): Shell script to start scheduler in background screen session
  - Automatic screen session creation
  - Error handling and validation
  - User-friendly status messages

- **`scheduler_terminal.py`**: Interactive scheduler terminal interface
- **`utils/progress_tracker.py`**: Enhanced scheduler progress monitoring system

#### **Major Features**
- **BATNA Adjustment System**: Added "BATNA Rate" and "BATNA + Amount" adjustment options
- **Centralized Date Management**: All date range calculations now use centralized configuration
- **Enhanced Progress Tracking**: Real-time progress monitoring for scheduler operations
- **Session Management**: Improved scheduler session handling with screen-based management

### 🔧 Changed

#### **Major Modifications**
- **`app_2.py`** (354 lines changed):
  - Added BATNA adjustment options to adjustment modal
  - Integrated centralized date manager
  - Enhanced live rates processing with backend integration
  - Improved UI with better date range display

- **`utils/backend_interface.py`** (192 lines changed):
  - Added BATNA functions: `get_batna_for_listing()`, `get_listing_batna_info()`, `apply_batna_to_selection()`
  - Integrated centralized date range management
  - Enhanced live rates loading and processing
  - Added proper logging system integration

- **`config/properties.yaml`** (249 lines changed):
  - **Property Consolidation**: Combined fb1 and fb2 into single onera property
  - Added BATNA values for all listings
  - Added unit counts for multi-unit listings
  - Streamlined property definitions

- **`src/pricing_engine/calculator.py`** (46 lines changed):
  - Added comprehensive logging for rule-based adjustments
  - Added helper functions for listing name and PMS lookup
  - Enhanced error handling for logging failures

- **`src/pricing_engine/dataloader.py`** (15 lines changed):
  - Replaced hardcoded debug dates with operational range
  - Updated property references from fb1 to onera
  - Dynamic debug logging using operational date range

- **`utils/scheduler.py`** (19 lines changed):
  - Replaced hardcoded date calculations with centralized manager
  - Removed complex date calculation logic

#### **Rates and Pull System Changes**
- **`rates/pull/nightly_pull.py`** (159 lines changed):
  - Added comprehensive retry logic for API calls
  - Enhanced handling of 429 rate limit errors
  - Better error recovery and logging

- **`rates/push/push_rates.py`** (91 lines changed):
  - Added comprehensive logging for rate pushes
  - Added function to get listing names from config
  - Enhanced error handling and logging

#### **Data Files Updates**
All data files updated with new pricing data and occupancy information:
- `data/*/pl_daily_*.csv` - Updated with new pricing calculations
- `data/*/nightly_pulled_overrides.csv` - Updated with latest PriceLabs data
- `data/outputs/updates_log.csv` - New comprehensive update log (11,506 lines)

**Data File Statistics**:
- **fb1**: 14,503 lines changed (major restructuring)
- **fb2**: 8,207 lines changed (major restructuring)
- **flo1**: 13,392 lines changed (major restructuring)
- **melrose1**: 6,136 lines changed
- **pblu1**: 6,076 lines changed
- **sos1**: 8,432 lines changed
- **spm1**: 2,835 lines changed
- **wb1**: 7,220 lines changed
- **atx1**: 2,845 lines changed

### 🗑️ Removed

#### **Documentation Files (Cleanup)**
- `ERROR_PREVENTION_GUIDE.md` (218 lines) - Moved to CHANGELOG.md
- `PROJECT_PLAN.md` (150 lines) - Project completed, no longer needed
- `add_los_push.md` (36 lines) - Feature implemented, documentation moved
- `calendar_view_implementation.md` (298 lines) - Feature implemented, documentation moved
- `USER_GUIDE.md` - User guide deleted

#### **Legacy Files**
- `app.py` (826 lines) - Replaced by `app_2.py`
- `test_rules_adjustor.py` (505 lines) - Test file, no longer needed
- `test_manual_refresh.py` - Test file removed
- `test_scheduler_progress.py` - Test file removed
- `view_scheduler_status.py` - Test file removed

#### **Backup Files (Cleanup)**
- `backups/backend_interface.py` (348 lines)
- `backups/run_pricing.py` (275 lines)
- `backups/src/pricing_engine/calculator.py` (304 lines)
- `backups/src/pricing_engine/dataloader.py` (303 lines)
- `backups/utils/backend_interface.py` (348 lines)
- `data/atx1/rate_table_atx1.csv.backup` - Backup file removed
- `data/wb1/pulled_overrides_2025-04-13.csv` - Old file removed
- `data/wb1/pulled_overrides.csv` - Duplicate file removed

#### **Legacy Properties**
- Moved fb1 and fb2 to backup directory (now consolidated into onera)

### 🎯 Major Improvements Summary

1. **BATNA Adjustment System**: Added two new adjustment options with full preview and application functionality
2. **Centralized Date Management**: New comprehensive date range management system
3. **Property Consolidation**: Combined fb1 and fb2 properties into single "onera" property
4. **Enhanced Logging System**: Comprehensive logging for all operations
5. **API Rate Limit Handling**: Retry logic and better error recovery
6. **Code Cleanup and Optimization**: Removed 9,170 lines of redundant code

### ✅ Verification Checklist
- [x] All BATNA functionality restored and working
- [x] Date management system properly integrated
- [x] Property consolidation completed
- [x] Logging system functional
- [x] API rate limiting handled
- [x] Code cleanup completed
- [x] Documentation updated
- [x] No critical functionality lost
- [x] All new files properly integrated
- [x] Configuration files updated

## [v1.10.0] - 2025-09-02

### Added
- **Comprehensive Logging System**: Complete overhaul of logging infrastructure with detailed tracking
- **Price Update Logging**: All rate pushes to PriceLabs are now logged with full details
- **Error Logging**: API errors and unexpected failures are captured with context
- **Frontend Logging**: Manual rate changes in the UI are tracked with user context
- **Rule-based Logging**: Automatic rule adjustments are logged with rule names and reasons
- **Rate Evolution Tracking**: Tools to track how rates evolve over time for any listing and date
- **Log Analysis Tools**: Scripts to analyze rate changes, create graphs, and track evolution patterns

### Enhanced
- **Logging Infrastructure**: Centralized logging setup with timestamped files and structured data
- **Error Handling**: Enhanced error capture with detailed context and failure reasons
- **Rate Tracking**: Complete visibility into rate lifecycle from initial pull to final push
- **Data Analysis**: Tools to analyze pricing patterns and rule effectiveness

### Technical Improvements
- **Logging Setup**: `rates/logging_setup.py` with centralized logging configuration
- **Price Update Logs**: Detailed logs with listing names, PMS systems, dates, prices, and reasons
- **Error Logs**: Comprehensive error tracking with context and troubleshooting information
- **Rate Evolution Tools**: `daily_rate_tracker.py` and `rate_evolution_tracker.py` for analysis
- **Log Cleanup**: Removed 535 empty log files, keeping only files with actual data

### Fixed
- **Empty Log Files**: All pricing update and error log files were empty (headers only) - now fully functional
- **Missing Logging**: Rate pushes, errors, and manual changes were not being logged - now tracked
- **Data Visibility**: No way to track rate evolution over time - now fully trackable

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