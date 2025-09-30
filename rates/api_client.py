import os
import requests
from typing import List, Dict, Optional
from datetime import datetime
import logging
from dotenv import load_dotenv
from .config import API_KEY, BASE_URL

logger = logging.getLogger(__name__)

class PriceLabsAPI:
    def __init__(self):
        self.api_key = API_KEY
        if not self.api_key:
            raise ValueError("PRICELABS_API_KEY environment variable is required")
        
        self.base_url = BASE_URL
        self.session = requests.Session()
        
        # Configure connection pooling for better performance
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # Create a retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Create HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools to cache
            pool_maxsize=20,      # Maximum number of connections to save in the pool
            max_retries=retry_strategy
        )
        
        # Mount the adapter for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
            'Connection': 'keep-alive'  # Enable keep-alive for connection reuse
        })

    def get_listings(self) -> List[Dict]:
        """Get all active listings"""
        response = self.session.get(f"{self.base_url}/listings")
        response.raise_for_status()
        
        # Log the response for debugging
        logger.debug(f"API Response: {response.json()}")
        
        data = response.json()
        return data.get('listings', []) if isinstance(data, dict) else []

    def get_listing_overrides(self, listing_id: str, pms: str = None) -> Dict:
        """Fetch overrides for a specific listing"""
        try:
            params = {}
            if pms:
                params['pms'] = pms
                
            response = self.session.get(
                f"{self.base_url}/listings/{listing_id}/overrides",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching overrides for listing {listing_id}: {e}")
            raise PriceLabsAPIError(f"Error fetching overrides: {e}")

    def get_listing_daily_data(self, listing_id: str, pms: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch daily price, availability, and booking status using the listing_prices endpoint."""
        try:
            payload = {
                "listings": [
                    {
                        "id": listing_id,
                        "pms": pms,
                        "dateFrom": start_date,
                        "dateTo": end_date
                        # "reason": True # Optional: Add if detailed pricing reasons are needed
                    }
                ]
            }
            logger.debug(f"Fetching daily data for {listing_id} from {start_date} to {end_date}")
            response = self.session.post(
                f"{self.base_url}/listing_prices",
                json=payload
            )
            response.raise_for_status()

            # The response is a list containing one element (for the one listing requested)
            # That element contains the 'data' key with the list of daily statuses.
            response_data = response.json()
            if isinstance(response_data, list) and len(response_data) > 0:
                listing_data = response_data[0]
                if 'data' in listing_data and isinstance(listing_data['data'], list):
                    logger.info(f"Successfully fetched {len(listing_data['data'])} daily data points for {listing_id}")
                    return listing_data['data']
                elif 'status' in listing_data: # Handle potential error statuses within the response
                    logger.error(f"API returned status '{listing_data['status']}' for listing {listing_id} in listing_prices call.")
                    # You might want to raise an error or return an empty list depending on desired handling
                    raise PriceLabsAPIError(f"Error fetching daily data: API status {listing_data['status']} for {listing_id}")
                else:
                    logger.warning(f"Unexpected response structure for listing {listing_id} in listing_prices: {listing_data}")
                    return []
            else:
                logger.warning(f"Received empty or invalid response for listing {listing_id} from listing_prices: {response_data}")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching daily data (listing_prices) for listing {listing_id}: {e}")
            raise PriceLabsAPIError(f"Error fetching daily data: {e}")
        except Exception as e:
            # Catch other potential issues like JSON decoding errors
            logger.error(f"Unexpected error processing daily data for listing {listing_id}: {e}")
            raise PriceLabsAPIError(f"Unexpected error processing daily data: {e}")

    def update_listing_overrides(
        self,
        listing_id: str,
        overrides: List[Dict],
        pms: str = None,
        update_children: bool = False
    ) -> Dict:
        """
        Update listing overrides with new prices
        
        Args:
            listing_id: The ID of the listing to update
            overrides: List of override objects with required fields:
                      date, price, price_type, currency, min_stay
            pms: PMS name (e.g. "cloudbeds", "hostaway", "ownerrez")
            update_children: Whether to update child listings
        """
        try:
            payload = {
                "update_children": update_children,
                "overrides": overrides
            }
            if pms:
                payload['pms'] = pms
            
            logger.debug(f"Sending update request for listing {listing_id}")
            logger.debug(f"Request URL: {self.base_url}/listings/{listing_id}/overrides")
            logger.debug(f"Headers: {self.session.headers}")
            logger.debug(f"Payload: {payload}")

            response = self.session.post(
                f"{self.base_url}/listings/{listing_id}/overrides",
                json=payload
            )
            
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content: {response.content}")
            
            if not response.ok:
                error_detail = response.json() if response.content else "No error details"
                logger.error(f"API error response: {error_detail}")
                logger.error(f"Response headers: {response.headers}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating overrides for listing {listing_id}: {e}")
            raise PriceLabsAPIError(f"Error updating overrides: {e}")

    def _validate_override(self, override: Dict) -> bool:
        """Validate override object has all required fields"""
        required_fields = ["date", "price", "price_type", "currency", "min_stay"]
        return all(field in override for field in required_fields)

    def update_listing(self, listing_id: str, data: Dict) -> Dict:
        """Update a listing's pricing"""
        response = self.session.put(f"{self.base_url}/listings/{listing_id}", json=data)
        response.raise_for_status()
        return response.json()

class PriceLabsAPIError(Exception):
    """Custom exception for API errors"""
    pass

def handle_api_error(response: requests.Response) -> None:
    """Handle API error responses with appropriate logging"""
    error_msg = f"API error: {response.status_code}"
    try:
        error_details = response.json()
        error_msg += f" - {error_details.get('message', '')}"
    except ValueError:
        pass
    
    if response.status_code == 400:
        raise PriceLabsAPIError(f"Invalid request parameters: {error_msg}")
    elif response.status_code == 401:
        raise PriceLabsAPIError(f"Authentication failed: {error_msg}")
    elif response.status_code == 404:
        raise PriceLabsAPIError(f"Listing not found: {error_msg}")
    elif response.status_code == 429:
        raise PriceLabsAPIError(f"Rate limit exceeded: {error_msg}")
    else:
        raise PriceLabsAPIError(error_msg) 