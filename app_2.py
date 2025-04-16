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

# Import backend interface functions
from utils import backend_interface

# Set page config
st.set_page_config(layout="wide", page_title="Rate Review Tool")

# Title
st.title("Internal Rate Review & Management Tool")

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

# Source column names
COL_BASELINE_SRC = "Baseline"
COL_SUGGESTED_SRC = "Suggested"
COL_EDITABLE_PRICE_SRC = "Editable Price"
COL_PROPERTY_SRC = "property"
COL_CALCULATED_TIER_SRC = "calculated_tier"

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
    COL_SELECT, COL_DATE, COL_PROPERTY, COL_TIER, COL_DAY_OF_WEEK, COL_OCC_CURR,
    COL_LIVE_RATE, COL_SUGGESTED, COL_DELTA, COL_EDITABLE_PRICE,
    COL_FLAG, COL_STATUS
]

# Define the exact columns we want to show, in order
DEFAULT_VISIBLE_COLUMNS = [
    COL_SELECT,
    COL_ID,
    COL_DATE,
    COL_PROPERTY,  # This is 'Unit Pool'
    COL_LISTING_NAME,
    COL_TIER,
    COL_DAY_OF_WEEK,
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
    COL_STATUS: "Status"
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
if 'adjustment_type' not in st.session_state:
    st.session_state.adjustment_type = 'value'
if 'adjustment_amount' not in st.session_state:
    st.session_state.adjustment_amount = 0.0

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
    print(f"\n[DEBUG] Starting price adjustment:")
    print(f"[DEBUG] Input - current_price: {current_price} ({type(current_price)})")
    print(f"[DEBUG] Input - adjustment_type: {adjustment_type}")
    print(f"[DEBUG] Input - adjustment_amount: {adjustment_amount} ({type(adjustment_amount)})")
    
    try:
        current_price = float(current_price)
        adjustment_amount = float(adjustment_amount)
        
        print(f"[DEBUG] Converted - current_price: {current_price}")
        print(f"[DEBUG] Converted - adjustment_amount: {adjustment_amount}")
        
        if adjustment_type == 'percentage':
            # Convert percentage to decimal and add to 1 for multiplication
            # e.g., 10% increase = 1.10, -10% decrease = 0.90
            multiplier = 1 + (adjustment_amount / 100)
            result = round(current_price * multiplier, 2)
            print(f"[DEBUG] Percentage calculation - multiplier: {multiplier}")
            print(f"[DEBUG] Percentage calculation - result: {result}")
            return result
        else:  # value
            result = round(current_price + adjustment_amount, 2)
            print(f"[DEBUG] Value calculation - result: {result}")
            return result
    except (ValueError, TypeError) as e:
        print(f"[DEBUG] Error in price adjustment: {e}")
        print(f"[DEBUG] Returning original price: {current_price}")
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

# Function to update selected IDs
def update_selected_ids(new_ids, all_visible_ids):
    current = st.session_state.selected_ids
    to_add = set(new_ids)
    to_remove = set(all_visible_ids) - to_add
    current.update(to_add)
    current.difference_update(to_remove)
    st.session_state.selected_ids = current

# Modify the caching and data loading functions
@st.cache_data
def load_and_prepare_data(property_selection, start_date, end_date):
    """Load and prepare data with proper initialization before caching"""
    # Load initial data
    generated_df = backend_interface.trigger_rate_generation(
        property_selection=property_selection,
        start_date=start_date,
        end_date=end_date
    )
    
    if generated_df is not None and not generated_df.empty:
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
        else:
            merged_df = generated_df.copy()
            merged_df[COL_LIVE_RATE] = 0.0
        
        # Initialize editable price based on current toggle state
        toggle_value = st.session_state.get('rate_source_toggle', 'Use Live Rate')
        source_col = COL_LIVE_RATE if toggle_value == 'Use Live Rate' else COL_SUGGESTED
        merged_df[COL_EDITABLE_PRICE_SRC] = pd.to_numeric(merged_df[source_col], errors='coerce').fillna(0.0)
        
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
                usecols=['listing_id', 'date', 'price'],
                dtype={'listing_id': str, 'date': str, 'price': float}
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
            print(f"[DEBUG] Source column {source_col} not found. Available columns: {df.columns.tolist()}")
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
    
    available_properties = backend_interface.get_available_properties()
    if not available_properties:
        st.error("Could not load property list from configuration. Please check config/properties.yaml")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.session_state.selected_properties = st.multiselect(
            "Select Property/Unit Pools:",
            options=available_properties,
            default=st.session_state.selected_properties,
            key='prop_select'
        )
    
    with col2:
        st.session_state.start_date = st.date_input(
            "Start Date:",
            value=st.session_state.start_date,
            key='start_date_input'
        )
        
    with col3:
        st.session_state.end_date = st.date_input(
            "End Date:",
            value=st.session_state.end_date,
            key='end_date_input'
        )
        
    if st.button("Generate Rates", key='generate_button', type="primary"):
        if not st.session_state.selected_properties:
            st.warning("Please select at least one property.")
            st.session_state.generate_clicked = False
        elif st.session_state.start_date > st.session_state.end_date:
            st.warning("Start Date cannot be after End Date.")
            st.session_state.generate_clicked = False
        else:
            st.session_state.generate_clicked = True
            st.session_state.generated_rates_df = None
            st.session_state.edited_rates_df = None
            st.session_state.results_are_displayed = False
            st.session_state.editable_rate_initialized = False
            st.rerun()
    
    st.markdown("---")

# --- Results Area ---
with results_area:
    if st.session_state.generate_clicked and not st.session_state.data_loaded:
        st.subheader("2. Review & Manage Rates")
        try:
            with st.spinner("Loading data..."):
                # Load and prepare data with caching
                prepared_df = load_and_prepare_data(
                    st.session_state.selected_properties,
                    st.session_state.start_date,
                    st.session_state.end_date
                )
                
                if prepared_df is not None:
                    # Store in session state
                    st.session_state.base_data = prepared_df.copy()
                    st.session_state.data_loaded = True
                    st.session_state.initial_load_complete = False  # Reset for new data load
                    update_filtered_data()
                    st.success("Data loaded successfully!")
                    st.rerun()  # Force a rerun to ensure proper grid initialization
                else:
                    st.error("No data was generated. Please check your parameters.")
                
        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.exception(e)
            st.session_state.data_loaded = False
            st.session_state.base_data = None

    elif not st.session_state.generate_clicked and st.session_state.base_data is None:
        st.info("Configure parameters above and click 'Generate Rates' to begin.")

    # Display area - use cached data
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
        with st.expander("Filter Displayed Rates", expanded=True):
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
                else:
                    column_defs.append({
                        **base_config,
                        'width': 120,
                        'editable': False
                    })

        # Set the columnDefs directly in grid options
        gb.configure_grid_options(columnDefs=column_defs)

        # Create grid with filtered columns and proper configuration
        grid_key = 'main_grid_' + ('initial' if not st.session_state.initial_load_complete else 'updated')
        grid_response = AgGrid(
            display_df,
            gridOptions=gb.build(),
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
            st.rerun()  # Force one rerun after initial load to ensure proper rendering

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
        st.session_state.selected_ids = set(selected_ids)
        
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
            
            display_columns = [COL_LISTING_ID, COL_DATE, COL_PROPERTY_SRC, COL_LISTING_NAME, COL_LIVE_RATE, COL_SUGGESTED, COL_EDITABLE_PRICE_SRC]
            valid_columns = [col for col in display_columns if col in display_df.columns]
            
            # Add a unique key for the data editor based on selections
            editor_key = f"selection_editor_{','.join(sorted(selected_ids))}"
            
            edited_selection = st.data_editor(
                display_df[valid_columns],
                hide_index=True,
                disabled=[col for col in valid_columns if col != COL_EDITABLE_PRICE_SRC],
                key=editor_key,
                column_config={
                    COL_LISTING_ID: st.column_config.TextColumn("ID"),
                    COL_DATE: st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    COL_PROPERTY_SRC: st.column_config.TextColumn("Property"),
                    COL_LISTING_NAME: st.column_config.TextColumn("Listing Name"),
                    COL_LIVE_RATE: st.column_config.NumberColumn("Live Rate $", format="$%.2f"),
                    COL_SUGGESTED: st.column_config.NumberColumn("Suggested Rate $", format="$%.2f"),
                    COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn("Editable Rate $", format="$%.2f", required=True, min_value=0)
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
            if st.button("Adjust Selected", key='adjust_button'):
                if current_action_df is not None:
                    selected_for_action = pd.DataFrame(grid_response.selected_rows)
                    if not selected_for_action.empty:
                        st.session_state.show_adjust_modal = True
                    else:
                        st.warning("No rows selected for adjustment.")
                else:
                    st.warning("No data available to adjust.")

            # Add adjustment modal
            if st.session_state.show_adjust_modal:
                with st.form(key="adjustment_form"):
                    st.subheader("Adjust Prices")
                    
                    # Adjustment type selection
                    st.session_state.adjustment_type = st.radio(
                        "Adjustment Type",
                        options=['value', 'percentage'],
                        format_func=lambda x: 'Fixed Amount ($)' if x == 'value' else 'Percentage (%)',
                        horizontal=True
                    )

                    # Direction and amount in separate columns
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        direction = st.radio(
                            "Direction",
                            options=['increase', 'decrease'],
                            format_func=lambda x: 'Increase (+)' if x == 'increase' else 'Decrease (-)',
                            horizontal=True
                        )
                    
                    with col2:
                        # Adjustment amount input with appropriate label
                        amount_label = "Adjustment Amount"
                        if st.session_state.adjustment_type == 'value':
                            amount = st.number_input(
                                amount_label,
                                min_value=0.0,
                                value=0.0,
                                step=1.0,
                                format="%.2f"
                            )
                        else:
                            amount = st.number_input(
                                amount_label,
                                min_value=0.0,
                                value=0.0,
                                step=1.0,
                                format="%.1f"
                            )
                    
                    # Calculate actual adjustment amount based on direction
                    st.session_state.adjustment_amount = -amount if direction == 'decrease' else amount
                    
                    # Show preview of adjustments
                    selected_for_preview = pd.DataFrame(grid_response.selected_rows)
                    if not selected_for_preview.empty:
                        st.write("Preview of adjustments:")
                        preview_df = selected_for_preview[[COL_LISTING_ID, COL_DATE, COL_PROPERTY_SRC, COL_EDITABLE_PRICE_SRC]].copy()
                        
                        # Debug information before adjustment
                        st.write("\n[DEBUG] Before adjustment:")
                        st.write(f"Preview DataFrame head:\n{preview_df.head()}")
                        
                        preview_df['New Price'] = preview_df[COL_EDITABLE_PRICE_SRC].apply(
                            lambda x: apply_price_adjustment(
                                x, 
                                st.session_state.adjustment_type,
                                st.session_state.adjustment_amount
                            )
                        )
                        preview_df['Change'] = preview_df['New Price'] - preview_df[COL_EDITABLE_PRICE_SRC]
                        preview_df['Change %'] = (preview_df['Change'] / preview_df[COL_EDITABLE_PRICE_SRC] * 100).round(1)
                        
                        # Debug information after adjustment
                        st.write("\n[DEBUG] After adjustment:")
                        st.write(f"Preview DataFrame with new prices:\n{preview_df.head()}")
                        
                        # Format and display preview
                        st.dataframe(
                            preview_df,
                            column_config={
                                COL_LISTING_ID: "ID",
                                COL_DATE: "Date",
                                COL_PROPERTY_SRC: "Property",
                                COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn(
                                    "Current Price",
                                    format="$%.2f"
                                ),
                                'New Price': st.column_config.NumberColumn(
                                    "New Price",
                                    format="$%.2f"
                                ),
                                'Change': st.column_config.NumberColumn(
                                    "Absolute Change",
                                    format="$%.2f",
                                    help="Absolute change in price"
                                ),
                                'Change %': st.column_config.NumberColumn(
                                    "Relative Change",
                                    format="%.1f%%",
                                    help="Percentage change in price"
                                )
                            },
                            hide_index=True
                        )
                        
                        # Form submit and cancel buttons
                        col1, col2 = st.columns(2)
                        with col1:
                            submit_text = f"Apply {direction.title()} by {amount:.2f}" + (" $" if st.session_state.adjustment_type == 'value' else " %")
                            submit = st.form_submit_button(
                                submit_text,
                                type="primary" if direction == 'increase' else "secondary"
                            )
                        with col2:
                            cancel = st.form_submit_button("Cancel")
                        
                        if submit:
                            updates = []
                            # Create a copy of the data to update
                            updated_selected_df = selected_df.copy()
                            
                            # Create comparison table of before values
                            print("\nBEFORE ADJUSTMENT:")
                            comparison_df = selected_df[[COL_LISTING_ID, COL_DATE, COL_EDITABLE_PRICE_SRC]].copy()
                            comparison_df.columns = ['Listing ID', 'Date', 'Original Price']
                            print(comparison_df.to_string(index=False))
                            
                            # Store original indices to maintain order
                            original_indices = selected_df.index.tolist()
                            
                            # Create a dictionary to store updates by listing_id and date
                            price_updates = {}
                            
                            for idx, row in selected_df.iterrows():
                                current_price = float(row[COL_EDITABLE_PRICE_SRC])
                                new_price = max(0, round(current_price + st.session_state.adjustment_amount, 2))
                                
                                rate_id = row.get('_id')
                                listing_id = row.get(COL_LISTING_ID)
                                date = row.get(COL_DATE)
                                
                                # Store update in dictionary
                                key = (listing_id, date)
                                price_updates[key] = new_price
                                
                                update_dict = {
                                    '_id': rate_id,
                                    'listing_id': listing_id,
                                    COL_EDITABLE_PRICE_SRC: new_price,
                                    'Status': 'Adjusted'
                                }
                                updates.append(update_dict)
                            
                            if updates:
                                print("\nAFTER ADJUSTMENT:")
                                # Update the DataFrame with new prices before showing it
                                for update in updates:
                                    mask = (updated_selected_df[COL_LISTING_ID] == update['listing_id'])
                                    updated_selected_df.loc[mask, COL_EDITABLE_PRICE_SRC] = update[COL_EDITABLE_PRICE_SRC]
                                
                                after_df = updated_selected_df[[COL_LISTING_ID, COL_DATE, COL_EDITABLE_PRICE_SRC]].copy()
                                after_df.columns = ['Listing ID', 'Date', 'New Price']
                                print(after_df.to_string(index=False))
                                
                                if backend_interface.update_rates(updates):
                                    # Update the edited_selection DataFrame with new prices
                                    for idx in edited_selection.index:
                                        listing_id = edited_selection.at[idx, COL_LISTING_ID]
                                        date = edited_selection.at[idx, COL_DATE]
                                        key = (listing_id, date)
                                        if key in price_updates:
                                            edited_selection.at[idx, COL_EDITABLE_PRICE_SRC] = price_updates[key]
                                    
                                    # Store the updated dataframe in session state
                                    st.session_state.updated_selected_df = updated_selected_df.copy()
                                    
                                    # Update filtered data
                                    update_filtered_data()
                                    
                                    # Show what's in the selected table
                                    print("\nSELECTED TABLE DATA:")
                                    selected_table = edited_selection[[COL_LISTING_ID, COL_DATE, COL_EDITABLE_PRICE_SRC]].copy()
                                    selected_table.columns = ['Listing ID', 'Date', 'Table Price']
                                    print(selected_table.to_string(index=False))
                                    
                                    st.toast(f"{len(updates)} rate adjustment(s) logged.", icon="✏️")
                                else:
                                    print("[DEBUG] Backend update failed")
                                    st.error("Failed to log adjustments.")
                            
                                st.session_state.show_adjust_modal = False
                                st.rerun()

                            if cancel:
                                st.session_state.show_adjust_modal = False
                                st.rerun()

        # with action_cols[1]:
        #     if st.button("Approve Selected", key='approve_button'):
        #         if current_action_df is not None:
        #             selected_for_action = pd.DataFrame(grid_response.selected_rows)
        #             if not selected_for_action.empty:
        #                 updates = []
        #                 ids_to_update_locally = []
        #                 for index, row in selected_for_action.iterrows():
        #                     update = {
        #                         COL_LISTING_ID: row[COL_LISTING_ID],
        #                         COL_STATUS: 'Approved'
        #                     }
        #                     updates.append(update)
        #                     ids_to_update_locally.append(row[COL_LISTING_ID])
                        
        #                 if updates:
        #                     if backend_interface.update_rates(updates):
        #                         st.toast(f"{len(updates)} rate approval(s) logged.", icon="👍")
        #                         # Update local state
        #                         st.session_state.base_data.loc[
        #                             st.session_state.base_data[COL_LISTING_ID].isin(ids_to_update_locally), 
        #                             COL_STATUS
        #                         ] = 'Approved'
        #                         st.rerun()
        #                     else:
        #                         st.error("Failed to log approvals.")
        #             else:
        #                 st.warning("No rows selected for approval.")
        #         else:
        #             st.warning("No data available to approve.")

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
                                selected_rates_dict[listing_id].append({
                                    "date": row[COL_DATE],
                                    "price": row[COL_EDITABLE_PRICE_SRC]
                                })
                        # Store in session state
                        st.session_state.rates_to_push = selected_rates_dict
                        st.session_state.show_push_confirm = True
                        st.rerun()
                    else:
                        st.warning("No rates selected to push.")
            
            # Show confirmation dialog if needed
            if st.session_state.show_push_confirm and st.session_state.rates_to_push:
                with st.expander("Review and Confirm Push", expanded=True):
                    st.write("The following rates will be pushed:")
                    st.json(st.session_state.rates_to_push)
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("✅ Confirm Push", type="primary", key="confirm_push"):
                            try:                                
                                for listing_id, rates in st.session_state.rates_to_push.items():
                                    success = push_rates_to_pricelabs(
                                        listing_id=listing_id,
                                        rates=rates
                                    )
                                    
                                    if success:
                                        st.success(f"✅ Pushed rates for {listing_id}")
                                    else:
                                        st.error(f"❌ Failed to push rates for {listing_id}")
                                        
                            except Exception as e:
                                st.error(f"Error during push: {str(e)}")
                                import traceback
                                st.code(traceback.format_exc(), language="python")
                    
                    with col2:
                        if st.button("❌ Cancel", key="cancel_push"):
                            st.session_state.show_push_confirm = False
                            st.session_state.rates_to_push = None
                            st.rerun()
