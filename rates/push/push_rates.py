import logging
from typing import List, Dict, Union, Optional
from datetime import datetime, timedelta
import click
import json
import yaml
from pathlib import Path
from ..api_client import PriceLabsAPI, PriceLabsAPIError

# Setup logging
logger = logging.getLogger(__name__)

def get_pms_for_listing(listing_id: str) -> str:
    """
    Get the PMS system name for a specific listing from the properties configuration.

    Args:
        listing_id: The PriceLabs listing ID

    Returns:
        str: PMS system name (defaults to 'cloudbeds' if not found)
    """
    try:
        config_path = Path(__file__).parent.parent.parent / 'config' / 'properties.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Search through all properties for the listing
        for property_data in config['properties'].values():
            for listing in property_data.get('listings', []):
                if listing['id'] == listing_id:
                    return property_data.get('pms', 'cloudbeds')
        
        logger.warning(f"Listing {listing_id} not found in configuration, using default PMS")
        return 'cloudbeds'
    except Exception as e:
        logger.error(f"Error reading PMS configuration: {str(e)}")
        return 'cloudbeds'

def push_rates_to_pricelabs(
    listing_id: str,
    rates: List[Dict[str, Union[str, float, int]]],
    pms: Optional[str] = None
) -> bool:
    """
    Push rates to PriceLabs API for a specific listing.

    Args:
        listing_id: The PriceLabs listing ID
        rates: List of rate dictionaries with format:
              [{"date": "YYYY-MM-DD", "price": float/int}]
        pms: Optional PMS system name (if not provided, will be read from config)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize API client
        api_client = PriceLabsAPI()

        # Get PMS from configuration if not provided
        if pms is None:
            pms = get_pms_for_listing(listing_id)

        # Format rates for PriceLabs API
        formatted_overrides = []
        for rate in rates:
            # Validate required fields
            if not all(k in rate for k in ["date", "price"]):
                logger.error(f"Missing required fields in rate data: {rate}")
                continue

            # Format the override
            override = {
                "date": rate["date"],
                "price": str(int(float(rate["price"]))),  # Convert to integer string
                "price_type": "fixed",
                "currency": rate.get("currency", "USD")
            }
            formatted_overrides.append(override)

        if not formatted_overrides:
            logger.error("No valid rates to push")
            return False

        # Push to PriceLabs
        logger.info(f"Pushing {len(formatted_overrides)} rates for listing {listing_id}")
        api_client.update_listing_overrides(
            listing_id=listing_id,
            overrides=formatted_overrides,
            pms=pms
        )
        
        logger.info(f"Successfully pushed rates for listing {listing_id}")
        return True

    except PriceLabsAPIError as e:
        logger.error(f"PriceLabs API error for listing {listing_id}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error pushing rates for listing {listing_id}: {str(e)}")
        return False

def push_rates_batch(
    rates_data: Dict[str, List[Dict]],
    pms: Optional[str] = None
) -> Dict[str, bool]:
    """
    Push rates for multiple listings in batch.

    Args:
        rates_data: Dictionary mapping listing IDs to their rates
                   {"listing_id": [{"date": "YYYY-MM-DD", "price": float/int}]}
        pms: Optional PMS system name (if not provided, will be read from config for each listing)

    Returns:
        Dict[str, bool]: Results for each listing ID (True if successful)
    """
    results = {}
    for listing_id, rates in rates_data.items():
        success = push_rates_to_pricelabs(
            listing_id=listing_id,
            rates=rates,
            pms=pms
        )
        results[listing_id] = success
    
    # Log summary
    success_count = sum(1 for success in results.values() if success)
    logger.info(f"Batch push completed. {success_count}/{len(results)} listings successful")
    
    return results

@click.command()
@click.option('--listing-id', required=True, help='PriceLabs listing ID')
@click.option('--rates-json', required=True, help='JSON string of rates in format: [{"date": "YYYY-MM-DD", "price": "123"}]')
@click.option('--pms', help='Optional PMS system name (if not provided, will be read from config)')
def cli(listing_id: str, rates_json: str, pms: Optional[str] = None):
    """Push rates to PriceLabs from JSON input."""
    try:
        rates = json.loads(rates_json)
        if not isinstance(rates, list):
            click.echo("Error: rates-json must be a JSON array", err=True)
            exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing JSON: {e}", err=True)
        exit(1)

    # Push rates
    success = push_rates_to_pricelabs(
        listing_id=listing_id,
        rates=rates,
        pms=pms
    )

    if success:
        click.echo(f"Successfully pushed {len(rates)} rates for listing {listing_id}")
    else:
        click.echo(f"Failed to push rates for listing {listing_id}", err=True)
        exit(1)

if __name__ == "__main__":
    cli()
