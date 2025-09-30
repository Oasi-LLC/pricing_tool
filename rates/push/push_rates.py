import logging
from typing import List, Dict, Union, Optional
from datetime import datetime, timedelta
import click
import json
import yaml
from pathlib import Path
from ..api_client import PriceLabsAPI, PriceLabsAPIError
from ..logging_setup import setup_logging, log_price_update, log_error

# Setup logging
logger = logging.getLogger(__name__)

# Add console handler if not already added
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

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

def get_listing_name(listing_id: str) -> str:
    """
    Get the listing name for a specific listing ID from the properties configuration.

    Args:
        listing_id: The PriceLabs listing ID

    Returns:
        str: Listing name (defaults to listing_id if not found)
    """
    try:
        config_path = Path(__file__).parent.parent.parent / 'config' / 'properties.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Search through all properties for the listing
        for property_data in config['properties'].values():
            for listing in property_data.get('listings', []):
                if listing['id'] == listing_id:
                    return listing.get('name', listing_id)
        
        logger.warning(f"Listing {listing_id} not found in configuration, using ID as name")
        return listing_id
    except Exception as e:
        logger.error(f"Error reading listing name: {str(e)}")
        return listing_id

def push_rates_to_pricelabs(
    listing_id: str,
    rates: List[Dict[str, Union[str, float, int]]],
    pms: Optional[str] = None
) -> Dict[str, Union[bool, str, List[Dict], int, Dict]]:
    """
    Push rates to PriceLabs API for a specific listing.

    Args:
        listing_id: The PriceLabs listing ID
        rates: List of rate dictionaries with format:
              [{"date": "YYYY-MM-DD", "price": float/int}]
        pms: Optional PMS system name (if not provided, will be read from config)

    Returns:
        Dict with the following keys:
            success (bool): True if successful, False otherwise
            message (str): Description of the result or error
            rates_pushed (List[Dict]): List of rates that were successfully pushed
            total_rates (int): Total number of rates attempted to push
            error_detail (str, optional): Detailed error message if any
            response (Dict, optional): Raw API response when available
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
                "currency": rate.get("currency", "USD"),
                "min_stay": int(rate.get("min_stay", 1))  # Default to 1 if not specified
            }
            formatted_overrides.append(override)

        if not formatted_overrides:
            return {
                "success": False,
                "message": "No valid rates to push",
                "rates_pushed": [],
                "total_rates": len(rates),
                "error_detail": "All rates were invalid or missing required fields",
            }

        # Push to PriceLabs
        logger.info(f"Pushing {len(formatted_overrides)} rates for listing {listing_id}")
        response = api_client.update_listing_overrides(
            listing_id=listing_id,
            overrides=formatted_overrides,
            pms=pms
        )
        
        logger.info(f"Successfully pushed rates for listing {listing_id}")
        
        # Log price updates to file
        try:
            price_logger, error_logger = setup_logging()
            listing_name = get_listing_name(listing_id)
            
            for override in formatted_overrides:
                log_price_update(
                    logger=price_logger,
                    listing_id=listing_id,
                    listing_name=listing_name,
                    pms_name=pms,
                    start_date=override['date'],
                    end_date=override['date'],
                    price=float(override['price']),
                    currency=override.get('currency', 'USD'),
                    price_type=override.get('price_type', 'fixed'),
                    minimum_stay=override.get('min_stay', 1),
                    reason="Rate Push to PriceLabs"
                )
        except Exception as log_error:
            logger.warning(f"Failed to log price update: {str(log_error)}")
        
        return {
            "success": True,
            "message": f"Successfully pushed {len(formatted_overrides)} rates",
            "rates_pushed": formatted_overrides,
            "total_rates": len(rates),
        }

    except PriceLabsAPIError as e:
        error_msg = f"PriceLabs API error for listing {listing_id}: {str(e)}"
        logger.error(error_msg)
        
        # Log error to error log file
        try:
            price_logger, error_logger = setup_logging()
            listing_name = get_listing_name(listing_id)
            log_error(
                logger=error_logger,
                listing_id=listing_id,
                listing_name=listing_name,
                pms_name=pms,
                error_type="PriceLabs API Error",
                error_message=str(e),
                context=f"Rate push failed for {len(rates)} rates"
            )
        except Exception as log_exception:
            logger.warning(f"Failed to log error: {str(log_exception)}")
        
        return {
            "success": False,
            "message": "API error occurred",
            "rates_pushed": [],
            "total_rates": len(rates),
            "error_detail": error_msg,
        }
    except Exception as e:
        error_msg = f"Unexpected error pushing rates for listing {listing_id}: {str(e)}"
        logger.error(error_msg)
        
        # Log error to error log file
        try:
            price_logger, error_logger = setup_logging()
            listing_name = get_listing_name(listing_id)
            log_error(
                logger=error_logger,
                listing_id=listing_id,
                listing_name=listing_name,
                pms_name=pms,
                error_type="Unexpected Error",
                error_message=str(e),
                context=f"Rate push failed for {len(rates)} rates"
            )
        except Exception as log_exception:
            logger.warning(f"Failed to log error: {str(log_exception)}")
        
        return {
            "success": False,
            "message": "Unexpected error occurred",
            "rates_pushed": [],
            "total_rates": len(rates),
            "error_detail": error_msg,
        }

def push_rates_batch(
    rates_data: Dict[str, List[Dict]],
    pms: Optional[str] = None
) -> Dict[str, Dict]:
    """
    Push rates for multiple listings in batch.

    Args:
        rates_data: Dictionary mapping listing IDs to their rates
                   {"listing_id": [{"date": "YYYY-MM-DD", "price": float/int}]}
        pms: Optional PMS system name (if not provided, will be read from config for each listing)

    Returns:
        Dict[str, Dict]: Results for each listing ID containing detailed push information
    """
    results = {}
    total_success = 0
    total_listings = len(rates_data)
    
    for listing_id, rates in rates_data.items():
        result = push_rates_to_pricelabs(
            listing_id=listing_id,
            rates=rates,
            pms=pms
        )
        results[listing_id] = result
        if result["success"]:
            total_success += 1
    
    # Log summary
    logger.info(f"Batch push completed. {total_success}/{total_listings} listings successful")
    
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
    result = push_rates_to_pricelabs(
        listing_id=listing_id,
        rates=rates,
        pms=pms
    )

    if result["success"]:
        click.echo(f"Successfully pushed {result['total_rates']} rates for listing {listing_id}")
    else:
        click.echo(f"Failed to push rates for listing {listing_id}: {result['message']}", err=True)
        exit(1)

if __name__ == "__main__":
    cli()
