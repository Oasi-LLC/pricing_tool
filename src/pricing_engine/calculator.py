# src/pricing_engine/calculator.py

import pandas as pd
import datetime
from typing import Dict, Set, Tuple, Optional, Any

# Assuming utils.py is in the same directory or Python path is set correctly
from . import utils # Use relative import within the package

def _get_rate_group_for_listing(listing_name: str, property_config: dict) -> Optional[str]:
    """
    Finds the rate group key (e.g., 'hard_unit', 'soft_unit') for a given listing
    based on the property's rate_group_mapping configuration.

    Args:
        listing_name: The name of the listing.
        property_config: The configuration dictionary for the specific property.

    Returns:
        The rate group key string (which should match a column name in the
        rate table) or None if the listing is not found in any mapping.
    """
    rate_mapping = property_config.get('rate_group_mapping', {})
    for group_key, listings_in_group in rate_mapping.items():
        if listing_name in listings_in_group:
            return group_key # Returns the key like 'hard_unit'
    print(f"Warning: Listing '{listing_name}' not found in any rate_group_mapping for property. Cannot determine rate column.")
    return None

def lookup_rate(
    rate_table_df: pd.DataFrame,
    tier_group: str,
    day_group: str,
    booking_window: str,
    occupancy_pct: float,
    urgency_band: Optional[str],
    rate_group_key: str # The key like 'rate_small' derived from listing
) -> Optional[float]:
    """
    Looks up the suggested rate in the rate table based on provided factors.

    Args:
        rate_table_df: The DataFrame containing rate rules for the property.
        tier_group: The tier group string (e.g., 'T0', 'T1-T3').
        day_group: The day group string (e.g., 'Mon-Wed').
        booking_window: The booking window label (e.g., '0-9 Days (W1)').
        occupancy_pct: The calculated occupancy percentage for the date.
        urgency_band: The urgency band string (e.g., '0-1') or None/empty string.
        rate_group_key: The specific rate column key (e.g., 'rate_small') to use.

    Returns:
        The suggested rate as a float, or None if no matching rule is found.
    """
    if not tier_group or not rate_group_key:
        return None # Cannot lookup without tier or target rate column

    # Ensure urgency_band is either a valid string or treated as 'match any'
    # Handle None or empty string for urgency band matching
    urgency_filter_active = bool(urgency_band) # True if urgency_band is not None/empty

    # Filter the DataFrame - Use inclusive boundaries for occupancy
    mask = (
        (rate_table_df['tier_group'] == tier_group) &
        (rate_table_df['day_group'] == day_group) &
        (rate_table_df['booking_window'] == booking_window) &
        (rate_table_df['occupancy_min_pct'] <= occupancy_pct) &
        (rate_table_df['occupancy_max_pct'] >= occupancy_pct)
    )

    # Add urgency band filter conditionally
    if urgency_filter_active:
        # Assumes rate table has an 'Urgency Breakdown' column, handle missing values
        mask &= (rate_table_df['Urgency Breakdown'].fillna('') == urgency_band)
    else:
        # If no urgency band applies to the request, match rows where
        # the table's urgency band is also empty/null (standard rule)
        mask &= (rate_table_df['Urgency Breakdown'].fillna('') == '')


    matching_rows = rate_table_df[mask]

    if not matching_rows.empty:
        # If multiple rules match, take the first one (or define more specific logic if needed)
        try:
            rate_value = matching_rows.iloc[0][rate_group_key]
            # Handle potential non-numeric values read from CSV
            return pd.to_numeric(rate_value, errors='coerce') # Returns NaN on conversion error
        except KeyError:
            print(f"Error: Rate column '{rate_group_key}' not found in rate table.")
            return None
        except Exception as e:
            print(f"Error retrieving rate value: {e}")
            return None
    else:
        # print(f"Debug: No rate rule found for Tier:{tier_group}, Day:{day_group}, Win:{booking_window}, Occ:{occupancy_pct:.2f}%, Urg:{urgency_band}, RateCol:{rate_group_key}")
        return None # No matching rule found


