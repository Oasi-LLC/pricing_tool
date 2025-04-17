# Pricing Tool Changelog

This file documents all significant changes to the pricing tool codebase.

## [Unreleased]

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