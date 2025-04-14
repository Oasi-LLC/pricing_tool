import streamlit as st
import pandas as pd
import datetime
import traceback # Import traceback for more detailed error logging if needed
import numpy as np # Import numpy for calculations
from pathlib import Path # Add Path import
import re # Import regex for parsing

# Import backend interface functions
from utils import backend_interface

# Set page config
st.set_page_config(layout="wide", page_title="Rate Review Tool")

# Title
st.title("Internal Rate Review & Management Tool")

# --- Constants for Column Names ---
# Define column names to avoid typos
COL_SELECT = "Select"
COL_VIEW_DETAILS = "View Details"
COL_DATE = "Date"
COL_PROPERTY = "Property"
COL_LISTING_ID = "listing_id" # Changed to match source df column name
COL_LISTING_NAME = "Listing Name"
COL_TIER = "Tier"
COL_DAY_OF_WEEK = "Day of Week"
# COL_LIVE_RATE = "Live Rate" # Revert back to the correct name with $
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
# Original source names if different from display
COL_BASELINE_SRC = "Baseline" # Keep for potential reference but remove usage for Live Rate
COL_SUGGESTED_SRC = "Suggested"
COL_EDITABLE_PRICE_SRC = "Editable Price"
COL_PROPERTY_SRC = "property"
COL_TIER_SRC = "tier_group"
COL_CALCULATED_TIER_SRC = "calculated_tier"

# Hidden source/technical columns - NOTE: Ensure listing_id matches COL_LISTING_ID if changed
HIDDEN_COLS = [COL_ID, COL_LISTING_ID, COL_TIER_SRC, "day_group", "booking_window", "urgency_band", "lookup_error"]
# Core visible columns (always shown) - Updated Order & Names
CORE_COLS = [
    COL_SELECT, COL_VIEW_DETAILS, COL_DATE, COL_PROPERTY, COL_TIER, COL_DAY_OF_WEEK, COL_OCC_CURR,
    COL_LIVE_RATE, COL_SUGGESTED, COL_DELTA, COL_EDITABLE_PRICE,
    COL_FLAG, COL_STATUS
]
# Optional columns
OPTIONAL_COLS = [COL_OCC_HIST, COL_PACE]

# --- Session State Initialization ---
# Initialize session state keys if they don't exist
if 'selected_properties' not in st.session_state:
    st.session_state.selected_properties = []
if 'start_date' not in st.session_state:
    st.session_state.start_date = datetime.date.today()
if 'end_date' not in st.session_state:
    st.session_state.end_date = datetime.date.today() + datetime.timedelta(days=30)
if 'generate_clicked' not in st.session_state:
    st.session_state.generate_clicked = False
# Add placeholders for data that will be generated later
if 'generated_rates_df' not in st.session_state:
    st.session_state.generated_rates_df = None
# To store edits from the data editor
if 'edited_rates_df' not in st.session_state:
    st.session_state.edited_rates_df = None
# For detail view selection
if 'selected_rate_id' not in st.session_state:
    st.session_state.selected_rate_id = None
# For calendar focus
if 'focus_date' not in st.session_state:
    st.session_state.focus_date = datetime.date.today()
# Add state for optional columns
if 'optional_columns' not in st.session_state:
    st.session_state.optional_columns = [] # Default to none selected
if 'results_are_displayed' not in st.session_state:
     st.session_state.results_are_displayed = False
# Add state for checkbox selections
if 'checkbox_selections' not in st.session_state:
    st.session_state.checkbox_selections = {}

# --- Add Filter Session State Initialization (Milestone 2) ---
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

# --- Add Toggle Session State Initialization ---
# Active source column name
if 'active_rate_source_col' not in st.session_state:
     st.session_state.active_rate_source_col = COL_LIVE_RATE # Default source
# UI toggle state
if 'rate_source_toggle' not in st.session_state:
    st.session_state.rate_source_toggle = 'Use Live Rate' # New default

# --- Natural Sort Helper for Tiers (Fix for Issue 3) ---
def natural_sort_key_tier(tier_string):
    """Provides a sort key for tier strings like 'T0', 'T10', 'None'."""
    if tier_string is None:
        return (-1, tier_string) # Place None types first
    tier_string = str(tier_string)
    match = re.match(r'T(\d+)', tier_string, re.IGNORECASE)
    if match:
        return (0, int(match.group(1))) # Sort numerically if pattern matches
    else:
        return (1, tier_string) # Place non-matching strings (like 'None') after None but before Tiers

# --- Callback Function for Clearing Filters (Fix for Issue 2) ---
def clear_all_filter_states():
    for key, default_value in filter_defaults.items():
        st.session_state[key] = default_value
    # No rerun needed here, Streamlit handles rerun after callback

