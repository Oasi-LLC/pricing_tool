# rates/pull/nightly_pull.py

import yaml
import pandas as pd
from datetime import datetime, timedelta
import logging
import logging.handlers # Added for FileHandler
from pathlib import Path
import sys
from typing import List, Dict, Optional

# Determine project root relative to this script's location (rates/pull/nightly_pull.py)
# Assumes the script is in rates/pull/ and config is in config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROPERTY_CONFIG_PATH = PROJECT_ROOT / "config" / "properties.yaml"
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" # Base directory for property data
LOG_DIR = PROJECT_ROOT / "logs"
EXECUTION_LOG_FILE = LOG_DIR / "pull_execution_log.txt"

# Add project root to sys.path to allow absolute imports like rates.api_client
sys.path.insert(0, str(PROJECT_ROOT))

# --- Ensure Log Directory Exists ---
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Setup Logging ---
try:
    from rates.logging_setup import setup_logging, log_error
    # Setup loggers - adjust if setup_logging returns specific loggers you need
    # For simplicity, just getting the main logger for this script.
    setup_logging() # Configure root logger or specific ones
    logger = logging.getLogger(__name__) # Get logger instance for this module
except ImportError as e:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import setup_logging. Using basic logger. Error: {e}")
    # Define a dummy log_error if needed
    def log_error(*args, **kwargs):
        logger.error(f"Error logged (dummy): {kwargs.get('error_reason', 'Unknown error')}")

# --- Setup Execution Logger ---
execution_logger = logging.getLogger('PullExecutionLogger')
execution_logger.setLevel(logging.INFO)
execution_handler = logging.FileHandler(EXECUTION_LOG_FILE, mode='a')
execution_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
execution_handler.setFormatter(execution_formatter)
execution_logger.addHandler(execution_handler)
# Prevent execution logs from propagating to the main logger if configured separately
execution_logger.propagate = False

# --- API Client Import ---
try:
    from rates.api_client import PriceLabsAPI, PriceLabsAPIError
except ImportError as e:
    logger.critical(f"Failed to import PriceLabsAPI. Ensure rates/api_client.py exists and PYTHONPATH is correct. Error: {e}")
    # Define a dummy class if import fails to potentially catch errors later
    class PriceLabsAPI:
        def get_listing_overrides(self, *args, **kwargs):
            logger.error("Dummy PriceLabsAPI called because import failed.")
            raise PriceLabsAPIError("PriceLabsAPI not imported correctly.")
    class PriceLabsAPIError(Exception):
        pass
    # Exit if we can't even get the API client
    sys.exit(1)

