import streamlit as st
import pandas as pd
import datetime
import traceback # Import traceback for more detailed error logging if needed
import numpy as np # Import numpy for calculations

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
COL_LISTING_ID = "Listing ID"
COL_LISTING_NAME = "Listing Name"
COL_TIER = "Tier"
COL_DAY_OF_WEEK = "Day of Week"
COL_LIVE_RATE = "Live Rate"
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
COL_BASELINE_SRC = "Baseline"
COL_SUGGESTED_SRC = "Suggested"
COL_EDITABLE_PRICE_SRC = "Editable Price"
COL_PROPERTY_SRC = "property"
COL_TIER_SRC = "tier_group"
COL_CALCULATED_TIER_SRC = "calculated_tier"

# Hidden source/technical columns
HIDDEN_COLS = [COL_ID, "listing_id", COL_TIER_SRC, "day_group", "booking_window", "urgency_band", "lookup_error"]
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

# --- Helper Functions ---
# (Could be moved to utils/frontend_utils.py later)
def prepare_calendar_data(df, focus_date, days_around=7):
    """Pivots rate data for calendar display around a focus date."""
    if df is None or df.empty:
        return pd.DataFrame()
    
    start_display = focus_date - datetime.timedelta(days=days_around)
    end_display = focus_date + datetime.timedelta(days=days_around)
    
    # Ensure Date column is datetime type if not already
    if not pd.api.types.is_datetime64_any_dtype(df[COL_DATE]):
        # Attempt conversion, handle potential errors if format is inconsistent
        try:
            df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
        except ValueError:
            st.error("Calendar View Error: Could not convert 'Date' column to datetime objects.")
            return pd.DataFrame()
        
    calendar_df = df[(df[COL_DATE] >= start_display) & (df[COL_DATE] <= end_display)].copy()
    
    if calendar_df.empty:
        return pd.DataFrame()
        
    try:
        # Use Editable Price for calendar if available and reflects edits
        pivot = pd.pivot_table(calendar_df, values=COL_EDITABLE_PRICE_SRC, index='Unit Pool', columns=COL_DATE, aggfunc='mean')
        pivot.columns = [col.strftime('%Y-%m-%d') for col in pivot.columns]
        return pivot
    except Exception as e:
        st.error(f"Error creating calendar pivot: {e}")
        return pd.DataFrame()

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
                st.session_state.edited_rates_df = generated_df.copy() if generated_df is not None else None # Initialize edited state
                
                if generated_df is not None:
                    if not generated_df.empty:
                        st.session_state.focus_date = pd.to_datetime(generated_df['Date']).min().date()
                    else:
                        st.session_state.focus_date = st.session_state.start_date # Fallback if empty df
                    st.toast("Rate generation complete!", icon="✅")
                else:
                    st.error("Rate generation failed or produced no results. Check logs.")
            
        except Exception as e:
            st.error("An unexpected error occurred during rate generation process.")
            st.exception(e) # Show detailed exception info in the UI for debugging
            st.session_state.generated_rates_df = None
            st.session_state.edited_rates_df = None
        finally:
             st.session_state.generate_clicked = False # Always reset flag after attempt

    # Display results if available
    if st.session_state.edited_rates_df is not None:
        # Use a flag in the main session state to track if results area is active
        if not st.session_state.results_are_displayed:
             st.subheader("2. Review & Manage Rates") # Ensure subheader is shown if data loaded
             st.session_state.results_are_displayed = True # Set the flag in the main session state

        current_display_df = st.session_state.edited_rates_df
        
        # --- Calculate derived columns for display (do this every time data is shown) --- 
        if COL_DATE in current_display_df.columns:
            try:
                # Ensure Date is datetime
                date_col = pd.to_datetime(current_display_df[COL_DATE])
                # Day of Week (Use %A for full name)
                current_display_df[COL_DAY_OF_WEEK] = date_col.dt.strftime('%A')
            except Exception as e:
                st.error(f"Error calculating Day of Week: {e}")
                # Assign a default or leave column out if calculation fails?
                if COL_DAY_OF_WEEK not in current_display_df.columns:
                     current_display_df[COL_DAY_OF_WEEK] = "Error"

        # --- Delta calculation (Uncommented) ---
        if COL_BASELINE_SRC in current_display_df.columns and COL_SUGGESTED_SRC in current_display_df.columns:
            live_rate = pd.to_numeric(current_display_df[COL_BASELINE_SRC], errors='coerce')
            suggested = pd.to_numeric(current_display_df[COL_SUGGESTED_SRC], errors='coerce')
            delta_pct = np.where(
                (live_rate.isna() | suggested.isna() | (live_rate == 0)), 
                np.nan, # Assign NaN if inputs invalid or live_rate is 0
                (suggested - live_rate) / live_rate * 100
            )
            current_display_df[COL_DELTA] = delta_pct
        else:
             if COL_DELTA not in current_display_df.columns:
                   current_display_df[COL_DELTA] = np.nan # Ensure column exists even if calculation fails
        # --- End derived column calculation --- 

        # --- Calendar View --- (FR8, FR9)
        calendar_container = st.container()
        with calendar_container:
            st.markdown("#### Contextual Calendar View")
            cal_col1, cal_col2, cal_col3 = st.columns([1, 3, 1])
            with cal_col1:
                 if st.button("< Prev Week", key='prev_week'):
                     st.session_state.focus_date -= datetime.timedelta(days=7)
                     st.rerun()
            with cal_col3:
                if st.button("Next Week >", key='next_week'):
                     st.session_state.focus_date += datetime.timedelta(days=7)
                     st.rerun()
            with cal_col2:
                 st.markdown(f"**Focus Date:** {st.session_state.focus_date.strftime('%Y-%m-%d')}")
            
            # Use current_display_df (editable state) for calendar pivot
            calendar_pivot = prepare_calendar_data(current_display_df, st.session_state.focus_date)
            if not calendar_pivot.empty:
                 # Format NaN properly for display
                 st.dataframe(calendar_pivot.style.format("${:.2f}", na_rep="-").highlight_null(), use_container_width=True)
            else:
                 st.write("No rate data available for the selected week around the focus date.")

        # --- Detail Pane --- (FR6, FR7)
        detail_container = st.container()
        with detail_container:
            if st.session_state.selected_rate_id:
                st.markdown("#### Focus Detail")
                # Find the row in the *current* display dataframe
                selected_row_data = current_display_df[current_display_df['_id'] == st.session_state.selected_rate_id]
                if not selected_row_data.empty:
                    # Pass the actual data Series to the backend function
                    details = backend_interface.get_rate_details(selected_row_data.iloc[0])
                    st.markdown(f"**{COL_PROPERTY}:** {details[COL_PROPERTY]} | **{COL_DATE}:** {details[COL_DATE].strftime('%Y-%m-%d')}")
                    det_col1, det_col2, det_col3 = st.columns(3)
                    with det_col1:
                        st.metric("Suggested Rate", f"${details['Suggested Price']:.2f}")
                        st.metric("Live Rate", f"${details[COL_BASELINE_SRC]:.2f}")
                    with det_col2:
                        st.metric("Current Live Rate", f"${details['Current Live Rate']:.2f}")
                        st.metric("Historical Pace", f"{details['Historical Pace']:.1f}")
                    with det_col3:
                         occ_curr = details['Occupancy %']['Current']
                         occ_hist = details['Occupancy %']['Historical']
                         st.metric(f"{COL_OCC_CURR} vs Hist", f"{occ_curr:.1f}%", f"{occ_curr - occ_hist:.1f}% vs {occ_hist:.1f}% Hist")
                    st.text(f"Flag Reason: {details[COL_FLAG]}")
                else:
                    st.warning("Selected rate ID not found in current data. Please regenerate or select another.")
                    st.session_state.selected_rate_id = None # Clear invalid selection
            else:
                st.info("Select 'View Details' on a row in the grid below to see details here.")
        st.markdown("--- ")

        # --- Display Grid Logic --- (FR4, FR5)
        grid_container = st.container()
        with grid_container:
            # Use the dataframe from session state which now includes derived columns
            df_for_editor = st.session_state.edited_rates_df.copy()
            
            # Ensure Select/View Details columns exist (should already be there)
            if COL_SELECT not in df_for_editor.columns: df_for_editor.insert(0, COL_SELECT, False)
            if COL_VIEW_DETAILS not in df_for_editor.columns: df_for_editor.insert(1, COL_VIEW_DETAILS, False)

            st.markdown("#### Rate Review Grid")
            # st.dataframe(df_for_editor.head()) # Debug: Check columns before editor
            # --- Add Debug Info --- Start
            st.write("DEBUG: Columns in DataFrame passed to editor:", df_for_editor.columns.tolist())
            # --- Add Debug Info --- End
            prev_selected_id = st.session_state.selected_rate_id
            
            # --- Dynamic Column Config for Data Editor (Check if COL_DAY_OF_WEEK is included) --- 
            potential_display_order_concepts = [
                COL_SELECT, COL_VIEW_DETAILS, COL_DATE, COL_PROPERTY, COL_LISTING_NAME, COL_TIER, COL_DAY_OF_WEEK, COL_OCC_CURR,
                COL_LIVE_RATE, COL_SUGGESTED, COL_DELTA,
                COL_EDITABLE_PRICE, 
                COL_FLAG] + st.session_state.optional_columns + [COL_STATUS]
            
            # Map display concepts back to the actual SOURCE column names present in the dataframe
            source_col_map = {
                COL_PROPERTY: COL_PROPERTY_SRC,
                COL_LISTING_NAME: "listing_name",
                COL_TIER: COL_CALCULATED_TIER_SRC,
                COL_LIVE_RATE: COL_BASELINE_SRC,
                COL_SUGGESTED: COL_SUGGESTED_SRC,
                COL_EDITABLE_PRICE: COL_EDITABLE_PRICE_SRC
            }
            display_order_actual_cols = []
            for col_concept in potential_display_order_concepts:
                actual_col = source_col_map.get(col_concept, col_concept)
                if actual_col in df_for_editor.columns:
                    display_order_actual_cols.append(actual_col)
                elif col_concept == actual_col and col_concept in df_for_editor.columns:
                    display_order_actual_cols.append(col_concept)
            
            # st.write("Actual Columns for Display Order:", display_order_actual_cols) # Debug
            # --- Add Debug Info --- Start
            st.write("DEBUG: Actual column names in display order:", display_order_actual_cols)
            # --- Add Debug Info --- End

            full_column_config = {
                COL_SELECT: st.column_config.CheckboxColumn("Select", help="Select rows for batch actions", default=False),
                COL_VIEW_DETAILS: st.column_config.CheckboxColumn("Details", help="View details for this row", default=False),
                COL_ID: None, 
                COL_DATE: st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                COL_PROPERTY_SRC: st.column_config.TextColumn("Property"),
                "listing_name": st.column_config.TextColumn(COL_LISTING_NAME),
                COL_CALCULATED_TIER_SRC: st.column_config.TextColumn("Tier"),
                COL_DAY_OF_WEEK: st.column_config.TextColumn("Day"), 
                COL_BASELINE_SRC: st.column_config.NumberColumn("Live Rate $", format="$%.2f", help="Current live rate (Placeholder)"),
                COL_SUGGESTED_SRC: st.column_config.NumberColumn("Suggested Rate $", format="$%.2f", help="Price suggested by the engine"),
                COL_DELTA: st.column_config.NumberColumn("Delta %", format="%.1f%%", help="%(Suggested - Live) / Live"),
                COL_EDITABLE_PRICE_SRC: st.column_config.NumberColumn("Editable Rate $", format="$%.2f", required=True, min_value=0),
                COL_FLAG: st.column_config.TextColumn("Flag"),
                COL_OCC_CURR: st.column_config.NumberColumn("Occ% Current", format="%.1f%%"),
                COL_OCC_HIST: st.column_config.NumberColumn("Occ% Historical", format="%.1f%%"),
                COL_PACE: st.column_config.NumberColumn("Pace Score", format="%.1f"),
                COL_STATUS: st.column_config.TextColumn("Status"),
                "day_group": None,
                "booking_window": None,
                "urgency_band": None,
                "lookup_error": None
            }
            
            active_column_config = {k: v for k, v in full_column_config.items() 
                                  if k in display_order_actual_cols or (k in full_column_config and full_column_config[k] is None)}
            # st.write("Active Config Keys:", list(active_column_config.keys())) # Debug
            # --- Add Debug Info --- Start
            st.write("DEBUG: Active config keys passed to editor:", list(active_column_config.keys()))
            # --- Add Debug Info --- End
            
            # Define columns that should always be disabled from editing (using actual source names)
            disabled_cols = [COL_DATE, COL_PROPERTY_SRC, "listing_name", COL_CALCULATED_TIER_SRC, COL_DAY_OF_WEEK, COL_BASELINE_SRC, COL_SUGGESTED_SRC, COL_DELTA,
                             COL_FLAG, COL_OCC_CURR, COL_OCC_HIST, COL_PACE, COL_STATUS] + HIDDEN_COLS
            if COL_OCC_HIST not in st.session_state.optional_columns and COL_OCC_HIST in disabled_cols: disabled_cols.remove(COL_OCC_HIST)
            if COL_PACE not in st.session_state.optional_columns and COL_PACE in disabled_cols: disabled_cols.remove(COL_PACE)
            disabled_cols = [col for col in disabled_cols if col in df_for_editor.columns] 

            # Use source dataframe for editor, but control display/order/config
            edited_df_result = st.data_editor(
                df_for_editor, 
                key='rate_grid_editor',
                hide_index=True,
                column_order=display_order_actual_cols, # Use the list of actual column names
                column_config=active_column_config, # Use filtered config
                disabled=disabled_cols, # Disabled list uses actual column names
                use_container_width=True
            )
            
            # No merge needed now as we edit the full df and just control display
            st.session_state.edited_rates_df = edited_df_result 
            
            # --- Logic to Handle Detail View Selection --- 
            selected_rows = edited_df_result[edited_df_result[COL_VIEW_DETAILS] == True]
            current_selection_id = None
            focus_date_from_selection = None

            if len(selected_rows) == 1:
                selected_index = selected_rows.index[0]
                current_selection_id = edited_df_result.loc[selected_index, COL_ID]
                focus_date_from_selection = pd.to_datetime(edited_df_result.loc[selected_index, COL_DATE]).date()
                if current_selection_id != prev_selected_id:
                    st.session_state.selected_rate_id = current_selection_id
                    if focus_date_from_selection:
                       st.session_state.focus_date = focus_date_from_selection
                    st.rerun()
            elif len(selected_rows) > 1:
                st.warning("Please select only one row to view details.")
                if prev_selected_id:
                     st.session_state.selected_rate_id = prev_selected_id
                     prev_row_indices = edited_df_result[edited_df_result[COL_ID] == prev_selected_id].index
                     if not prev_row_indices.empty:
                         st.session_state.edited_rates_df.loc[prev_row_indices, COL_VIEW_DETAILS] = True 
                         st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df[COL_ID] != prev_selected_id, COL_VIEW_DETAILS] = False
                else:
                     st.session_state.selected_rate_id = None
                     st.session_state.edited_rates_df[COL_VIEW_DETAILS] = False
                st.rerun()
            elif len(selected_rows) == 0 and prev_selected_id is not None:
                 st.session_state.selected_rate_id = None
                 st.rerun()

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