# --- Callback Function for Updating Editable Rate Source ---
# --- MODIFIED Callback: Only updates the active source column name state ---
def update_editable_rate_source():
    toggle_value = st.session_state.get('rate_source_toggle', 'Use Live Rate')
    
    new_source_col_name = COL_LIVE_RATE # Default
    if toggle_value == 'Use Suggested Rate':
        new_source_col_name = COL_SUGGESTED_SRC
    elif toggle_value == 'Use Live Rate':
        new_source_col_name = COL_LIVE_RATE

    st.session_state.active_rate_source_col = new_source_col_name
    print(f"[DEBUG] Callback set active_rate_source_col to: {new_source_col_name}")
    # No explicit rerun needed, state change handled by Streamlit

# --- Helper Functions ---
# (Could be moved to utils/frontend_utils.py later)
# def prepare_calendar_data(df, focus_date, days_around=7):
#     """Pivots rate data for calendar display around a focus date."""
#     if df is None or df.empty:
#         return pd.DataFrame()
    
#     start_display = focus_date - datetime.timedelta(days=days_around)
#     end_display = focus_date + datetime.timedelta(days=days_around)
    
#     # Ensure Date column is datetime type if not already
#     if not pd.api.types.is_datetime64_any_dtype(df[COL_DATE]):
#         # Attempt conversion, handle potential errors if format is inconsistent
#         try:
#             df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
#         except ValueError:
#             st.error("Calendar View Error: Could not convert 'Date' column to datetime objects.")
#             return pd.DataFrame()
        
#     calendar_df = df[(df[COL_DATE] >= start_display) & (df[COL_DATE] <= end_display)].copy()
    
#     if calendar_df.empty:
#         return pd.DataFrame()
        
#     try:
#         # Use Editable Price for calendar if available and reflects edits
#         pivot = pd.pivot_table(calendar_df, values=COL_EDITABLE_PRICE_SRC, index='Unit Pool', columns=COL_DATE, aggfunc='mean')
#         pivot.columns = [col.strftime('%Y-%m-%d') for col in pivot.columns]
#         return pivot
#     except Exception as e:
#         st.error(f"Error creating calendar pivot: {e}")
#         return pd.DataFrame()

# --- Add apply_filters Function (Milestone 3) ---
def apply_filters(df, filter_state):
    """Applies filters to the DataFrame based on the filter_state dictionary."""
    if df is None or df.empty:
         return pd.DataFrame() # Return empty if no data

    filtered_df = df.copy() # Start with a copy

    # Apply Date Filter (ensure date column is datetime.date or compatible)
    date_col = COL_DATE # Use the constant defined earlier
    if date_col not in filtered_df.columns:
        st.warning(f"Date column '{date_col}' not found for filtering.")
    else:
        # Convert to datetime objects first if not already, then extract date
        if not pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]) and not all(isinstance(d, datetime.date) for d in filtered_df[date_col].dropna()):
            try:
                filtered_df[date_col] = pd.to_datetime(filtered_df[date_col]).dt.date
            except Exception as e:
                st.warning(f"Could not parse Date column '{date_col}' for filtering: {e}")
                # Continue filtering with potentially unparsed dates

        start_date = filter_state.get('filter_start_date')
        end_date = filter_state.get('filter_end_date')
        # Ensure comparison is possible if conversion failed but dates exist
        if start_date and date_col in filtered_df.columns:
             try:
                filtered_df = filtered_df[filtered_df[date_col] >= start_date]
             except TypeError: # Handle case where comparison fails (e.g., comparing string and date)
                 st.warning(f"Could not apply start date filter due to type mismatch in {date_col}.")
        if end_date and date_col in filtered_df.columns:
             try:
                filtered_df = filtered_df[filtered_df[date_col] <= end_date]
             except TypeError:
                 st.warning(f"Could not apply end date filter due to type mismatch in {date_col}.")

    # Apply Multiselect Filters (using source/derived column names)
    multi_select_filters = {
        'filter_properties': COL_PROPERTY_SRC, # Use source name
        'filter_tiers': COL_CALCULATED_TIER_SRC,       # Use source name
        'filter_dow': COL_DAY_OF_WEEK,    # Use derived name
        'filter_flags': COL_FLAG,         # Use standard name
        'filter_statuses': COL_STATUS      # Use standard name
    }
    for state_key, col_name in multi_select_filters.items():
        if col_name not in filtered_df.columns:
             st.warning(f"Multiselect filter column '{col_name}' not found.")
             continue # Skip this filter if column missing
        selected_values = filter_state.get(state_key)
        if selected_values: # If list is not empty
            # Convert column to string for robust comparison, handle potential NaN
            # Also convert selected_values to string in case they are not
            filtered_df = filtered_df[filtered_df[col_name].astype(str).isin([str(v) for v in selected_values])]

    # Apply Numeric Range Filters (using standard/derived column names)
    numeric_filters = {
        'filter_min_occ': (COL_OCC_CURR, '>='), 'filter_max_occ': (COL_OCC_CURR, '<='),
        'filter_min_live_rate': (COL_LIVE_RATE, '>='), 'filter_max_live_rate': (COL_LIVE_RATE, '<='),
        'filter_min_delta': (COL_DELTA, '>='), 'filter_max_delta': (COL_DELTA, '<='),
    }
    for state_key, (col_name, operator) in numeric_filters.items():
         if col_name not in filtered_df.columns:
              st.warning(f"Numeric filter column '{col_name}' not found.")
              continue # Skip if column missing

         filter_value = filter_state.get(state_key)
         if filter_value is not None:
              # Ensure column is numeric, coerce errors to NaN
              numeric_col = pd.to_numeric(filtered_df[col_name], errors='coerce')
              # Filter out rows where conversion failed (NaN)
              valid_rows = numeric_col.notna()
              if operator == '>=':
                   filtered_df = filtered_df[valid_rows & (numeric_col[valid_rows] >= filter_value)]
              elif operator == '<=':
                   filtered_df = filtered_df[valid_rows & (numeric_col[valid_rows] <= filter_value)]

    return filtered_df