def get_adjusted_rate(
    ref_date: datetime.date,
    target_day_group: str, # Day group to use for lookup (e.g., 'Mon-Wed')
    listing_name: str,
    multiplier: float,
    occupancy_pct: float, # Occupancy for the ORIGINAL date being priced
    rate_table_df: pd.DataFrame,
    date_tier_map: Dict[str, str],
    booking_window_label: str, # Booking window for the ORIGINAL date
    property_config: dict,
    today: datetime.date # Today's date for potential urgency calc on ref_date
) -> Optional[float]:
    """
    Calculates an adjusted rate based on a reference date's tier and other factors.
    Used by the Thursday/Sunday rules.

    Args:
        ref_date: The reference date (e.g., Wednesday for Thursday rule) to get the tier from.
        target_day_group: The day group to use for the lookup (typically 'Mon-Wed').
        listing_name: The specific listing being priced.
        multiplier: The factor to multiply the looked-up rate by (e.g., 1.1, 1.2).
        occupancy_pct: The occupancy percentage for the *original* date being priced.
        rate_table_df: The rate table DataFrame.
        date_tier_map: Map of date strings to tier groups.
        booking_window_label: The booking window label for the *original* date.
        property_config: Configuration for the property (for rate group mapping).
        today: Today's date for urgency band calculation based on ref_date.

    Returns:
        The calculated adjusted rate, or None if lookup fails.
    """
    ref_date_str = utils.format_date(ref_date)
    ref_tier_group = date_tier_map.get(ref_date_str)

    if not ref_tier_group:
        print(f"Warning: Tier group not found for reference date {ref_date_str} during adjustment calculation.")
        return None

    rate_group_key = _get_rate_group_for_listing(listing_name, property_config)
    if not rate_group_key:
        return None # Warning already printed by helper function

    # Determine if urgency applies based on the REFERENCE date's tier and window/occupancy
    # The original script logic checks urgency based on ref_date's tier/window/occ
    # Let's recalculate urgency based on the reference date
    ref_urgency_band = ""
    # Logic from original script: Apply urgency if Tier 10-15, W1, Occ <= 30%
    # We use the ORIGINAL date's occupancy and booking window here as per original logic
    if (ref_tier_group in ["T10-T12", "T13-T15"]) and \
       (booking_window_label == "0-9 Days (W1)") and \
       (occupancy_pct <= 30):
       # Urgency band itself depends on days between ref_date and today
        ref_urgency_band = utils.get_urgency_band(ref_date, today)


    # Perform the lookup using reference date's tier, target day group, original occupancy, etc.
    base_rate = lookup_rate(
        rate_table_df=rate_table_df,
        tier_group=ref_tier_group,
        day_group=target_day_group, # Use the specified day group ('Mon-Wed')
        booking_window=booking_window_label, # Use original booking window
        occupancy_pct=occupancy_pct, # Use original occupancy
        urgency_band=ref_urgency_band, # Urgency determined by ref_date context
        rate_group_key=rate_group_key
    )

    if base_rate is not None and pd.notna(base_rate): # Check if lookup succeeded and is not NaN
        return base_rate * multiplier
    else:
        # print(f"Debug: Adjusted rate lookup failed for RefDate:{ref_date_str}, Tier:{ref_tier_group}, DayGrp:{target_day_group}, Occ:{occupancy_pct:.2f}%, Urg:{ref_urgency_band}")
        return None


def apply_adjustment_rules(
    current_date: datetime.date,
    listing_name: str,
    occupancy_pct: float, # Occupancy for current_date
    rate_table_df: pd.DataFrame,
    date_tier_map: Dict[str, str],
    booked_blocked_set: Set[Tuple[str, str]],
    booking_window_label: str, # Booking window for current_date
    property_config: dict,
    today: datetime.date # Today's date for urgency calcs
) -> Optional[float]:
    """
    Checks and applies Thursday or Sunday adjustment rules.

    Args:
        current_date: The date for which the rate is being calculated.
        listing_name: The specific listing.
        occupancy_pct: Occupancy percentage for current_date.
        rate_table_df: Rate table DataFrame.
        date_tier_map: Map of date strings to tiers.
        booked_blocked_set: Set of ('listing', 'YYYY-MM-DD') for booked/blocked dates.
        booking_window_label: Booking window label for current_date.
        property_config: Property configuration.
        today: Today's date.

    Returns:
        The adjusted rate if a rule applies and calculation succeeds, otherwise None.
    """
    adjusted_rate: Optional[float] = None
    weekday = current_date.weekday() # Monday = 0, Sunday = 6

    # --- Thursday Rule ---
    if weekday == 3: # Thursday
        friday_date = utils.add_days(current_date, 1)
        friday_date_str = utils.format_date(friday_date)
        is_friday_booked = (listing_name, friday_date_str) in booked_blocked_set

        if is_friday_booked:
            print(f"Applying Thursday rule for {listing_name} on {utils.format_date(current_date)} (Friday booked)")
            wednesday_date = utils.add_days(current_date, -1)
            wednesday_date_str = utils.format_date(wednesday_date)
            is_wednesday_booked = (listing_name, wednesday_date_str) in booked_blocked_set
            multiplier = 1.2 if is_wednesday_booked else 1.1

            adjusted_rate = get_adjusted_rate(
                ref_date=wednesday_date, # Use Wednesday's tier
                target_day_group='Mon-Wed', # Look up using Mon-Wed rules
                listing_name=listing_name,
                multiplier=multiplier,
                occupancy_pct=occupancy_pct, # Use Thursday's occupancy
                rate_table_df=rate_table_df,
                date_tier_map=date_tier_map,
                booking_window_label=booking_window_label, # Use Thursday's window
                property_config=property_config,
                today=today
            )

    # --- Sunday Rule ---
    elif weekday == 6: # Sunday
        saturday_date = utils.add_days(current_date, -1)
        saturday_date_str = utils.format_date(saturday_date)
        is_saturday_booked = (listing_name, saturday_date_str) in booked_blocked_set

        if is_saturday_booked:
            print(f"Applying Sunday rule for {listing_name} on {utils.format_date(current_date)} (Saturday booked)")
            monday_date = utils.add_days(current_date, 1)
            multiplier = 1.2

            adjusted_rate = get_adjusted_rate(
                ref_date=monday_date, # Use Monday's tier
                target_day_group='Mon-Wed', # Look up using Mon-Wed rules
                listing_name=listing_name,
                multiplier=multiplier,
                occupancy_pct=occupancy_pct, # Use Sunday's occupancy
                rate_table_df=rate_table_df,
                date_tier_map=date_tier_map,
                booking_window_label=booking_window_label, # Use Sunday's window
                property_config=property_config,
                today=today
            )

    return adjusted_rate
