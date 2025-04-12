import streamlit as st
import pandas as pd
import datetime
import traceback # Import traceback for more detailed error logging if needed

# Import backend interface functions
from utils import backend_interface

# Set page config
st.set_page_config(layout="wide", page_title="Rate Review Tool")

# Title
st.title("Internal Rate Review & Management Tool")

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

# --- Helper Functions ---
# (Could be moved to utils/frontend_utils.py later)
def prepare_calendar_data(df, focus_date, days_around=7):
    """Pivots rate data for calendar display around a focus date."""
    if df is None or df.empty:
        return pd.DataFrame()
    
    start_display = focus_date - datetime.timedelta(days=days_around)
    end_display = focus_date + datetime.timedelta(days=days_around)
    
    # Ensure Date column is datetime type if not already
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        # Attempt conversion, handle potential errors if format is inconsistent
        try:
            df['Date'] = pd.to_datetime(df['Date']).dt.date
        except ValueError:
            st.error("Calendar View Error: Could not convert 'Date' column to datetime objects.")
            return pd.DataFrame()
        
    calendar_df = df[(df['Date'] >= start_display) & (df['Date'] <= end_display)].copy()
    
    if calendar_df.empty:
        return pd.DataFrame()
        
    try:
        # Use Editable Price for calendar if available and reflects edits
        pivot = pd.pivot_table(calendar_df, values='Editable Price', index='Unit Pool', columns='Date', aggfunc='mean')
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
        if 'results_are_displayed' not in st.session_state:
             st.subheader("2. Review & Manage Rates") # Ensure subheader is shown if data loaded
             st.session_state.results_are_displayed = True # Set the flag in the main session state

        current_display_df = st.session_state.edited_rates_df
        
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
                    st.markdown(f"**Unit Pool:** {details['Unit Pool']} | **Date:** {details['Date'].strftime('%Y-%m-%d')}")
                    det_col1, det_col2, det_col3 = st.columns(3)
                    with det_col1:
                        st.metric("Suggested Price", f"${details['Suggested Price']:.2f}")
                        st.metric("Baseline Price", f"${details['Baseline']:.2f}")
                    with det_col2:
                        st.metric("Current Live Rate", f"${details['Current Live Rate']:.2f}")
                        st.metric("Historical Pace", f"{details['Historical Pace']:.1f}")
                    with det_col3:
                         occ_curr = details['Occupancy %']['Current']
                         occ_hist = details['Occupancy %']['Historical']
                         st.metric("Occupancy % (Curr vs Hist)", f"{occ_curr:.1f}%", f"{occ_curr - occ_hist:.1f}% vs {occ_hist:.1f}% Hist")
                    st.text(f"Flag Reason: {details['Flag Reason']}")
                else:
                    st.warning("Selected rate ID not found in current data. Please regenerate or select another.")
                    st.session_state.selected_rate_id = None # Clear invalid selection
            else:
                st.info("Select 'View Details' on a row in the grid below to see details here.")
        st.markdown("--- ")

        # --- Display Grid Logic --- (FR4, FR5)
        grid_container = st.container()
        with grid_container:
            df_for_editor = current_display_df.copy() # Work with a copy for the editor
            
            # Ensure Select/View Details columns exist
            if 'Select' not in df_for_editor.columns:
                df_for_editor.insert(0, 'Select', False)
            if 'View Details' not in df_for_editor.columns:
                df_for_editor.insert(1, 'View Details', False)

            st.markdown("#### Rate Review Grid")
            prev_selected_id = st.session_state.selected_rate_id

            edited_df_result = st.data_editor(
                df_for_editor,
                key='rate_grid_editor',
                hide_index=True,
                column_order=("Select", "View Details", "Date", "Unit Pool", "Suggested", "Editable Price", "Flag", "Baseline", "Occ% (Curr)", "Occ% (Hist)", "Pace", "Status"),
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", help="Select rows for batch actions", default=False),
                    "View Details": st.column_config.CheckboxColumn("Details", help="View details for this row", default=False),
                    "_id": None, 
                    "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    "Suggested": st.column_config.NumberColumn("Suggested $", format="$%.2f", help="Price suggested by the engine"),
                    "Baseline": st.column_config.NumberColumn("Baseline $", format="$%.2f"),
                    "Occ% (Curr)": st.column_config.NumberColumn("Occ% Current", format="%.1f%%"),
                    "Occ% (Hist)": st.column_config.NumberColumn("Occ% Historical", format="%.1f%%"),
                    "Pace": st.column_config.NumberColumn("Pace Score", format="%.1f"),
                    "Editable Price": st.column_config.NumberColumn("Editable Price $", format="$%.2f", required=True, min_value=0),
                    "Flag": st.column_config.TextColumn("Flag"),
                    "Status": st.column_config.TextColumn("Status")
                },
                 disabled=["_id", "Date", "Unit Pool", "Suggested", "Flag", "Baseline", "Occ% (Curr)", "Occ% (Hist)", "Pace", "Status", "property", "listing_id", "tier_group", "day_group", "booking_window", "urgency_band", "lookup_error"], # Disable calculated/source cols
                use_container_width=True
            )
            
            # Store result back immediately
            st.session_state.edited_rates_df = edited_df_result
            
            # --- Logic to Handle Detail View Selection --- 
            selected_rows = edited_df_result[edited_df_result['View Details'] == True]
            # ... (Keep existing detail selection logic using edited_df_result) ...
            current_selection_id = None
            focus_date_from_selection = None

            if len(selected_rows) == 1:
                selected_index = selected_rows.index[0]
                current_selection_id = edited_df_result.loc[selected_index, '_id']
                focus_date_from_selection = pd.to_datetime(edited_df_result.loc[selected_index, 'Date']).date()
                if current_selection_id != prev_selected_id:
                    st.session_state.selected_rate_id = current_selection_id
                    if focus_date_from_selection:
                       st.session_state.focus_date = focus_date_from_selection
                    st.rerun()
            elif len(selected_rows) > 1:
                st.warning("Please select only one row to view details.")
                if prev_selected_id:
                     st.session_state.selected_rate_id = prev_selected_id
                     prev_row_indices = edited_df_result[edited_df_result['_id'] == prev_selected_id].index
                     if not prev_row_indices.empty:
                         st.session_state.edited_rates_df.loc[prev_row_indices, 'View Details'] = True 
                         st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df['_id'] != prev_selected_id, 'View Details'] = False
                else:
                     st.session_state.selected_rate_id = None
                     st.session_state.edited_rates_df['View Details'] = False
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
                                    '_id': row['_id'],
                                    'Editable Price': row['Editable Price']
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
                                    '_id': row['_id'],
                                    'Status': 'Approved' 
                                })
                                ids_to_update_locally.append(row['_id'])
                            
                            if backend_interface.update_rates(updates):
                                st.toast(f"{len(updates)} rate approval(s) logged.", icon="👍")
                                # Update local state
                                st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df['_id'].isin(ids_to_update_locally), 'Status'] = 'Approved'
                                # Also uncheck 'Select' after action
                                st.session_state.edited_rates_df.loc[st.session_state.edited_rates_df['_id'].isin(ids_to_update_locally), 'Select'] = False
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
                            approved_ids = approved_rates['_id'].tolist()
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