# --- Main App Structure --- 
st.write("Configure parameters and generate rates to begin the review process.")

config_area = st.container()
results_area = st.container()

# --- Configuration Area --- 
with config_area:
    st.subheader("1. Configure Rate Generation")
    
    # Use cached function to get properties
    available_properties = backend_interface.get_available_properties()
    if not available_properties:
        st.error("Could not load property list from configuration. Please check config/properties.yaml")
        st.stop()
    
    # Layout for selections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Property Selection (FR1)
        st.session_state.selected_properties = st.multiselect(
            label="Select Property/Unit Pools:",
            options=available_properties,
            default=st.session_state.selected_properties, # Use session state for persistence
            key='prop_select' # Assign key for potential callbacks if needed later
        )
    
    with col2:
        # Start Date Selection (FR1)
        st.session_state.start_date = st.date_input(
            label="Start Date:", 
            value=st.session_state.start_date, 
            key='start_date_input'
        )
        
    with col3:
        # End Date Selection (FR1)
        st.session_state.end_date = st.date_input(
            label="End Date:", 
            value=st.session_state.end_date, 
            key='end_date_input'
        )
        
    # --- Display Options --- 
    with st.expander("Display Options"):
        st.session_state.optional_columns = st.multiselect(
            "Select Optional Columns to Display:",
            options=OPTIONAL_COLS,
            default=st.session_state.optional_columns,
            key='optional_cols_select'
        )
    
    # Generate Button (FR2)
    # We only set the flag here. Processing happens in Milestone 3.
    if st.button("Generate Rates", key='generate_button', type="primary"):
        if not st.session_state.selected_properties:
            st.warning("Please select at least one property.")
            st.session_state.generate_clicked = False # Ensure flag is false if validation fails
        elif st.session_state.start_date > st.session_state.end_date:
             st.warning("Start Date cannot be after End Date.")
             st.session_state.generate_clicked = False
        else:
            st.session_state.generate_clicked = True
            # Reset potentially previously generated data when generating anew
            st.session_state.generated_rates_df = None 
            st.session_state.edited_rates_df = None  # Reset previous edits
            st.session_state.selected_rate_id = None # Reset selection on new generation
            st.session_state.results_are_displayed = False # Reset display flag
            st.session_state.editable_rate_initialized = False # Reset initialization flag
            st.rerun() # Rerun to immediately show spinner in results area
    
    st.markdown("--- ") # Use standard markdown horizontal rule

