import click
import yaml # Added for YAML loading
import os # Added for path joining
from pathlib import Path # Added for path handling
from datetime import datetime
import logging
from typing import List, Tuple, Optional, Dict # Updated typing

# Assuming PriceLabsAPI and setup_api_client exist and handle API initialization
# If they are in different locations, adjust the import path accordingly.
try:
    from ..api_client import PriceLabsAPI
    from ..logging_setup import setup_logging, log_error
    # Removed config import from here as it's not used directly at top level anymore
except ImportError:
    # Fallback for running script directly for testing, adjust as necessary
    print("Warning: Running outside of package context. Adjust imports if needed.")
    # Add dummy implementations or adjust sys.path if required for standalone execution
    class PriceLabsAPI:
        def __init__(self):
            print("Dummy PriceLabsAPI initialized.")
            pass
        def get_listing_overrides(self, listing_id: str, pms: str = None, start_date: str = None, end_date: str = None) -> dict:
            print(f"Fetching dummy overrides for {listing_id} (PMS: {pms}) from {start_date} to {end_date}")
            return {'overrides': []} # Return empty list for dummy

    # Basic logging setup if not running as part of the package
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    price_logger, error_logger = logger, logger
    def log_error(*args, **kwargs):
        logger.error(f"Error logged: {kwargs.get('error_reason', 'Unknown error')}")

# Determine project root relative to this script's location (rates/pull/pull_rates.py)
# Assumes the script is in rates/pull/ and config is in config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROPERTY_CONFIG_PATH = PROJECT_ROOT / "config" / "properties.yaml"

# Setup logging using methods that should now be importable
try:
    from ..logging_setup import setup_logging
    price_logger, error_logger = setup_logging()
except ImportError:
     # Use basic logger if setup_logging failed to import (should not happen when run as module)
     logger = logging.getLogger(__name__)
     logger.warning("Could not import setup_logging. Using basic logger.")
     price_logger, error_logger = logger, logger

logger = logging.getLogger(__name__) # Get logger instance for this module

