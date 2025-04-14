import streamlit as st
import pandas as pd
import datetime
import traceback
import numpy as np
from pathlib import Path
import re
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Import backend interface functions
from utils import backend_interface

# Set page config
st.set_page_config(layout="wide", page_title="Rate Review Tool")

# Title
st.title("Internal Rate Review & Management Tool")

# --- Constants for Column Names ---
COL_SELECT = "Select"
COL_DATE = "Date"
COL_PROPERTY = "Property"
COL_LISTING_ID = "listing_id"
COL_LISTING_NAME = "Listing Name"
COL_TIER = "Tier"
COL_DAY_OF_WEEK = "Day of Week"
COL_LIVE_RATE = "Live Rate $"
COL_SUGGESTED = "Suggested Rate"
COL_DELTA = "Delta"
COL_EDITABLE_PRICE = "Editable Rate"
COL_FLAG = "Flag"
COL_OCC_CURR = "Occ% (Curr)"
COL_OCC_HIST = "Occ% (Hist)"
COL_PACE = "Pace"
COL_STATUS = "Status"
COL_ID = "_id"

# Source column names
COL_BASELINE_SRC = "Baseline"
COL_SUGGESTED_SRC = "Suggested"
COL_EDITABLE_PRICE_SRC = "Editable Price"
COL_PROPERTY_SRC = "property"
COL_TIER_SRC = "tier_group"
COL_CALCULATED_TIER_SRC = "calculated_tier"

# Hidden columns
HIDDEN_COLS = [COL_ID, COL_LISTING_ID, COL_TIER_SRC, "day_group", "booking_window", "urgency_band", "lookup_error"]

# Core visible columns
CORE_COLS = [
    COL_SELECT, COL_DATE, COL_PROPERTY, COL_TIER, COL_DAY_OF_WEEK, COL_OCC_CURR,
    COL_LIVE_RATE, COL_SUGGESTED, COL_DELTA, COL_EDITABLE_PRICE,
    COL_FLAG, COL_STATUS
]

# Optional columns
OPTIONAL_COLS = [COL_OCC_HIST, COL_PACE]

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
if 'optional_columns' not in st.session_state:
    st.session_state.optional_columns = []
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
        
    with st.expander("Display Options"):
        st.session_state.optional_columns = st.multiselect(
            "Select Optional Columns to Display:",
            options=OPTIONAL_COLS,
            default=st.session_state.optional_columns,
            key='optional_cols_select'
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

        # Ensure Select column exists and initialize with previous selections
        if COL_SELECT not in display_df.columns:
            display_df[COL_SELECT] = False
        if st.session_state.checkbox_selections:
            display_df[COL_SELECT] = display_df[COL_ID].map(st.session_state.checkbox_selections).fillna(False)

        # Configure AgGrid
        gb = GridOptionsBuilder.from_dataframe(display_df)
        gb.configure_selection(selection_mode='multiple', use_checkbox=True)
        gb.configure_column(COL_SELECT, headerCheckboxSelection=True, headerCheckboxSelectionFilteredOnly=True)
        gb.configure_column(COL_DATE, type=["dateColumnFilter", "customDateTimeFormat"], custom_format_string='YYYY-MM-DD')
        gb.configure_column(COL_LIVE_RATE, type=["numericColumn", "numberColumnFilter", "customNumericFormat"], precision=2, valueFormatter="'$' + value.toFixed(2)")
        gb.configure_column(COL_SUGGESTED_SRC, type=["numericColumn", "numberColumnFilter", "customNumericFormat"], precision=2, valueFormatter="'$' + value.toFixed(2)")
        gb.configure_column(COL_EDITABLE_PRICE_SRC, type=["numericColumn", "numberColumnFilter", "customNumericFormat"], precision=2, valueFormatter="'$' + value.toFixed(2)", editable=True)
        gb.configure_column(COL_DELTA, type=["numericColumn", "numberColumnFilter", "customNumericFormat"], precision=1, valueFormatter="value.toFixed(1) + '%'")
        
        # Configure grid options with selection callback
        gb.configure_grid_options(
            onSelectionChanged="""
            function() {
                var selectedRows = this.api.getSelectedRows();
                var selectedIds = selectedRows.map(function(row) { return row._id; });
                window.parent.postMessage({
                    type: 'custom',
                    selectedIds: selectedIds
                }, '*');
            }
            """
        )
        
        grid_response = AgGrid(
            display_df,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            reload_data=False,
            key='main_grid'
        )

        # Debug logging for selection state
        with st.expander("Debug Selection Info", expanded=False):
            st.write("Grid Response Keys:", grid_response.keys() if isinstance(grid_response, dict) else "Not a dict")
            st.write("Selected Rows Count:", len(grid_response['selected_rows']) if isinstance(grid_response, dict) and 'selected_rows' in grid_response else "No selection data")
            st.write("Selection Model:", grid_response.get('selected_rows', []))
            st.write("Current Checkbox Selections:", st.session_state.checkbox_selections)

        # Ensure grid_response is a dictionary and 'selected_rows' exists
        if isinstance(grid_response, dict) and 'selected_rows' in grid_response:
            selected_ids = [row[COL_ID] for row in grid_response['selected_rows']]
            all_visible_ids = display_df[COL_ID].tolist()
            update_selected_ids(selected_ids, all_visible_ids)
        else:
            selected_ids = []
            st.warning("No rows selected or grid response is invalid.")

        # Display selection summary
        if selected_ids:
            st.info(f"Selected {len(selected_ids)} rows")
            # Create a summary DataFrame of selected rows
            selected_df = pd.DataFrame(selected_ids)
            if not selected_df.empty:
                st.dataframe(
                    selected_df[[COL_DATE, COL_PROPERTY_SRC, COL_LIVE_RATE, COL_SUGGESTED_SRC, COL_EDITABLE_PRICE_SRC]],
                    hide_index=True
                )

        # Actions
        st.markdown("---")
        st.markdown("#### Actions")
        action_cols = st.columns(3)
        
        with action_cols[0]:
            if st.button("Adjust Selected", key='adjust_button'):
                if st.session_state.selected_ids:
                    updates = [
                        {COL_ID: row_id, COL_EDITABLE_PRICE_SRC: display_df.loc[display_df[COL_ID] == row_id, COL_EDITABLE_PRICE_SRC].values[0]}
                        for row_id in st.session_state.selected_ids
                    ]
                    if updates:
                        if backend_interface.update_rates(updates):
                            st.toast(f"{len(updates)} rate adjustment(s) logged.", icon="✏️")
                        else:
                            st.error("Failed to log adjustments.")
                    else:
                        st.warning("No valid rows selected for adjustment.")
                else:
                    st.warning("No rows selected for adjustment.")

        with action_cols[1]:
            if st.button("Approve Selected", key='approve_button'):
                if st.session_state.selected_ids:
                    updates = [
                        {COL_ID: row_id, COL_STATUS: 'Approved'}
                        for row_id in st.session_state.selected_ids
                    ]
                    if updates:
                        if backend_interface.update_rates(updates):
                            st.toast(f"{len(updates)} rate approval(s) logged.", icon="👍")
                            for row_id in st.session_state.selected_ids:
                                idx = st.session_state.edited_rates_df[COL_ID] == row_id
                                st.session_state.edited_rates_df.loc[idx, COL_STATUS] = 'Approved'
                            st.rerun()
                        else:
                            st.error("Failed to log approvals.")
                    else:
                        st.warning("No valid rows selected for approval.")
                else:
                    st.warning("No rows selected for approval.")

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

# Add a button to clear selections
if st.button("Clear Selections"):
    st.session_state.selected_ids.clear() 