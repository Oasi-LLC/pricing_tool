# rates/pull/nightly_pull.py

import yaml
import pandas as pd
from datetime import datetime, timedelta
import logging
import logging.handlers # Added for FileHandler
from pathlib import Path
import sys
import time # Add this import
from typing import List, Dict, Optional
import requests

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

# --- Retry Logic for API Calls ---
def fetch_overrides_with_retry(api_client, listing_id: str, pms: str, max_retries: int = 3, retry_delay: int = 30) -> Optional[Dict]:
    """Fetch overrides for a listing with retry logic and rate limit handling."""
    listing_name = "Unknown"  # Will be updated by caller if available
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Fetching overrides for {listing_id} (attempt {attempt + 1}/{max_retries})")
            overrides_response = api_client.get_listing_overrides(listing_id, pms=pms)
            logger.debug(f"Successfully fetched overrides for {listing_id}")
            return overrides_response
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limited (429) for {listing_id}, waiting {retry_delay}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Overrides fetch failed after {max_retries} attempts due to rate limiting for {listing_id}")
                    raise e
            else:
                logger.error(f"Overrides fetch failed with HTTP error for {listing_id}: {e}")
                raise e
                
        except PriceLabsAPIError as api_err:
            if "429" in str(api_err) or "rate limit" in str(api_err).lower():
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limited for {listing_id}, waiting {retry_delay}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Overrides fetch failed after {max_retries} attempts due to rate limiting for {listing_id}")
                    raise api_err
            else:
                logger.error(f"API Error fetching overrides for {listing_id}: {api_err}")
                raise api_err
                
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Overrides fetch failed for {listing_id}, waiting {retry_delay}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Overrides fetch failed with error for {listing_id}: {e}")
                raise e
    
    return None

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
def run_nightly_pull(progress_callback=None, status_callback=None):
    """
    Run nightly pull with optional progress callbacks for UI updates.
    
    Args:
        progress_callback: Function to call with progress (0.0 to 1.0)
        status_callback: Function to call with status messages
    """
    logger.info("Starting nightly override pull...")
    
    if status_callback:
        status_callback("Starting nightly override pull...")

    # --- Date Calculation ---
    from utils.date_manager import get_nightly_pull_range
    
    start_date, end_date = get_nightly_pull_range()
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    today_str = datetime.now().date().strftime('%Y-%m-%d')
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

        # --- Initialize API Client with Connection Pooling ---
        try:
            api_client = PriceLabsAPI()
            logger.info("PriceLabs API client initialized with connection pooling.")
            logger.info("Using persistent HTTP session for all API calls to improve performance.")
        except Exception as e:
            logger.critical(f"Failed to initialize PriceLabs API client: {e}")
            raise # Re-raise to be caught by outer try/except

        # --- Process Each Property ---
        total_properties = len(properties_config)
        for i, (property_name, config) in enumerate(properties_config.items()):
            logger.info(f"--- Processing Property: {property_name} ---")
            
            # Update progress
            if progress_callback:
                progress = (i + 1) / total_properties
                progress_callback(progress)
            
            if status_callback:
                status_callback(f"Processing {property_name} ({i+1}/{total_properties})")
            property_pms = config.get('pms')
            property_listings = config.get('listings', [])

            if not property_pms:
                logger.warning(f"PMS not defined for property '{property_name}'. Skipping.")
                continue
            if not property_listings:
                logger.warning(f"No listings defined for property '{property_name}'. Skipping.")
                continue

            property_overrides_data = [] # Collect data for this property
            failed_listings = [] # Track failed listings for retry

            # First pass: Process all listings with retry logic
            for listing_info in property_listings:
                listing_id = str(listing_info.get('id'))
                listing_name = listing_info.get('name', 'N/A')
                if not listing_id:
                    logger.warning(f"Skipping listing with missing ID in property '{property_name}'")
                    continue

                logger.debug(f"Fetching overrides for Listing ID: {listing_id} (Name: {listing_name}, PMS: {property_pms})")

                try:
                    # Add a 0.5-second delay before the API call to respect rate limits (optimized)
                    time.sleep(0.5)
                    
                    # Use retry logic for fetching overrides
                    overrides_response = fetch_overrides_with_retry(api_client, listing_id, property_pms, max_retries=3, retry_delay=30)
                    
                    if overrides_response is None:
                        logger.error(f"Failed to fetch overrides for {listing_id} after all retries")
                        failed_listings.append(listing_info)
                        continue
                    
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

                except Exception as e:
                    logger.error(f"Unexpected error processing {listing_id}: {e}")
                    failed_listings.append(listing_info)
                    # Log detailed error using log_error if available
                    log_error(
                        logger=logger,
                        error_reason=f"Unexpected error processing listing: {e}",
                        listing_id=listing_id,
                        listing_name=listing_name,
                        pms_name=property_pms
                    )

            # Second pass: Retry failed listings sequentially with longer delays
            if failed_listings:
                logger.info(f"Retrying {len(failed_listings)} failed listings for property '{property_name}'...")
                retry_delay = 60  # 60 seconds between retries for failed listings
                
                for i, listing_info in enumerate(failed_listings):
                    listing_id = str(listing_info.get('id'))
                    listing_name = listing_info.get('name', 'N/A')
                    
                    logger.info(f"Retrying {listing_name} ({listing_id}) - {i+1}/{len(failed_listings)}")
                    
                    try:
                        # Add delay between retries to avoid rate limiting
                        if i > 0:
                            logger.info(f"Waiting {retry_delay}s before retry...")
                            time.sleep(retry_delay)
                        
                        # Use retry logic for fetching overrides
                        overrides_response = fetch_overrides_with_retry(api_client, listing_id, property_pms, max_retries=3, retry_delay=60)
                        
                        if overrides_response is None:
                            logger.error(f"Failed to fetch overrides for {listing_id} after retry")
                            continue
                        
                        all_listing_overrides = overrides_response.get('overrides', [])
                        logger.info(f"Successfully retried {listing_name} - received {len(all_listing_overrides)} overrides")

                        # Filter for fixed price types and date range
                        for override in all_listing_overrides:
                            if override.get('price_type') == 'fixed':
                                override_date_str = override.get('date')
                                if not override_date_str:
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

                                except (ValueError, Exception):
                                    continue  # Skip invalid dates
                        
                        logger.info(f"Successfully processed retry for {listing_name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to retry {listing_name}: {e}")
                        log_error(
                            logger=logger,
                            error_reason=f"Failed to retry listing: {e}",
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
        # Clean up API client session
        try:
            if 'api_client' in locals() and hasattr(api_client, 'session'):
                api_client.session.close()
                logger.info("API client session closed successfully.")
        except Exception as cleanup_e:
            logger.warning(f"Error closing API client session: {cleanup_e}")
        
        if error_occurred is None:
            execution_logger.info("SUCCESS - Override pull completed.")
        # Failure message is logged in the except block

if __name__ == "__main__":
    run_nightly_pull() 