# --- Configuration Loading ---
def load_full_config() -> Optional[Dict]:
    """Loads the entire properties configuration from the YAML file."""
    try:
        with open(PROPERTY_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            if 'properties' in config:
                logger.info(f"Successfully loaded property configurations from {PROPERTY_CONFIG_PATH}")
                return config['properties']
            else:
                logger.error(f"'properties' key not found in {PROPERTY_CONFIG_PATH}")
                return None
    except FileNotFoundError:
        logger.error(f"Property configuration file not found at {PROPERTY_CONFIG_PATH}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {PROPERTY_CONFIG_PATH}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading property config: {e}")
        return None

# --- Main Pull Logic ---
def run_nightly_pull():
    logger.info("Starting nightly override pull...")

    # --- Date Calculation ---
    today = datetime.now().date()
    start_date = today
    end_date = today + timedelta(days=365) # Extend to 365 days
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    logger.info(f"Fetching overrides from {start_date_str} to {end_date_str}")

    # Log start of execution
    execution_logger.info(f"START - Fetching overrides from {start_date_str} to {end_date_str}")
    
    error_occurred = None # Flag to track if an error happened
    
    try:
        # --- Load Config ---
        properties_config = load_full_config()
        if not properties_config:
            logger.critical("Failed to load property configurations. Aborting.")
            raise ValueError("Failed to load property configurations.") # Raise error to be caught

        # --- Initialize API Client ---
        try:
            api_client = PriceLabsAPI()
            logger.info("PriceLabs API client initialized.")
        except Exception as e:
            logger.critical(f"Failed to initialize PriceLabs API client: {e}")
            raise # Re-raise to be caught by outer try/except

        # --- Process Each Property ---
        for property_name, config in properties_config.items():
            logger.info(f"--- Processing Property: {property_name} ---")
            property_pms = config.get('pms')
            property_listings = config.get('listings', [])

            if not property_pms:
                logger.warning(f"PMS not defined for property '{property_name}'. Skipping.")
                continue
            if not property_listings:
                logger.warning(f"No listings defined for property '{property_name}'. Skipping.")
                continue

            property_overrides_data = [] # Collect data for this property

            for listing_info in property_listings:
                listing_id = str(listing_info.get('id'))
                listing_name = listing_info.get('name', 'N/A')
                if not listing_id:
                    logger.warning(f"Skipping listing with missing ID in property '{property_name}'")
                    continue

                logger.debug(f"Fetching overrides for Listing ID: {listing_id} (Name: {listing_name}, PMS: {property_pms})")

                try:
                    # Fetch all overrides for the listing
                    overrides_response = api_client.get_listing_overrides(listing_id, pms=property_pms)
                    all_listing_overrides = overrides_response.get('overrides', [])
                    logger.debug(f"Received {len(all_listing_overrides)} total overrides for {listing_id}.")

                    # Filter for fixed price types and date range
                    for override in all_listing_overrides:
                        if override.get('price_type') == 'fixed':
                            override_date_str = override.get('date')
                            if not override_date_str:
                                logger.warning(f"Skipping override for {listing_id} with missing date.")
                                continue

                            try:
                                override_date = datetime.strptime(override_date_str, '%Y-%m-%d').date()
                                if start_date <= override_date <= end_date:
                                    price = override.get('price')
                                    currency = override.get('currency')
                                    min_stay = override.get('min_stay')

                                    if price is not None:
                                        property_overrides_data.append({
                                            'listing_id': listing_id,
                                            'date': override_date_str,
                                            'price': price,
                                            'currency': currency,
                                            'min_stay': min_stay
                                        })
                                    else:
                                        logger.warning(f"Skipping override for {listing_id} on {override_date_str} due to missing price.")

                            except ValueError:
                                logger.warning(f"Skipping override for {listing_id} due to invalid date format: {override_date_str}")
                            except Exception as date_exc:
                                # Log specific date processing error, but don't abort the whole run
                                logger.error(f"Error processing date for override in {listing_id} ({override_date_str}): {date_exc}")

                except PriceLabsAPIError as api_err:
                    logger.error(f"API Error fetching overrides for {listing_id}: {api_err}")
                    # Log error but continue to next listing/property if possible
                    # Log detailed error using log_error if available
                    log_error(
                        logger=logger, # Use current logger
                        error_reason=f"API Error fetching overrides: {api_err}",
                        listing_id=listing_id,
                        listing_name=listing_name,
                        pms_name=property_pms
                        # Add other relevant fields if needed/available
                    )
                except Exception as e:
                    logger.error(f"Unexpected error fetching overrides for {listing_id}: {e}")
                    # Log error but continue to next listing/property if possible
                    log_error(
                        logger=logger,
                        error_reason=f"Unexpected error fetching overrides: {e}",
                        listing_id=listing_id,
                        listing_name=listing_name,
                        pms_name=property_pms
                    )

            # --- Save Property Data to CSV ---
            if property_overrides_data:
                try:
                    output_df = pd.DataFrame(property_overrides_data)
                    # Ensure correct column order
                    output_df = output_df[['listing_id', 'date', 'price', 'currency', 'min_stay']]

                    # Define paths
                    property_data_path = DATA_OUTPUT_DIR / property_name
                    archive_path = property_data_path / "archive"
                    output_filename = f"{property_name}_nightly_pulled_overrides.csv"
                    current_file_path = property_data_path / output_filename
                    
                    # Ensure directories exist
                    property_data_path.mkdir(parents=True, exist_ok=True)
                    archive_path.mkdir(parents=True, exist_ok=True)
                    
                    # Archive existing file if it exists
                    if current_file_path.exists():
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        archive_filename = f"{property_name}_nightly_pulled_overrides_{timestamp}.csv"
                        archive_filepath = archive_path / archive_filename
                        try:
                            current_file_path.rename(archive_filepath)
                            logger.info(f"Archived existing file to {archive_filepath}")
                        except OSError as move_err:
                             logger.error(f"Failed to archive {current_file_path} to {archive_filepath}: {move_err}")
                             # Decide if we should continue or abort? For now, continue and overwrite.
                             logger.warning(f"Proceeding to overwrite {current_file_path} despite archival failure.")

                    # Save new file with consistent name
                    output_df.to_csv(current_file_path, index=False)
                    logger.info(f"Successfully saved {len(output_df)} overrides for property '{property_name}' to {current_file_path}")

                except Exception as save_e:
                    logger.error(f"Failed to save overrides CSV for property '{property_name}': {save_e}")
            else:
                logger.info(f"No fixed overrides found within the date range for property '{property_name}'. No CSV file created.")

        logger.info("Nightly override pull finished.")
        
    except Exception as e:
        error_occurred = e # Store the exception
        logger.exception("An error occurred during the nightly pull process.") # Log full traceback
        execution_logger.error(f"FAILURE - Override pull failed: {type(e).__name__}: {e}")
        
    finally:
        if error_occurred is None:
            execution_logger.info("SUCCESS - Override pull completed.")
        # Failure message is logged in the except block

if __name__ == "__main__":
    run_nightly_pull() 