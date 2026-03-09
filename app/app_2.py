import sys
from pathlib import Path

# Ensure project root is on path when run as streamlit run app/app_2.py
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
import pandas as pd
import datetime
import traceback
import numpy as np
import re
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode, ColumnsAutoSizeMode
import json
from rates.push.push_rates import push_rates_to_pricelabs, push_rates_batch
import os

# Import backend interface functions
from utils import backend_interface

# Import scheduler functions
import utils.scheduler as _scheduler_module
load_scheduler_config = _scheduler_module.load_scheduler_config
save_scheduler_config = _scheduler_module.save_scheduler_config
get_scheduler_status = _scheduler_module.get_scheduler_status
is_time_to_refresh = _scheduler_module.is_time_to_refresh
run_scheduled_refresh = _scheduler_module.run_scheduled_refresh
get_lisbon_time = _scheduler_module.get_lisbon_time
estimate_api_call_volume = _scheduler_module.estimate_api_call_volume
get_dynamic_date_range = _scheduler_module.get_dynamic_date_range
send_custom_alert = getattr(_scheduler_module, "send_custom_alert", None)
is_deployed_no_backend = getattr(_scheduler_module, "is_deployed_no_backend", None)
get_refresh_progress = getattr(_scheduler_module, "get_refresh_progress", None)
if is_deployed_no_backend is None:
    def is_deployed_no_backend():
        import os
        if os.environ.get("PRICING_TOOL_DEPLOYED", "").strip() in ("1", "true", "yes"):
            return True
        try:
            config = load_scheduler_config()
            return (config.get("deployment_mode") or "local").lower() == "cloud"
        except Exception:
            return False
if get_refresh_progress is None:
    def get_refresh_progress():
        return {"refresh_active": False, "current_step": None, "current_operation": None, "total_progress": 0, "properties_completed": 0, "properties_total": 0}
if send_custom_alert is None:
    def send_custom_alert(text):
        return False

# Auto-start scheduler functionality (only when not deployed without backend)
import subprocess
import threading
import time

def ensure_scheduler_running():
    """Ensure the scheduler daemon is running when the app starts. No-op in deployed (no-backend) mode."""
    if is_deployed_no_backend():
        return False  # Daemon not available in cloud deployment
    try:
        # Check if scheduler is already running
        result = subprocess.run(
            ["pgrep", "-f", "scheduler_daemon.py"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return True  # Scheduler is already running
        
        # Start the scheduler if it's not running
        project_root = Path(__file__).resolve().parent.parent
        venv_python = project_root / "venv" / "bin" / "python"
        scheduler_script = project_root / "scheduler" / "scheduler_daemon.py"
        
        if not scheduler_script.exists():
            return False
        
        # Start scheduler in background
        subprocess.Popen(
            [str(venv_python), str(scheduler_script)],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Wait a moment for it to start
        time.sleep(2)
        
        # Verify it started
        result = subprocess.run(
            ["pgrep", "-f", "scheduler_daemon.py"],
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0
        
    except Exception:
        # Do not surface subprocess errors to the user (e.g. pgrep missing on Windows, or in cloud)
        return False

# Start scheduler when app loads (skipped in deployed no-backend mode)
if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = ensure_scheduler_running()

# Set page config
st.set_page_config(layout="wide", page_title="Rate Review Tool")

# Title
st.title("Internal Rate Review & Management Tool")

# Add this helper at the top of the file (after imports)
def rerun():
    if hasattr(st, 'rerun'):
        st.rerun()
    elif hasattr(st, 'experimental_rerun'):
        st.experimental_rerun()

# --- Constants for Column Names ---
COL_SELECT = 'Select'
COL_ID = '_id'
COL_DATE = 'Date'
COL_PROPERTY = 'Unit Pool'
COL_LISTING_NAME = 'listing_name'
COL_LISTING_ID = 'listing_id'
COL_TIER = 'calculated_tier'
COL_TIER_SRC = 'tier_group'
COL_DAY_OF_WEEK = 'Day of Week'
COL_LIVE_RATE = 'Live Rate $'
COL_SUGGESTED = 'Suggested'
COL_DELTA = 'Delta'
COL_EDITABLE_PRICE = 'Editable Price'
COL_FLAG = 'Flag'
COL_STATUS = 'Status'
COL_OCC_CURR = 'Occ% (Curr)'
COL_OCC_HIST = "Occ% (Hist)"
COL_PACE = "Pace"
COL_MIN_STAY = "Min Stay"
COL_EDITABLE_MIN_STAY = "Editable Min Stay"

# Source column names
COL_BASELINE_SRC = "Baseline"
COL_SUGGESTED_SRC = "Suggested"
COL_EDITABLE_PRICE_SRC = "Editable Price"
COL_PROPERTY_SRC = "property"
COL_CALCULATED_TIER_SRC = "calculated_tier"
COL_EDITABLE_MIN_STAY_SRC = "Editable Min Stay"

# Hidden columns (updated to include all columns we don't want to show)
HIDDEN_COLS = [
    'property',  # Hide 'property' since we're using 'Unit Pool'
    'listing_id',
    'tier_group',
    'day_group',
    'booking_window',
    'urgency_band',
    'lookup_error',
    'date',  # Hide internal date column
    'Baseline',
    'Occ% (Hist)',
    'Pace'
]

# Core visible columns
CORE_COLS = [
    COL_SELECT, COL_DATE, COL_PROPERTY, COL_TIER, COL_DAY_OF_WEEK,
    COL_MIN_STAY,
    COL_OCC_CURR,
    COL_LIVE_RATE, COL_SUGGESTED, COL_DELTA, COL_EDITABLE_PRICE,
    COL_FLAG, COL_STATUS
]

# Define the exact columns we want to show, in order
DEFAULT_VISIBLE_COLUMNS = [
    COL_SELECT,
    COL_ID,
    COL_DATE,
    COL_PROPERTY,
    COL_LISTING_NAME,
    COL_TIER,
    COL_DAY_OF_WEEK,
    COL_MIN_STAY,
    COL_EDITABLE_MIN_STAY,
    COL_OCC_CURR,
    COL_LIVE_RATE,
    COL_SUGGESTED,
    COL_DELTA,
    COL_EDITABLE_PRICE,
    COL_FLAG,
    COL_STATUS
]

# Column display names mapping
COLUMN_DISPLAY_NAMES = {
    COL_SELECT: "Select",
    COL_ID: "ID",
    COL_DATE: "Date",
    COL_PROPERTY: "Property",
    COL_LISTING_NAME: "Listing Name",
    COL_TIER: "Tier",
    COL_DAY_OF_WEEK: "Day",
    COL_OCC_CURR: "Occ% Current",
    COL_LIVE_RATE: "Live Rate $",
    COL_SUGGESTED: "Suggested Rate $",
    COL_DELTA: "Delta %",
    COL_EDITABLE_PRICE: "Editable Rate $",
    COL_FLAG: "Flag",
    COL_STATUS: "Status",
    COL_MIN_STAY: "Min Stay",
    COL_EDITABLE_MIN_STAY: "Editable Min Stay"
}

# --- Session State Initialization ---
if 'selected_properties' not in st.session_state:
    st.session_state.selected_properties = []
if 'start_date' not in st.session_state or 'end_date' not in st.session_state:
    try:
        from utils.date_manager import get_ui_default_range
        _ui_start, _ui_end = get_ui_default_range()
        st.session_state.start_date = _ui_start
        st.session_state.end_date = _ui_end
    except Exception:
        st.session_state.start_date = datetime.date.today()
        st.session_state.end_date = datetime.date.today() + datetime.timedelta(days=30)
if 'generate_clicked' not in st.session_state:
    st.session_state.generate_clicked = False
if 'generated_rates_df' not in st.session_state:
    st.session_state.generated_rates_df = None
if 'edited_rates_df' not in st.session_state:
    st.session_state.edited_rates_df = None
if 'results_are_displayed' not in st.session_state:
    st.session_state.results_are_displayed = False
if 'checkbox_selections' not in st.session_state:
    st.session_state.checkbox_selections = {}
if 'selected_ids' not in st.session_state:
    st.session_state.selected_ids = set()
if 'initial_load_complete' not in st.session_state:
    st.session_state.initial_load_complete = False
if 'show_adjust_modal' not in st.session_state:
    st.session_state.show_adjust_modal = False
if 'show_los_adjust_modal' not in st.session_state:  # Add LOS modal state
    st.session_state.show_los_adjust_modal = False
if 'adjustment_type' not in st.session_state:
    st.session_state.adjustment_type = 'value'
if 'adjustment_amount' not in st.session_state:
    st.session_state.adjustment_amount = 0.0
if 'los_adjustment_amount' not in st.session_state:  # Add LOS adjustment amount
    st.session_state.los_adjustment_amount = 1

# Add rules adjuster states to session state initialization
if 'rules_applied' not in st.session_state:
    st.session_state.rules_applied = False
if 'rules_results' not in st.session_state:
    st.session_state.rules_results = None
if 'show_rules_results' not in st.session_state:
    st.session_state.show_rules_results = False

# Add refresh operation states to session state initialization
if 'refresh_all_clicked' not in st.session_state:
    st.session_state.refresh_all_clicked = False
if 'refresh_nightly_clicked' not in st.session_state:
    st.session_state.refresh_nightly_clicked = False
if 'refresh_current_clicked' not in st.session_state:
    st.session_state.refresh_current_clicked = False
if 'refresh_property_clicked' not in st.session_state:
    st.session_state.refresh_property_clicked = False
if 'refresh_all_data_clicked' not in st.session_state:
    st.session_state.refresh_all_data_clicked = False
if 'refresh_status' not in st.session_state:
    st.session_state.refresh_status = ""
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = None

# Add scheduler states to session state initialization
if 'scheduler_enabled' not in st.session_state:
    st.session_state.scheduler_enabled = False
if 'scheduler_refresh_clicked' not in st.session_state:
    st.session_state.scheduler_refresh_clicked = False
if 'scheduler_status' not in st.session_state:
    st.session_state.scheduler_status = ""
if 'manual_refresh_in_progress' not in st.session_state:
    st.session_state.manual_refresh_in_progress = False
if 'manual_refresh_thread' not in st.session_state:
    st.session_state.manual_refresh_thread = None
if 'single_property_refresh_clicked' not in st.session_state:
    st.session_state.single_property_refresh_clicked = False
if 'single_property_refresh_key' not in st.session_state:
    st.session_state.single_property_refresh_key = None
if 'cloud_scheduled_refresh_thread' not in st.session_state:
    st.session_state.cloud_scheduled_refresh_thread = None

# Filter defaults - removed since filtering is now handled by the grid

# Rate source toggle state
if 'active_rate_source_col' not in st.session_state:
    st.session_state.active_rate_source_col = COL_LIVE_RATE
if 'rate_source_toggle' not in st.session_state:
    st.session_state.rate_source_toggle = 'Use Live Rate'

# Helper functions
def natural_sort_key_tier(tier_string):
    if tier_string is None:
        return (-1, tier_string)
    tier_string = str(tier_string)
    match = re.match(r'T(\d+)', tier_string, re.IGNORECASE)
    if match:
        return (0, int(match.group(1)))
    else:
        return (1, tier_string)

def apply_price_adjustment(current_price, adjustment_type, adjustment_amount):
    """Apply price adjustment based on type and amount"""
    try:
        current_price = float(current_price)
        adjustment_amount = float(adjustment_amount)
        
        if adjustment_type == 'percentage':
            # Convert percentage to decimal and add to 1 for multiplication
            # e.g., 10% increase = 1.10, -10% decrease = 0.90
            multiplier = 1 + (adjustment_amount / 100)
            result = round(current_price * multiplier, 2)
            return result
        else:  # value
            result = round(current_price + adjustment_amount, 2)
            return result
    except (ValueError, TypeError) as e:
        return current_price

def _check_adjacent_weekday_los_for_target(target_date, df, property_key, listing_id, day_offset):
    """
    Check if the adjacent weekday has 1-night minimum for a specific target day.
    This function correctly identifies which adjacent weekday to check based on the target day.
    
    Args:
        target_date: The target date to check
        df: DataFrame with rate data
        property_key: Property key
        listing_id: Specific listing ID to check
        day_offset: Day offset from the rule trigger date (e.g., -2 for Thursday, -1 for Friday, +1 for Sunday)
    
    Returns:
        bool: True if the adjacent weekday has 1-night minimum
    """
    # Determine which adjacent weekday to check based on the target day
    if day_offset == -2:  # Thursday: check Wednesday (day before Thursday)
        adjacent_weekday = target_date - datetime.timedelta(days=1)
        print(f"🔍 DEBUG: Thursday target ({target_date}), checking Wednesday ({adjacent_weekday})")
    elif day_offset == -1:  # Friday: check Wednesday (two days before Friday)
        adjacent_weekday = target_date - datetime.timedelta(days=2)
        print(f"🔍 DEBUG: Friday target ({target_date}), checking Wednesday ({adjacent_weekday})")
    elif day_offset == 1:  # Sunday: check Monday (day after Sunday)
        adjacent_weekday = target_date + datetime.timedelta(days=1)
        print(f"🔍 DEBUG: Sunday target ({target_date}), checking Monday ({adjacent_weekday})")
    else:
        print(f"🔍 DEBUG: Unknown day_offset {day_offset}, cannot determine adjacent weekday")
        return False
    
    adjacent_weekday_str = adjacent_weekday.strftime('%Y-%m-%d')
    
    # Get the listing data for this adjacent weekday
    adjacent_data = df[
        (df['Date'] == adjacent_weekday_str) & 
        (df['Unit Pool'] == property_key) & 
        (df['listing_id'] == listing_id)
    ]
    
    if adjacent_data.empty:
        print(f"🔍 DEBUG: No data found for adjacent weekday {adjacent_weekday_str}")
        return False
    
    min_stay = adjacent_data.iloc[0].get('Min Stay', 1)
    if pd.isna(min_stay):
        min_stay = 1
    
    print(f"🔍 DEBUG: Adjacent weekday {adjacent_weekday_str} has min stay: {min_stay}")
    
    # Return True if the adjacent weekday has 1-night minimum
    return min_stay == 1

def apply_rules_to_live_rates(df, selected_properties):
    """
    Apply property-specific rules to live rates and return adjusted rates.
    
    Args:
        df: DataFrame with rate data
        selected_properties: List of selected property keys
    
    Returns:
        Dict with results of rule application
    """
    if df is None or df.empty:
        return {
            'success': False,
            'message': 'No data available for rule application',
            'adjusted_rates': [],
            'total_rates': 0
        }
    
    # Load property configurations
    properties_config = backend_interface.load_properties_config()
    if not properties_config:
        return {
            'success': False,
            'message': 'Could not load property configurations',
            'adjusted_rates': [],
            'total_rates': 0
        }
    
    adjusted_rates = []
    total_rates = 0
    adjusted_dates = set()  # Track which dates have been adjusted to prevent double adjustments
    
    # Process each property
    for property_key in selected_properties:
        if property_key not in properties_config:
            continue
            
        prop_config = properties_config[property_key]
        property_df = df[df['Unit Pool'] == property_key].copy()
        
        if property_df.empty:
            continue
            
        # Get adjustment rules for this property
        adjustment_rules = prop_config.get('adjustment_rules', [])
        
        if not adjustment_rules:
            continue
            
        print(f"🔍 DEBUG: Processing {property_key} with {len(adjustment_rules)} rules")
        
        # Apply each rule
        for rule in adjustment_rules:
            rule_name = rule.get('name', 'Unnamed Rule')
            target_weekday = rule.get('target_weekday')
            conditions = rule.get('conditions', [])
            actions = rule.get('actions', [])
            
            if target_weekday is None:
                continue
                
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            print(f"🔍 DEBUG: Rule '{rule_name}' targets {weekday_names[target_weekday]} (weekday {target_weekday})")
            print(f"🔍 DEBUG: Conditions: {conditions}")
            
            # Filter for the target weekday
            weekday_dates = []
            for date_str in property_df['Date'].unique():
                try:
                    # Handle potential NaN values in date strings
                    if pd.isna(date_str):
                        continue
                    date_obj = datetime.datetime.strptime(str(date_str), '%Y-%m-%d').date()
                    if date_obj.weekday() == target_weekday:
                        weekday_dates.append(date_str)
                except (ValueError, TypeError):
                    continue
            
            print(f"🔍 DEBUG: Found {len(weekday_dates)} {weekday_names[target_weekday]} dates: {weekday_dates[:5]}...")
            
            if not weekday_dates:
                continue
                
            # Apply rule to each date
            for date_str in weekday_dates:
                try:
                    # Handle potential NaN values in date strings
                    if pd.isna(date_str):
                        continue
                    date_obj = datetime.datetime.strptime(str(date_str), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    continue
                
                print(f"🔍 DEBUG: Checking date {date_str} for rule '{rule_name}'")
                
                # Check if this date has already been adjusted (prevent double adjustments)
                date_key = f"{property_key}_{rule_name}_{date_str}"
                if date_key in adjusted_dates:
                    continue
                
                # Apply ALL actions defined for this rule
                if not actions:
                    continue

                # Apply to all listings for this property on this date
                date_listings = property_df[property_df['Date'] == date_str]

                for _, row in date_listings.iterrows():
                    # Do not skip booked rows outright: booked rows can TRIGGER adjacent-day LOS rules
                    is_booked = (row['Flag'] == '🔒 Booked')

                    for selected_action in actions:
                        multiplier = selected_action.get('multiplier', 1.0)
                        ref_day_offset = selected_action.get('reference_day_offset', 0)
                        los_adjustment = selected_action.get('los_adjustment')
                        check_adjacent_weekday_los = selected_action.get('check_adjacent_weekday_los', False)
                        target_adjacent_days = selected_action.get('target_adjacent_days')
                        min_stay_adjustment = selected_action.get('min_stay_adjustment')

                        # Compute reference date for this action
                        ref_date = date_obj + datetime.timedelta(days=ref_day_offset)
                        ref_date_str = ref_date.strftime('%Y-%m-%d')

                        # Apply to all listings for this property on this date (action scope)
                        # Note: reuse current row context below
                    
                        # Check if conditions are met for this specific listing
                        conditions_met = True
                        for i, condition in enumerate(conditions):
                            condition_result = _check_rule_condition(condition, date_obj, property_df, property_key, row['listing_id'])
                            print(f"🔍 DEBUG: Condition {i+1}: {condition} -> {condition_result} for listing {row['listing_id']}")
                            if not condition_result:
                                conditions_met = False
                                break

                        if not conditions_met:
                            print(f"🔍 DEBUG: Conditions not met for {date_str}, listing {row['listing_id']}, skipping")
                            continue

                        print(f"🔍 DEBUG: ✅ Conditions met for {date_str}, listing {row['listing_id']}, applying rule")

                        # Get reference day's live rate for this listing (for price adjustments)
                        ref_date_listings = property_df[
                            (property_df['Date'] == ref_date_str) &
                            (property_df['listing_id'] == row['listing_id'])
                        ]

                        # Initialize accumulators for this listing/date combination
                        current_min_stay = row.get('Min Stay', 1)
                        current_live_rate = row.get('Live Rate $', 0)

                        # Handle NaN values
                        if pd.isna(current_min_stay):
                            current_min_stay = 1
                        if pd.isna(current_live_rate):
                            current_live_rate = 0

                        acc_price = float(current_live_rate)
                        acc_min_stay = int(current_min_stay)
                        overall_change_applied = False
                        overall_reasons = []
                        last_ref_date_str = 'N/A'
                        last_ref_live_rate = 'N/A'
                        
                        # Store original values for comparison
                        original_price = float(current_live_rate)
                        original_min_stay = int(current_min_stay)

                        # Apply price adjustment if multiplier is specified and reference data exists
                        if not is_booked and multiplier != 1.0:
                            ref_live_rate = None

                            # Primary reference (e.g., Thu uses Wed, Sun uses Mon)
                            if not ref_date_listings.empty:
                                ref_live_rate = ref_date_listings.iloc[0].get('Live Rate $', 0)
                                if pd.isna(ref_live_rate):
                                    ref_live_rate = 0

                            # Fallback: one more day in the same direction (Thu→Tue, Sun→Tue)
                            if (ref_live_rate is None or ref_live_rate <= 0):
                                fallback_offset = ref_day_offset - 1 if ref_day_offset < 0 else ref_day_offset + 1
                                fb_date = date_obj + datetime.timedelta(days=fallback_offset)
                                fb_date_str = fb_date.strftime('%Y-%m-%d')
                                fb_listings = property_df[
                                    (property_df['Date'] == fb_date_str) &
                                    (property_df['listing_id'] == row['listing_id'])
                                ]
                                if not fb_listings.empty:
                                    fb_live = fb_listings.iloc[0].get('Live Rate $', 0)
                                    if not pd.isna(fb_live):
                                        ref_live_rate = float(fb_live)

                            if not ref_live_rate or ref_live_rate <= 0:
                                overall_reasons.append("reference rate missing (primary & fallback)")
                            else:
                                calculated_new_price = round(ref_live_rate * multiplier, 2)
                                # Guard: do not raise prices via rules; only reduce or keep the same
                                if calculated_new_price < acc_price:
                                    acc_price = calculated_new_price
                                    overall_change_applied = True
                                    last_ref_date_str = ref_date_str
                                    last_ref_live_rate = ref_live_rate
                                else:
                                    overall_reasons.append("would increase price; kept original")
                                    last_ref_date_str = ref_date_str
                                    last_ref_live_rate = ref_live_rate

                        # NEW: Handle min stay adjustment rules with target_adjacent_days
                        if min_stay_adjustment is not None and target_adjacent_days is not None:
                            print(f"🔍 DEBUG: Processing min stay reduction rule with target_adjacent_days: {target_adjacent_days}")
                            if is_booked:
                                print(f"🔍 DEBUG: Saturday (or target) listing {row['listing_id']} is booked, processing adjacent days for this listing only")
                                # Process other target days (Thursday/Friday) for this specific listing
                                for day_offset in target_adjacent_days:
                                    if day_offset == 0:  # Skip current date (already processed above)
                                        continue

                                    target_date = date_obj + datetime.timedelta(days=day_offset)
                                    target_date_str = target_date.strftime('%Y-%m-%d')

                                    print(f"🔍 DEBUG: Processing target date {target_date_str} (offset {day_offset}) for Saturday listing {row['listing_id']}")

                                    # Check if target date exists in data
                                    target_date_listings = property_df[property_df['Date'] == target_date_str]
                                    if target_date_listings.empty:
                                        print(f"🔍 DEBUG: Target date {target_date_str} not found in data, skipping")
                                        continue

                                    # CRITICAL FIX: Only process the specific listing that was booked on Saturday
                                    target_listing_data = target_date_listings[target_date_listings['listing_id'] == row['listing_id']]
                                    if target_listing_data.empty:
                                        print(f"🔍 DEBUG: Target listing {row['listing_id']} not found on target date {target_date_str}, skipping")
                                        continue

                                    target_row = target_listing_data.iloc[0]
                                    if target_row['Flag'] == '🔒 Booked':
                                        overall_reasons.append(f"target {target_date_str} booked; skipped")
                                        continue

                                    target_current_min_stay = target_row.get('Min Stay', 1)
                                    if pd.isna(target_current_min_stay):
                                        target_current_min_stay = 1

                                    target_new_min_stay = target_current_min_stay

                                    if check_adjacent_weekday_los:
                                        # Check if adjacent weekday has 1-night minimum for this target day
                                        adjacent_has_1night = _check_adjacent_weekday_los_for_target(
                                            target_date, property_df, property_key, target_row['listing_id'], day_offset
                                        )
                                        if adjacent_has_1night:
                                            target_new_min_stay = min_stay_adjustment
                                        else:
                                            overall_reasons.append(f"prereq failed for {target_date_str} (weekday not 1-night)")
                                            continue
                                    else:
                                        target_new_min_stay = min_stay_adjustment

                                    # Only append a target adjustment when it actually changes something
                                    if target_new_min_stay != target_current_min_stay:
                                        adjusted_rates.append({
                                            'listing_id': target_row['listing_id'],
                                            'listing_name': target_row['listing_name'],
                                            'date': target_date_str,
                                            'original_price': target_row.get('Live Rate $', 0),
                                            'new_price': target_row.get('Live Rate $', 0),  # No price change in this path
                                            'original_min_stay': target_current_min_stay,
                                            'new_min_stay': target_new_min_stay,
                                            'rule_applied': rule_name,
                                            'multiplier': 1.0,
                                            'property': property_key,
                                            'reference_date': 'N/A',
                                            'reference_rate': 'N/A',
                                            'change_applied': True,
                                            'reason': ''
                                        })
                                    else:
                                        overall_reasons.append(f"no LOS change needed on {target_date_str} (already {target_current_min_stay}n)")
                            else:
                                print(f"🔍 DEBUG: Saturday listing {row['listing_id']} is NOT booked, skipping adjacent day processing")

                        # Apply traditional LOS adjustment if specified (for backward compatibility)
                        elif los_adjustment is not None:
                            if check_adjacent_weekday_los:
                                adjacent_has_2night = _check_adjacent_weekday_los(date_obj, property_df, property_key, row['listing_id'])
                                if adjacent_has_2night:
                                    if los_adjustment != acc_min_stay:
                                        acc_min_stay = los_adjustment
                                        overall_change_applied = True
                                else:
                                    overall_reasons.append("LOS prerequisite failed; skipped")
                            else:
                                if los_adjustment != acc_min_stay:
                                    acc_min_stay = los_adjustment
                                    overall_change_applied = True

                        # Only mark as changed if there were actual modifications by rules
                        if acc_price != original_price or acc_min_stay != original_min_stay:
                            overall_change_applied = True
                            
                        # Debug logging
                        print(f"🔍 DEBUG: {date_str} {row['listing_name']}: price {original_price}→{acc_price}, min_stay {original_min_stay}→{acc_min_stay}, change_applied={overall_change_applied}, reasons={overall_reasons}")

                        adjusted_rates.append({
                            'listing_id': row['listing_id'],
                            'listing_name': row['listing_name'],
                            'date': date_str,
                            'original_price': current_live_rate,
                            'new_price': acc_price,
                            'original_min_stay': current_min_stay,
                            'new_min_stay': acc_min_stay,
                            'rule_applied': rule_name,  # aggregated
                            'multiplier': 1.0,          # aggregated
                            'property': property_key,
                            'reference_date': last_ref_date_str,
                            'reference_rate': last_ref_live_rate,
                            'change_applied': overall_change_applied,
                            'reason': "; ".join(overall_reasons) if overall_reasons else ''
                        })

                # Mark this date as adjusted
                adjusted_dates.add(date_key)
    
    total_rates = len(adjusted_rates)
    
    # Count actual changes
    actual_changes = sum(1 for rate in adjusted_rates if rate.get('change_applied', False))
    
    return {
        'success': True,
        'adjusted_rates': adjusted_rates,
        'total_rates': total_rates,
        'actual_changes': actual_changes,
        'message': f'Applied rules to {len(adjusted_rates)} rates across {len(selected_properties)} properties ({actual_changes} with actual changes)',
    }

def _check_rule_condition(condition, date_obj, df, property_key, listing_id=None):
    """
    Check if a rule condition is met.
    
    Args:
        condition: Condition configuration dict
        date_obj: Date to check
        df: DataFrame with rate data
        property_key: Property key
        listing_id: Specific listing ID to check (optional)
    
    Returns:
        bool: True if condition is met
    """
    if condition is None:
        return True
        
    condition_type = condition.get('type')
    
    if condition_type == 'adjacent_day_booked':
        day_offset = condition.get('day_offset', 0)
        adjacent_date = date_obj + datetime.timedelta(days=day_offset)
        adjacent_date_str = adjacent_date.strftime('%Y-%m-%d')
        
        # Check if the specific listing is booked on the adjacent date
        if listing_id:
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key) &
                (df['listing_id'] == listing_id)
            ]
            is_booked = any(adjacent_data['Flag'] == '🔒 Booked')
        else:
            # Fallback to property-wide check if no specific listing provided
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key)
            ]
            is_booked = any(adjacent_data['Flag'] == '🔒 Booked')
        
        print(f"🔍 DEBUG: adjacent_day_booked check for {adjacent_date_str}: {is_booked}")
        print(f"🔍 DEBUG: Found {len(adjacent_data)} rows for {adjacent_date_str}")
        if not adjacent_data.empty:
            print(f"🔍 DEBUG: Flag values: {adjacent_data['Flag'].unique()}")
            print(f"🔍 DEBUG: Listing IDs for {adjacent_date_str}: {adjacent_data['listing_id'].unique()}")
            print(f"🔍 DEBUG: Listing names for {adjacent_date_str}: {adjacent_data['listing_name'].unique()}")
        
        return is_booked
    
    elif condition_type == 'adjacent_day_not_booked':
        day_offset = condition.get('day_offset', 0)
        adjacent_date = date_obj + datetime.timedelta(days=day_offset)
        adjacent_date_str = adjacent_date.strftime('%Y-%m-%d')
        
        # Check if the specific listing is NOT booked on the adjacent date
        if listing_id:
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key) &
                (df['listing_id'] == listing_id)
            ]
            is_not_booked = not any(adjacent_data['Flag'] == '🔒 Booked')
        else:
            # Fallback to property-wide check if no specific listing provided
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key)
            ]
            is_not_booked = not any(adjacent_data['Flag'] == '🔒 Booked')
        
        print(f"🔍 DEBUG: adjacent_day_not_booked check for {adjacent_date_str}: {is_not_booked}")
        print(f"🔍 DEBUG: Found {len(adjacent_data)} rows for {adjacent_date_str}")
        if not adjacent_data.empty:
            print(f"🔍 DEBUG: Flag values: {adjacent_data['Flag'].unique()}")
            print(f"🔍 DEBUG: Listing IDs for {adjacent_date_str}: {adjacent_data['listing_id'].unique()}")
            print(f"🔍 DEBUG: Listing names for {adjacent_date_str}: {adjacent_data['listing_name'].unique()}")
        
        return is_not_booked
    
    elif condition_type == 'upcoming_weekend':
        # Check if this is the immediate upcoming weekend
        today = datetime.datetime.now().date()
        
        # Calculate days until this Friday
        current_weekday = date_obj.weekday()
        days_until_friday = (4 - today.weekday()) % 7  # 4 = Friday
        if days_until_friday == 0:  # Today is Friday
            days_until_friday = 7  # Next Friday
        
        # Calculate the immediate upcoming Friday
        upcoming_friday = today + datetime.timedelta(days=days_until_friday)
        upcoming_saturday = upcoming_friday + datetime.timedelta(days=1)
        
        # Return True only if current_date is the upcoming Friday or Saturday
        is_upcoming_weekend = date_obj in [upcoming_friday, upcoming_saturday]
        print(f"🔍 DEBUG: upcoming_weekend condition for {date_obj}: {is_upcoming_weekend}")
        print(f"🔍 DEBUG: Today: {today}, Upcoming Friday: {upcoming_friday}, Upcoming Saturday: {upcoming_saturday}")
        return is_upcoming_weekend
    
    return False

