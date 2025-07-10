# Pricing Tool Changelog

This file documents all significant changes to the pricing tool codebase.

## [v1.6.0] - 2024-07-09

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