def load_property_config(property_name: str) -> Optional[Dict]:
    """Loads configuration for a specific property from the YAML file."""
    try:
        with open(PROPERTY_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            if property_name in config.get('properties', {}):
                return config['properties'][property_name]
            else:
                logger.error(f"Property '{property_name}' not found in {PROPERTY_CONFIG_PATH}")
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


def validate_date(ctx, param, value):
    """Callback to validate date format."""
    if value is None:
        # This shouldn't happen if required=True, but good practice
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise click.BadParameter('Date must be in YYYY-MM-DD format.')

def setup_api_client_local() -> PriceLabsAPI:
    """Initialize and return API client specifically for this script."""
    try:
        # Assuming PriceLabsAPI loads credentials internally (e.g., from env vars via config)
        return PriceLabsAPI()
    except Exception as e:
        logger.error(f"Failed to initialize API client: {e}")
        # Use click.echo for user feedback in CLI context
        click.echo(f"Error: Failed to initialize API client: {e}", err=True)
        raise click.Abort()


@click.command()
@click.option('--listing-id', '-l', 'listing_ids_input', multiple=True, help='PriceLabs Listing ID(s) to fetch rates for. Can specify multiple times. Requires --pms OR --property.')
@click.option('--property', '-p', 'property_name', help='Property name (e.g., fb1, wb1) defined in config/properties.yaml. Fetches all listings for this property unless --listing-id is also specified.')
@click.option('--pms', help='Specify PMS directly. Overrides PMS from property config if --property is also used.')
@click.option('--start-date', '-s', required=True, callback=validate_date, help='Start date for fetching rates (YYYY-MM-DD).')
@click.option('--end-date', '-e', required=True, callback=validate_date, help='End date for fetching rates (YYYY-MM-DD).')
def fetch_rates(listing_ids_input: Tuple[str], property_name: Optional[str], pms: Optional[str], start_date, end_date):
    """
    Fetches and displays PriceLabs fixed price overrides for specified listings
    or properties within a given date range.

    Requires EITHER --property OR (--listing-id AND --pms).
    Can also use --property AND --listing-id (optionally with --pms to override).
    """
    if start_date > end_date:
        click.echo("Error: Start date cannot be after end date.", err=True)
        raise click.Abort()

    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    target_listing_ids = []
    effective_pms = None
    property_config = None

    # --- Determine Target Listings and PMS ---
    if property_name:
        property_config = load_property_config(property_name)
        if not property_config:
            raise click.Abort() # Error logged in load_property_config

        # PMS: Use command-line --pms if provided, otherwise use property config PMS
        effective_pms = pms or property_config.get('pms')
        if not effective_pms:
            click.echo(f"Error: PMS not specified via --pms and not found in config for property '{property_name}'.", err=True)
            raise click.Abort()

        property_listing_ids = [str(item['id']) for item in property_config.get('listings', [])]
        if not property_listing_ids:
             click.echo(f"Warning: No listings found in config for property '{property_name}'.", err=True)
             # Continue if specific listing IDs were provided, otherwise abort.
             if not listing_ids_input:
                 return


        if listing_ids_input:
            # Use specific listing IDs provided, but validate they belong to the property
            valid_ids = []
            invalid_ids = []
            for l_id in listing_ids_input:
                if l_id in property_listing_ids:
                    valid_ids.append(l_id)
                else:
                    invalid_ids.append(l_id)
            if invalid_ids:
                 click.echo(f"Warning: The following listing IDs provided via --listing-id do not belong to property '{property_name}' and will be ignored: {', '.join(invalid_ids)}", err=True)
            if not valid_ids:
                 click.echo(f"Error: None of the specified listing IDs belong to property '{property_name}'.", err=True)
                 raise click.Abort()
            target_listing_ids = valid_ids
        else:
            # Use all listings from the property config
            target_listing_ids = property_listing_ids

    elif listing_ids_input:
        # Requires --pms if --property is not given
        if not pms:
            click.echo("Error: --pms is required when specifying --listing-id without --property.", err=True)
            raise click.Abort()
        effective_pms = pms
        target_listing_ids = list(listing_ids_input) # Convert tuple to list

    else:
        # No property or listing ID provided
        click.echo("Error: Must specify --property OR --listing-id.", err=True)
        raise click.Abort()

    if not target_listing_ids:
        click.echo("Error: No target listing IDs determined.", err=True)
        # This case might occur if --property was given but had no listings, and --listing-id was not used.
        return

    # --- Fetch Rates ---
    try:
        api_client = setup_api_client_local()
    except click.Abort:
        return # Exit gracefully, error already displayed

    click.echo(f"Fetching rates for {len(target_listing_ids)} listing(s):")
    click.echo(f"  IDs: {', '.join(target_listing_ids)}")
    click.echo(f"  PMS: {effective_pms}")
    if property_name:
        click.echo(f"  Property: {property_name}")
    click.echo(f"  Date range: {start_date_str} to {end_date_str}")

    all_overrides_found_overall = False # Track if any overrides are found across all listings

    for l_id in target_listing_ids:
        click.echo(f"--- Processing Listing ID: {l_id} ---")
        try:
            # Pass the determined effective_pms
            # Pass start/end dates if API supports it (check PriceLabsAPI implementation)
            overrides_data = api_client.get_listing_overrides(l_id, pms=effective_pms) # Potentially add start_date=start_date_str, end_date=end_date_str

            listing_overrides = overrides_data.get('overrides', [])

            if not listing_overrides:
                 click.echo("No overrides found for this listing.")
                 continue # Move to the next listing ID

            filtered_overrides = []
            for override in listing_overrides:
                 # Ensure the override has a date and price, and is of type 'fixed'
                 if 'date' in override and 'price' in override and override.get('price_type') == 'fixed':
                     try:
                         override_date = datetime.strptime(override['date'], '%Y-%m-%d').date()
                         # Filter by date range
                         if start_date <= override_date <= end_date:
                             filtered_overrides.append({
                                 'date': override['date'],
                                 'price': override['price']
                                 # Consider adding currency if available and needed: 'currency': override.get('currency')
                             })
                             all_overrides_found_overall = True # Mark that at least one override was found
                     except ValueError:
                         # Log invalid date format but continue processing other overrides
                         logger.warning(f"Skipping override for listing {l_id} due to invalid date format: {override['date']}")
                     except Exception as e:
                          # Log other errors during override processing
                          logger.error(f"Error processing an override for listing {l_id}, date {override.get('date', 'N/A')}: {e}")

            if filtered_overrides:
                # Sort by date for readability
                filtered_overrides.sort(key=lambda x: x['date'])
                click.echo(f"Found {len(filtered_overrides)} fixed price overrides in range:")
                for override in filtered_overrides:
                    click.echo(f"  Date: {override['date']}, Price: {override['price']}") # Add currency display if needed
            else:
                click.echo("No fixed price overrides found within the specified date range for this listing.")

        except Exception as e:
            error_message = f"Failed to fetch or process overrides for listing {l_id}: {str(e)}"
            click.echo(f"Error: {error_message}", err=True)
            # Use the imported log_error if available
            # Determine listing name from property config if possible, otherwise use N/A
            listing_name_from_config = "N/A"
            if property_config:
                for item in property_config.get('listings', []):
                    if str(item['id']) == l_id:
                        listing_name_from_config = item.get('name', "N/A")
                        break

            # Safely call log_error even if imports failed
            if 'log_error' in globals() and callable(log_error):
                 log_error(
                      error_logger if 'error_logger' in globals() else logger,
                      listing_id=l_id,
                      listing_name=listing_name_from_config,
                      pms_name=effective_pms or "N/A",
                      start_date=start_date_str,
                      end_date=end_date_str,
                      old_price=0.0, # Not applicable here
                      new_price=0.0, # Not applicable here
                      currency="N/A", # Currency info might not be readily available here
                      error_reason=error_message
                 )
            else:
                 # Fallback basic logging
                 logger.error(error_message)
            # Continue to the next listing ID instead of aborting all
            continue

    if not all_overrides_found_overall:
         click.echo(f"No fixed price overrides found for any processed listing(s) in the date range {start_date_str} to {end_date_str}.")


if __name__ == "__main__":
    fetch_rates() 