import streamlit as st
import pandas as pd
import datetime
import traceback
import numpy as np
from pathlib import Path
import re
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode, ColumnsAutoSizeMode
import json
from rates.push.push_rates import push_rates_to_pricelabs, push_rates_batch
import os

# Import backend interface functions
from utils import backend_interface

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
if 'start_date' not in st.session_state:
    st.session_state.start_date = datetime.date.today()
if 'end_date' not in st.session_state:
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

# Add refresh operation states to session state initialization
if 'refresh_all_clicked' not in st.session_state:
    st.session_state.refresh_all_clicked = False
if 'refresh_nightly_clicked' not in st.session_state:
    st.session_state.refresh_nightly_clicked = False
if 'refresh_current_clicked' not in st.session_state:
    st.session_state.refresh_current_clicked = False
if 'refresh_status' not in st.session_state:
    st.session_state.refresh_status = ""
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = None

# Filter defaults
filter_defaults = {
    'filter_start_date': None, 'filter_end_date': None,
    'filter_properties': [], 'filter_tiers': [], 'filter_dow': [],
    'filter_min_occ': None, 'filter_max_occ': None,
    'filter_min_live_rate': None, 'filter_max_live_rate': None,
    'filter_min_delta': None, 'filter_max_delta': None,
    'filter_flags': [], 'filter_statuses': []
}

for key, default_value in filter_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

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

def clear_all_filter_states():
    for key, default_value in filter_defaults.items():
        st.session_state[key] = default_value

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

def apply_filters(df, filter_state):
    if df is None or df.empty:
        return pd.DataFrame()

    filtered_df = df.copy()

    # Date filters
    if filter_state.get('filter_start_date'):
        filtered_df = filtered_df[pd.to_datetime(filtered_df[COL_DATE]).dt.date >= filter_state['filter_start_date']]
    if filter_state.get('filter_end_date'):
        filtered_df = filtered_df[pd.to_datetime(filtered_df[COL_DATE]).dt.date <= filter_state['filter_end_date']]

    # Multi-select filters
    if filter_state.get('filter_properties'):
        filtered_df = filtered_df[filtered_df[COL_PROPERTY_SRC].isin(filter_state['filter_properties'])]
    if filter_state.get('filter_tiers'):
        filtered_df = filtered_df[filtered_df[COL_CALCULATED_TIER_SRC].isin(filter_state['filter_tiers'])]
    if filter_state.get('filter_dow'):
        filtered_df = filtered_df[filtered_df[COL_DAY_OF_WEEK].isin(filter_state['filter_dow'])]
    if filter_state.get('filter_flags'):
        filtered_df = filtered_df[filtered_df[COL_FLAG].isin(filter_state['filter_flags'])]
    if filter_state.get('filter_statuses'):
        filtered_df = filtered_df[filtered_df[COL_STATUS].isin(filter_state['filter_statuses'])]

    # Numeric range filters
    if filter_state.get('filter_min_occ') is not None:
        filtered_df = filtered_df[pd.to_numeric(filtered_df[COL_OCC_CURR], errors='coerce') >= filter_state['filter_min_occ']]
    if filter_state.get('filter_max_occ') is not None:
        filtered_df = filtered_df[pd.to_numeric(filtered_df[COL_OCC_CURR], errors='coerce') <= filter_state['filter_max_occ']]
    if filter_state.get('filter_min_live_rate') is not None:
        filtered_df = filtered_df[pd.to_numeric(filtered_df[COL_LIVE_RATE], errors='coerce') >= filter_state['filter_min_live_rate']]
    if filter_state.get('filter_max_live_rate') is not None:
        filtered_df = filtered_df[pd.to_numeric(filtered_df[COL_LIVE_RATE], errors='coerce') <= filter_state['filter_max_live_rate']]
    if filter_state.get('filter_min_delta') is not None:
        filtered_df = filtered_df[pd.to_numeric(filtered_df[COL_DELTA], errors='coerce') >= filter_state['filter_min_delta']]
    if filter_state.get('filter_max_delta') is not None:
        filtered_df = filtered_df[pd.to_numeric(filtered_df[COL_DELTA], errors='coerce') <= filter_state['filter_max_delta']]

    return filtered_df

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