def _check_adjacent_weekday_los(date_obj, df, property_key, listing_id):
    """
    DEPRECATED: This function is hardcoded to check Mon-Wed and should not be used for new rules.
    Use _check_adjacent_weekday_los_for_target() instead for proper adjacent weekday checking.
    
    Check if adjacent weekdays (Mon-Wed) have 2-night minimum for a specific listing.
    
    Args:
        date_obj: Date to check
        df: DataFrame with rate data
        property_key: Property key
        listing_id: Specific listing ID to check
    
    Returns:
        bool: True if adjacent weekdays have 2-night minimum
    """
    # DEPRECATED: This function is hardcoded to check Mon-Wed regardless of target day
    # Check Monday, Tuesday, Wednesday (weekdays 0, 1, 2)
    adjacent_weekdays = []
    for i in range(3):  # Mon, Tue, Wed
        weekday_date = date_obj + datetime.timedelta(days=i)
        adjacent_weekdays.append(weekday_date)
    
    for weekday_date in adjacent_weekdays:
        weekday_date_str = weekday_date.strftime('%Y-%m-%d')
        
        # Get the listing data for this weekday
        listing_data = df[
            (df['Date'] == weekday_date_str) & 
            (df['Unit Pool'] == property_key) & 
            (df['listing_id'] == listing_id)
        ]
        
        if not listing_data.empty:
            min_stay = listing_data.iloc[0].get('Min Stay', 1)
            if pd.isna(min_stay):
                min_stay = 1
            
            # If any weekday has 2-night minimum, return True
            if min_stay >= 2:
                return True
    
    # If no weekdays have 2-night minimum, return False
    return False

def clear_all_filter_states():
    # This function is no longer needed since filtering is handled by the grid
    pass

def update_editable_rate_source():
    """Update editable rate values based on selected source"""
    if st.session_state.base_data is not None:
        toggle_value = st.session_state.get('rate_source_toggle', 'Use Live Rate')
        source_col = COL_LIVE_RATE if toggle_value == 'Use Live Rate' else COL_SUGGESTED
        
        if source_col in st.session_state.base_data.columns:
            # Update editable price with values from selected source
            st.session_state.base_data[COL_EDITABLE_PRICE_SRC] = pd.to_numeric(
                st.session_state.base_data[source_col], 
                errors='coerce'
            ).fillna(0.0)
            update_filtered_data()
        else:
            st.error(f"Source column '{source_col}' not found in data")



