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
        
        # Define column order to match original app.py
        column_order = [
            COL_SELECT,  # Ensure Select is first
            '_id',       # Add ID column
            COL_DATE,
            COL_PROPERTY_SRC,
            COL_TIER,
            COL_DAY_OF_WEEK,
            COL_OCC_CURR,
            COL_LIVE_RATE,
            COL_SUGGESTED_SRC,
            COL_DELTA,
            COL_EDITABLE_PRICE_SRC,
            COL_FLAG,
            COL_STATUS
        ] + st.session_state.optional_columns

        print("\n=== Column Configuration ===")
        print(f"Configured column order: {column_order}")
        
        # Configure selection mode
        gb.configure_selection(
            selection_mode='multiple',
            use_checkbox=True,
            pre_selected_rows=[]
        )
        
        # Configure column order and formatting
        for col in column_order:
            if col in display_df.columns:
                base_config = {
                    'resizable': True,
                    'cellStyle': {'textAlign': 'left'},
                    'headerClass': 'ag-header-cell-left'
                }
                
                if col == COL_DATE:
                    gb.configure_column(col, 
                        type=["dateColumnFilter", "customDateTimeFormat"],
                        custom_format_string='YYYY-MM-DD',
                        width=120,
                        **base_config
                    )
                elif col in [COL_LIVE_RATE, COL_SUGGESTED_SRC, COL_EDITABLE_PRICE_SRC]:
                    gb.configure_column(col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=2,
                        valueFormatter="'$' + value.toFixed(2)",
                        editable=(col == COL_EDITABLE_PRICE_SRC),
                        width=130,
                        **base_config
                    )
                elif col == COL_DELTA:
                    gb.configure_column(col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=1,
                        valueFormatter="value.toFixed(1) + '%'",
                        width=100,
                        **base_config
                    )
                elif col in [COL_OCC_CURR, COL_OCC_HIST]:
                    gb.configure_column(col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=1,
                        valueFormatter="value.toFixed(1) + '%'",
                        width=110,
                        **base_config
                    )
                elif col == COL_PACE:
                    gb.configure_column(col,
                        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                        precision=1,
                        valueFormatter="value.toFixed(1)",
                        width=100,
                        **base_config
                    )
                elif col == COL_SELECT:
                    gb.configure_column(col,
                        width=50,
                        headerCheckboxSelection=True,
                        headerCheckboxSelectionFilteredOnly=True,
                        checkboxSelection=True,
                        pinned='left',
                        **base_config
                    )
                elif col == '_id':
                    gb.configure_column(col,
                        width=80,
                        **base_config
                    )
                elif col == COL_PROPERTY_SRC:
                    gb.configure_column(col,
                        width=200,
                        **base_config
                    )
                elif col == COL_TIER:
                    gb.configure_column(col,
                        width=90,
                        **base_config
                    )
                elif col == COL_DAY_OF_WEEK:
                    gb.configure_column(col,
                        width=120,
                        **base_config
                    )
                else:
                    gb.configure_column(col,
                        width=120,
                        **base_config
                    )

        # Configure grid options
        gb.configure_grid_options(
            domLayout='autoHeight',
            enableCellTextSelection=True,
            ensureDomOrder=True,
            defaultColDef={
                'resizable': True,
                'sortable': True,
                'filter': True,
                'cellStyle': {'textAlign': 'center'},
                'headerClass': 'ag-header-cell-center'
            }
        )

        # Add custom CSS for center alignment
        st.markdown("""
        <style>
        .ag-header-cell-center {
            text-align: center !important;
        }
        .ag-cell {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Define columns that should be disabled from editing
        disabled_cols = [
            COL_DATE, COL_PROPERTY_SRC, COL_LISTING_NAME, COL_CALCULATED_TIER_SRC, 
            COL_DAY_OF_WEEK, COL_LIVE_RATE, COL_SUGGESTED_SRC, COL_DELTA,
            COL_FLAG, COL_OCC_CURR, COL_OCC_HIST, COL_PACE, COL_STATUS, '_id'
        ] + [col for col in HIDDEN_COLS if col != '_id']  # Include hidden cols except _id

        # Remove optional columns from disabled list if they're not selected
        if COL_OCC_HIST not in st.session_state.optional_columns and COL_OCC_HIST in disabled_cols:
            disabled_cols.remove(COL_OCC_HIST)
        if COL_PACE not in st.session_state.optional_columns and COL_PACE in disabled_cols:
            disabled_cols.remove(COL_PACE)

        # Filter disabled_cols to only include those actually present in the DataFrame
        disabled_cols = [col for col in disabled_cols if col in display_df.columns]

        print("\n=== Grid Configuration ===")
        print(f"Editable columns: {[col for col in display_df.columns if col not in disabled_cols]}")
        print(f"Disabled columns: {disabled_cols}")

        # Ensure Select column exists and is first
        if COL_SELECT not in display_df.columns:
            display_df.insert(0, COL_SELECT, False)
        elif list(display_df.columns).index(COL_SELECT) != 0:
            # If Select exists but is not first, reorder columns
            cols = list(display_df.columns)
            cols.remove(COL_SELECT)
            display_df = display_df[[COL_SELECT] + cols]

        # Simplify row IDs to sequential numbers
        if '_id' in display_df.columns:
            display_df = display_df.reset_index(drop=True)
            display_df['_id'] = display_df.index
            print("\n=== Row IDs ===")
            print(f"Simplified row IDs: {display_df['_id'].tolist()}")
        
        grid_response = AgGrid(
            display_df,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            reload_data=False,
            key='main_grid',
            disabled=disabled_cols,
            column_order=column_order
        )

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

        # Process selected rows - now handling as DataFrame
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
            display_columns = [COL_ID, COL_LISTING_ID, COL_DATE, COL_PROPERTY_SRC, COL_LIVE_RATE, COL_SUGGESTED_SRC, COL_EDITABLE_PRICE_SRC]
            valid_columns = [col for col in display_columns if col in selected_df.columns]
            print("\n=== Display Columns ===")
            print(f"Valid display columns: {valid_columns}")
            edited_selection = st.data_editor(
                selected_df[valid_columns],
                hide_index=True,
                disabled=[col for col in valid_columns if col != COL_EDITABLE_PRICE_SRC],
                column_config={
                    COL_ID: st.column_config.TextColumn("ID"),
                    COL_LISTING_ID: st.column_config.TextColumn("Listing ID"),
                    COL_DATE: st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    COL_PROPERTY_SRC: st.column_config.TextColumn("Property"),
                    COL_LIVE_RATE: st.column_config.NumberColumn("Live Rate $", format="$%.2f"),
                    COL_SUGGESTED_SRC: st.column_config.NumberColumn("Suggested Rate $", format="$%.2f"),
                    COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn("Editable Rate $", format="$%.2f", required=True, min_value=0)
                }
            )
            
            # Update the main dataframe with any edits made in the selection summary
            if edited_selection is not None:
                for idx, row in edited_selection.iterrows():
                    row_id = row[COL_ID]
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
