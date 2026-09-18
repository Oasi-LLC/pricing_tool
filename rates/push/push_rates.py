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

def _load_properties_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / 'config' / 'properties.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config.get('properties', {})

def get_pms_for_listing(listing_id: str) -> str:
    """
    Get the PMS system name for a specific listing from the properties configuration.
    """
    try:
        for property_data in _load_properties_config().values():
            property_pms = property_data.get('pms', 'cloudbeds')
            for listing in property_data.get('listings', []):
                if listing['id'] == listing_id:
                    return property_pms
                for mirror in listing.get('push_mirrors', []):
                    if mirror.get('id') == listing_id:
                        return mirror.get('pms', property_pms)

        logger.warning(f"Listing {listing_id} not found in configuration, using default PMS")
        return 'cloudbeds'
    except Exception as e:
        logger.error(f"Error reading PMS configuration: {str(e)}")
        return 'cloudbeds'

def _build_push_mirror_index() -> Dict[str, List[Dict[str, str]]]:
    """Build bidirectional push mirror map: listing_id -> [{id, pms}, ...]."""
    index: Dict[str, List[Dict[str, str]]] = {}
    try:
        for property_data in _load_properties_config().values():
            primary_pms = property_data.get('pms', 'cloudbeds')
            for listing in property_data.get('listings', []):
                primary_id = str(listing.get('id', '')).strip()
                if not primary_id:
                    continue
                for mirror in listing.get('push_mirrors', []):
                    mirror_id = str(mirror.get('id', '')).strip()
                    mirror_pms = mirror.get('pms')
                    if not mirror_id or not mirror_pms:
                        continue
                    index.setdefault(primary_id, []).append({'id': mirror_id, 'pms': mirror_pms})
                    index.setdefault(mirror_id, []).append({'id': primary_id, 'pms': primary_pms})
    except Exception as e:
        logger.error(f"Error building push mirror index: {str(e)}")
    return index

def _get_push_targets(listing_id: str, pms: Optional[str] = None) -> List[tuple]:
    """Return unique (listing_id, pms) targets including configured mirrors."""
    listing_pms = pms or get_pms_for_listing(listing_id)
    targets = [(listing_id, listing_pms)]
    seen = {listing_id}
    for mirror in _build_push_mirror_index().get(listing_id, []):
        mirror_id = mirror['id']
        if mirror_id in seen:
            continue
        targets.append((mirror_id, mirror['pms']))
        seen.add(mirror_id)
    return targets

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

def _push_rates_single(
    listing_id: str,
    formatted_overrides: List[Dict],
    pms: str,
    total_rates: int,
) -> Dict[str, Union[bool, str, List[Dict], int, Dict]]:
    """Push pre-formatted overrides to one listing/PMS target."""
    api_client = PriceLabsAPI()
    logger.info(f"Pushing {len(formatted_overrides)} rates for listing {listing_id} (pms={pms})")
    api_client.update_listing_overrides(
        listing_id=listing_id,
        overrides=formatted_overrides,
        update_children=True,
        pms=pms
    )
    logger.info(f"Successfully pushed rates for listing {listing_id} (pms={pms})")

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
    except Exception as log_error_exc:
        logger.warning(f"Failed to log price update: {str(log_error_exc)}")

    return {
        "success": True,
        "message": f"Successfully pushed {len(formatted_overrides)} rates",
        "rates_pushed": formatted_overrides,
        "total_rates": total_rates,
        "pms": pms,
    }

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
        formatted_overrides = []
        for rate in rates:
            if not all(k in rate for k in ["date", "price"]):
                logger.error(f"Missing required fields in rate data: {rate}")
                continue

            override = {
                "date": rate["date"],
                "price": str(int(float(rate["price"]))),
                "price_type": "fixed",
                "currency": rate.get("currency", "USD"),
                "min_stay": int(rate.get("min_stay", 1))
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

        push_targets = _get_push_targets(listing_id, pms)
        target_results = []
        errors = []
        for target_id, target_pms in push_targets:
            try:
                target_results.append(
                    _push_rates_single(
                        listing_id=target_id,
                        formatted_overrides=formatted_overrides,
                        pms=target_pms,
                        total_rates=len(rates),
                    )
                )
            except PriceLabsAPIError as target_error:
                error_msg = (
                    f"PriceLabs API error for listing {target_id} (pms={target_pms}): {target_error}"
                )
                logger.error(error_msg)
                errors.append(error_msg)
                target_results.append({
                    "success": False,
                    "message": "API error occurred",
                    "rates_pushed": [],
                    "total_rates": len(rates),
                    "error_detail": error_msg,
                    "pms": target_pms,
                    "listing_id": target_id,
                })
            except Exception as target_error:
                error_msg = (
                    f"Unexpected error for listing {target_id} (pms={target_pms}): {target_error}"
                )
                logger.error(error_msg)
                errors.append(error_msg)
                target_results.append({
                    "success": False,
                    "message": "Unexpected error occurred",
                    "rates_pushed": [],
                    "total_rates": len(rates),
                    "error_detail": error_msg,
                    "pms": target_pms,
                    "listing_id": target_id,
                })

        all_success = all(result.get("success") for result in target_results)
        pushed_count = sum(len(result.get("rates_pushed", [])) for result in target_results if result.get("success"))
        mirror_count = len(push_targets) - 1
        if all_success and mirror_count > 0:
            message = (
                f"Successfully pushed {len(formatted_overrides)} rates to "
                f"{len(push_targets)} listing target(s)"
            )
        elif all_success:
            message = f"Successfully pushed {len(formatted_overrides)} rates"
        else:
            message = f"Push completed with {len(errors)} failure(s)"

        return {
            "success": all_success,
            "message": message,
            "rates_pushed": formatted_overrides if all_success else [],
            "total_rates": len(rates),
            "targets": [
                {"listing_id": target_id, "pms": target_pms}
                for target_id, target_pms in push_targets
            ],
            "target_results": target_results,
            "pushed_count": pushed_count,
            "error_detail": "; ".join(errors) if errors else None,
        }

    except PriceLabsAPIError as e:
        error_pms = pms or get_pms_for_listing(listing_id)
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
                pms_name=error_pms,
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
        error_pms = pms or get_pms_for_listing(listing_id)
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
                pms_name=error_pms,
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