# --- Results Area --- 
with results_area:
    # Only attempt generation if button was clicked
    if st.session_state.generate_clicked:
        st.subheader("2. Review & Manage Rates") # Show subheader only when generating/showing results
        try:
            with st.spinner("Generating rates..."):
                # Call backend function which now orchestrates generation
                generated_df = backend_interface.trigger_rate_generation(
                    property_selection=st.session_state.selected_properties,
                    start_date=st.session_state.start_date,
                    end_date=st.session_state.end_date
                )

            # Store results in session state
            st.session_state.generated_rates_df = generated_df 
            # st.session_state.edited_rates_df = generated_df.copy() if generated_df is not None else None # Defer copy until after merge
            
            if generated_df is not None and not generated_df.empty:
                # --- Add Live Rate Data Merge --- Start
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
                            # Ensure date format consistency (YYYY-MM-DD string)
                            live_df['date'] = pd.to_datetime(live_df['date']).dt.strftime('%Y-%m-%d')
                            all_live_rates_dfs.append(live_df)
                            # st.write(f"DEBUG: Loaded {len(live_df)} live rates for {prop_name}") # Debug
                        except Exception as e:
                            st.warning(f"Could not load or process live rates file for {prop_name}: {e}")
                    else:
                        st.warning(f"Live rates file not found for {prop_name}: {live_rates_path}")
                        
                if all_live_rates_dfs:
                    combined_live_rates_df = pd.concat(all_live_rates_dfs, ignore_index=True)
                    # Prepare generated_df date column (assuming it's called COL_DATE)
                    # Check if generated_df already has dates as strings
                    if not pd.api.types.is_string_dtype(generated_df[COL_DATE]):
                        generated_df[COL_DATE] = pd.to_datetime(generated_df[COL_DATE]).dt.strftime('%Y-%m-%d')
                    
                    # Perform the merge
                    merged_df = pd.merge(
                        generated_df,
                        combined_live_rates_df,
                        left_on=[COL_LISTING_ID, COL_DATE], # Use the correct constant for listing_id
                        right_on=['listing_id', 'date'],
                        how='left',
                        suffixes=('', '_live') # Add suffix to avoid potential conflicts
                    )
                    
                    # Rename the merged price column to our target name
                    merged_df.rename(columns={'price': COL_LIVE_RATE}, inplace=True)
                    # Ensure the column exists, filling missing with NaN or 0.0? Let's use NaN then fill with 0
                    if COL_LIVE_RATE not in merged_df.columns:
                         merged_df[COL_LIVE_RATE] = 0.0 # Ensure column exists
                    else:
                         # Ensure numeric and fill missing values with 0
                         merged_df[COL_LIVE_RATE] = pd.to_numeric(merged_df[COL_LIVE_RATE], errors='coerce').fillna(0.0)
                    # st.write("DEBUG: Columns after merge:", merged_df.columns.tolist()) # Debug
                else:
                    st.warning("No live rate data loaded. 'Live Rate $' column will be set to $0.00.")
                    merged_df = generated_df.copy()
                    merged_df[COL_LIVE_RATE] = 0.0 # Ensure column exists with 0
                
                # --- Initialize Editable Rate Column based on Default Toggle State ---
                # This happens only once when data is first generated/merged.
                if not st.session_state.get('editable_rate_initialized', False):
                    print("[DEBUG] Running Editable Rate Initialization") # Add debug print
                    initial_source_col = COL_LIVE_RATE # Default to live rate
                    if initial_source_col in merged_df.columns:
                        if COL_EDITABLE_PRICE_SRC not in merged_df.columns:
                             st.info(f"Initializing '{COL_EDITABLE_PRICE_SRC}' based on default '{initial_source_col}'.")
                        # Set or overwrite Editable Price with the default source
                        merged_df[COL_EDITABLE_PRICE_SRC] = pd.to_numeric(merged_df[initial_source_col], errors='coerce').fillna(0.0)
                        st.session_state.editable_rate_initialized = True # Set flag after successful init
                        print("[DEBUG] Initialization complete, flag set to True.")
                    else:
                        st.warning(f"Default source column '{initial_source_col}' not found. Cannot initialize Editable Rate.")
                        # Ensure Editable Rate exists even if source is missing
                        if COL_EDITABLE_PRICE_SRC not in merged_df.columns:
                            merged_df[COL_EDITABLE_PRICE_SRC] = 0.0 # Or np.nan

                # Now store the prepared dataframe in session state
                st.session_state.edited_rates_df = merged_df.copy()
                
                # Set focus date only if data loaded successfully
                st.session_state.focus_date = pd.to_datetime(generated_df[COL_DATE]).min().date()
                st.session_state.results_are_displayed = True # Data loaded/merged, mark results as displayed

            elif st.session_state.generate_clicked: # Handle case where backend returned None or empty
                 st.error("Failed to generate rates or no data found for the selected parameters.")
                 st.session_state.edited_rates_df = None # Clear any old data
                 st.session_state.results_are_displayed = False

        except Exception as e:
            st.error(f"An error occurred during rate generation: {e}")
            st.exception(e) # Show detailed traceback in app
            st.session_state.edited_rates_df = None
            st.session_state.results_are_displayed = False
            st.session_state.generate_clicked = False # Reset flag on error

    # --- Display Area (only show if results are ready) ---
    # --- Apply Rate Source Toggle Logic ---
    # This block runs on every rerun after data is loaded
    if 'edited_rates_df' in st.session_state and isinstance(st.session_state.edited_rates_df, pd.DataFrame):
        active_source = st.session_state.get('active_rate_source_col', COL_LIVE_RATE)
        target_col = COL_EDITABLE_PRICE_SRC
        df = st.session_state.edited_rates_df # Modify state directly before passing down

        if active_source in df.columns and target_col in df.columns:
             print(f"[DEBUG] Applying active source '{active_source}' to '{target_col}'.")
             try:
                 current_editable_head = df[target_col].head().to_string()
                 # Check if update is actually needed to avoid unnecessary writes
                 if not df[target_col].equals(pd.to_numeric(df[active_source], errors='coerce').fillna(0.0)):
                     df[target_col] = pd.to_numeric(df[active_source], errors='coerce').fillna(0.0)
                     st.session_state.edited_rates_df = df # Ensure state is updated if modified
                     print(f"[DEBUG] Updated '{target_col}' from '{active_source}'. New head: {df[target_col].head()}")
                 else:
                      print(f"[DEBUG] '{target_col}' already matches '{active_source}'. No update needed.")
             except Exception as e:
                 st.error(f"Error applying rate source '{active_source}' to '{target_col}': {e}")
        elif active_source not in df.columns:
             st.warning(f"Active source column '{active_source}' not found.")

    if st.session_state.results_are_displayed and st.session_state.edited_rates_df is not None:
        
        # Get the source DataFrame (potentially already edited and with source toggled)
        display_df_source = st.session_state.get('edited_rates_df', pd.DataFrame()).copy() # Work on a copy
        
        # --- Calculate derived columns NEEDED FOR FILTERING directly on the source df --- 
        if not display_df_source.empty:
            # Calculate derived columns if they don't already exist
            if COL_DAY_OF_WEEK not in display_df_source.columns:
                try:
                    if COL_DATE in display_df_source.columns:
                        date_col_dt = pd.to_datetime(display_df_source[COL_DATE], errors='coerce')
                        display_df_source[COL_DAY_OF_WEEK] = date_col_dt.dt.strftime('%A')
                    else:
                        display_df_source[COL_DAY_OF_WEEK] = "N/A"
                except Exception as e:
                    st.warning(f"Could not calculate Day of Week: {e}")
                    display_df_source[COL_DAY_OF_WEEK] = "Error"

            # Delta Calculation
            if COL_DELTA not in display_df_source.columns:
                if COL_LIVE_RATE in display_df_source.columns and COL_SUGGESTED_SRC in display_df_source.columns:
                    live_rate = pd.to_numeric(display_df_source[COL_LIVE_RATE], errors='coerce').fillna(0.0)
                    suggested = pd.to_numeric(display_df_source[COL_SUGGESTED_SRC], errors='coerce')
                    
                    delta = np.where(
                        live_rate != 0, 
                        ((suggested - live_rate) / live_rate) * 100, 
                        np.nan
                    )
                    display_df_source[COL_DELTA] = delta
                else:
                    display_df_source[COL_DELTA] = np.nan
        # --------------------------------------------------------------------------

        # --- Populate Dynamic Filter Options (Milestone 2) ---
        # Define fallback empty lists first
        dynamic_property_options, dynamic_tier_options, dynamic_dow_options, dynamic_flag_options, dynamic_status_options = [], [], [], [], []
        # Now use display_df_source which has derived columns
        if not display_df_source.empty:
            # Use source column names defined earlier
            # Ensure columns exist and handle potential NaNs by converting to string
            if COL_PROPERTY_SRC in display_df_source: dynamic_property_options = sorted(display_df_source[COL_PROPERTY_SRC].astype(str).unique())
            if COL_CALCULATED_TIER_SRC in display_df_source:
                # Use natural sort key for Tiers (Fix for Issue 3)
                unique_tiers = display_df_source[COL_CALCULATED_TIER_SRC].astype(str).unique()
                dynamic_tier_options = sorted(unique_tiers, key=natural_sort_key_tier)
            if COL_DAY_OF_WEEK in display_df_source: dynamic_dow_options = sorted(display_df_source[COL_DAY_OF_WEEK].astype(str).unique()) # Now should exist
            if COL_FLAG in display_df_source: dynamic_flag_options = sorted(display_df_source[COL_FLAG].astype(str).unique())
            if COL_STATUS in display_df_source: dynamic_status_options = sorted(display_df_source[COL_STATUS].astype(str).unique())

        # --- Add Editable Rate Source Toggle UI ---
        st.radio(
            "Set Initial Value for Editable Rate $",
            options=['Use Live Rate', 'Use Suggested Rate'],
            key='rate_source_toggle', # Link to session state
            horizontal=True,
            on_change=update_editable_rate_source # Trigger callback on change
        )
        st.markdown("--- ") # Separator

        with st.expander("Filter Displayed Rates", expanded=True):
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
            with filter_col1:
                # Link to session state (Milestone 2)
                st.date_input("Filter Start Date", key='filter_start_date') # value managed by key
                st.date_input("Filter End Date", key='filter_end_date')
                st.multiselect("Filter Properties", options=dynamic_property_options, key='filter_properties') 
                st.multiselect("Filter Tiers", options=dynamic_tier_options, key='filter_tiers') 
            with filter_col2:
                st.multiselect("Filter Day of Week", options=dynamic_dow_options, key='filter_dow') # Options now populated
                st.multiselect("Filter Flags", options=dynamic_flag_options, key='filter_flags')
                st.multiselect("Filter Status", options=dynamic_status_options, key='filter_statuses')
            with filter_col3:
                st.number_input("Min Occ% (Curr)", key='filter_min_occ', placeholder="Enter min %", step=0.1, format="%.1f")
                st.number_input("Max Occ% (Curr)", key='filter_max_occ', placeholder="Enter max %", step=0.1, format="%.1f")
                st.number_input("Min Live Rate $", key='filter_min_live_rate', placeholder="Enter min $", step=0.01, format="%.2f")
                st.number_input("Max Live Rate $", key='filter_max_live_rate', placeholder="Enter max $", step=0.01, format="%.2f")
            with filter_col4:
                st.number_input("Min Delta %", key='filter_min_delta', placeholder="Enter min %", step=0.1, format="%.1f")
                st.number_input("Max Delta %", key='filter_max_delta', placeholder="Enter max %", step=0.1, format="%.1f")
                st.markdown("<br/>", unsafe_allow_html=True) # Add some space

                # Modified Clear Button to use callback (Fix for Issue 2)
                st.button("Clear All Filters", key="clear_filters_m2_cb", on_click=clear_all_filter_states)

        grid_container = st.container()
        # --- Filter Data Integration (Milestone 3) ---
        # display_df_source already retrieved and includes derived columns now
        if not display_df_source.empty:
             # Create filter_state dict from current st.session_state values
             current_filter_state = {key: st.session_state.get(key) for key in filter_defaults.keys()}
             # Apply filters
             filtered_display_df = apply_filters(display_df_source, current_filter_state) # Apply filters to df with derived cols
        else:
             filtered_display_df = pd.DataFrame() # Start with empty if no source data

        # --- Display Grid with Filtered Data ---
        with grid_container: # Now display the grid using the filtered data
            df_for_editor = filtered_display_df # Use the filtered df which has derived cols
            
            print(f"[DEBUG] Passing DataFrame to data_editor. Target Col (head): {df_for_editor[COL_EDITABLE_PRICE_SRC].head()}") # Log 6
            
            # Ensure Select column exists
            if COL_SELECT not in df_for_editor.columns: df_for_editor.insert(0, COL_SELECT, False)
            
            st.markdown("#### Rate Review Grid")
            # st.dataframe(df_for_editor.head()) # Debug: Check columns before editor
            # --- Add Debug Info --- Start
            # st.write("DEBUG: Columns in DataFrame passed to editor:", df_for_editor.columns.tolist())
            # --- Add Debug Info --- End
            # prev_selected_id = st.session_state.selected_rate_id # Commented out - no longer needed
            
            # --- Dynamic Column Config for Data Editor (Check if COL_DAY_OF_WEEK is included) --- 
            potential_display_order_concepts = [
                # COL_SELECT, COL_VIEW_DETAILS, COL_DATE, COL_PROPERTY, COL_LISTING_NAME, COL_TIER, COL_DAY_OF_WEEK, COL_OCC_CURR, # Removed VIEW_DETAILS
                COL_SELECT, COL_DATE, COL_PROPERTY, COL_LISTING_NAME, COL_TIER, COL_DAY_OF_WEEK, COL_OCC_CURR,
                COL_LIVE_RATE, COL_SUGGESTED, COL_DELTA,
                COL_EDITABLE_PRICE, 
                COL_FLAG] + st.session_state.optional_columns + [COL_STATUS]
            
            # Map display concepts back to the actual SOURCE column names present in the dataframe
            source_col_map = {
                COL_PROPERTY: COL_PROPERTY_SRC,
                COL_LISTING_NAME: "listing_name",
                COL_TIER: COL_CALCULATED_TIER_SRC,
                # COL_LIVE_RATE: COL_BASELINE_SRC, # Remove this mapping
                COL_SUGGESTED: COL_SUGGESTED_SRC,
                COL_EDITABLE_PRICE: COL_EDITABLE_PRICE_SRC
            }
            display_order_actual_cols = []
            for col_concept in potential_display_order_concepts:
                actual_col = source_col_map.get(col_concept, col_concept)
                if actual_col in df_for_editor.columns:
                    display_order_actual_cols.append(actual_col)
                # No need for elif, if concept == actual_col it's handled above
            
            # st.write("Actual Columns for Display Order:", display_order_actual_cols) # Debug
            # --- Add Debug Info --- Start
            # st.write("DEBUG: Actual column names in display order:", display_order_actual_cols)
            # --- Add Debug Info --- End

            full_column_config = {
                COL_SELECT: st.column_config.CheckboxColumn("Select", help="Select rows for batch actions", default=False),
                # COL_VIEW_DETAILS: st.column_config.CheckboxColumn("Details", help="View details for this row", default=False), # Removed
                COL_VIEW_DETAILS: None, # Ensure it's hidden
                COL_ID: None, 
                COL_DATE: st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                COL_PROPERTY_SRC: st.column_config.TextColumn("Property"),
                "listing_name": st.column_config.TextColumn(COL_LISTING_NAME),
                COL_CALCULATED_TIER_SRC: st.column_config.TextColumn("Tier"),
                COL_DAY_OF_WEEK: st.column_config.TextColumn("Day"), 
                # COL_BASELINE_SRC: st.column_config.NumberColumn(COL_LIVE_RATE, format="$%.2f", help="Current live rate (using Baseline source)"), # Remove baseline config
                COL_LIVE_RATE: st.column_config.NumberColumn(COL_LIVE_RATE, format="$%.2f", help="Current live rate from nightly pull"), # Correct config key and label
                COL_SUGGESTED_SRC: st.column_config.NumberColumn("Suggested Rate $", format="$%.2f", help="Price suggested by the engine"),
                COL_DELTA: st.column_config.NumberColumn("Delta %", format="%.1f%%", help="%(Suggested - Live) / Live"),
                COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn("Editable Rate $", format="$%.2f", required=True, min_value=0),
                COL_FLAG: st.column_config.TextColumn("Flag"),
                COL_OCC_CURR: st.column_config.NumberColumn("Occ% Current", format="%.1f%%"),
                COL_OCC_HIST: st.column_config.NumberColumn("Occ% Historical", format="%.1f%%"),
                COL_PACE: st.column_config.NumberColumn("Pace Score", format="%.1f"),
                COL_STATUS: st.column_config.TextColumn("Status"),
                # "day_group": None, # Keep technical columns hidden
                # "booking_window": None,
                # "urgency_band": None,
                # "lookup_error": None
                # Explicitly add technical columns needed for backend but hidden from editor
                COL_LISTING_ID: None,
                COL_TIER_SRC: None,
            }
            # Add any other technical columns that should NOT be displayed but ARE needed by backend
            for col in HIDDEN_COLS:
                 if col not in full_column_config:
                      full_column_config[col] = None
            
            active_column_config = {k: v for k, v in full_column_config.items() 
                                  if k in display_order_actual_cols or (k in full_column_config and full_column_config[k] is None)}
            # st.write("Active Config Keys:", list(active_column_config.keys())) # Debug
            # --- Add Debug Info --- Start
            # st.write("DEBUG: Active config keys passed to editor:", list(active_column_config.keys()))
            # --- Add Debug Info --- End
            
            # Define columns that should always be disabled from editing (using actual source names)
            disabled_cols = [COL_DATE, COL_PROPERTY_SRC, "listing_name", COL_CALCULATED_TIER_SRC, COL_DAY_OF_WEEK, 
                             # COL_BASELINE_SRC, # Remove baseline source
                             COL_LIVE_RATE, # Disable the correct merged column
                             COL_SUGGESTED_SRC, COL_DELTA,
                             COL_FLAG, COL_OCC_CURR, COL_OCC_HIST, COL_PACE, COL_STATUS] + HIDDEN_COLS
            if COL_OCC_HIST not in st.session_state.optional_columns and COL_OCC_HIST in disabled_cols: disabled_cols.remove(COL_OCC_HIST)
            if COL_PACE not in st.session_state.optional_columns and COL_PACE in disabled_cols: disabled_cols.remove(COL_PACE)
            # Filter disabled_cols to only include those actually present in the editor's dataframe
            disabled_cols = [col for col in disabled_cols if col in df_for_editor.columns] 

            # Use source dataframe for editor, but control display/order/config
            edited_df_result = st.data_editor(
                df_for_editor, # Now passing the filtered dataframe
                key='rate_grid_editor',
                hide_index=True,
                column_order=display_order_actual_cols, # Use the list of actual column names
                column_config=active_column_config, # Use filtered config
                disabled=disabled_cols, # Disabled list uses actual column names
                use_container_width=True
            )
            
            # --- Edit Persistence Logic (Milestone 4) ---
            # Compare the DataFrame returned by the editor with the filtered DataFrame passed into it.
            # Reset indices for accurate comparison, as filtering changes the index.
            if not df_for_editor.reset_index(drop=True).equals(edited_df_result.reset_index(drop=True)):
                # Edits were made in the data editor.
                if COL_ID not in edited_df_result.columns:
                    st.error(f"Critical Error: Unique ID column '{COL_ID}' missing after edit. Cannot save changes.")
                elif display_df_source is None or display_df_source.empty:
                    st.error("Cannot save edits: Original data source (edited_rates_df) is missing or empty.")
                else:
                    try:
                        # Use the unique ID (COL_ID) as index for efficient update.
                        edited_subset_indexed = edited_df_result.set_index(COL_ID)
                        original_full_indexed = display_df_source.set_index(COL_ID)

                        # Define the columns that are user-editable in the grid config.
                        editable_source_columns = [COL_EDITABLE_PRICE_SRC, COL_SELECT]

                        # Update the original full DataFrame using the edited subset.
                        # .update aligns on index (COL_ID) and updates only the specified columns.
                        original_full_indexed.update(edited_subset_indexed[editable_source_columns])

                        # Store checkbox selections in session state
                        checkbox_state = edited_df_result.set_index(COL_ID)[COL_SELECT].to_dict()
                        st.session_state.checkbox_selections = checkbox_state

                        # Save the updated full DataFrame back to session state.
                        st.session_state['edited_rates_df'] = original_full_indexed.reset_index()
                        st.toast("Changes saved.", icon="💾")
                        # Rerun to ensure UI consistency after state update.
                        st.rerun()

                    except KeyError as e:
                        # Handle cases where COL_ID or editable columns might be missing unexpectedly.
                        st.error(f"Error saving changes: Could not find index/column '{e}'. Edits might be lost.")
                    except Exception as e:
                        # Catch any other unexpected errors during the update process.
                        st.error(f"An unexpected error occurred while saving edits: {e}")
                        st.exception(e) # Log the full traceback for debugging

            # Ensure Select column exists and restore checkbox state
            if COL_SELECT not in df_for_editor.columns: 
                df_for_editor.insert(0, COL_SELECT, False)

            # Restore checkbox state from session state if available
            if st.session_state.checkbox_selections:
                df_for_editor[COL_SELECT] = df_for_editor[COL_ID].map(st.session_state.checkbox_selections).fillna(False)

            # --- Logic to Handle Detail View Selection --- COMMENTED OUT
            # selected_rows = edited_df_result[edited_df_result[COL_VIEW_DETAILS] == True]
            # current_selection_id = None
            # focus_date_from_selection = None

            # if len(selected_rows) == 1:
            #     selected_index = selected_rows.index[0]
            #     current_selection_id = edited_df_result.loc[selected_index, COL_ID]
            #     focus_date_from_selection = pd.to_datetime(edited_df_result.loc[selected_index, COL_DATE]).date()
            #     if current_selection_id != prev_selected_id:
            #         st.session_state.selected_rate_id = current_selection_id
            #         if focus_date_from_selection:
            #            st.session_state.focus_date = focus_date_from_selection
            #         st.rerun()
            # elif len(selected_rows) > 1:
            #     st.warning("Please select only one row to view details.")
            #     if prev_selected_id:
            #          st.session_state.selected_rate_id = prev_selected_id
            #          prev_row_indices = edited_df_result[edited_df_result[COL_ID] == prev_selected_id].index
            #          if not prev_row_indices.empty:
            #              st.session_state.edited_rates_df.loc[prev_row_indices, COL_VIEW_DETAILS] = True 
            #              st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df[COL_ID] != prev_selected_id, COL_VIEW_DETAILS] = False
            #     else:
            #          st.session_state.selected_rate_id = None
            #          st.session_state.edited_rates_df[COL_VIEW_DETAILS] = False
            #     st.rerun()
            # elif len(selected_rows) == 0 and prev_selected_id is not None:
            #      st.session_state.selected_rate_id = None
            #      st.rerun()

        # --- Actions Container --- (FR10, FR11, FR12)
        st.markdown("--- ")
        actions_container = st.container()
        with actions_container:
            st.markdown("#### Actions")
            action_cols = st.columns(3)
            
            # Pass the current dataframe to action handlers if needed
            current_action_df = st.session_state.edited_rates_df 
            
            with action_cols[0]: # Adjust Selected
                if st.button("Adjust Selected", key='adjust_button'):
                    if current_action_df is not None:
                        selected_for_action = current_action_df[current_action_df['Select'] == True]
                        if not selected_for_action.empty:
                            updates = []
                            for index, row in selected_for_action.iterrows():
                                updates.append({
                                    COL_ID: row[COL_ID],
                                    COL_EDITABLE_PRICE_SRC: row[COL_EDITABLE_PRICE_SRC]
                                })
                            if backend_interface.update_rates(updates):
                                st.toast(f"{len(updates)} rate adjustment(s) logged.", icon="✏️")
                            else:
                                st.error("Failed to log adjustments.")
                        else:
                            st.warning("No rows selected for adjustment.")
                    else:
                         st.warning("No data available to adjust.")

            with action_cols[1]: # Approve Selected
                if st.button("Approve Selected", key='approve_button'):
                    if current_action_df is not None:
                        selected_for_action = current_action_df[current_action_df['Select'] == True]
                        if not selected_for_action.empty:
                            updates = []
                            ids_to_update_locally = []
                            for index, row in selected_for_action.iterrows():
                                updates.append({
                                    COL_ID: row[COL_ID],
                                    COL_STATUS: 'Approved' 
                                })
                                ids_to_update_locally.append(row[COL_ID])
                            
                            if backend_interface.update_rates(updates):
                                st.toast(f"{len(updates)} rate approval(s) logged.", icon="👍")
                                # Update local state
                                st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df[COL_ID].isin(ids_to_update_locally), COL_STATUS] = 'Approved'
                                # Also uncheck 'Select' after action
                                st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df[COL_ID].isin(ids_to_update_locally), 'Select'] = False
                                st.rerun()
                            else:
                                st.error("Failed to log approvals.")
                        else:
                            st.warning("No rows selected for approval.")
                    else:
                        st.warning("No data available to approve.")
                        
            with action_cols[2]: # Push Approved Rates Live
                 if st.button("Push Approved Rates Live", key='push_button', type="secondary"): # Changed type
                     if current_action_df is not None:
                        approved_rates = current_action_df[current_action_df['Status'] == 'Approved']
                        if not approved_rates.empty:
                            approved_ids = approved_rates[COL_ID].tolist()
                            # Add confirmation dialog
                            confirm = st.confirm(f"Push {len(approved_ids)} approved rate(s) live? This will write to an output file.")
                            if confirm:
                                with st.spinner("Pushing rates live..."):
                                    if backend_interface.push_rates_live(approved_ids, approved_rates):
                                        st.toast(f"{len(approved_ids)} approved rate(s) written to output file.", icon="🚀")
                                    else:
                                        st.error("Failed to push rates live.")
                        else:
                            st.warning("No rates currently marked as 'Approved' to push.")
                     else:
                         st.warning("No data available to push.")
            
    # Show initial message if no data generated yet and not clicked
    elif not st.session_state.generate_clicked and st.session_state.edited_rates_df is None:
        st.info("Configure parameters above and click 'Generate Rates' to begin.")

# --- Remove Verification Sidebar --- 
# (Sidebar code removed) 