def get_full_dataset_for_calculations():
    """Get the full dataset for calculations if available"""
    if hasattr(st, 'session_state') and hasattr(st.session_state, 'full_dataset_for_calculations'):
        return st.session_state.full_dataset_for_calculations
    elif hasattr(st, 'session_state') and hasattr(st.session_state, 'base_data'):
        return st.session_state.base_data
    else:
        return None

# Function to update selected IDs
def update_selected_ids(new_ids, all_visible_ids):
    current = st.session_state.selected_ids
    to_add = set(new_ids)
    to_remove = set(all_visible_ids) - to_add
    current.update(to_add)
    current.difference_update(to_remove)
    st.session_state.selected_ids = current

# Helper function to get currency for a listing
def get_currency_for_listing(listing_id: str, property_key: str = None, date: str = None) -> str:
    """
    Get currency for a listing. Defaults to MXN for azulik1, USD for others.
    Can also look up currency from override data if available.
    """
    # Check if it's azulik property by property key (normalize to lowercase)
    if property_key and property_key.lower() in ['azulik1', 'azulik']:
        return 'MXN'
    
    # Fallback: Check if listing_id belongs to azulik by checking azulik override file
    # Azulik listing IDs start with 283597___
    if listing_id and listing_id.startswith('283597___'):
        return 'MXN'
    
    # Try to get currency from override data if date is provided
    if date and property_key:
        try:
            override_path = Path(f"data/{property_key}/{property_key}_nightly_pulled_overrides.csv")
            if override_path.exists():
                override_df = pd.read_csv(override_path)
                if 'currency' in override_df.columns:
                    match = override_df[(override_df['listing_id'] == listing_id) & (override_df['date'] == date)]
                    if not match.empty:
                        currency = match.iloc[0]['currency']
                        if pd.notna(currency) and currency:
                            return str(currency)
        except Exception:
            pass  # Fall through to default
    
    # Default to USD for all other properties
    return 'USD'

# Modify the caching and data loading functions
def load_and_prepare_data(property_selection, start_date, end_date):
    """Load and prepare data with proper initialization before caching"""
    # Always request full range from backend for accurate occupancy calculations
    from utils.date_manager import get_full_calculation_range
    full_start_date, full_end_date = get_full_calculation_range()
    print(f"[DEBUG] Calling backend with full_start_date={full_start_date}, full_end_date={full_end_date}")
    # Load initial data with full 2-year range
    generated_df = backend_interface.trigger_rate_generation(
        property_selection=property_selection,
        start_date=full_start_date,
        end_date=full_end_date
    )
    # Debug: Print shape and date range before filtering
    if generated_df is not None and not generated_df.empty:
        print(f"[DEBUG] Backend returned {len(generated_df)} rows, covering dates: {generated_df['Date'].min()} to {generated_df['Date'].max()}")
        
        # Debug: Print date column type and unique values before filtering
        print(f"[DEBUG] Date column type before filtering: {type(generated_df[COL_DATE].iloc[0])}")
        print(f"[DEBUG] Unique dates before filtering: {sorted(generated_df[COL_DATE].unique())[:10]}...")  # Show first 10
        print(f"[DEBUG] start_date type: {type(start_date)}, end_date type: {type(end_date)}")
        
        # Restore filtering to only show user-selected dates
        generated_df[COL_DATE] = pd.to_datetime(generated_df[COL_DATE])
        filtered_df = generated_df[
            (generated_df[COL_DATE].dt.date >= start_date) & 
            (generated_df[COL_DATE].dt.date <= end_date)
        ]
        filtered_df[COL_DATE] = filtered_df[COL_DATE].dt.strftime('%Y-%m-%d')
        print(f"[DEBUG] After filtering: {len(filtered_df)} rows, covering dates: {filtered_df[COL_DATE].min()} to {filtered_df[COL_DATE].max()}")
        print(f"[DEBUG] Unique dates after filtering: {sorted(filtered_df[COL_DATE].unique())[:10]}...")
        # Additional debug: show first 5 rows and unique flag/occ values
        print("[DEBUG] First 5 rows after filtering:")
        print(filtered_df[[COL_DATE, 'listing_id', 'listing_name', 'Flag', 'Occ% (Curr)']].head())
        print(f"[DEBUG] Unique Flag values: {filtered_df['Flag'].unique()}")
        print(f"[DEBUG] Unique Occ% (Curr) values: {filtered_df['Occ% (Curr)'].unique()}")
        generated_df = filtered_df
        
        # Check if backend already provides live rates data
        backend_has_live_rates = COL_LIVE_RATE in generated_df.columns and COL_MIN_STAY in generated_df.columns
        
        # Process live rates only if backend doesn't provide them
        all_live_rates_dfs = []
        if not backend_has_live_rates:
            for prop_name in property_selection:
                live_df = process_live_rates(prop_name)
                if live_df is not None:
                    all_live_rates_dfs.append(live_df)
        
        # Merge live rates only if we have them and backend doesn't provide them
        if all_live_rates_dfs and not backend_has_live_rates:
            combined_live_rates_df = pd.concat(all_live_rates_dfs, ignore_index=True)
            if not pd.api.types.is_string_dtype(generated_df[COL_DATE]):
                generated_df[COL_DATE] = pd.to_datetime(generated_df[COL_DATE]).dt.strftime('%Y-%m-%d')
            
            merged_df = pd.merge(
                generated_df,
                combined_live_rates_df,
                left_on=[COL_LISTING_ID, COL_DATE],
                right_on=['listing_id', 'date'],
                how='left',
                suffixes=('', '_live')
            )
            
            # Ensure proper column names
            # Backend now provides 'Live Rate $' and 'Min Stay' directly, but handle legacy format too
            if 'price' in merged_df.columns:
                merged_df.rename(columns={'price': COL_LIVE_RATE}, inplace=True)
            if COL_LIVE_RATE not in merged_df.columns:
                merged_df[COL_LIVE_RATE] = 0.0
            if COL_SUGGESTED not in merged_df.columns and 'Suggested' in merged_df.columns:
                merged_df.rename(columns={'Suggested': COL_SUGGESTED}, inplace=True)
            if 'min_stay' in merged_df.columns:
                merged_df.rename(columns={'min_stay': COL_MIN_STAY}, inplace=True)
            if COL_MIN_STAY not in merged_df.columns:
                merged_df[COL_MIN_STAY] = 1  # Default minimum stay of 1
        else:
            # Backend provides live rates data or no live rates files found
            merged_df = generated_df.copy()
            if COL_LIVE_RATE not in merged_df.columns:
                merged_df[COL_LIVE_RATE] = 0.0
            if COL_MIN_STAY not in merged_df.columns:
                merged_df[COL_MIN_STAY] = 1  # Default minimum stay of 1
        
        # Initialize editable price based on current toggle state
        toggle_value = st.session_state.get('rate_source_toggle', 'Use Live Rate')
        source_col = COL_LIVE_RATE if toggle_value == 'Use Live Rate' else COL_SUGGESTED
        merged_df[COL_EDITABLE_PRICE_SRC] = pd.to_numeric(merged_df[source_col], errors='coerce').fillna(0.0)
        
        # Initialize editable min stay with current min stay values
        merged_df[COL_EDITABLE_MIN_STAY_SRC] = pd.to_numeric(merged_df[COL_MIN_STAY], errors='coerce').fillna(1)
        
        # Calculate all derived columns
        merged_df = calculate_derived_columns(merged_df)
        
        return merged_df
    
    return None

def process_live_rates(property_name):
    """Load live rates for a property (no caching to ensure fresh data)"""
    live_rates_filename = f"{property_name}_nightly_pulled_overrides.csv"
    live_rates_path = Path("data") / property_name / live_rates_filename
    if live_rates_path.exists():
        try:
            return pd.read_csv(
                live_rates_path,
                usecols=['listing_id', 'date', 'price', 'min_stay'],
                dtype={'listing_id': str, 'date': str, 'price': float, 'min_stay': 'Int64'}
            )
        except Exception as e:
            st.warning(f"Could not load live rates for {property_name}: {e}")
    return None

def calculate_derived_columns(df):
    """Calculate derived columns for the dataframe"""
    if df is None or df.empty:
        return df
        
    df = df.copy()
    
    # Add Day of Week if not present
    if COL_DAY_OF_WEEK not in df.columns:
        df[COL_DAY_OF_WEEK] = pd.to_datetime(df[COL_DATE]).dt.strftime('%A')
    
    # Calculate Delta if not present
    if COL_DELTA not in df.columns:
        if COL_LIVE_RATE in df.columns and COL_SUGGESTED in df.columns:
            live_rate = pd.to_numeric(df[COL_LIVE_RATE], errors='coerce').fillna(0.0)
            suggested = pd.to_numeric(df[COL_SUGGESTED], errors='coerce')
            df[COL_DELTA] = np.where(
                live_rate != 0,
                ((suggested - live_rate) / live_rate) * 100,
                np.nan
            )
        else:
            df[COL_DELTA] = np.nan
    
    # Initialize Editable Price based on current toggle state
    if COL_EDITABLE_PRICE_SRC not in df.columns:
        toggle_value = st.session_state.get('rate_source_toggle', 'Use Live Rate')
        source_col = COL_LIVE_RATE if toggle_value == 'Use Live Rate' else COL_SUGGESTED
        if source_col in df.columns:
            df[COL_EDITABLE_PRICE_SRC] = pd.to_numeric(df[source_col], errors='coerce').fillna(0.0)
        else:
            df[COL_EDITABLE_PRICE_SRC] = 0.0
            
    return df

def initialize_session_state():
    """Initialize all session state variables"""
    if 'base_data' not in st.session_state:
        st.session_state.base_data = None
    if 'filtered_data' not in st.session_state:
        st.session_state.filtered_data = None
    if 'display_data' not in st.session_state:
        st.session_state.display_data = None
    if 'filter_state' not in st.session_state:
        st.session_state.filter_state = {}
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    
    # Clear properties config cache to ensure fresh rules are loaded
    if hasattr(st, 'cache_data'):
        st.cache_data.clear()
    


def update_filtered_data():
    """Update filtered data - simplified since filtering is now handled by the grid"""
    if st.session_state.base_data is not None:
        st.session_state.filtered_data = st.session_state.base_data.copy()

def on_filter_change():
    """Callback for filter changes - no longer needed since filtering is handled by the grid"""
    pass

# Initialize session state
initialize_session_state()

# --- Main App Structure ---
st.write("Configure parameters and generate rates to begin the review process.")

config_area = st.container()
results_area = st.container()

