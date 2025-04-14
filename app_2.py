import streamlit as st
import pandas as pd
import datetime
import traceback
import numpy as np
from pathlib import Path
import re
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode, ColumnsAutoSizeMode

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

def natural_sort_key_tier(tier_string):
    if tier_string is None:
        return (-1, tier_string)
    tier_string = str(tier_string)
    match = re.match(r'T(\d+)', tier_string, re.IGNORECASE)
    if match:
        return (0, int(match.group(1)))
    else:
        return (1, tier_string)

def clear_all_filter_states():
    for key, default_value in filter_defaults.items():
        st.session_state[key] = default_value

def update_editable_rate_source():
    toggle_value = st.session_state.get('rate_source_toggle', 'Use Live Rate')
    new_source_col_name = COL_LIVE_RATE if toggle_value == 'Use Live Rate' else COL_SUGGESTED_SRC
    st.session_state.active_rate_source_col = new_source_col_name

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
    if st.session_state.generate_clicked:
        st.subheader("2. Review & Manage Rates")
        try:
            with st.spinner("Generating rates..."):
                generated_df = backend_interface.trigger_rate_generation(
                    property_selection=st.session_state.selected_properties,
                    start_date=st.session_state.start_date,
                    end_date=st.session_state.end_date
                )

            st.session_state.generated_rates_df = generated_df
            
            if generated_df is not None and not generated_df.empty:
                # Live rate data merge
                merged_df = None
                all_live_rates_dfs = []
                properties_in_data = generated_df[COL_PROPERTY_SRC].unique()
                
                for prop_name in properties_in_data:
                    live_rates_filename = f"{prop_name}_nightly_pulled_overrides.csv"
                    live_rates_path = Path("data") / prop_name / live_rates_filename
                    if live_rates_path.exists():
                        try:
                            live_df = pd.read_csv(
                                live_rates_path,
                                usecols=['listing_id', 'date', 'price'],
                                dtype={'listing_id': str, 'date': str, 'price': float}
                            )
                            live_df['date'] = pd.to_datetime(live_df['date']).dt.strftime('%Y-%m-%d')
                            all_live_rates_dfs.append(live_df)
                        except Exception as e:
                            st.warning(f"Could not load or process live rates file for {prop_name}: {e}")
                    else:
                        st.warning(f"Live rates file not found for {prop_name}: {live_rates_path}")
                
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
                    
                    merged_df.rename(columns={'price': COL_LIVE_RATE}, inplace=True)
                    if COL_LIVE_RATE not in merged_df.columns:
                        merged_df[COL_LIVE_RATE] = 0.0
                    else:
                        merged_df[COL_LIVE_RATE] = pd.to_numeric(merged_df[COL_LIVE_RATE], errors='coerce').fillna(0.0)
                else:
                    st.warning("No live rate data loaded. 'Live Rate $' column will be set to $0.00.")
                    merged_df = generated_df.copy()
                    merged_df[COL_LIVE_RATE] = 0.0
                
                # Initialize Editable Rate Column
                if not st.session_state.get('editable_rate_initialized', False):
                    initial_source_col = COL_LIVE_RATE
                    if initial_source_col in merged_df.columns:
                        if COL_EDITABLE_PRICE_SRC not in merged_df.columns:
                            st.info(f"Initializing '{COL_EDITABLE_PRICE_SRC}' based on default '{initial_source_col}'.")
                        merged_df[COL_EDITABLE_PRICE_SRC] = pd.to_numeric(merged_df[initial_source_col], errors='coerce').fillna(0.0)
                        st.session_state.editable_rate_initialized = True
                    else:
                        st.warning(f"Default source column '{initial_source_col}' not found. Cannot initialize Editable Rate.")
                        if COL_EDITABLE_PRICE_SRC not in merged_df.columns:
                            merged_df[COL_EDITABLE_PRICE_SRC] = 0.0

                st.session_state.edited_rates_df = merged_df.copy()
                st.session_state.results_are_displayed = True

            elif st.session_state.generate_clicked:
                st.error("Failed to generate rates or no data found for the selected parameters.")
                st.session_state.edited_rates_df = None
                st.session_state.results_are_displayed = False

        except Exception as e:
            st.error(f"An error occurred during rate generation: {e}")
            st.exception(e)
            st.session_state.edited_rates_df = None
            st.session_state.results_are_displayed = False
            st.session_state.generate_clicked = False

    if st.session_state.results_are_displayed and st.session_state.edited_rates_df is not None:
        # Calculate derived columns first
        df = st.session_state.edited_rates_df.copy()
        
        # Debug prints
        print("\n=== Debug Information ===")
        print("Original DataFrame Columns:", df.columns.tolist())
        
        # Add Day of Week if not present
        if COL_DAY_OF_WEEK not in df.columns:
            df[COL_DAY_OF_WEEK] = pd.to_datetime(df[COL_DATE]).dt.strftime('%A')
        
        # Calculate Delta if not present
        if COL_DELTA not in df.columns:
            if COL_LIVE_RATE in df.columns and COL_SUGGESTED_SRC in df.columns:
                live_rate = pd.to_numeric(df[COL_LIVE_RATE], errors='coerce').fillna(0.0)
                suggested = pd.to_numeric(df[COL_SUGGESTED_SRC], errors='coerce')
                df[COL_DELTA] = np.where(
                    live_rate != 0,
                    ((suggested - live_rate) / live_rate) * 100,
                    np.nan
                )
            else:
                df[COL_DELTA] = np.nan
        
        # Update the session state with derived columns
        st.session_state.edited_rates_df = df

        # Rate source toggle
        st.radio(
            "Set Initial Value for Editable Rate $",
            options=['Use Live Rate', 'Use Suggested Rate'],
            key='rate_source_toggle',
            horizontal=True,
            on_change=update_editable_rate_source
        )
        st.markdown("---")

        # Filters
        with st.expander("Filter Displayed Rates", expanded=True):
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
            
            with filter_col1:
                st.date_input("Filter Start Date", key='filter_start_date')
                st.date_input("Filter End Date", key='filter_end_date')
                st.multiselect("Filter Properties", 
                             options=sorted(df[COL_PROPERTY_SRC].unique()),
                             key='filter_properties')
                st.multiselect("Filter Tiers", 
                             options=sorted(df[COL_CALCULATED_TIER_SRC].unique(), key=natural_sort_key_tier),
                             key='filter_tiers')
            
            with filter_col2:
                st.multiselect("Filter Day of Week", 
                             options=sorted(df[COL_DAY_OF_WEEK].unique()),
                             key='filter_dow')
                st.multiselect("Filter Flags", 
                             options=sorted(df[COL_FLAG].unique()),
                             key='filter_flags')
                st.multiselect("Filter Status", 
                             options=sorted(df[COL_STATUS].unique()),
                             key='filter_statuses')
            
            with filter_col3:
                st.number_input("Min Occ% (Curr)", key='filter_min_occ', step=0.1, format="%.1f")
                st.number_input("Max Occ% (Curr)", key='filter_max_occ', step=0.1, format="%.1f")
                st.number_input("Min Live Rate $", key='filter_min_live_rate', step=0.01, format="%.2f")
                st.number_input("Max Live Rate $", key='filter_max_live_rate', step=0.01, format="%.2f")
            
            with filter_col4:
                st.number_input("Min Delta %", key='filter_min_delta', step=0.1, format="%.1f")
                st.number_input("Max Delta %", key='filter_max_delta', step=0.1, format="%.1f")
                st.markdown("<br/>", unsafe_allow_html=True)
                st.button("Clear All Filters", key="clear_filters_m2_cb", on_click=clear_all_filter_states)

        # Apply filters
        display_df = apply_filters(df, st.session_state)

        # Reset index and use listing IDs
        display_df = display_df.reset_index(drop=True)
        display_df[COL_ID] = display_df[COL_LISTING_ID]  # Use listing_id as the ID

        # Ensure Select column exists and initialize with previous selections
        if COL_SELECT not in display_df.columns:
            display_df[COL_SELECT] = False
        if st.session_state.checkbox_selections:
            display_df[COL_SELECT] = display_df[COL_ID].map(st.session_state.checkbox_selections).fillna(False)

        # Debug information about columns
        print("\n=== Column Debug Information ===")
        print("Default Visible Columns:", DEFAULT_VISIBLE_COLUMNS)
        print("Actual Columns in DataFrame:", display_df.columns.tolist())
        
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

        # Configure columns in exact order
        column_order = [
            COL_SELECT,
            COL_ID,
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

        # First, hide all columns
        for col in display_df.columns:
            gb.configure_column(col, hide=True)

        # Then configure visible columns in exact order with specific settings
        for idx, col in enumerate(column_order):
            if col in display_df.columns:
                base_config = {
                    'resizable': True,
                    'cellStyle': {'textAlign': 'left'},
                    'headerClass': 'ag-header-cell-left',
                    'headerName': COLUMN_DISPLAY_NAMES.get(col, col),
                    'hide': False,
                    'suppressMovable': True,
                    'lockPosition': True,
                    'sortIndex': idx
                }
                
                print(f"Configuring grid column: {col} -> {COLUMN_DISPLAY_NAMES.get(col, col)}")
                
                if col == COL_DATE:
                    gb.configure_column(
                        col,
                        type=["dateColumnFilter", "customDateTimeFormat"],
                        custom_format_string='YYYY-MM-DD',
                        width=120,
                        editable=False,
                        **base_config
                    )
                elif col in [COL_LIVE_RATE, COL_SUGGESTED, COL_EDITABLE_PRICE]:
                    gb.configure_column(
                        col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=2,
                        valueFormatter="'$' + value.toFixed(2)",
                        editable=(col == COL_EDITABLE_PRICE),
                        width=130,
                        **base_config
                    )
                elif col == COL_DELTA:
                    gb.configure_column(
                        col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=1,
                        valueFormatter="value.toFixed(1) + '%'",
                        width=100,
                        editable=False,
                        **base_config
                    )
                elif col == COL_OCC_CURR:
                    gb.configure_column(
                        col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=1,
                        valueFormatter="value.toFixed(1) + '%'",
                        width=110,
                        editable=False,
                        **base_config
                    )
                elif col == COL_SELECT:
                    gb.configure_column(
                        col,
                        width=50,
                        headerCheckboxSelection=True,
                        headerCheckboxSelectionFilteredOnly=True,
                        checkboxSelection=True,
                        pinned='left',
                        editable=False,
                        **base_config
                    )
                elif col == COL_ID:
                    gb.configure_column(
                        col,
                        width=200,  # Wider column for listing IDs
                        type=["textColumn"],  # Change to text type for listing IDs
                        editable=False,
                        **{**base_config, 'hide': False}
                    )
                elif col in [COL_PROPERTY, COL_LISTING_NAME]:
                    gb.configure_column(
                        col,
                        width=200,
                        editable=False,
                        **base_config
                    )
                else:
                    gb.configure_column(
                        col,
                        width=120,
                        editable=False,
                        **base_config
                    )

        # Create grid with filtered columns and proper configuration
        grid_response = AgGrid(
            display_df,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            reload_data=False,
            key='main_grid',
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
            allow_unsafe_jscode=True,
            custom_css={
                ".ag-header-cell-label": {"justify-content": "left !important"},
                ".ag-cell": {"padding-left": "5px !important"}
            }
        )

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

        # Debug logging for selection state
        with st.expander("Debug Selection Info", expanded=False):
            st.write("Grid Response Type:", type(grid_response))
            print("\n=== Grid Response Debug ===")
            print(f"Grid Response Type: {type(grid_response)}")
            
            if hasattr(grid_response, 'selected_rows'):
                selected_df = pd.DataFrame(grid_response.selected_rows)
                print("\n=== Selected Rows Data ===")
                print(f"Selected DataFrame Shape: {selected_df.shape}")
                print(f"Selected DataFrame Columns: {selected_df.columns.tolist()}")
                print("\nFirst few rows of selected data:")
                print(selected_df.head().to_string())
                
                st.write("Selected Rows DataFrame:", selected_df)
                st.write("Selected Rows Shape:", selected_df.shape)
                st.write("Selected Rows Columns:", selected_df.columns.tolist())
            st.write("Current Checkbox Selections:", st.session_state.checkbox_selections)

        # Process selected rows
        selected_df = pd.DataFrame(grid_response.selected_rows) if hasattr(grid_response, 'selected_rows') else pd.DataFrame()
        
        # Extract IDs from selected DataFrame
        selected_ids = selected_df[COL_ID].tolist() if not selected_df.empty else []
        print("\n=== Selected IDs ===")
        print(f"Number of selected IDs: {len(selected_ids)}")
        print(f"Selected IDs: {selected_ids}")
        
        # Update session state with current selections
        st.session_state.selected_ids = set(selected_ids)
        print(f"\nSession state selected_ids updated: {st.session_state.selected_ids}")
        
        # Display selection summary
        if not selected_df.empty:
            st.info(f"Selected {len(selected_ids)} rows")
            display_columns = [COL_ID, COL_DATE, COL_PROPERTY_SRC, COL_LISTING_NAME, COL_LIVE_RATE, COL_SUGGESTED_SRC, COL_EDITABLE_PRICE_SRC]
            valid_columns = [col for col in display_columns if col in selected_df.columns]
            print("\n=== Display Columns ===")
            print(f"Valid display columns: {valid_columns}")
            edited_selection = st.data_editor(
                selected_df[valid_columns],
                hide_index=True,
                disabled=[col for col in valid_columns if col != COL_EDITABLE_PRICE_SRC],
                column_config={
                    COL_ID: st.column_config.TextColumn("ID"),
                    COL_DATE: st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    COL_PROPERTY_SRC: st.column_config.TextColumn("Property"),
                    COL_LISTING_NAME: st.column_config.TextColumn("Listing Name"),
                    COL_LIVE_RATE: st.column_config.NumberColumn("Live Rate $", format="$%.2f"),
                    COL_SUGGESTED_SRC: st.column_config.NumberColumn("Suggested Rate $", format="$%.2f"),
                    COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn("Editable Rate $", format="$%.2f", required=True, min_value=0)
                }
            )
            
            # Update the main dataframe with any edits made in the selection summary
            if edited_selection is not None:
                for _, row in edited_selection.iterrows():
                    row_id = row[COL_ID]  # Get ID from the row
                    new_editable_price = row[COL_EDITABLE_PRICE_SRC]
                    mask = st.session_state.edited_rates_df[COL_ID] == row_id
                    st.session_state.edited_rates_df.loc[mask, COL_EDITABLE_PRICE_SRC] = new_editable_price

        # Actions
        st.markdown("---")
        st.markdown("#### Actions")
        action_cols = st.columns(3)
        
        # Pass the current dataframe to action handlers
        current_action_df = st.session_state.edited_rates_df
        
        with action_cols[0]:
            if st.button("Adjust Selected", key='adjust_button'):
                if current_action_df is not None:
                    # Get selected rows from grid response
                    selected_for_action = pd.DataFrame(grid_response.selected_rows)
                    if not selected_for_action.empty:
                        updates = []
                        for index, row in selected_for_action.iterrows():
                            update = {
                                COL_ID: row[COL_ID],
                                COL_EDITABLE_PRICE_SRC: row[COL_EDITABLE_PRICE_SRC]
                            }
                            updates.append(update)
                            print(f"Prepared update: {update}")
                        
                        if updates:
                            if backend_interface.update_rates(updates):
                                print("\nSuccessfully logged rate adjustments")
                                st.toast(f"{len(updates)} rate adjustment(s) logged.", icon="✏️")
                            else:
                                print("\nFailed to log rate adjustments")
                                st.error("Failed to log adjustments.")
                    else:
                        st.warning("No rows selected for adjustment.")
                else:
                    st.warning("No data available to adjust.")

        with action_cols[1]:
            if st.button("Approve Selected", key='approve_button'):
                if current_action_df is not None:
                    # Get selected rows from grid response
                    selected_for_action = pd.DataFrame(grid_response.selected_rows)
                    if not selected_for_action.empty:
                        updates = []
                        ids_to_update_locally = []
                        for index, row in selected_for_action.iterrows():
                            update = {
                                COL_ID: row[COL_ID],
                                COL_STATUS: 'Approved'
                            }
                            updates.append(update)
                            ids_to_update_locally.append(row[COL_ID])
                            print(f"Prepared update: {update}")
                        
                        if updates:
                            if backend_interface.update_rates(updates):
                                print("\nSuccessfully logged rate approvals")
                                st.toast(f"{len(updates)} rate approval(s) logged.", icon="👍")
                                # Update local state
                                print(f"\nUpdating status for {len(ids_to_update_locally)} rows in main DataFrame")
                                st.session_state.edited_rates_df.loc[
                                    st.session_state.edited_rates_df[COL_ID].isin(ids_to_update_locally), 
                                    COL_STATUS
                                ] = 'Approved'
                                st.rerun()
                            else:
                                print("\nFailed to log rate approvals")
                                st.error("Failed to log approvals.")
                    else:
                        st.warning("No rows selected for approval.")
                else:
                    st.warning("No data available to approve.")

        with action_cols[2]:
            if st.button("Push Approved Rates Live", key='push_button', type="secondary"):
                approved_rates = display_df[display_df[COL_STATUS] == 'Approved']
                if not approved_rates.empty:
                    approved_ids = approved_rates[COL_ID].tolist()
                    confirm = st.confirm(f"Push {len(approved_ids)} approved rate(s) live? This will write to an output file.")
                    if confirm:
                        with st.spinner("Pushing rates live..."):
                            if backend_interface.push_rates_live(approved_ids, approved_rates):
                                st.toast(f"{len(approved_ids)} approved rate(s) written to output file.", icon="🚀")
                            else:
                                st.error("Failed to push rates live.")
                else:
                    st.warning("No rates currently marked as 'Approved' to push.")

    elif not st.session_state.generate_clicked and st.session_state.edited_rates_df is None:
        st.info("Configure parameters above and click 'Generate Rates' to begin.")
