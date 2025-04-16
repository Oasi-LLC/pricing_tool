import streamlit as st
import pandas as pd
import datetime
import yaml
from pathlib import Path
import traceback
import uuid # For generating unique IDs
from typing import Optional, Dict # Import Dict
import logging # <-- Add logging import

# --- Import necessary functions from the pricing engine --- 
# Assuming PYTHONPATH is set correctly or the structure allows these imports
# Adjust relative paths if needed based on execution context
from src.pricing_engine import dataloader, calculator, utils

CONFIG_PATH = Path("config/properties.yaml")
OUTPUT_DIR = Path("data/outputs")
LOG_DIR = Path("logs") # <-- Define log directory
LOG_DIR.mkdir(parents=True, exist_ok=True) # <-- Ensure log directory exists

# --- Cached Functions --- 

@st.cache_data(ttl=3600) # Cache for 1 hour
def load_properties_config():
    """Loads the properties configuration from YAML."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        if "properties" not in config or not isinstance(config["properties"], dict):
            st.error("Invalid properties.yaml structure: Missing top-level 'properties' key or it's not a dictionary.")
            return None
        print(f"Loaded properties config from {CONFIG_PATH}")
        return config["properties"]
    except FileNotFoundError:
        st.error(f"Configuration file not found: {CONFIG_PATH}")
        return None
    except yaml.YAMLError as e:
        st.error(f"Error parsing YAML configuration file {CONFIG_PATH}: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred loading configuration: {e}")
        return None

@st.cache_data
def get_available_properties() -> list:
    """Returns a list of available property keys from the config."""
    properties_config = load_properties_config()
    if properties_config:
        return list(properties_config.keys())
    return []

# Caching get_rate_details might be less useful if it just formats passed data,
# but can be added if it performs expensive lookups later.
# @st.cache_data
def get_rate_details(rate_data_row: pd.Series) -> dict:
    """Extracts and formats details for a specific rate from its data row."""
    # This function now expects the actual data row (Pandas Series) as input
    # Modification in app.py needed: Pass the row instead of just the ID.
    if rate_data_row is None or rate_data_row.empty:
        return {'Unit Pool': 'Unknown', 'Date': datetime.date.today(), 'Suggested Price': 0.0, 'Current Live Rate': 0.0, 'Baseline': 0.0, 'Flag Reason': '', 'Occupancy %': {'Current': 0.0, 'Historical': 0.0}, 'Historical Pace': 0.0, 'lookup_error': ''}

    # Extract details - use .get() for robustness against missing columns
    details = {
        'Unit Pool': rate_data_row.get('Unit Pool', 'N/A'),
        'Date': pd.to_datetime(rate_data_row.get('Date')).date() if pd.notna(rate_data_row.get('Date')) else datetime.date.today(),
        'Suggested Price': float(rate_data_row.get('Suggested', 0.0)) if pd.notna(rate_data_row.get('Suggested')) else 0.0,
        'Current Live Rate': float(rate_data_row.get('Current Live Rate', 0.0)) if pd.notna(rate_data_row.get('Current Live Rate')) else 0.0, # Assuming this column exists or is added
        'Baseline': float(rate_data_row.get('Baseline', 0.0)) if pd.notna(rate_data_row.get('Baseline')) else 0.0,
        'Flag Reason': rate_data_row.get('Flag', ''), # Use Flag column for reason for now
        'Occupancy %': {
            'Current': float(rate_data_row.get('Occ% (Curr)', 0.0)) if pd.notna(rate_data_row.get('Occ% (Curr)')) else 0.0,
            'Historical': float(rate_data_row.get('Occ% (Hist)', 0.0)) if pd.notna(rate_data_row.get('Occ% (Hist)')) else 0.0
        },
        'Historical Pace': float(rate_data_row.get('Pace', 0.0)) if pd.notna(rate_data_row.get('Pace')) else 0.0,
        'lookup_error': rate_data_row.get('lookup_error', '') # Add the lookup error message
    }
    return details


# --- Core Logic Functions (No Caching - need fresh results) ---

def trigger_rate_generation(property_selection: list, start_date: datetime.date, end_date: datetime.date) -> Optional[pd.DataFrame]:
    """Orchestrates loading data and calculating rates for selected properties/dates."""

    # --- Setup Logging for this run ---
    run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = LOG_DIR / f"rate_generation_{run_timestamp}.log"
    # Configure logging (basic setup, customize format/level as needed)
    # Remove existing handlers to avoid duplicate logs if function is called multiple times
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            # logging.StreamHandler() # Optionally add stream handler for console output too
        ]
    )
    logging.info(f"Starting rate generation run. Log file: {log_filename}")
    logging.info(f"Properties selected: {property_selection}")
    logging.info(f"Date range: {start_date} to {end_date}")
    # --- End Logging Setup ---

    all_properties_config = load_properties_config()
    if not all_properties_config:
        logging.error("Failed to load properties configuration.") # <-- Log error
        return None

    all_results = []
    today = datetime.date.today()
    logging.info(f"Reference date (today): {today}") # <-- Log info

    for prop_name in property_selection:
        logging.info(f"Processing property: {prop_name}") # <-- Log info
        if prop_name not in all_properties_config:
            st.warning(f"Configuration not found for property: {prop_name}. Skipping.")
            logging.warning(f"Configuration not found for property: {prop_name}. Skipping.") # <-- Log warning
            continue

        prop_config = all_properties_config[prop_name]
        listing_ids_for_property = [str(listing['id']) for listing in prop_config.get('listings', []) if 'id' in listing]

        if not listing_ids_for_property:
            st.warning(f"No listing IDs found in config for property: {prop_name}. Skipping.")
            logging.warning(f"No listing IDs found in config for property: {prop_name}. Skipping.") # <-- Log warning
            continue

        try:
            logging.info(f"--- Loading data for {prop_name} ---") # <-- Log info
            # Load event multipliers along with other data
            rate_table_df, date_tier_map, booked_blocked_set, occupancy_map, event_multiplier_map = dataloader.load_and_preprocess_data(prop_name, prop_config)
            logging.info(f"--- Data loaded for {prop_name}. Calculating rates... ---") # <-- Log info

            date_range = pd.date_range(start_date, end_date, freq='D')

            for current_date in date_range:
                current_date_obj = current_date.date()
                current_date_str = utils.format_date(current_date_obj)
                day_group = utils.get_day_group(current_date_obj)
                booking_window = utils.get_booking_window_label(current_date_obj, today, prop_config.get('booking_window_definitions', []))
                tier_group = date_tier_map.get(current_date_str)
                occupancy_pct = occupancy_map.get(current_date_str, 0.0)
                urgency_band = utils.get_urgency_band(current_date_obj, today, prop_config.get('urgency_band_definitions', []))

                if not tier_group:
                    # st.warning(f"Tier group not found for {current_date_str} in property {prop_name}. Skipping rate calculation for this date.")
                    logging.warning(f"Property {prop_name}: Tier group not found for {current_date_str}. Skipping rate calculation for this date.") # <-- Log warning
                    # Option: Create a result row indicating missing tier?
                    continue # Skip this date if no tier

                # Check for event multiplier for this date
                event_multiplier = None
                if event_multiplier_map and current_date_str in event_multiplier_map:
                    event_multiplier = event_multiplier_map[current_date_str]

                for listing_id in listing_ids_for_property:
                    rate_group_key = calculator._get_rate_group_for_listing_id(listing_id, prop_config)
                    if not rate_group_key:
                         # st.warning(f"Rate group key not found for listing {listing_id} in property {prop_name}. Skipping.")
                         logging.warning(f"Property {prop_name}: Rate group key not found for listing {listing_id}. Skipping.") # <-- Log warning
                         continue

                    suggested_rate = None
                    error_msg = None
                    flag = '' # Placeholder for flag logic
                    baseline = 0.0 # Placeholder for baseline logic
                    occ_curr = occupancy_pct
                    occ_hist = 0.0 # Placeholder
                    pace = 0.0 # Placeholder
                    calculated_tier = None # Initialize calculated tier

                    # --- Check if Booked/Blocked ---
                    if (listing_id, current_date_str) in booked_blocked_set:
                        flag = '🔒 Booked'
                        # Skip rate calculation, set rates to None or 0? Let's use None.
                        suggested_rate = None
                        adjusted_rate = None # Not applicable
                        calculated_tier = None # Not applicable
                        error_msg = None # Not applicable
                    else:
                        # --- Proceed with rate calculation only if not booked/blocked ---

                        # Check adjustment rules first
                        # Now returns a tuple: (rate, tier)
                        adjusted_rate, calculated_tier_from_adjustment = calculator.apply_adjustment_rules(
                            current_date=current_date_obj,
                            listing_id=listing_id,
                            occupancy_pct=occupancy_pct,
                            rate_table_df=rate_table_df,
                            date_tier_map=date_tier_map,
                            booked_blocked_set=booked_blocked_set,
                            booking_window_label=booking_window,
                            property_config=prop_config,
                            today=today
                        )

                        if adjusted_rate is not None:
                            suggested_rate = adjusted_rate
                            flag = '↕️'
                            # Use the tier returned by the adjustment rule logic
                            calculated_tier = calculated_tier_from_adjustment
                        else:
                            # Standard lookup if no adjustment rule
                            suggested_rate, calculated_tier, error_msg = calculator.lookup_rate(
                                rate_table_df=rate_table_df,
                                tier_group=tier_group,
                                day_group=day_group,
                                booking_window=booking_window,
                                occupancy_pct=occupancy_pct,
                                urgency_band=urgency_band,
                                rate_group_key=rate_group_key
                            )

                        # Apply event multiplier AFTER base rate calculation (adjustment or lookup)
                        if suggested_rate is not None and event_multiplier is not None:
                            suggested_rate *= event_multiplier
                            # Prepend event flag, keep existing flags if any
                            flag = "🗓️ " + flag

                        if error_msg:
                            # Decide how to handle lookup errors - skip row, default rate, specific flag?
                            # st.warning(f"Rate lookup error for {listing_id} on {current_date_str}: {error_msg}")
                            logging.warning(f"Rate lookup error for Prop:{prop_name} Listing:{listing_id} Date:{current_date_str} - {error_msg}") # <-- Log the specific error
                            flag = '❌ Error' # Indicate lookup error
                            suggested_rate = None # Ensure rate is None on error

                    # Generate a unique ID for this rate instance
                    # Combine key elements for a somewhat readable ID
                    rate_id = f"rate_{prop_name}_{listing_id}_{current_date_str}_{uuid.uuid4().hex[:4]}"

                    # Find listing name from config (Corrected lookup for list of dicts)
                    listing_name = next((item.get('name', listing_id) for item in prop_config.get('listings', []) if str(item.get('id')) == listing_id), listing_id) # Fallback to ID

                    # TODO: Implement actual logic for Baseline, Occ% Hist, Pace, Flagging
                    # These might require more historical data loading or comparison logic

                    # Append result row
                    all_results.append({
                        '_id': rate_id,
                        'Date': current_date_obj,
                        'Unit Pool': prop_name, # Assign prop_name (e.g., 'fb1') to Unit Pool
                        'listing_name': listing_name, # Assign looked-up name here
                        'Suggested': suggested_rate,
                        'Flag': flag.strip(), # Remove trailing space if only event flag
                        'Baseline': baseline,
                        'Occ% (Curr)': occ_curr,
                        'Occ% (Hist)': occ_hist,
                        'Pace': pace,
                        'Editable Price': suggested_rate if suggested_rate is not None else 0.0, # Default editable to suggested
                        'Status': 'Needs Review',
                        # Include raw data for potential detail view needs?
                        'property': prop_name,
                        'listing_id': listing_id,
                        'tier_group': tier_group,
                        'day_group': day_group,
                        'booking_window': booking_window,
                        'urgency_band': urgency_band,
                        'lookup_error': error_msg,
                        'calculated_tier': calculated_tier, # Store the specific calculated tier
                        'tier_group': tier_group, # Keep original tier_group for reference if needed
                        'day_group': day_group,
                    })

        except (FileNotFoundError, KeyError, ValueError) as e:
            st.error(f"Error processing property {prop_name}: {e}")
            logging.error(f"Error processing property {prop_name}: {e}") # Log main error
            logging.error(f"{traceback.format_exc()}") # Log traceback separately
            traceback.print_exc() # Print full traceback for debugging
            continue # Skip to next property on error
        except Exception as e:
            st.error(f"Unexpected error processing property {prop_name}: {e}")
            logging.error(f"Unexpected error processing property {prop_name}: {e}") # Log main error
            logging.error(f"{traceback.format_exc()}") # Log traceback separately
            traceback.print_exc()
            continue

    if not all_results:
        st.warning("No rate results were generated. Check configuration and data files.")
        logging.warning("No rate results were generated.") # <-- Log warning
        return None

    logging.info(f"--- Rate calculation complete. {len(all_results)} total rate entries generated. ---") # <-- Log info
    results_df = pd.DataFrame(all_results)
    return results_df


def update_rates(updates: list):
    """Logs rate updates (adjustments/approvals). For MVP, writes to a log file."""
    log_file = OUTPUT_DIR / "updates_log.csv"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entries = []

    for update in updates:
        log_entry = {
            'timestamp': now,
            'rate_id': update.get('_id', update.get('listing_id')),  # Try _id first, then listing_id as fallback
            'new_price': update.get('Editable Price'),
            'new_status': update.get('Status', 'Updated')  # Default to 'Updated' if no status provided
        }
        log_entries.append(log_entry)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        log_df = pd.DataFrame(log_entries)
        
        # Check if file exists to append header correctly
        write_header = not log_file.exists()
        log_df.to_csv(log_file, mode='a', header=write_header, index=False)
        return True
    except Exception as e:
        traceback.print_exc()
        st.error(f"Error logging updates to {log_file}: {e}")
        return False

def push_rates_live(approved_rate_ids: list, all_rates_df: pd.DataFrame):
    """Writes approved rates to an output CSV file."""
    if all_rates_df is None or all_rates_df.empty:
        st.error("Cannot push rates: No rate data available.")
        return False
    if not approved_rate_ids:
        st.warning("No approved rate IDs provided to push.")
        return False # Or True, depending if this is considered an error

    # Filter the DataFrame provided from the Streamlit app's session state
    rates_to_push = all_rates_df[all_rates_df['_id'].isin(approved_rate_ids)].copy()

    if rates_to_push.empty:
        st.warning("No matching rates found for the approved IDs provided.")
        return False

    # Define output file path
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"pushed_rates_{timestamp}.csv"

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        # Select and order columns for output (adjust as needed)
        output_columns = ['Date', 'Unit Pool', 'listing_id', 'Editable Price', 'Status', '_id']
        # Filter columns, handling potential missing ones gracefully
        output_columns = [col for col in output_columns if col in rates_to_push.columns]
        rates_to_push[output_columns].to_csv(output_file, index=False)
        print(f"Successfully wrote {len(rates_to_push)} approved rates to {output_file}")
        return True
    except Exception as e:
        st.error(f"Error writing approved rates to {output_file}: {e}")
        traceback.print_exc()
        return False 