# --- Configuration Area ---
with config_area:
    st.subheader("1. Configure Rate Generation")
    
    # Use cached function to get properties
    available_properties = backend_interface.get_available_properties()
    property_display_names = backend_interface.get_property_display_names()
    if not available_properties:
        st.error("Could not load property list from configuration. Please check config/properties.yaml")
        st.stop()
    
    # Layout for selections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Property Selection (FR1)
        current_selected_properties = st.multiselect(
            label="Select Property/Unit Pools:",
            options=available_properties,
            default=st.session_state.selected_properties, # Use session state for persistence
            format_func=lambda x: property_display_names.get(x, x),
            key='prop_select' # Assign key for potential callbacks if needed later
        )
    
    with col2:
        # Start Date Selection (FR1) - allow full range from config so dates after Dec 31 are selectable
        from utils.date_manager import get_full_calculation_range
        _range_start, _range_end = get_full_calculation_range()
        current_start_date = st.date_input(
            label="Start Date:",
            value=st.session_state.start_date,
            min_value=_range_start,
            max_value=_range_end,
            key='start_date_input'
        )
    
    with col3:
        # End Date Selection (FR1)
        current_end_date = st.date_input(
            label="End Date:",
            value=st.session_state.end_date,
            min_value=_range_start,
            max_value=_range_end,
            key='end_date_input'
        )
    
    # Data timestamps will be shown in the Auto-Refresh Scheduler section
    
    # Only update session state and generate when button is clicked
    if st.button("Generate Rates", key='generate_button', type="primary"):
        if not current_selected_properties:
            st.warning("Please select at least one property.")
            st.session_state.generate_clicked = False
        elif current_start_date > current_end_date:
            st.warning("Start Date cannot be after End Date.")
            st.session_state.generate_clicked = False
        else:
            st.session_state.selected_properties = current_selected_properties
            st.session_state.start_date = current_start_date
            st.session_state.end_date = current_end_date
            st.session_state.generate_clicked = True
            st.session_state.generated_rates_df = None
            st.session_state.edited_rates_df = None
            st.session_state.results_are_displayed = False
            st.session_state.editable_rate_initialized = False
            rerun()
    # If any selection changes and generate_clicked is True, clear results
    if (current_selected_properties != st.session_state.selected_properties or
        current_start_date != st.session_state.start_date or
        current_end_date != st.session_state.end_date):
        st.session_state.generate_clicked = False
        st.session_state.results_are_displayed = False
        st.session_state.generated_rates_df = None
        st.session_state.edited_rates_df = None
    
    # Data Management Section - Combined into one operation
    st.markdown("### 📊 Data Management")
    
    # Show last refresh time if available
    if st.session_state.last_refresh_time:
        st.info(f"📅 Last data refresh: {st.session_state.last_refresh_time}")
    
    # Add helpful explanation
    st.info("💡 **Need fresh data?** This will update both pricing and property data:")
    
    # Single combined button
    st.markdown("**🔄 Refresh All Data**")
    st.markdown("*Downloads fresh pricing data for all properties, then updates property data for selected properties*")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Refresh All Data", key='refresh_all_data_button', 
                    help="Downloads fresh pricing data for all properties, then updates property data for selected properties",
                    type="primary"):
            if not current_selected_properties:
                st.warning("⚠️ Please select at least one property first.")
            else:
                st.session_state.refresh_all_data_clicked = True
                st.session_state.refresh_status = f"Starting data refresh: pricing for all properties, property data for {len(current_selected_properties)} selected properties..."
                rerun()
    
    # Show what data will be updated
    st.markdown("**📋 Data that will be updated:**")
    st.markdown("• **📈 Current Pricing:** Latest rate overrides and changes from PriceLabs (ALL properties)")
    st.markdown("• **📊 Property Data:** Daily occupancy, booking patterns, and availability (selected properties only)")
    # Display current date ranges from centralized config
    from utils.date_manager import get_nightly_pull_range, get_bulk_processing_range
    pricing_start, pricing_end = get_nightly_pull_range()
    property_start, property_end = get_bulk_processing_range()
    st.caption(f"📅 Pricing data range: {pricing_start.strftime('%Y-%m-%d')} to {pricing_end.strftime('%Y-%m-%d')}")
    st.caption(f"📅 Property data range: {property_start.strftime('%Y-%m-%d')} to {property_end.strftime('%Y-%m-%d')}")
    
    # Show refresh status if any refresh operation is in progress
    if st.session_state.refresh_nightly_clicked or st.session_state.refresh_property_clicked or st.session_state.refresh_all_data_clicked:
        with st.spinner(st.session_state.refresh_status):
            try:
                if st.session_state.refresh_nightly_clicked:
                    # Run nightly_pull.py for a 2-year range
                    import subprocess
                    import sys
                    from datetime import datetime
                    from utils.date_manager import get_nightly_pull_range
                    
                    # Use centralized date management
                    start_date_obj, end_date_obj = get_nightly_pull_range()
                    start_date = start_date_obj.strftime('%Y-%m-%d')
                    end_date = end_date_obj.strftime('%Y-%m-%d')
                    
                    result = subprocess.run([
                        sys.executable, "rates/pull/nightly_pull.py", start_date, end_date
                    ], 
                    capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
                    if result.returncode == 0:
                        st.success("✅ **Current pricing data downloaded successfully!**")
                        st.info("📈 Updated: Current pricing overrides and rate changes from PriceLabs")
                        st.info(f"📅 Pricing data range: {start_date} to {end_date}")
                        st.session_state.refresh_nightly_clicked = False
                        st.session_state.refresh_status = ""
                        st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # Clear cache and reset data state to force reload
                        st.cache_data.clear()
                        st.session_state.data_loaded = False
                        st.session_state.base_data = None
                        st.session_state.filtered_data = None
                        st.session_state.generated_rates_df = None
                        st.session_state.edited_rates_df = None
                        st.session_state.results_are_displayed = False
                        # Clear rules adjuster results when data is refreshed
                        st.session_state.rules_applied = False
                        st.session_state.rules_results = None
                        st.session_state.show_rules_results = False
                        rerun()
                    else:
                        st.error(f"❌ **Failed to download current pricing data**")
                        st.error(f"Error details: {result.stderr}")
                        st.info("💡 Try again in a few minutes, or contact support if the problem persists.")
                        st.session_state.refresh_nightly_clicked = False
                        st.session_state.refresh_status = ""
                
                elif st.session_state.refresh_property_clicked:
                    # Run generate_pl_daily_comprehensive.py for selected properties
                    import subprocess
                    import sys
                    from datetime import datetime
                    
                    success_count = 0
                    total_count = len(current_selected_properties)
                    
                    # Add progress indication
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, property_key in enumerate(current_selected_properties):
                        status_text.text(f"🔄 Updating {property_key}... ({i+1}/{total_count})")
                        
                        # Use centralized date management for property data
                        from utils.date_manager import get_bulk_processing_range
                        bulk_start_obj, bulk_end_obj = get_bulk_processing_range()
                        start_date_str = bulk_start_obj.strftime('%Y-%m-%d')
                        end_date_str = bulk_end_obj.strftime('%Y-%m-%d')
                        
                        result = subprocess.run([
                            sys.executable, "scripts/generate_pl_daily_comprehensive.py", 
                            property_key, start_date_str, end_date_str
                        ], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
                        
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            st.error(f"❌ Error updating {property_key}: {result.stderr}")
                        
                        # Update progress
                        progress_bar.progress((i + 1) / total_count)
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    
                    if success_count == total_count:
                        st.success(f"✅ **Property data updated successfully!** ({success_count}/{total_count} properties)")
                        st.info("📊 Updated: Daily occupancy, booking patterns, and availability data")
                        st.info(f"📅 Data range: {start_date_str} to {end_date_str}")
                    else:
                        st.warning(f"⚠️ **Partial update completed** - {success_count}/{total_count} properties updated successfully.")
                        st.error(f"❌ Some properties failed to update. Check the error messages above.")
                    
                    st.session_state.refresh_property_clicked = False
                    st.session_state.refresh_status = ""
                    st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Clear cache and reset data state to force reload
                    st.cache_data.clear()
                    st.session_state.data_loaded = False
                    st.session_state.base_data = None
                    st.session_state.filtered_data = None
                    st.session_state.generated_rates_df = None
                    st.session_state.edited_rates_df = None
                    st.session_state.results_are_displayed = False
                    # Clear rules adjuster results when data is refreshed
                    st.session_state.rules_applied = False
                    st.session_state.rules_results = None
                    st.session_state.show_rules_results = False
                    rerun()
                
                elif st.session_state.refresh_all_data_clicked:
                    # Simplified refresh: Always run nightly pull + property data generation
                    import subprocess
                    import sys
                    from datetime import datetime, timedelta
                    import os
                    import time
                    
                    st.info("🔄 **Refresh All Data:** Starting comprehensive data refresh...")
                    print(f"\n{'='*80}")
                    print(f"🔄 REFRESH ALL DATA - STARTING AT {datetime.now()}")
                    print(f"{'='*80}")
                    print(f"🏠 Properties selected: {current_selected_properties}")
                    
                    # Step 1: Always download current pricing data for ALL properties
                    st.info("🔄 **Step 1/3:** Downloading current pricing data for all properties...")
                    print("🔄 REFRESH ALL DATA: Step 1/3 - Downloading current pricing data for all properties...")
                    
                    # Get current pricing data using centralized date management
                    from utils.date_manager import get_nightly_pull_range
                    start_date_obj, end_date_obj = get_nightly_pull_range()
                    start_date = start_date_obj.strftime('%Y-%m-%d')
                    end_date = end_date_obj.strftime('%Y-%m-%d')
                    
                    st.info(f"📅 **Date range for pricing data:** {start_date} to {end_date}")
                    print(f"📅 REFRESH ALL DATA: Date range for pricing data: {start_date} to {end_date}")
                    
                    st.info("🔄 **Running nightly_pull.py script...**")
                    print("🔄 REFRESH ALL DATA: Running nightly_pull.py script...")
                    result = subprocess.run([
                        sys.executable, "rates/pull/nightly_pull.py", start_date, end_date
                    ], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
                    
                    st.info(f"📊 **nightly_pull.py exit code:** {result.returncode}")
                    print(f"📊 REFRESH ALL DATA: nightly_pull.py exit code: {result.returncode}")
                    
                    if result.stdout:
                        st.info(f"📤 **nightly_pull.py output:** {result.stdout[:500]}...")
                        print(f"📤 REFRESH ALL DATA: nightly_pull.py stdout: {result.stdout[:500]}...")
                    if result.stderr:
                        st.info(f"⚠️ **nightly_pull.py errors:** {result.stderr[:500]}...")
                        print(f"⚠️ REFRESH ALL DATA: nightly_pull.py stderr: {result.stderr[:500]}...")
                    
                    if result.returncode == 0:
                        st.success("✅ **Step 1 Complete:** Current pricing data downloaded successfully for all properties!")
                        print("✅ REFRESH ALL DATA: Step 1 Complete - Current pricing data downloaded successfully for all properties!")
                    else:
                        st.error(f"❌ **Step 1 Failed:** Error downloading pricing data: {result.stderr}")
                        print(f"❌ REFRESH ALL DATA: Step 1 Failed - Error downloading pricing data: {result.stderr}")
                        st.session_state.refresh_all_data_clicked = False
                        st.session_state.refresh_status = ""
                        st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        rerun()
                    
                    # Step 2: Wait for API rate limit reset before updating property data
                    st.info("⏳ **Step 2/3:** Waiting for API rate limit reset (1 minute)...")
                    st.info("🔄 This prevents rate limiting conflicts between nightly pull and PL daily generation")
                    print("⏳ REFRESH ALL DATA: Step 2/3 - Waiting for API rate limit reset (1 minute)...")
                    print("🔄 REFRESH ALL DATA: This prevents rate limiting conflicts between nightly pull and PL daily generation")
                    
                    # Wait 1 minute (60 seconds) for API rate limit reset
                    for remaining in range(60, 0, -15):  # Countdown every 15 seconds
                        minutes = remaining // 60
                        seconds = remaining % 60
                        st.info(f"⏳ **Waiting:** {minutes:02d}:{seconds:02d} remaining...")
                        print(f"⏳ REFRESH ALL DATA: Waiting: {minutes:02d}:{seconds:02d} remaining...")
                        time.sleep(15)  # Wait 15 seconds
                    
                    st.info("✅ **Rate limit reset complete!** Starting property data update...")
                    print("✅ REFRESH ALL DATA: Rate limit reset complete! Starting property data update...")
                    
                    # Step 3: Update property data for SELECTED properties only using bulk processing range
                    from utils.date_manager import get_bulk_processing_range
                    bulk_start_date_obj, bulk_end_date_obj = get_bulk_processing_range()
                    bulk_start_date = bulk_start_date_obj.strftime('%Y-%m-%d')
                    bulk_end_date = bulk_end_date_obj.strftime('%Y-%m-%d')
                    
                    st.info("🔄 **Step 3/3:** Updating property data for selected properties...")
                    print("🔄 REFRESH ALL DATA: Step 3/3 - Updating property data for selected properties...")
                    st.info(f"🏠 **Processing {len(current_selected_properties)} properties:** {current_selected_properties}")
                    st.info(f"📅 **Property data range:** {bulk_start_date} to {bulk_end_date}")
                    print(f"🏠 REFRESH ALL DATA: Processing {len(current_selected_properties)} properties: {current_selected_properties}")
                    print(f"📅 REFRESH ALL DATA: Property data range: {bulk_start_date} to {bulk_end_date}")
                    
                    success_count = 0
                    total_count = len(current_selected_properties)
                    
                    # Enhanced progress indication with status text
                    pl_progress_bar = st.progress(0)
                    pl_status_text = st.empty()
                    
                    for i, property_key in enumerate(current_selected_properties):
                        # Update progress
                        progress = (i + 1) / total_count
                        pl_progress_bar.progress(progress)
                        pl_status_text.text(f"Generating PL daily data for {property_key} ({i+1}/{total_count})")
                        
                        st.info(f"🔍 **DEBUG:** Starting property {property_key} ({i+1}/{total_count})")
                        st.info(f"📅 **DEBUG:** Date range for {property_key}: {bulk_start_date} to {bulk_end_date}")
                        print(f"🔍 SMART REFRESH: Starting property {property_key} ({i+1}/{total_count})")
                        print(f"📅 SMART REFRESH: Date range for {property_key}: {bulk_start_date} to {bulk_end_date}")
                        
                        # Use bulk processing date range for selected property
                        st.info(f"🚀 **DEBUG:** Running command: python generate_pl_daily_comprehensive.py {property_key} {bulk_start_date} {bulk_end_date}")
                        print(f"🚀 SMART REFRESH: Running command: python generate_pl_daily_comprehensive.py {property_key} {bulk_start_date} {bulk_end_date}")
                        
                        result = subprocess.run([
                            sys.executable, "scripts/generate_pl_daily_comprehensive.py", 
                            property_key, bulk_start_date, bulk_end_date
                        ], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
                        
                        st.info(f"📊 **DEBUG:** {property_key} script exit code: {result.returncode}")
                        print(f"📊 SMART REFRESH: {property_key} script exit code: {result.returncode}")
                        
                        if result.stdout:
                            st.info(f"📤 **DEBUG:** {property_key} stdout: {result.stdout[:1000]}...")
                            print(f"📤 SMART REFRESH: {property_key} stdout: {result.stdout[:1000]}...")
                        if result.stderr:
                            st.info(f"⚠️ **DEBUG:** {property_key} stderr: {result.stderr[:1000]}...")
                            print(f"⚠️ SMART REFRESH: {property_key} stderr: {result.stderr[:1000]}...")
                        
                        # Parse the PL daily script output to extract success/failure details
                        successful_listings = []
                        failed_listings = []
                        total_listings = 0
                        
                        if result.stdout:
                            # Extract listing processing results from the script output
                            lines = result.stdout.split('\n')
                            for line in lines:
                                if "Successfully processed:" in line:
                                    # Extract count from "✅ Successfully processed: X"
                                    try:
                                        count_part = line.split("Successfully processed:")[1].strip()
                                        successful_count = int(count_part)
                                    except:
                                        successful_count = 0
                                elif "Failed to process:" in line:
                                    # Extract count from "❌ Failed to process: X"
                                    try:
                                        count_part = line.split("Failed to process:")[1].strip()
                                        failed_count = int(count_part)
                                    except:
                                        failed_count = 0
                                elif "Total listings in config:" in line:
                                    # Extract total from "🏠 Total listings in config: X"
                                    try:
                                        count_part = line.split("Total listings in config:")[1].strip()
                                        total_listings = int(count_part)
                                    except:
                                        total_listings = 0
                                elif "Successful listings:" in line:
                                    # Extract successful listing names
                                    try:
                                        listings_part = line.split("Successful listings:")[1].strip()
                                        successful_listings = [name.strip() for name in listings_part.split(',')]
                                    except:
                                        successful_listings = []
                                elif "Failed listings:" in line:
                                    # Extract failed listing names
                                    try:
                                        listings_part = line.split("Failed listings:")[1].strip()
                                        failed_listings = [name.strip() for name in listings_part.split(',')]
                                    except:
                                        failed_listings = []
                        
                        if result.returncode == 0:
                            success_count += 1
                            
                            # Show detailed success/failure breakdown
                            if total_listings > 0:
                                if failed_listings:
                                    st.warning(f"⚠️ **Partial Success:** {property_key} completed with {len(successful_listings)}/{total_listings} listings processed")
                                    st.success(f"✅ **Successful listings:** {', '.join(successful_listings)}")
                                    st.error(f"❌ **Failed listings:** {', '.join(failed_listings)}")
                                    st.info("💡 **Next Steps:** Some listings failed. Check API access or try refreshing individual listings.")
                                else:
                                    st.success(f"✅ **Complete Success:** {property_key} completed with all {len(successful_listings)}/{total_listings} listings processed")
                                    st.success(f"✅ **All listings successful:** {', '.join(successful_listings)}")
                            else:
                                st.success(f"✅ **DEBUG:** {property_key} completed successfully!")
                            
                            print(f"✅ TERMINAL DEBUG: {property_key} completed successfully!")
                        else:
                            st.error(f"❌ **DEBUG:** {property_key} failed with exit code {result.returncode}")
                            print(f"❌ TERMINAL DEBUG: {property_key} failed with exit code {result.returncode}")
                        
                        # Progress is already updated in the loop above
                    
                    # Clear progress indicators
                    pl_progress_bar.empty()
                    pl_status_text.empty()
                    
                    if success_count == total_count:
                        st.success(f"✅ **Complete Data Refresh Successful!**")
                        st.info("📈 Updated: Current pricing overrides and rate changes from PriceLabs")
                        st.info("📊 Updated: Daily occupancy, booking patterns, and availability data")
                        st.info(f"📅 Data range: {bulk_start_date} to {bulk_end_date}")
                        st.info(f"🏠 Properties updated: {success_count}/{total_count}")
                        print(f"✅ TERMINAL DEBUG: Complete Data Refresh Successful! {success_count}/{total_count} properties updated")
                        
                        # DEBUG: Show what files were created and their sizes
                        st.info("🔍 **DEBUG:** Checking created files...")
                        print("🔍 TERMINAL DEBUG: Checking created files...")
                        for prop in current_selected_properties:
                            pl_daily_path = f"data/{prop}/pl_daily_{prop}.csv"
                            nightly_path = f"data/{prop}/{prop}_nightly_pulled_overrides.csv"
                            
                            if os.path.exists(pl_daily_path):
                                size = os.path.getsize(pl_daily_path)
                                st.info(f"📁 **DEBUG:** {pl_daily_path} - {size} bytes")
                                print(f"📁 TERMINAL DEBUG: {pl_daily_path} - {size} bytes")
                                
                                # Count lines in the file
                                try:
                                    with open(pl_daily_path, 'r') as f:
                                        line_count = sum(1 for line in f)
                                    st.info(f"📊 **DEBUG:** {pl_daily_path} - {line_count} lines")
                                    print(f"📊 TERMINAL DEBUG: {pl_daily_path} - {line_count} lines")
                                except Exception as e:
                                    st.info(f"⚠️ **DEBUG:** Could not count lines in {pl_daily_path}: {e}")
                                    print(f"⚠️ TERMINAL DEBUG: Could not count lines in {pl_daily_path}: {e}")
                            else:
                                st.warning(f"❌ **DEBUG:** {pl_daily_path} does not exist!")
                                print(f"❌ TERMINAL DEBUG: {pl_daily_path} does not exist!")
                                
                            if os.path.exists(nightly_path):
                                size = os.path.getsize(nightly_path)
                                st.info(f"📁 **DEBUG:** {nightly_path} - {size} bytes")
                                print(f"📁 TERMINAL DEBUG: {nightly_path} - {size} bytes")
                            else:
                                st.warning(f"❌ **DEBUG:** {nightly_path} does not exist!")
                                print(f"⚠️ TERMINAL DEBUG: {nightly_path} does not exist!")
                    else:
                        st.warning(f"⚠️ **Partial update completed** - {success_count}/{total_count} properties updated successfully.")
                        st.error(f"❌ Some properties failed to update. Check the error messages above.")
                        print(f"⚠️ SMART REFRESH: Partial update completed - {success_count}/{total_count} properties updated successfully")
                        print(f"❌ SMART REFRESH: Some properties failed to update. Check the error messages above")
                    
                    st.session_state.refresh_all_data_clicked = False
                    st.session_state.refresh_status = ""
                    st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    print(f"{'='*80}")
                    print(f"🔄 SMART REFRESH ALL DATA - COMPLETED AT {datetime.now()}")
                    print(f"✅ Final status: {success_count}/{total_count} properties updated successfully")
                    print(f"{'='*80}\n")
                    
                    # Clear cache and reset data state to force reload
                    st.cache_data.clear()
                    st.session_state.data_loaded = False
                    st.session_state.base_data = None
                    st.session_state.filtered_data = None
                    st.session_state.generated_rates_df = None
                    st.session_state.edited_rates_df = None
                    st.session_state.results_are_displayed = False
                    # Clear rules adjuster results when data is refreshed
                    st.session_state.rules_applied = False
                    st.session_state.rules_results = None
                    st.session_state.show_rules_results = False
                    rerun()
                    
            except Exception as e:
                st.error(f"❌ **An unexpected error occurred during the data refresh**")
                st.error(f"Error details: {str(e)}")
                st.info("💡 Please try again, or contact support if the problem persists.")
                st.session_state.refresh_nightly_clicked = False
                st.session_state.refresh_property_clicked = False
                st.session_state.refresh_all_data_clicked = False
                st.session_state.refresh_status = ""
    
    # Auto-Refresh Scheduler Section
    st.subheader("🔔 Auto-Refresh Scheduler")

    try:
        scheduler_status = get_scheduler_status()
        deployed_no_backend = scheduler_status.get('deployed_no_backend', False)

        # Handle single-property refresh: nightly_pull (all) then pl_daily (this property); use actual scripts, no test scripts
        if st.session_state.single_property_refresh_clicked and st.session_state.single_property_refresh_key:
            prop_key = st.session_state.single_property_refresh_key
            start_date, end_date = get_dynamic_date_range()
            with st.spinner(f"Nightly pull (all), then pl_daily for **{prop_key}**…"):
                nightly = subprocess.run(
                    [sys.executable, "rates/pull/nightly_pull.py", start_date, end_date],
                    cwd=str(_project_root),
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if nightly.returncode != 0:
                    err = (nightly.stderr or nightly.stdout or "").strip()[:500]
                    st.error(f"❌ Nightly pull failed. Check logs.")
                    if err:
                        st.code(err)
                    send_custom_alert(
                        f"⚠️ *Pricing Tool – single-property refresh failed*\n*Step:* nightly_pull\n*Property:* {prop_key}\n*Time:* {datetime.datetime.now().isoformat()}\n*Error:* {err}"
                    )
                    st.session_state.single_property_refresh_clicked = False
                    st.session_state.single_property_refresh_key = None
                    rerun()
                pl_daily = subprocess.run(
                    [sys.executable, "scripts/generate_pl_daily_comprehensive.py", prop_key],
                    cwd=str(_project_root),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if pl_daily.returncode != 0:
                    err = (pl_daily.stderr or pl_daily.stdout or "").strip()[:500]
                    st.error(f"❌ pl_daily failed for **{prop_key}**. Check logs.")
                    if err:
                        st.code(err)
                    send_custom_alert(
                        f"⚠️ *Pricing Tool – single-property refresh failed*\n*Step:* pl_daily\n*Property:* {prop_key}\n*Time:* {datetime.datetime.now().isoformat()}\n*Error:* {err}"
                    )
                    st.session_state.single_property_refresh_clicked = False
                    st.session_state.single_property_refresh_key = None
                    rerun()
            st.success(f"✅ **{prop_key}** refreshed (nightly pull + pl_daily). Alert sent to Slack if configured.")
            send_custom_alert(
                f"✅ *Pricing Tool – single-property refresh completed*\n*Property:* {prop_key}\n*Time:* {datetime.datetime.now().isoformat()}"
            )
            st.session_state.single_property_refresh_clicked = False
            st.session_state.single_property_refresh_key = None
            rerun()

        if deployed_no_backend:
            # Deployed without persistent backend (e.g. Streamlit Cloud): no daemon; refresh runs when app is opened at scheduled times or via buttons
            st.markdown("""
            <div style="background-color: #2d3748; padding: 12px; border-radius: 5px; border-left: 4px solid #63b3ed;">
                <strong>☁️ Cloud deployment</strong><br>
                <small>Refresh runs automatically when you open the app around scheduled times (1:00 & 13:22 Lisbon), or use <strong>Run refresh now</strong> / <strong>Refresh this property</strong> below.</small><br>
                <small>💡 <em>Data is stored only for this session; run a refresh after opening the app to load data and generate rates.</em></small>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("---")
            # Data file timestamps and last refresh
            pl_daily_time = None
            nightly_time = None
            if current_selected_properties:
                prop = current_selected_properties[0]
                pl_daily_path = _project_root / "data" / prop / f"pl_daily_{prop}.csv"
                nightly_path = _project_root / "data" / prop / f"{prop}_nightly_pulled_overrides.csv"
                if pl_daily_path.exists():
                    pl_daily_time = os.path.getmtime(str(pl_daily_path))
                if nightly_path.exists():
                    nightly_time = os.path.getmtime(str(nightly_path))
            import datetime as dt
            data_col1, data_col2 = st.columns(2)
            with data_col1:
                st.markdown("**📊 Data Files Status:**")
                if current_selected_properties and pl_daily_time:
                    st.markdown(f"• **Property Data:** {dt.datetime.fromtimestamp(pl_daily_time).strftime('%b %d, %H:%M')}")
                else:
                    st.markdown("• **Property Data:** Not found")
                if current_selected_properties and nightly_time:
                    st.markdown(f"• **Current Pricing:** {dt.datetime.fromtimestamp(nightly_time).strftime('%b %d, %H:%M')}")
                else:
                    st.markdown("• **Current Pricing:** Not found")
            with data_col2:
                st.markdown("**⏰ Status:**")
                if scheduler_status.get('next_refresh'):
                    st.markdown(f"• **Next refresh:** {scheduler_status['next_refresh'].strftime('%b %d, %H:%M')} (open app around then to run)")
                if scheduler_status.get('last_refresh'):
                    last_line = f"• **Last refresh (scheduled or manual):** {scheduler_status['last_refresh'].strftime('%b %d, %H:%M')}"
                    outcome = scheduler_status.get('last_run_outcome')
                    if outcome:
                        if outcome.get('success'):
                            n = outcome.get('properties_refreshed')
                            last_line += f" — ✅ Success ({n} properties)" if n is not None else " — ✅ Success"
                        else:
                            step = outcome.get('error_step') or 'refresh'
                            last_line += f" — ❌ Failed: {step}"
                    st.markdown(last_line)
                else:
                    st.markdown("• **Last refresh (scheduled or manual):** —")
            _est = estimate_api_call_volume()
            if _est.get("total_properties", 0) > 0:
                _min = _est.get("estimated_duration_minutes", 0)
                _n = _est.get("total_api_calls", 0)
                st.caption(f"Estimated: ~{max(1, int(round(_min)))} min ({_est['total_properties']} properties, {_n} API calls)")
            if st.button("🔄 Run refresh now", key="scheduler_manual_refresh_cloud", help="Run nightly pull and PL daily generation now (may take several minutes)"):
                st.session_state.scheduler_refresh_clicked = True
                rerun()
            st.caption("Runs nightly pull then pl_daily for all properties.")
            _one_prop_list = backend_interface.get_available_properties() or []
            if _one_prop_list:
                st.markdown("**Refresh one property:** nightly pull (all) → pl_daily (selected)")
                _col_sel, _col_btn = st.columns([2, 1])
                with _col_sel:
                    _sel_prop = st.selectbox("Property", _one_prop_list, key="single_prop_cloud", label_visibility="collapsed")
                with _col_btn:
                    if st.button("Refresh this property", key="single_property_refresh_cloud", help="Run nightly_pull for all, then pl_daily for selected property; sends Slack alert"):
                        st.session_state.single_property_refresh_clicked = True
                        st.session_state.single_property_refresh_key = _sel_prop
                        rerun()
        else:
            # Local: full scheduler UI with daemon and enable checkbox
            current_lisbon_time = get_lisbon_time()
            config = load_scheduler_config()
            enabled = config.get('enabled', False)

            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    if enabled:
                        st.markdown("""
                        <div style="background-color: #1f4e1f; padding: 10px; border-radius: 5px; border-left: 4px solid #4CAF50;">
                            <strong>🟢 Auto-Refresh Active</strong><br>
                            <small>Data refreshes automatically at 1 AM & 1 PM Lisbon time</small>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="background-color: #4e1f1f; padding: 10px; border-radius: 5px; border-left: 4px solid #f44336;">
                            <strong>🔴 Auto-Refresh Inactive</strong><br>
                            <small>Manual refresh required</small>
                        </div>
                        """, unsafe_allow_html=True)
                with col2:
                    new_enabled = st.checkbox(
                        "Enable Auto-Refresh",
                        value=enabled,
                        key="scheduler_enabled_checkbox",
                        help="Toggle automatic data refresh"
                    )
                if new_enabled != enabled:
                    config['enabled'] = new_enabled
                    if save_scheduler_config(config):
                        st.success("✅ Settings saved")
                        rerun()
                    else:
                        st.error("❌ Save failed")

            st.markdown("---")
            pl_daily_time = None
            nightly_time = None
            if current_selected_properties:
                prop = current_selected_properties[0]
                pl_daily_path = _project_root / "data" / prop / f"pl_daily_{prop}.csv"
                nightly_path = _project_root / "data" / prop / f"{prop}_nightly_pulled_overrides.csv"
                if pl_daily_path.exists():
                    pl_daily_time = os.path.getmtime(str(pl_daily_path))
                if nightly_path.exists():
                    nightly_time = os.path.getmtime(str(nightly_path))
            import datetime as dt
            try:
                data_col1, data_col2 = st.columns(2)
                with data_col1:
                    st.markdown("**📊 Data Files Status:**")
                    if current_selected_properties and pl_daily_time:
                        st.markdown(f"• **Property Data:** {dt.datetime.fromtimestamp(pl_daily_time).strftime('%b %d, %H:%M')}")
                    else:
                        st.markdown("• **Property Data:** Not found")
                    if current_selected_properties and nightly_time:
                        st.markdown(f"• **Current Pricing:** {dt.datetime.fromtimestamp(nightly_time).strftime('%b %d, %H:%M')}")
                    else:
                        st.markdown("• **Current Pricing:** Not found")
                with data_col2:
                    st.markdown("**⏰ Scheduler Status:**")
                    if enabled:
                        if scheduler_status.get('next_refresh'):
                            next_refresh = scheduler_status['next_refresh']
                            st.markdown(f"• **Next refresh:** {next_refresh.strftime('%b %d, %H:%M')}")
                            _now = get_lisbon_time()
                            _sec = (next_refresh - _now).total_seconds()
                            if _sec > 3600:
                                st.markdown(f"  _in ~{int(round(_sec / 3600))} h_")
                            elif _sec > 60:
                                st.markdown(f"  _in ~{int(round(_sec / 60))} min_")
                            elif _sec > 0:
                                st.markdown("  _in under 1 min_")
                        if scheduler_status.get('last_refresh'):
                            last_refresh = scheduler_status['last_refresh']
                            last_line = f"• **Last refresh (scheduled or manual):** {last_refresh.strftime('%b %d, %H:%M')}"
                            outcome = scheduler_status.get('last_run_outcome')
                            if outcome:
                                if outcome.get('success'):
                                    n = outcome.get('properties_refreshed')
                                    last_line += f" — ✅ Success ({n} properties)" if n is not None else " — ✅ Success"
                                else:
                                    step = outcome.get('error_step') or 'refresh'
                                    last_line += f" — ❌ Failed: {step}"
                            st.markdown(last_line)
                        st.markdown(f"• **Current Time:** {current_lisbon_time.strftime('%b %d, %H:%M')} (Lisbon)")
                    else:
                        st.markdown("• **Status:** Auto-refresh disabled")
                        st.markdown(f"• **Current Time:** {current_lisbon_time.strftime('%b %d, %H:%M')} (Lisbon)")
            except Exception as e:
                st.error(f"❌ Error displaying scheduler status: {e}")
                st.info("💡 Please check scheduler configuration and try again.")

            _est = estimate_api_call_volume()
            if _est.get("total_properties", 0) > 0:
                _min = _est.get("estimated_duration_minutes", 0)
                _n = _est.get("total_api_calls", 0)
                st.caption(f"Estimated: ~{max(1, int(round(_min)))} min ({_est['total_properties']} properties, {_n} API calls)")
            if st.button("🔄 Run refresh now", key="scheduler_manual_refresh_local", help="Run nightly pull and PL daily generation now"):
                st.session_state.scheduler_refresh_clicked = True
                rerun()
            st.caption("Runs nightly pull then pl_daily for all properties.")
            _one_prop_list = backend_interface.get_available_properties() or []
            if _one_prop_list:
                st.markdown("**Refresh one property:** nightly pull (all) → pl_daily (selected)")
                _col_sel, _col_btn = st.columns([2, 1])
                with _col_sel:
                    _sel_prop = st.selectbox("Property", _one_prop_list, key="single_prop_local", label_visibility="collapsed")
                with _col_btn:
                    if st.button("Refresh this property", key="single_property_refresh_local", help="Run nightly_pull for all, then pl_daily for selected property; sends Slack alert"):
                        st.session_state.single_property_refresh_clicked = True
                        st.session_state.single_property_refresh_key = _sel_prop
                        rerun()

            # Check if it's time to refresh and run if needed (local and cloud)
            # In cloud: run in background thread and show progress. In local: daemon may run it; app can also run it and show progress.
        _enabled = scheduler_status.get("enabled", False)
        _time_to_refresh = _enabled and is_time_to_refresh()
        _cloud_refresh_thread = st.session_state.get("cloud_scheduled_refresh_thread")
        _cloud_thread_alive = _cloud_refresh_thread is not None and _cloud_refresh_thread.is_alive()
        if _time_to_refresh or (deployed_no_backend and _cloud_thread_alive):
            try:
                from utils.progress_tracker import get_scheduler_status
                progress_status = get_scheduler_status()
                refresh_active = progress_status.get("refresh_active", False)

                # Cloud: scheduled refresh runs in background thread; show progress until done
                if deployed_no_backend:
                    # Check thread-finished first so we clear banner even if status file is stale (refresh_active still True)
                    if _cloud_refresh_thread is not None and not _cloud_refresh_thread.is_alive():
                        # Thread finished; show result from outcome file
                        _outcome_file = _project_root / "logs" / "last_scheduler_run_outcome.json"
                        if _outcome_file.exists():
                            try:
                                with open(_outcome_file) as _f:
                                    _res = json.load(_f)
                                if _res.get("success"):
                                    _n = _res.get("properties_refreshed")
                                    st.success(f"✅ Scheduled refresh completed ({_n} properties)." if _n is not None else "✅ Scheduled refresh completed.")
                                    st.cache_data.clear()
                                    st.session_state.data_loaded = False
                                    st.session_state.base_data = None
                                    st.session_state.filtered_data = None
                                    st.session_state.generated_rates_df = None
                                    st.session_state.edited_rates_df = None
                                    st.session_state.results_are_displayed = False
                                else:
                                    st.error(f"❌ Scheduled refresh failed: {_res.get('error_step', 'refresh')}")
                            except Exception:
                                st.success("✅ Scheduled refresh completed.")
                        else:
                            st.success("✅ Scheduled refresh completed.")
                        st.session_state.cloud_scheduled_refresh_thread = None
                        st.rerun()
                    elif _cloud_thread_alive or refresh_active:
                        st.info("🔄 **Scheduled refresh is running...**")
                        try:
                            progress = get_refresh_progress()
                            step = progress.get("current_step") or "—"
                            op = progress.get("current_operation") or "—"
                            pct = progress.get("total_progress", 0)
                            n_done = progress.get("properties_completed", 0)
                            n_tot = progress.get("properties_total", 0)
                            step_label = "Step 1: Nightly pull" if step == "nightly_pull" else ("Step 2: PL daily" if step == "pl_daily_generation" else step)
                            st.markdown(f"**{step_label}** — {pct:.0f}%")
                            if op and op != "—":
                                st.caption(op)
                            if n_tot > 0:
                                st.caption(f"Properties: {n_done}/{n_tot} completed")
                        except Exception:
                            st.caption("Running…")
                        time.sleep(2)
                        st.rerun()
                    elif _time_to_refresh:
                        # Start scheduled refresh in background (cloud)
                        st.info("🔄 **Starting scheduled refresh…** (runs in background)")
                        def _run_scheduled():
                            run_scheduled_refresh()
                        _t = threading.Thread(target=_run_scheduled)
                        _t.start()
                        st.session_state.cloud_scheduled_refresh_thread = _t
                        time.sleep(1)
                        st.rerun()
                else:
                    # Local: check if daemon already started a refresh, else run in foreground
                    if progress_status.get("refresh_active", False):
                        st.info("🔄 **Scheduled refresh is running...**")
                        with st.container():
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                total_progress = progress_status.get("total_progress", 0)
                                st.progress(total_progress / 100)
                                st.write(f"**Overall Progress:** {total_progress:.1f}%")
                                current_step = progress_status.get("current_step", "Unknown")
                                step_progress = progress_status.get("step_progress", 0)
                                current_operation = progress_status.get("current_operation", "")
                                st.write(f"**Current Step:** {current_step.replace('_', ' ').title()}")
                                st.write(f"**Step Progress:** {step_progress:.1f}%")
                                if current_operation:
                                    st.write(f"**Operation:** {current_operation}")
                            with col2:
                                properties_total = progress_status.get("properties_total", 0)
                                properties_completed = progress_status.get("properties_completed", 0)
                                properties_failed = progress_status.get("properties_failed", 0)
                                st.write(f"**Properties:** {properties_completed}/{properties_total} completed")
                                if properties_failed > 0:
                                    st.write(f"**Failed:** {properties_failed}")
                                api_calls_made = progress_status.get("api_calls_made", 0)
                                api_calls_total = progress_status.get("api_calls_total", 0)
                                if api_calls_total > 0:
                                    st.write(f"**API Calls:** {api_calls_made}/{api_calls_total}")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.info("🔄 Starting scheduled refresh...")
                        success = run_scheduled_refresh()
                        if success:
                            st.success("✅ Refresh completed successfully!")
                            st.cache_data.clear()
                            st.session_state.data_loaded = False
                            st.session_state.base_data = None
                            st.session_state.filtered_data = None
                            st.session_state.generated_rates_df = None
                            st.session_state.edited_rates_df = None
                        else:
                            st.error("❌ Refresh failed. Check logs for details.")
                        
            except Exception as e:
                st.error(f"❌ Error checking refresh progress: {e}")
                st.info("🔄 Running scheduled refresh...")
                try:
                    success = run_scheduled_refresh()
                    if success:
                        st.success("✅ Refresh completed successfully!")
                        st.cache_data.clear()
                        st.session_state.data_loaded = False
                        st.session_state.base_data = None
                        st.session_state.filtered_data = None
                        st.session_state.generated_rates_df = None
                        st.session_state.edited_rates_df = None
                    else:
                        st.error("❌ Refresh failed. Check logs for details.")
                except Exception as e2:
                    st.error(f"❌ Refresh error: {e2}")
                st.session_state.results_are_displayed = False
                if deployed_no_backend:
                    st.session_state.cloud_scheduled_refresh_thread = None
                rerun()
        
        # Handle manual refresh (with live progress: run in background, poll status file)
        if st.session_state.scheduler_refresh_clicked:
            _result_file = _project_root / "logs" / "last_manual_refresh_result.json"
            if not st.session_state.manual_refresh_in_progress:
                # First run after click: start refresh in background thread
                st.session_state.manual_refresh_in_progress = True
                def _run_refresh_and_save():
                    try:
                        ok = run_scheduled_refresh()
                        _result_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(_result_file, "w") as f:
                            json.dump({"success": ok, "error": None}, f)
                    except Exception as e:
                        _result_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(_result_file, "w") as f:
                            json.dump({"success": False, "error": str(e)}, f)
                t = threading.Thread(target=_run_refresh_and_save)
                t.start()
                st.session_state.manual_refresh_thread = t
                st.rerun()
            t = st.session_state.manual_refresh_thread
            if t and t.is_alive():
                # Show live progress from scheduler status file
                st.info("🔄 **Full refresh:** nightly pull → generate pl_daily for all properties. This may take 10–15 minutes.")
                try:
                    progress = get_refresh_progress()
                    step = progress.get("current_step") or "—"
                    op = progress.get("current_operation") or "—"
                    pct = progress.get("total_progress", 0)
                    n_done = progress.get("properties_completed", 0)
                    n_tot = progress.get("properties_total", 0)
                    step_label = "Step 1: Nightly pull" if step == "nightly_pull" else ("Step 2: PL daily" if step == "pl_daily_generation" else step)
                    st.markdown(f"**{step_label}** — {pct:.0f}%")
                    if op and op != "—":
                        st.caption(op)
                    if n_tot > 0:
                        st.caption(f"Properties: {n_done}/{n_tot} completed")
                except Exception:
                    st.caption("Running… (progress will update in a few seconds)")
                time.sleep(2)
                st.rerun()
            # Thread finished: show result and clear state
            success = False
            err_msg = None
            if _result_file.exists():
                try:
                    with open(_result_file) as f:
                        res = json.load(f)
                    success = res.get("success", False)
                    err_msg = res.get("error")
                except Exception:
                    pass
            if success:
                progress = get_refresh_progress()
                props_done = progress.get("properties_completed") or progress.get("properties_total") or 0
                summary = f" ({props_done} properties refreshed)" if props_done else ""
                st.success(f"✅ Manual refresh completed successfully!{summary}")
                st.cache_data.clear()
                st.session_state.data_loaded = False
                st.session_state.base_data = None
                st.session_state.filtered_data = None
                st.session_state.generated_rates_df = None
                st.session_state.edited_rates_df = None
                st.session_state.results_are_displayed = False
            else:
                st.error(f"❌ Manual scheduled refresh failed. {err_msg or 'Check logs for details.'}")
            st.session_state.scheduler_refresh_clicked = False
            st.session_state.scheduler_status = ""
            st.session_state.manual_refresh_in_progress = False
            st.session_state.manual_refresh_thread = None
            st.rerun()
    
    except Exception as e:
        st.error(f"❌ Error loading scheduler: {e}")
        st.info("💡 Please check scheduler configuration and try again.")
    
    st.markdown("---")

# --- Results Area ---
with results_area:
    if st.session_state.generate_clicked:
        st.subheader("2. Review & Manage Rates")

        # Add view toggle - moved outside the data loading condition
        view_mode = st.radio(
            "Select View Mode:",
            ["Table View", "Calendar View"],
            horizontal=True,
            key="view_mode"
        )

        if view_mode == "Table View":
            if not st.session_state.data_loaded:
                try:
                    with st.spinner("Loading data..."):
                        st.info("🔄 Generating rates for selected properties and date range...")
                        st.info("📊 Using full 2-year dataset for accurate occupancy calculations")
                        
                        # Load and prepare data with caching
                        prepared_df = load_and_prepare_data(
                            st.session_state.selected_properties,
                            st.session_state.start_date,
                            st.session_state.end_date
                        )
                        
                        if prepared_df is not None:
                            # Store in session state
                            st.session_state.base_data = prepared_df.copy()
                            
                            # Store full dataset for calculations if available
                            if hasattr(st, 'session_state') and hasattr(st.session_state, 'full_dataset_df'):
                                st.session_state.full_dataset_for_calculations = st.session_state.full_dataset_df.copy()
                                st.info(f"✅ Full dataset loaded: {len(st.session_state.full_dataset_for_calculations)} entries available for calculations")
                            
                            st.session_state.data_loaded = True
                            st.session_state.initial_load_complete = False  # Reset for new data load
                            update_filtered_data()
                            st.success("Data loaded successfully!")
                            rerun()  # Force a rerun to ensure proper grid initialization
                        else:
                            st.error("No data was generated. Please check your parameters.")
                    
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.exception(e)
                    st.session_state.data_loaded = False
                    st.session_state.base_data = None

            # Display the table view if data is loaded
            if st.session_state.data_loaded and st.session_state.base_data is not None:
                # Rate source toggle
                st.radio(
                    "Set Initial Value for Editable Rate $",
                    options=['Use Live Rate', 'Use Suggested Rate'],
                    key='rate_source_toggle',
                    horizontal=True,
                    on_change=update_editable_rate_source
                )
                
                # Add immediate update if toggle changes
                if 'previous_toggle_value' not in st.session_state:
                    st.session_state.previous_toggle_value = st.session_state.rate_source_toggle
                elif st.session_state.previous_toggle_value != st.session_state.rate_source_toggle:
                    update_editable_rate_source()
                    st.session_state.previous_toggle_value = st.session_state.rate_source_toggle
                
                # Rules Adjuster for Table View (Main Area)
                if st.session_state.base_data is not None and st.session_state.selected_properties:
                    with st.expander("🔧 Rules Adjuster", expanded=False):
                        st.markdown("*Apply property-specific rules to live rates*")
                        
                        # Show available rules for selected properties
                        properties_config = backend_interface.load_properties_config()
                        if properties_config:
                            st.markdown("**📋 Available Rules:**")
                            for prop_key in st.session_state.selected_properties:
                                if prop_key in properties_config:
                                    prop_config = properties_config[prop_key]
                                    adjustment_rules = prop_config.get('adjustment_rules', [])
                                    if adjustment_rules:
                                        st.markdown(f"**{prop_config.get('name', prop_key)}:**")
                                        for rule in adjustment_rules:
                                            rule_name = rule.get('name', 'Unnamed Rule')
                                            target_weekday = rule.get('target_weekday')
                                            weekday_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][target_weekday] if target_weekday is not None else 'Unknown'
                                            st.markdown(f"  • {rule_name} (applies to {weekday_name}s)")
                                    else:
                                        st.markdown(f"**{prop_config.get('name', prop_key)}:** No rules configured")
                        
                        # Rule application button
                        if st.button("🔧 Apply Rules", key="table_apply_rules_button"):
                            st.session_state.rules_applied = True
                            st.session_state.rules_results = apply_rules_to_live_rates(
                                st.session_state.base_data, 
                                st.session_state.selected_properties
                            )
                            rerun()
                        
                        # Reset button
                        if st.button("🔄 Reset", key="table_reset_rules_button"):
                            st.session_state.rules_applied = False
                            st.session_state.rules_results = None
                            st.session_state.show_rules_results = False
                            rerun()
                        
                        # Cache refresh button
                        if st.button("🔄 Refresh Rules Cache", key="table_refresh_cache_button"):
                            st.cache_data.clear()
                            st.success("✅ Rules cache cleared! Rules should now be up to date.")
                            rerun()
                        
                        # Show results if rules were applied
                        if st.session_state.rules_applied and st.session_state.rules_results:
                            results = st.session_state.rules_results
                            
                            if results['success']:
                                st.success(f"✅ {results['message']}")
                                
                                if results['adjusted_rates']:
                                    st.markdown("**📊 Results:**")
                                    
                                    # Show summary of total vs. actual changes
                                    total_rates = len(results['adjusted_rates'])
                                    actual_changes = results.get('actual_changes', 0)
                                    st.info(f"📈 **Summary:** {total_rates} total rule applications, {actual_changes} with actual changes")
                                    
                                    # Add toggle for showing only changes
                                    show_only_changes = st.checkbox("Show only rows with changes", value=True)
                                    
                                    # Create comprehensive display for main area
                                    display_data = []
                                    for rate in results['adjusted_rates']:
                                        if show_only_changes and not rate.get('change_applied', False):
                                            continue
                                        # Determine adjustment type
                                        rate_change = f"${rate['original_price']:.0f} → ${rate['new_price']:.0f}" if rate['new_price'] != rate['original_price'] else "-"
                                        min_stay_change = f"{rate['original_min_stay']} → {rate['new_min_stay']}" if rate['new_min_stay'] != rate['original_min_stay'] else "-"
                                        
                                        display_data.append({
                                            'Day': f"{rate['date']} ({datetime.datetime.strptime(rate['date'], '%Y-%m-%d').strftime('%Y')})",
                                            'Listing': rate['listing_name'],
                                            'Rate Adjustment': rate_change,
                                            'Min Stay Adjustment': min_stay_change,
                                            'Rules': rate['rule_applied'],
                                            'Reason': rate.get('reason', '')
                                        })
                                    
                                    # Display comprehensive results
                                    st.dataframe(
                                        pd.DataFrame(display_data),
                                        hide_index=True,
                                        column_config={
                                            'Day': st.column_config.TextColumn("Day"),
                                            'Listing': st.column_config.TextColumn("Listing"),
                                            'Rate Adjustment': st.column_config.TextColumn("Rate Adjustment"),
                                            'Min Stay Adjustment': st.column_config.TextColumn("Min Stay Adjustment"),
                                            'Rules': st.column_config.TextColumn("Rules"),
                                            'Reason': st.column_config.TextColumn("Reason")
                                        },
                                        use_container_width=True
                                    )
                                    
                                    # Push button
                                    if st.button("🚀 Push to PriceLabs", key="table_push_button", type="primary"):
                                        # Prepare rates for pushing - exclude no-change rows and merge per (listing, date)
                                        rates_to_push = {}
                                        for rate in results['adjusted_rates']:
                                            # Only push real changes
                                            if not rate.get('change_applied', False):
                                                continue
                                            if rate['new_price'] == rate['original_price'] and rate['new_min_stay'] == rate['original_min_stay']:
                                                continue

                                            listing_id = rate['listing_id']
                                            date_key_push = rate['date']
                                            
                                            # Initialize structure if needed
                                            if listing_id not in rates_to_push:
                                                rates_to_push[listing_id] = {}
                                            if date_key_push not in rates_to_push[listing_id]:
                                                # Get currency for this listing
                                                currency = get_currency_for_listing(listing_id, rate.get('property'), date_key_push)
                                                # Start with original values
                                                rates_to_push[listing_id][date_key_push] = {
                                                    "date": date_key_push,
                                                    "price": rate['original_price'],
                                                    "min_stay": rate['original_min_stay'],
                                                    "currency": currency
                                                }
                                            
                                            # Merge changes - only update fields that actually changed
                                            if rate['new_price'] != rate['original_price']:
                                                rates_to_push[listing_id][date_key_push]["price"] = rate['new_price']
                                            if rate['new_min_stay'] != rate['original_min_stay']:
                                                rates_to_push[listing_id][date_key_push]["min_stay"] = rate['new_min_stay']
                                            # Currency is already set above, no need to update it

                                        # Convert inner dicts to lists for the batch API
                                        for lid in list(rates_to_push.keys()):
                                            rates_to_push[lid] = list(rates_to_push[lid].values())
                                        
                                        # Count what's actually being pushed
                                        total_rates_to_push = sum(len(rates) for rates in rates_to_push.values())
                                        
                                        # Push to PriceLabs
                                        try:
                                            push_results = push_rates_batch(rates_to_push)
                                            success_count = sum(1 for result in push_results.values() if result["success"])
                                            total_count = len(push_results)
                                            
                                            if success_count == total_count:
                                                st.success(f"✅ Pushed {total_rates_to_push} rates with actual changes")
                                            elif success_count > 0:
                                                st.warning(f"⚠️ {success_count}/{total_count} successful")
                                            else:
                                                st.error(f"❌ Push failed")
                                                
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                                else:
                                    st.info("ℹ️ No rates adjusted")
                            else:
                                st.error(f"❌ {results['message']}")
                        else:
                            st.info("💡 Generate rates to use Rules Adjuster")
                
                # Use the base data directly - filtering is handled by the grid itself
                display_df = st.session_state.base_data

                # Reset index and use listing IDs
                display_df = display_df.reset_index(drop=True)
                display_df[COL_LISTING_ID] = display_df[COL_LISTING_ID]  # Use listing_id as the ID

                # Ensure Select column exists and initialize with previous selections
                if COL_SELECT not in display_df.columns:
                    display_df[COL_SELECT] = False
                if st.session_state.checkbox_selections:
                    display_df[COL_SELECT] = display_df[COL_LISTING_ID].map(st.session_state.checkbox_selections).fillna(False)

                # Configure grid options
                gb = GridOptionsBuilder.from_dataframe(display_df)
                
                # Configure selection mode first
                gb.configure_selection(
                    selection_mode='multiple',
                    use_checkbox=True,
                    pre_selected_rows=[]
                )

                # Configure default options
                gb.configure_grid_options(
                    domLayout='autoHeight',
                    enableCellTextSelection=True,
                    ensureDomOrder=True,
                    defaultColDef={
                        'resizable': True,
                        'sortable': True,
                        'filter': True,
                        'cellStyle': {'textAlign': 'left'},
                        'headerClass': 'ag-header-cell-left',
                        'suppressMovable': True,
                        'lockPosition': True
                    }
                )

                # Initialize columnDefs as a list
                column_defs = []

                # Configure columns in exact order
                column_order = [
                    COL_SELECT,
                    COL_LISTING_ID,
                    COL_DATE,
                    COL_PROPERTY,
                    COL_LISTING_NAME,
                    COL_TIER,
                    COL_DAY_OF_WEEK,
                    COL_MIN_STAY,
                    COL_EDITABLE_MIN_STAY,
                    COL_OCC_CURR,
                    COL_LIVE_RATE,
                    COL_SUGGESTED,
                    COL_DELTA,
                    COL_EDITABLE_PRICE,
                    COL_FLAG,
                    COL_STATUS
                ]

                # Configure columns in exact order
                for idx, col in enumerate(column_order):
                    if col in display_df.columns:
                        base_config = {
                            'field': col,
                            'resizable': True,
                            'cellStyle': {'textAlign': 'left'},
                            'headerClass': 'ag-header-cell-left',
                            'headerName': COLUMN_DISPLAY_NAMES.get(col, col),
                            'hide': False,
                            'suppressMovable': True,
                            'lockPosition': True,
                            'sortIndex': idx
                        }
                        
                        if col == COL_DATE:
                            column_defs.append({
                                **base_config,
                                'type': ["dateColumnFilter", "customDateTimeFormat"],
                                'custom_format_string': 'YYYY-MM-DD',
                                'width': 120,
                                'editable': False
                            })
                        elif col in [COL_LIVE_RATE, COL_SUGGESTED, COL_EDITABLE_PRICE]:
                            column_defs.append({
                                **base_config,
                                'type': ["numericColumn", "numberColumnFilter", "customNumericFormat"],
                                'precision': 2,
                                'valueFormatter': "'$' + value.toFixed(2)",
                                'editable': (col == COL_EDITABLE_PRICE),
                                'width': 130
                            })
                        elif col == COL_DELTA:
                            column_defs.append({
                                **base_config,
                                'type': ["numericColumn", "numberColumnFilter", "customNumericFormat"],
                                'precision': 1,
                                'valueFormatter': "value.toFixed(1) + '%'",
                                'width': 100,
                                'editable': False
                            })
                        elif col == COL_OCC_CURR:
                            column_defs.append({
                                **base_config,
                                'type': ["numericColumn", "numberColumnFilter", "customNumericFormat"],
                                'precision': 1,
                                'valueFormatter': "value.toFixed(1) + '%'",
                                'width': 110,
                                'editable': False
                            })
                        elif col == COL_SELECT:
                            column_defs.append({
                                **base_config,
                                'width': 50,
                                'headerCheckboxSelection': True,
                                'headerCheckboxSelectionFilteredOnly': True,
                                'checkboxSelection': True,
                                'pinned': 'left',
                                'editable': False
                            })
                        elif col == COL_LISTING_ID:
                            column_defs.append({
                                **base_config,
                                'width': 200,
                                'type': ["textColumn"],
                                'editable': False,
                                'hide': False
                            })
                        elif col in [COL_PROPERTY, COL_LISTING_NAME]:
                            column_defs.append({
                                **base_config,
                                'width': 200,
                                'editable': False
                            })
                        elif col == COL_MIN_STAY:
                            column_defs.append({
                                **base_config,
                                'type': ["numericColumn", "numberColumnFilter", "customNumericFormat"],
                                'precision': 0,
                                'width': 100,
                                'editable': False
                            })
                        elif col == COL_EDITABLE_MIN_STAY:
                            column_defs.append({
                                **base_config,
                                'type': ["numericColumn", "numberColumnFilter", "customNumericFormat"],
                                'precision': 0,
                                'width': 120,
                                'editable': True
                            })
                        else:
                            column_defs.append({
                                **base_config,
                                'width': 120,
                                'editable': False
                            })

                grid_options = gb.build()
                grid_options['columnDefs'] = column_defs

                # Create grid with filtered columns and proper configuration
                grid_key = 'main_grid_' + ('initial' if not st.session_state.initial_load_complete else 'updated')
                grid_response = AgGrid(
                    display_df,
                    gridOptions=grid_options,
                    update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.SELECTION_CHANGED,
                    fit_columns_on_grid_load=True,
                    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                    reload_data=not st.session_state.initial_load_complete,  # Force reload on initial load
                    key=grid_key,
                    columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
                    allow_unsafe_jscode=True,
                    custom_css={
                        ".ag-header-cell-label": {"justify-content": "left !important"},
                        ".ag-cell": {"padding-left": "5px !important"}
                    }
                )

                # Update initial load flag after grid is created
                if not st.session_state.initial_load_complete:
                    st.session_state.initial_load_complete = True
                    rerun()  # Force one rerun after initial load to ensure proper rendering

                # Add custom CSS for column alignment
                st.markdown("""
                <style>
                .ag-theme-streamlit .ag-header-cell-label {
                    justify-content: left !important;
                }
                .ag-theme-streamlit .ag-cell {
                    padding-left: 5px !important;
                }
                </style>
                """, unsafe_allow_html=True)
                # Process selected rows
                selected_df = pd.DataFrame(grid_response.selected_rows) if hasattr(grid_response, 'selected_rows') else pd.DataFrame()
                
                # Extract IDs from selected DataFrame
                selected_ids = selected_df[COL_LISTING_ID].tolist() if not selected_df.empty else []
                
                # Update session state with current selections
                previous_selected_ids = st.session_state.get('selected_ids', set())
                st.session_state.selected_ids = set(selected_ids)
                # If the selection changed, clear the updated_selected_df
                if set(selected_ids) != previous_selected_ids and 'updated_selected_df' in st.session_state:
                    del st.session_state.updated_selected_df
                
                # Clear updated_selected_df if no rows are selected
                if not selected_df.empty:
                    st.info(f"Selected {len(selected_ids)} rows")
                    
                    # If we have updated data and all selected IDs are in it, use it
                    if 'updated_selected_df' in st.session_state:
                        updated_df = st.session_state.updated_selected_df
                        if all(id in updated_df[COL_LISTING_ID].values for id in selected_ids):
                            display_df = updated_df[updated_df[COL_LISTING_ID].isin(selected_ids)]
                        else:
                            display_df = selected_df
                            if 'updated_selected_df' in st.session_state:
                                del st.session_state.updated_selected_df
                    else:
                        display_df = selected_df
                    
                    # Use the same columns as the main table, but exclude the Select column
                    display_columns = [col for col in DEFAULT_VISIBLE_COLUMNS if col != COL_SELECT]
                    # Ensure listing_id is included in valid columns
                    if COL_LISTING_ID not in display_columns:
                        display_columns.append(COL_LISTING_ID)
                    valid_columns = [col for col in display_columns if col in display_df.columns]
                    
                    # Add a unique key for the data editor based on selections
                    editor_key = f"selection_editor_{','.join(sorted(selected_ids))}"
                    
                    # Define editable columns
                    editable_columns = [COL_EDITABLE_PRICE_SRC, COL_EDITABLE_MIN_STAY]
                    
                    # Ensure listing_id is in the DataFrame
                    if COL_LISTING_ID not in display_df.columns:
                        display_df[COL_LISTING_ID] = display_df.index
                    
                    edited_selection = st.data_editor(
                        display_df[valid_columns],
                        hide_index=True,
                        disabled=[col for col in valid_columns if col not in editable_columns],
                        key=editor_key,
                        column_config={
                            COL_LISTING_ID: st.column_config.TextColumn("ID", disabled=True),
                            COL_DATE: st.column_config.DateColumn("Date", format="YYYY-MM-DD", disabled=True),
                            COL_PROPERTY: st.column_config.TextColumn("Property", disabled=True),
                            COL_LISTING_NAME: st.column_config.TextColumn("Listing Name", disabled=True),
                            COL_TIER: st.column_config.TextColumn("Tier", disabled=True),
                            COL_DAY_OF_WEEK: st.column_config.TextColumn("Day", disabled=True),
                            COL_MIN_STAY: st.column_config.NumberColumn("Min Stay", format="%.0f", required=True, min_value=1, disabled=True),
                            COL_EDITABLE_MIN_STAY: st.column_config.NumberColumn("Editable Min Stay", format="%.0f", required=True, min_value=1),
                            COL_OCC_CURR: st.column_config.NumberColumn("Occ% Current", format="%.1f%%", disabled=True),
                            COL_LIVE_RATE: st.column_config.NumberColumn("Live Rate $", format="$%.2f", disabled=True),
                            COL_SUGGESTED: st.column_config.NumberColumn("Suggested Rate $", format="$%.2f", disabled=True),
                            COL_DELTA: st.column_config.NumberColumn("Delta %", format="%.1f%%", disabled=True),
                            COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn("Editable Rate $", format="$%.2f", required=True, min_value=0),
                            COL_FLAG: st.column_config.TextColumn("Flag", disabled=True),
                            COL_STATUS: st.column_config.TextColumn("Status", disabled=True)
                        }
                    )

            else:
                if 'updated_selected_df' in st.session_state:
                    del st.session_state.updated_selected_df

            # Actions
            st.markdown("---")
            st.markdown("#### Actions")
            action_cols = st.columns(3)
            
            # Pass the current dataframe to action handlers
            current_action_df = st.session_state.base_data
            
            with action_cols[0]:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Adjust Selected", key='adjust_button'):
                        if current_action_df is not None:
                            selected_for_action = pd.DataFrame(grid_response.selected_rows)
                            if not selected_for_action.empty:
                                st.session_state.show_adjust_modal = True
                            else:
                                st.warning("No rows selected for adjustment.")
                        else:
                            st.warning("No data available to adjust.")
                with col2:
                    if st.button("Adjust LOS", key='adjust_los_button'):
                        if current_action_df is not None:
                            selected_for_action = pd.DataFrame(grid_response.selected_rows)
                            if not selected_for_action.empty:
                                st.session_state.show_los_adjust_modal = True
                            else:
                                st.warning("No rows selected for LOS adjustment.")
                        else:
                            st.warning("No data available to adjust.")

            # Add enhanced adjustment modal
            if st.session_state.show_adjust_modal:
                # Use updated data if available, otherwise use original selection
                if 'updated_selected_df' in st.session_state:
                    # Filter updated data to only include currently selected rows
                    selected_ids = set(selected_df[COL_LISTING_ID].values)
                    updated_df = st.session_state.updated_selected_df
                    selected_for_preview = updated_df[updated_df[COL_LISTING_ID].isin(selected_ids)]
                else:
                    selected_for_preview = pd.DataFrame(grid_response.selected_rows)
                
                if not selected_for_preview.empty:
                    st.subheader("Adjust Prices for Selected Rows")
                    st.write(f"**Selected {len(selected_for_preview)} rows**")
                    # Adjustment configuration
                    col1, col2 = st.columns(2)
                    with col1:
                        adjustment_type = st.selectbox(
                            "Adjustment Type:",
                            options=['percentage', 'value', 'set_value', 'batna', 'batna_plus', 'batna_plus_percent'],
                            format_func=lambda x: {
                                'percentage': 'Percentage (%)',
                                'value': 'Fixed Amount ($)',
                                'set_value': 'Set Specific Value ($)',
                                'batna': 'BATNA Rate',
                                'batna_plus': 'BATNA + Amount',
                                'batna_plus_percent': 'BATNA + x%'
                            }[x],
                            key="simple_adj_type"
                        )
                    with col2:
                        if adjustment_type == 'set_value':
                            # Use the current price of the first selected row as the default
                            try:
                                default_set_value = float(selected_for_preview.iloc[0][COL_EDITABLE_PRICE_SRC])
                            except Exception:
                                default_set_value = 0.0
                            amount = st.number_input(
                                "New Rate:",
                                min_value=0.0,
                                value=default_set_value,
                                step=10.0,
                                format="%.2f",
                                key="simple_adj_amount"
                            )
                        elif adjustment_type == 'batna_plus':
                            amount = st.number_input(
                                "Amount to Add to BATNA:",
                                min_value=0.0,
                                value=0.0,
                                step=1.0,
                                format="%.2f",
                                key="simple_adj_amount"
                            )
                        elif adjustment_type == 'batna_plus_percent':
                            amount = st.number_input(
                                "Percentage to Add to BATNA:",
                                min_value=0.0,
                                value=10.0,
                                step=1.0,
                                format="%.1f",
                                key="simple_adj_amount"
                            )
                        else:
                            amount = st.number_input(
                                "Amount:",
                                min_value=0.0,
                                value=10.0,
                                step=1.0,
                                format="%.2f" if adjustment_type == 'value' else "%.1f",
                                key="simple_adj_amount"
                            )
                    direction = None
                    if adjustment_type in ['percentage', 'value']:
                        direction = st.radio(
                            "Direction:",
                            options=['increase', 'decrease'],
                            format_func=lambda x: 'Increase (+)' if x == 'increase' else 'Decrease (-)',
                            horizontal=True,
                            key="simple_adj_direction"
                        )
                        actual_amount = amount if direction == 'increase' else -amount
                    elif adjustment_type in ['batna', 'batna_plus', 'batna_plus_percent']:
                        actual_amount = amount  # For BATNA types, amount is used as-is
                    else:
                        actual_amount = amount
                    # --- Preview (now outside the form, always live) ---
                    st.markdown("---")
                    st.write("**Preview of Adjustments:** (updates live as you change values)")
                    preview_data = []
                    for idx, row in selected_for_preview.iterrows():
                        current_price = float(row[COL_EDITABLE_PRICE_SRC])
                        if adjustment_type == 'set_value':
                            # If nonsense or invalid, use current price
                            try:
                                new_price = float(amount)
                                if new_price <= 0:
                                    new_price = current_price
                                new_price = round(new_price)
                            except Exception:
                                new_price = round(current_price)
                        elif adjustment_type == 'batna':
                            # Get BATNA value for this listing (date-aware)
                            listing_id = row.get(COL_LISTING_ID)
                            batna_value = backend_interface.get_batna_for_listing(listing_id, row.get(COL_DATE))
                            if batna_value is not None:
                                new_price = round(batna_value)
                            else:
                                new_price = round(current_price)  # Keep current if no BATNA found
                        elif adjustment_type == 'batna_plus':
                            # Get BATNA value and add amount
                            listing_id = row.get(COL_LISTING_ID)
                            batna_value = backend_interface.get_batna_for_listing(listing_id, row.get(COL_DATE))
                            if batna_value is not None:
                                new_price = round(batna_value + amount)
                            else:
                                new_price = round(current_price)  # Keep current if no BATNA found
                        elif adjustment_type == 'batna_plus_percent':
                            # Get BATNA value and add percentage of BATNA
                            listing_id = row.get(COL_LISTING_ID)
                            batna_value = backend_interface.get_batna_for_listing(listing_id, row.get(COL_DATE))
                            if batna_value is not None:
                                # Calculate percentage amount and add to BATNA
                                percent_amount = batna_value * (amount / 100)
                                new_price = round(batna_value + percent_amount)
                            else:
                                new_price = round(current_price)  # Keep current if no BATNA found
                        else:
                            new_price = round(apply_price_adjustment(current_price, adjustment_type, actual_amount))
                        preview_data.append({
                            'Listing Name': row[COL_LISTING_NAME],
                            'Date': row[COL_DATE],
                            'Current Price': current_price,
                            'New Price': new_price
                        })
                    st.dataframe(pd.DataFrame(preview_data))
                    # --- Form for Apply/Cancel only ---
                    with st.form(key="simple_adjustment_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            submit = st.form_submit_button("Apply Adjustment")
                        with col2:
                            cancel = st.form_submit_button("Cancel")
                        if submit:
                            updates = []
                            # Use updated data if available, otherwise use original selection
                            if 'updated_selected_df' in st.session_state:
                                working_df = st.session_state.updated_selected_df.copy()
                            else:
                                working_df = selected_df.copy()
                            
                            working_df[COL_EDITABLE_PRICE_SRC] = working_df[COL_EDITABLE_PRICE_SRC].astype(float)
                            price_updates = {}
                            
                            # Get the selected rows from the working dataframe
                            selected_ids = set(selected_df[COL_LISTING_ID].values)
                            rows_to_update = working_df[working_df[COL_LISTING_ID].isin(selected_ids)]
                            
                            for idx, row in rows_to_update.iterrows():
                                current_price = float(row[COL_EDITABLE_PRICE_SRC])
                                if adjustment_type == 'set_value':
                                    # If nonsense or invalid, use current price
                                    try:
                                        new_price = float(amount)
                                        if new_price <= 0:
                                            new_price = current_price
                                        new_price = round(new_price)
                                    except Exception:
                                        new_price = round(current_price)
                                elif adjustment_type == 'batna':
                                    # Get BATNA value for this listing (date-aware)
                                    listing_id = row.get(COL_LISTING_ID)
                                    batna_value = backend_interface.get_batna_for_listing(listing_id, row.get(COL_DATE))
                                    if batna_value is not None:
                                        new_price = round(batna_value)
                                    else:
                                        new_price = round(current_price)  # Keep current if no BATNA found
                                elif adjustment_type == 'batna_plus':
                                    # Get BATNA value and add amount
                                    listing_id = row.get(COL_LISTING_ID)
                                    batna_value = backend_interface.get_batna_for_listing(listing_id, row.get(COL_DATE))
                                    if batna_value is not None:
                                        new_price = round(batna_value + amount)
                                    else:
                                        new_price = round(current_price)  # Keep current if no BATNA found
                                elif adjustment_type == 'batna_plus_percent':
                                    # Get BATNA value and add percentage of BATNA
                                    listing_id = row.get(COL_LISTING_ID)
                                    batna_value = backend_interface.get_batna_for_listing(listing_id, row.get(COL_DATE))
                                    if batna_value is not None:
                                        # Calculate percentage amount and add to BATNA
                                        percent_amount = batna_value * (amount / 100)
                                        new_price = round(batna_value + percent_amount)
                                    else:
                                        new_price = round(current_price)  # Keep current if no BATNA found
                                else:
                                    new_price = round(apply_price_adjustment(current_price, adjustment_type, actual_amount))
                                rate_id = row.get('_id')
                                listing_id = row.get(COL_LISTING_ID)
                                date = row.get(COL_DATE)
                                key = (listing_id, date)
                                price_updates[key] = new_price
                                update_dict = {
                                    '_id': rate_id,
                                    'listing_id': listing_id,
                                    COL_DATE: date,
                                    COL_EDITABLE_PRICE_SRC: new_price,
                                    'Status': 'Adjusted'
                                }
                                updates.append(update_dict)
                            if backend_interface.update_rates(updates):
                                edited_selection = working_df.copy()
                                edited_selection[COL_EDITABLE_PRICE_SRC] = edited_selection[COL_EDITABLE_PRICE_SRC].astype(float)
                                for idx in edited_selection.index:
                                    listing_id = edited_selection.at[idx, COL_LISTING_ID]
                                    date = edited_selection.at[idx, COL_DATE]
                                    key = (listing_id, date)
                                    if key in price_updates:
                                        edited_selection.at[idx, COL_EDITABLE_PRICE_SRC] = price_updates[key]
                                st.session_state.updated_selected_df = edited_selection.copy()
                                update_filtered_data()
                                st.toast(f"{len(updates)} rate adjustment(s) applied.", icon="✏️")
                            else:
                                st.error("Failed to log adjustments.")
                            st.session_state.show_adjust_modal = False
                            rerun()
                        if cancel:
                            st.session_state.show_adjust_modal = False
                            rerun()

            # Add enhanced LOS adjustment modal
            if st.session_state.show_los_adjust_modal:
                # Use updated data if available, otherwise use original selection
                if 'updated_selected_df' in st.session_state:
                    # Filter updated data to only include currently selected rows
                    selected_ids = set(selected_df[COL_LISTING_ID].values)
                    updated_df = st.session_state.updated_selected_df
                    selected_for_preview = updated_df[updated_df[COL_LISTING_ID].isin(selected_ids)]
                else:
                    selected_for_preview = pd.DataFrame(grid_response.selected_rows)
                
                if not selected_for_preview.empty:
                    st.subheader("Adjust Min Stay for Selected Rows")
                    st.write(f"**Selected {len(selected_for_preview)} rows**")
                    
                    # LOS adjustment configuration
                    col1, col2 = st.columns(2)
                    with col1:
                        los_adjustment_type = st.selectbox(
                            "Adjustment Type:",
                            options=['increment', 'set_value'],
                            format_func=lambda x: {
                                'increment': 'Increment/Decrement',
                                'set_value': 'Set Specific Value'
                            }[x],
                            key="los_adj_type"
                        )
                    with col2:
                        if los_adjustment_type == 'set_value':
                            # Use the current min stay of the first selected row as the default
                            try:
                                default_set_value = int(selected_for_preview.iloc[0][COL_EDITABLE_MIN_STAY])
                            except Exception:
                                default_set_value = 1
                            los_amount = st.number_input(
                                "New Min Stay:",
                                min_value=1,
                                value=default_set_value,
                                step=1,
                                format="%d",
                                key="los_adj_amount"
                            )
                        else:
                            los_amount = st.number_input(
                                "Amount:",
                                min_value=1,
                                value=1,
                                step=1,
                                format="%d",
                                key="los_adj_amount"
                            )
                    
                    # Direction for increment adjustments
                    if los_adjustment_type == 'increment':
                        los_direction = st.radio(
                            "Direction:",
                            options=['increase', 'decrease'],
                            format_func=lambda x: 'Increase (+)' if x == 'increase' else 'Decrease (-)',
                            horizontal=True,
                            key="los_adj_direction"
                        )
                        actual_los_amount = los_amount if los_direction == 'increase' else -los_amount
                    else:
                        actual_los_amount = los_amount
                    
                    # --- Live Preview (outside the form, always live) ---
                    st.markdown("---")
                    st.write("**Preview of Min Stay Adjustments:** (updates live as you change values)")
                    los_preview_data = []
                    for idx, row in selected_for_preview.iterrows():
                        current_min_stay = int(row[COL_EDITABLE_MIN_STAY])
                        if los_adjustment_type == 'set_value':
                            new_min_stay = max(1, int(los_amount))
                        else:
                            new_min_stay = max(1, current_min_stay + actual_los_amount)
                        
                        los_preview_data.append({
                            'Listing Name': row[COL_LISTING_NAME],
                            'Date': row[COL_DATE],
                            'Current Min Stay': current_min_stay,
                            'New Min Stay': new_min_stay
                        })
                    
                    st.dataframe(
                        pd.DataFrame(los_preview_data),
                        column_config={
                            'Listing Name': st.column_config.TextColumn("Listing Name"),
                            'Date': st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                            'Current Min Stay': st.column_config.NumberColumn("Current Min Stay", format="%d"),
                            'New Min Stay': st.column_config.NumberColumn("New Min Stay", format="%d")
                        },
                        hide_index=True
                    )
                    
                    # --- Form for Apply/Cancel only ---
                    with st.form(key="los_adjustment_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            submit = st.form_submit_button("Apply Min Stay Adjustment")
                        with col2:
                            cancel = st.form_submit_button("Cancel")
                        
                        if submit:
                            updates = []
                            # Use updated data if available, otherwise use original selection
                            if 'updated_selected_df' in st.session_state:
                                working_df = st.session_state.updated_selected_df.copy()
                            else:
                                working_df = selected_df.copy()
                            
                            working_df[COL_EDITABLE_MIN_STAY] = working_df[COL_EDITABLE_MIN_STAY].astype(int)
                            los_updates = {}
                            
                            # Get the selected rows from the working dataframe
                            selected_ids = set(selected_df[COL_LISTING_ID].values)
                            rows_to_update = working_df[working_df[COL_LISTING_ID].isin(selected_ids)]
                            
                            for idx, row in rows_to_update.iterrows():
                                current_min_stay = int(row[COL_EDITABLE_MIN_STAY])
                                
                                if los_adjustment_type == 'set_value':
                                    new_min_stay = max(1, int(los_amount))
                                else:
                                    new_min_stay = max(1, current_min_stay + actual_los_amount)
                                
                                rate_id = row.get('_id')
                                listing_id = row.get(COL_LISTING_ID)
                                date = row.get(COL_DATE)
                                key = (listing_id, date)
                                los_updates[key] = new_min_stay
                                
                                update_dict = {
                                    '_id': rate_id,
                                    'listing_id': listing_id,
                                    COL_DATE: date,
                                    COL_EDITABLE_MIN_STAY: new_min_stay,
                                    'Status': 'LOS Adjusted'
                                }
                                updates.append(update_dict)
                            
                            if backend_interface.update_rates(updates):
                                edited_selection = working_df.copy()
                                edited_selection[COL_EDITABLE_MIN_STAY] = edited_selection[COL_EDITABLE_MIN_STAY].astype(int)
                                
                                for idx in edited_selection.index:
                                    listing_id = edited_selection.at[idx, COL_LISTING_ID]
                                    date = edited_selection.at[idx, COL_DATE]
                                    key = (listing_id, date)
                                    if key in los_updates:
                                        edited_selection.at[idx, COL_EDITABLE_MIN_STAY] = los_updates[key]
                                
                                st.session_state.updated_selected_df = edited_selection.copy()
                                update_filtered_data()
                                st.toast(f"{len(updates)} min stay adjustment(s) applied.", icon="✏️")
                            else:
                                st.error("Failed to log adjustments.")
                            
                            st.session_state.show_los_adjust_modal = False
                            rerun()
                        
                        if cancel:
                            st.session_state.show_los_adjust_modal = False
                            rerun()

            with action_cols[2]:
                # Initialize push confirmation state if not exists
                if 'show_push_confirm' not in st.session_state:
                    st.session_state.show_push_confirm = False
                    st.session_state.rates_to_push = None

                if not st.session_state.show_push_confirm:
                    if st.button("Push Selected Rates", key='push_button', type="secondary"):
                        if not edited_selection.empty:
                            # Prepare the rates dictionary
                            selected_rates_dict = {}
                            for listing_id, group in edited_selection.groupby(COL_LISTING_ID):
                                selected_rates_dict[listing_id] = []
                                for _, row in group.iterrows():
                                    # Get property key for currency lookup
                                    property_key = row.get(COL_PROPERTY_SRC, None)
                                    date_str = row[COL_DATE]
                                    
                                    rate_data = {
                                        "date": date_str,
                                        "price": row[COL_EDITABLE_PRICE_SRC],
                                        "currency": get_currency_for_listing(listing_id, property_key, date_str)
                                    }
                                    # Add min_stay if it exists and is different from default
                                    if COL_EDITABLE_MIN_STAY in row and pd.notna(row[COL_EDITABLE_MIN_STAY]):
                                        rate_data["min_stay"] = int(row[COL_EDITABLE_MIN_STAY])
                                    selected_rates_dict[listing_id].append(rate_data)
                            # Store in session state
                            st.session_state.rates_to_push = selected_rates_dict
                            st.session_state.show_push_confirm = True
                            rerun()
                        else:
                            st.warning("No rates selected to push.")
                
                # Show confirmation dialog if needed
                if st.session_state.show_push_confirm and st.session_state.rates_to_push:
                    with st.expander("Review and Confirm Push", expanded=True):
                        st.write("The following rates will be pushed:")
                        # Create a more readable display of the rates
                        display_data = []
                        for listing_id, rates in st.session_state.rates_to_push.items():
                            for rate in rates:
                                display_data.append({
                                    "Listing ID": listing_id,
                                    "Date": rate["date"],
                                    "Price": f"${rate['price']:.2f}",
                                    "Min Stay": rate.get("min_stay", "Default")
                                })
                        st.dataframe(
                            pd.DataFrame(display_data),
                            hide_index=True,
                            column_config={
                                "Listing ID": st.column_config.TextColumn("Listing ID"),
                                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                                "Price": st.column_config.TextColumn("Price"),
                                "Min Stay": st.column_config.TextColumn("Min Stay")
                            }
                        )
                        
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("✅ Confirm Push", type="primary", key="confirm_push"):
                                try:
                                    # Use push_rates_batch instead of individual calls
                                    results = push_rates_batch(st.session_state.rates_to_push)
                                    # Process results
                                    success_count = sum(1 for result in results.values() if result["success"])
                                    total_count = len(results)
                                    
                                    if success_count == total_count:
                                        st.success(f"✅ Successfully pushed rates and LOS for all {total_count} listings")
                                    elif success_count > 0:
                                        st.warning(f"⚠️ Partially successful: pushed rates and LOS for {success_count} out of {total_count} listings")
                                        # Show detailed results for failed pushes
                                        failed_listings = {
                                            listing_id: result 
                                            for listing_id, result in results.items() 
                                            if not result["success"]
                                        }
                                        if failed_listings:
                                            st.error("Failed listings:")
                                            for listing_id, result in failed_listings.items():
                                                st.error(f"❌ {listing_id}: {result.get('error_detail', result['message'])}")
                                    else:
                                        st.error(f"❌ Failed to push rates for all {total_count} listings")
                                        # Show error details for all failures
                                        for listing_id, result in results.items():
                                            st.error(f"❌ {listing_id}: {result.get('error_detail', result['message'])}")
                                        
                                except Exception as e:
                                    st.error(f"Error during batch push: {str(e)}")
                                    import traceback
                                    st.code(traceback.format_exc(), language="python")
                        
                        with col2:
                            if st.button("❌ Cancel", key="cancel_push"):
                                st.session_state.show_push_confirm = False
                                st.session_state.rates_to_push = None
                                rerun()

            # Rules Adjuster is now in sidebar for both views

        else:
            # Calendar view with Rules Adjuster in main area
            from utils.calendar_view import render_calendar_view
            
            # Rules Adjuster for Calendar View (Main Area)
            if st.session_state.base_data is not None and st.session_state.selected_properties:
                with st.expander("🔧 Rules Adjuster", expanded=False):
                    st.markdown("*Apply property-specific rules to live rates*")
                    
                    # Show available rules for selected properties
                    properties_config = backend_interface.load_properties_config()
                    if properties_config:
                        st.markdown("**📋 Available Rules:**")
                        for prop_key in st.session_state.selected_properties:
                            if prop_key in properties_config:
                                prop_config = properties_config[prop_key]
                                adjustment_rules = prop_config.get('adjustment_rules', [])
                                if adjustment_rules:
                                    st.markdown(f"**{prop_config.get('name', prop_key)}:**")
                                    for rule in adjustment_rules:
                                        rule_name = rule.get('name', 'Unnamed Rule')
                                        target_weekday = rule.get('target_weekday')
                                        weekday_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][target_weekday] if target_weekday is not None else 'Unknown'
                                        st.markdown(f"  • {rule_name} (applies to {weekday_name}s)")
                                else:
                                    st.markdown(f"**{prop_config.get('name', prop_key)}:** No rules configured")
                    
                    # Rule application button
                    if st.button("🔧 Apply Rules", key="calendar_apply_rules_button"):
                        st.session_state.rules_applied = True
                        st.session_state.rules_results = apply_rules_to_live_rates(
                            st.session_state.base_data, 
                            st.session_state.selected_properties
                        )
                        rerun()
                    
                    # Reset button
                    if st.button("🔄 Reset", key="calendar_reset_rules_button"):
                        st.session_state.rules_applied = False
                        st.session_state.rules_results = None
                        st.session_state.show_rules_results = False
                        rerun()
                    
                    # Cache refresh button
                    if st.button("🔄 Refresh Rules Cache", key="calendar_refresh_cache_button"):
                        st.cache_data.clear()
                        st.success("✅ Rules cache cleared! Rules should now be up to date.")
                        rerun()
                    
                    # Show results if rules were applied
                    if st.session_state.rules_applied and st.session_state.rules_results:
                        results = st.session_state.rules_results
                        
                        if results['success']:
                            st.success(f"✅ {results['message']}")
                            
                            if results['adjusted_rates']:
                                st.markdown("**📊 Results:**")
                                
                                # Show summary of total vs. actual changes
                                total_rates = len(results['adjusted_rates'])
                                actual_changes = results.get('actual_changes', 0)
                                st.info(f"📈 **Summary:** {total_rates} total rule applications, {actual_changes} with actual changes")
                                
                                # Add toggle for showing only changes
                                show_only_changes = st.checkbox("Show only rows with changes", value=True, key="calendar_show_changes")
                                
                                # Create comprehensive display for main area
                                display_data = []
                                for rate in results['adjusted_rates']:
                                    if show_only_changes and not rate.get('change_applied', False):
                                        continue
                                    # Determine adjustment type
                                    rate_change = f"${rate['original_price']:.0f} → ${rate['new_price']:.0f}" if rate['new_price'] != rate['original_price'] else "-"
                                    min_stay_change = f"{rate['original_min_stay']} → {rate['new_min_stay']}" if rate['new_min_stay'] != rate['original_min_stay'] else "-"
                                    
                                    display_data.append({
                                        'Day': f"{rate['date']} ({datetime.datetime.strptime(rate['date'], '%Y-%m-%d').strftime('%Y')})",
                                        'Listing': rate['listing_name'],
                                        'Rate Adjustment': rate_change,
                                        'Min Stay Adjustment': min_stay_change,
                                        'Rules': rate['rule_applied'],
                                        'Reason': rate.get('reason', '')
                                    })
                                
                                # Display comprehensive results
                                st.dataframe(
                                    pd.DataFrame(display_data),
                                    hide_index=True,
                                    column_config={
                                        'Day': st.column_config.TextColumn("Day"),
                                        'Listing': st.column_config.TextColumn("Listing"),
                                        'Rate Adjustment': st.column_config.TextColumn("Rate Adjustment"),
                                        'Min Stay Adjustment': st.column_config.TextColumn("Min Stay Adjustment"),
                                        'Rules': st.column_config.TextColumn("Rules"),
                                        'Reason': st.column_config.TextColumn("Reason")
                                    },
                                    use_container_width=True
                                )
                                
                                # Push button
                                if st.button("🚀 Push to PriceLabs", key="calendar_push_button", type="primary"):
                                    # Prepare rates for pushing - exclude no-change rows and de-duplicate per (listing, date)
                                    rates_to_push = {}
                                    for rate in results['adjusted_rates']:
                                        # Only push real changes
                                        if not rate.get('change_applied', False):
                                            continue
                                        if rate['new_price'] == rate['original_price'] and rate['new_min_stay'] == rate['original_min_stay']:
                                            continue

                                        listing_id = rate['listing_id']
                                        date_key_push = rate['date']
                                        if listing_id not in rates_to_push:
                                            rates_to_push[listing_id] = {}
                                        # Get currency for this listing
                                        currency = get_currency_for_listing(listing_id, rate.get('property'), date_key_push)
                                        # last-write-wins per (listing, date)
                                        rates_to_push[listing_id][date_key_push] = {
                                            "date": date_key_push,
                                            "price": rate['new_price'],
                                            "min_stay": rate['new_min_stay'],
                                            "currency": currency
                                        }

                                    # Convert inner dicts to lists for the batch API
                                    for lid in list(rates_to_push.keys()):
                                        rates_to_push[lid] = list(rates_to_push[lid].values())
                                    
                                    # Count what's actually being pushed
                                    total_rates_to_push = sum(len(rates) for rates in rates_to_push.values())
                                    
                                    # Push to PriceLabs
                                    try:
                                        push_results = push_rates_batch(rates_to_push)
                                        success_count = sum(1 for result in push_results.values() if result["success"])
                                        total_count = len(push_results)
                                        
                                        if success_count == total_count:
                                            st.success(f"✅ Pushed {total_rates_to_push} rates with actual changes")
                                        elif success_count > 0:
                                            st.warning(f"⚠️ {success_count}/{total_count} successful")
                                        else:
                                            st.error(f"❌ Push failed")
                                            
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                            else:
                                st.info("ℹ️ No rates adjusted")
                        else:
                            st.error(f"❌ {results['message']}")
                    else:
                        st.info("💡 Generate rates to use Rules Adjuster")
            
            # Main calendar view
            if st.session_state.base_data is not None:
                render_calendar_view(st.session_state.base_data, None)
            else:
                st.info("Please generate rates first to view the calendar.")

    elif not st.session_state.generate_clicked and st.session_state.base_data is None:
        st.info("Configure parameters above and click 'Generate Rates' to begin.")




