import click
from datetime import datetime
import logging
from typing import List, Tuple

# Assuming PriceLabsAPI and setup_api_client exist and handle API initialization
# If they are in different locations, adjust the import path accordingly.
try:
    from .api_client import PriceLabsAPI
    from .logging_setup import setup_logging, log_error
    from .config import LOG_FORMAT, LOG_LEVEL
except ImportError:
    # Fallback for running script directly for testing, adjust as necessary
    print("Warning: Running outside of package context. Adjust imports if needed.")
    # Add dummy implementations or adjust sys.path if required for standalone execution
    class PriceLabsAPI:
        def __init__(self):
            print("Dummy PriceLabsAPI initialized.")
            # Implement minimal methods needed for script logic if necessary for testing
            # Example: Load API key from env var or config file here
            pass
        def get_listing_overrides(self, listing_id: str, pms: str = None, start_date: str = None, end_date: str = None) -> dict:
             # Dummy implementation for testing
            print(f"Fetching dummy overrides for {listing_id} from {start_date} to {end_date}")
            # Return a structure similar to the actual API response
            # Ensure 'overrides' key exists, even if empty
            return {'overrides': [{'date': '2024-08-15', 'price': '150', 'price_type': 'fixed'}, {'date': '2024-08-16', 'price': '160', 'price_type': 'fixed'}]}


    # Basic logging setup if not running as part of the package
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    # Dummy loggers if setup_logging is unavailable
    price_logger, error_logger = logger, logger 
    def log_error(*args, **kwargs):
        logger.error(f"Error logged: {kwargs.get('error_reason', 'Unknown error')}")


# Setup logging
logging.basicConfig(
    level=LOG_LEVEL if 'LOG_LEVEL' in globals() else logging.INFO,
    format=LOG_FORMAT if 'LOG_FORMAT' in globals() else '%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
if 'setup_logging' in globals():
     price_logger, error_logger = setup_logging()
else:
     # Use basic logger if setup_logging failed to import
     price_logger, error_logger = logger, logger 


def validate_date(ctx, param, value):
    """Callback to validate date format."""
    if value is None:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise click.BadParameter('Date must be in YYYY-MM-DD format.')

def setup_api_client_local() -> PriceLabsAPI:
    """Initialize and return API client specifically for this script."""
    try:
        # Assuming PriceLabsAPI loads credentials internally (e.g., from env vars)
        return PriceLabsAPI()
    except Exception as e:
        logger.error(f"Failed to initialize API client: {e}")
        raise click.Abort(f"Failed to initialize API client: {e}")


@click.command()
@click.option('--listing-id', '-l', multiple=True, required=True, help='PriceLabs Listing ID(s) to fetch rates for. Can specify multiple times.')
@click.option('--start-date', '-s', required=True, callback=validate_date, help='Start date for fetching rates (YYYY-MM-DD).')
@click.option('--end-date', '-e', required=True, callback=validate_date, help='End date for fetching rates (YYYY-MM-DD).')
@click.option('--pms', help='(Optional) Specify PMS if needed by the API client or for filtering.')
def fetch_rates(listing_id: Tuple[str], start_date, end_date, pms: str):
    """
    Fetches and displays PriceLabs fixed price overrides for specified listings
    within a given date range.
    """
    if start_date > end_date:
        click.echo("Error: Start date cannot be after end date.", err=True)
        raise click.Abort()

    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    try:
        api_client = setup_api_client_local()
    except Exception as e:
        click.echo(f"Error setting up API client: {e}", err=True)
        # Error is logged in setup_api_client_local
        return # Exit gracefully

    click.echo(f"Fetching rates for listings: {', '.join(listing_id)}")
    click.echo(f"Date range: {start_date_str} to {end_date_str}")
    if pms:
      click.echo(f"Using PMS filter: {pms}")


    all_overrides_found = False

    for l_id in listing_id:
        click.echo(f"--- Processing Listing ID: {l_id} ---")
        try:
            # Fetch overrides for the broad range; PriceLabs API might support date range filtering directly
            # Adjust the call if the API supports start_date and end_date parameters
            overrides_data = api_client.get_listing_overrides(l_id, pms=pms) # Add start_date=start_date_str, end_date=end_date_str if supported
            
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
                             })
                             all_overrides_found = True
                     except ValueError:
                         logger.warning(f"Skipping override for listing {l_id} due to invalid date format: {override['date']}")
                     except Exception as e:
                          logger.error(f"Error processing override for listing {l_id}, date {override.get('date', 'N/A')}: {e}")


            if filtered_overrides:
                # Sort by date for readability
                filtered_overrides.sort(key=lambda x: x['date'])
                click.echo(f"Found {len(filtered_overrides)} fixed price overrides in range:")
                for override in filtered_overrides:
                    click.echo(f"  Date: {override['date']}, Price: {override['price']}")
            else:
                click.echo("No fixed price overrides found within the specified date range.")

        except Exception as e:
            error_message = f"Failed to fetch or process overrides for listing {l_id}: {str(e)}"
            click.echo(f"Error: {error_message}", err=True)
            # Use the imported log_error if available
            if 'log_error' in globals() and callable(log_error):
                 log_error(
                      error_logger if 'error_logger' in globals() else logger, 
                      listing_id=l_id, 
                      listing_name="N/A", # Name not available in this context
                      pms_name=pms or "N/A", 
                      start_date=start_date_str, 
                      end_date=end_date_str, 
                      old_price=0.0, 
                      new_price=0.0, 
                      currency="N/A", # Currency not available
                      error_reason=error_message
                 )
            else:
                 # Fallback basic logging
                 logger.error(error_message)
            # Continue to the next listing ID instead of aborting all
            continue 

    if not all_overrides_found and listing_id:
         click.echo("No fixed price overrides found for any specified listing in the given date range.")


if __name__ == "__main__":
    fetch_rates() 