# Modify the caching and data loading functions
def load_and_prepare_data(property_selection, start_date, end_date):
    """Load and prepare data with proper initialization before caching"""
    # Always request full 2-year range from backend for accurate occupancy calculations
    full_start_date = datetime.date(2025, 1, 1)
    full_end_date = datetime.date(2025, 12, 31)  # Use 2025 only since that's what we have data for
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
        
        # Process live rates
        all_live_rates_dfs = []
        for prop_name in property_selection:
            live_df = process_live_rates(prop_name)
            if live_df is not None:
                all_live_rates_dfs.append(live_df)
        
        # Merge live rates
        if all_live_rates_dfs:
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
            merged_df = generated_df.copy()
            merged_df[COL_LIVE_RATE] = 0.0
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

@st.cache_data
def process_live_rates(property_name):
    """Cache live rates loading per property"""
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

def update_filtered_data():
    """Update filtered data based on current filter state"""
    if st.session_state.base_data is not None:
        st.session_state.filtered_data = apply_filters(
            st.session_state.base_data,
            st.session_state.filter_state
        )

def on_filter_change():
    """Callback for filter changes"""
    update_filtered_data()

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
        # Start Date Selection (FR1)
        current_start_date = st.date_input(
            label="Start Date:", 
            value=st.session_state.start_date, 
            key='start_date_input'
        )
    
    with col3:
        # End Date Selection (FR1)
        current_end_date = st.date_input(
            label="End Date:", 
            value=st.session_state.end_date, 
            key='end_date_input'
        )
    
    # --- Show last update times for pl_daily and nightly override files ---
    if current_selected_properties:
        prop = current_selected_properties[0]
        pl_daily_path = f"data/{prop}/pl_daily_{prop}.csv"
        nightly_path = f"data/{prop}/{prop}_nightly_pulled_overrides.csv"
        pl_daily_time = None
        nightly_time = None
        if os.path.exists(pl_daily_path):
            pl_daily_time = os.path.getmtime(pl_daily_path)
        if os.path.exists(nightly_path):
            nightly_time = os.path.getmtime(nightly_path)
        import datetime as dt
        st.info(f"pl_daily last updated: {dt.datetime.fromtimestamp(pl_daily_time).strftime('%Y-%m-%d %H:%M:%S') if pl_daily_time else 'Not found'}")
        st.info(f"Nightly override last updated: {dt.datetime.fromtimestamp(nightly_time).strftime('%Y-%m-%d %H:%M:%S') if nightly_time else 'Not found'}")
    
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
    
    # Add refresh buttons - always visible
    st.markdown("### Data Management")
    
    # Show last refresh time if available
    if st.session_state.last_refresh_time:
        st.info(f"📅 Last data refresh: {st.session_state.last_refresh_time}")
    
    refresh_col1, refresh_col2, refresh_col3 = st.columns(3)
    
    with refresh_col1:
        if st.button("🔄 Refresh All Data", key='refresh_all_button', help="Generate fresh data for all properties (selected range ±30 days)"):
            st.session_state.refresh_all_clicked = True
            st.session_state.refresh_status = "Starting refresh of all properties..."
            rerun()
        # Show the date range for all data refresh
        user_start = st.session_state.start_date
        user_end = st.session_state.end_date
        from datetime import timedelta
        start_date = (user_start - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = (user_end + timedelta(days=30)).strftime('%Y-%m-%d')
        st.caption(f"Will refresh all properties for: {start_date} to {end_date}")
    
    with refresh_col2:
        if st.button("📊 Update Nightly Data", key='refresh_nightly_button', help="Pull latest overrides from PriceLabs (2-year range)"):
            st.session_state.refresh_nightly_clicked = True
            st.session_state.refresh_status = "Pulling latest nightly data..."
            rerun()
        # Show the date range for nightly data update
        st.caption("Will update nightly data for: 2025-01-01 to 2026-12-31")
    
    with refresh_col3:
        if st.button("🔄 Refresh Current Property", key='refresh_current_button', help="Generate 2-year data for selected properties (2025-2026)"):
            if not current_selected_properties:
                st.warning("Please select at least one property first.")
            else:
                st.session_state.refresh_current_clicked = True
                st.session_state.refresh_status = f"Refreshing 2-year data for {len(current_selected_properties)} properties..."
                rerun()
        # Show the date range for current property refresh
        st.caption("Will refresh selected properties for: 2025-01-01 to 2026-12-31")
    
    # Show refresh status if any refresh operation is in progress
    if st.session_state.refresh_all_clicked or st.session_state.refresh_nightly_clicked or st.session_state.refresh_current_clicked:
        with st.spinner(st.session_state.refresh_status):
            try:
                if st.session_state.refresh_all_clicked:
                    # Run generate_pl_daily_comprehensive.py for all properties
                    import subprocess
                    import sys
                    from datetime import datetime, timedelta
                    
                    # Get all property keys from config
                    import yaml
                    with open('config/properties.yaml', 'r') as f:
                        config = yaml.safe_load(f)
                    all_properties = list(config['properties'].keys())
                    
                    # Use selected date range ±30 days
                    user_start = st.session_state.start_date
                    user_end = st.session_state.end_date
                    start_date = (user_start - timedelta(days=30)).strftime('%Y-%m-%d')
                    end_date = (user_end + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    success_count = 0
                    total_count = len(all_properties)
                    
                    for property_key in all_properties:
                        result = subprocess.run([
                            sys.executable, "generate_pl_daily_comprehensive.py", 
                            property_key, start_date, end_date
                        ], capture_output=True, text=True, cwd=".")
                        
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            st.error(f"❌ Error refreshing {property_key}: {result.stderr}")
                    
                    if success_count == total_count:
                        st.success(f"✅ Successfully refreshed {success_count}/{total_count} properties with data for {start_date} to {end_date}!")
                    else:
                        st.warning(f"⚠️ Refreshed {success_count}/{total_count} properties successfully.")
                    
                    st.session_state.refresh_all_clicked = False
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
                    rerun()
                
                elif st.session_state.refresh_nightly_clicked:
                    # Run nightly_pull.py for a 2-year range
                    import subprocess
                    import sys
                    from datetime import datetime
                    start_date = "2025-01-01"
                    end_date = "2026-12-31"
                    result = subprocess.run([
                        sys.executable, "rates/pull/nightly_pull.py", start_date, end_date
                    ], 
                    capture_output=True, text=True, cwd=".")
                    if result.returncode == 0:
                        st.success("✅ Nightly data updated successfully!")
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
                        rerun()
                    else:
                        st.error(f"❌ Error updating nightly data: {result.stderr}")
                        st.session_state.refresh_nightly_clicked = False
                        st.session_state.refresh_status = ""
                
                elif st.session_state.refresh_current_clicked:
                    # Run generate_pl_daily_comprehensive.py for selected properties
                    import subprocess
                    import sys
                    from datetime import datetime
                    
                    success_count = 0
                    total_count = len(current_selected_properties)
                    
                    for property_key in current_selected_properties:
                        # Generate 2-year data (2025-01-01 to 2026-12-31) instead of user's date range
                        start_date_str = "2025-01-01"
                        end_date_str = "2026-12-31"
                        
                        result = subprocess.run([
                            sys.executable, "generate_pl_daily_comprehensive.py", 
                            property_key, start_date_str, end_date_str
                        ], capture_output=True, text=True, cwd=".")
                        
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            st.error(f"❌ Error refreshing {property_key}: {result.stderr}")
                    
                    if success_count == total_count:
                        st.success(f"✅ Successfully refreshed {success_count}/{total_count} properties with 2-year data!")
                    else:
                        st.warning(f"⚠️ Refreshed {success_count}/{total_count} properties successfully.")
                    
                    st.session_state.refresh_current_clicked = False
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
                    rerun()
                    
            except Exception as e:
                st.error(f"❌ An error occurred during refresh: {str(e)}")
                st.session_state.refresh_all_clicked = False
                st.session_state.refresh_nightly_clicked = False
                st.session_state.refresh_current_clicked = False
                st.session_state.refresh_status = ""
    
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
                
                # Filters with callbacks
                with st.expander("Filter Displayed Rates", expanded=False):
                    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
                    
                    with filter_col1:
                        st.date_input("Filter Start Date", key='filter_start_date', on_change=on_filter_change)
                        st.date_input("Filter End Date", key='filter_end_date', on_change=on_filter_change)
                        st.multiselect("Filter Properties", 
                                     options=sorted(st.session_state.base_data[COL_PROPERTY_SRC].unique()),
                                     key='filter_properties',
                                     on_change=on_filter_change)
                        st.multiselect("Filter Tiers", 
                                     options=sorted(st.session_state.base_data[COL_CALCULATED_TIER_SRC].unique(), key=natural_sort_key_tier),
                                     key='filter_tiers',
                                     on_change=on_filter_change)
                    
                    with filter_col2:
                        st.multiselect("Filter Day of Week", 
                                     options=sorted(st.session_state.base_data[COL_DAY_OF_WEEK].unique()),
                                     key='filter_dow',
                                     on_change=on_filter_change)
                        st.multiselect("Filter Flags", 
                                     options=sorted(st.session_state.base_data[COL_FLAG].unique()),
                                     key='filter_flags',
                                     on_change=on_filter_change)
                        st.multiselect("Filter Status", 
                                     options=sorted(st.session_state.base_data[COL_STATUS].unique()),
                                     key='filter_statuses',
                                     on_change=on_filter_change)
                    
                    with filter_col3:
                        st.number_input("Min Occ% (Curr)", key='filter_min_occ', step=0.1, format="%.1f", on_change=on_filter_change)
                        st.number_input("Max Occ% (Curr)", key='filter_max_occ', step=0.1, format="%.1f", on_change=on_filter_change)
                        st.number_input("Min Live Rate $", key='filter_min_live_rate', step=0.01, format="%.2f", on_change=on_filter_change)
                        st.number_input("Max Live Rate $", key='filter_max_live_rate', step=0.01, format="%.2f", on_change=on_filter_change)
                    
                    with filter_col4:
                        st.number_input("Min Delta %", key='filter_min_delta', step=0.1, format="%.1f", on_change=on_filter_change)
                        st.number_input("Max Delta %", key='filter_max_delta', step=0.1, format="%.1f", on_change=on_filter_change)
                        st.markdown("<br/>", unsafe_allow_html=True)
                        st.button("Clear All Filters", key="clear_filters_m2_cb", on_click=clear_all_filter_states)

                # Apply filters
                display_df = st.session_state.filtered_data

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
                            options=['percentage', 'value', 'set_value'],
                            format_func=lambda x: {
                                'percentage': 'Percentage (%)',
                                'value': 'Fixed Amount ($)',
                                'set_value': 'Set Specific Value ($)'
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
                                    rate_data = {
                                        "date": row[COL_DATE],
                                        "price": row[COL_EDITABLE_PRICE_SRC]
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

        else:
            # Calendar view
            from utils.calendar_view import render_calendar_view
            if st.session_state.base_data is not None:
                render_calendar_view(st.session_state.base_data, None)
            else:
                st.info("Please generate rates first to view the calendar.")

    elif not st.session_state.generate_clicked and st.session_state.base_data is None:
        st.info("Configure parameters above and click 'Generate Rates' to begin.")
