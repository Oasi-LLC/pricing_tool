# src/pricing_engine/calculator.py

import pandas as pd
import datetime
from typing import Dict, Set, Tuple, Optional, Any

# Assuming utils.py is in the same directory or Python path is set correctly
from . import utils # Use relative import within the package

def _get_rate_group_for_listing_id(listing_id: str, property_config: dict) -> Optional[str]:
    """
    Finds the rate group key (e.g., 'rate_1', 'rate_2') for a given listing ID
    based on the property's rate_group_mapping configuration (which maps keys to IDs).

    Args:
        listing_id: The ID of the listing.
        property_config: The configuration dictionary for the specific property.

    Returns:
        The rate group key string (which should match a column name in the
        rate table) or None if the listing ID is not found in any mapping.
    """
    rate_mapping = property_config.get('rate_group_mapping', {})
    for group_key, ids_in_group in rate_mapping.items():
        if listing_id in ids_in_group: # Check if ID is in the list
            return group_key # Returns the key like 'rate_1'
    # Optional: Add warning if ID not found
    # print(f"Warning: Listing ID '{listing_id}' not found in any rate_group_mapping for property. Cannot determine rate column.")
    return None

def lookup_rate(
    rate_table_df: pd.DataFrame,
    tier_group: str,
    day_group: str,
    booking_window: str,
    occupancy_pct: float,
    urgency_band: Optional[str],
    rate_group_key: str # The key like 'rate_small' derived from listing
) -> Tuple[Optional[float], Optional[str]]: # Return tuple: (rate, error_message)
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
        A tuple containing:
        - The suggested rate as a float, or None if no matching rule is found.
        - An error message string if lookup fails, otherwise None.
    """
    if not tier_group or not rate_group_key:
        error_msg = f"Lookup failed: Invalid input (Tier: {tier_group}, RateKey: {rate_group_key})"
        return None, error_msg # Cannot lookup without tier or target rate column

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
            rate_numeric = pd.to_numeric(rate_value, errors='coerce') # Returns NaN on conversion error
            if pd.isna(rate_numeric):
                error_msg = f"Lookup Error: Non-numeric rate value '{rate_value}' found for RateKey: {rate_group_key} with inputs Tier:{tier_group}, Day:{day_group}, Win:{booking_window}, Occ:{occupancy_pct:.2f}%, Urg:{urgency_band}"
                return None, error_msg
            else:
                return rate_numeric, None # Success
        except KeyError:
            error_msg = f"Lookup Error: Rate column '{rate_group_key}' not found in rate table."
            # print(error_msg) # Optional console print
            return None, error_msg
        except Exception as e:
            error_msg = f"Lookup Error: Unexpected error retrieving rate value: {e}"
            # print(error_msg) # Optional console print
            return None, error_msg
    else:
        error_msg = f"Lookup Failed: No rule found for Tier:{tier_group}, Day:{day_group}, Win:{booking_window}, Occ:{occupancy_pct:.2f}%, Urg:{urgency_band}, RateCol:{rate_group_key}"
        # print(error_msg) # Optional console print
        return None, error_msg # No matching rule found


def get_adjusted_rate(
    ref_date: datetime.date,
    target_day_group: str, # Day group to use for lookup (e.g., 'Mon-Wed')
    listing_id: str,
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
        listing_id: The specific listing ID.
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

    # Use the ID-based lookup function
    rate_group_key = _get_rate_group_for_listing_id(listing_id, property_config)
    if not rate_group_key:
        # Consider adding a warning here if the ID lookup fails
        print(f"Warning: Failed to find rate group for Listing ID '{listing_id}' during adjustment.")
        return None

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
    # IMPORTANT: get_adjusted_rate now uses lookup_rate internally.
    # We only care about the rate here, not the error message from the lookup.
    # Error handling for the base lookup should happen in the main script.
    base_rate, _ = lookup_rate( # Unpack the tuple, ignore the error message here
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


def _check_condition(
    condition_config: Optional[Dict[str, Any]],
    current_date: datetime.date,
    listing_id: str,
    booked_blocked_set: Set[Tuple[str, str]]
) -> bool:
    """Checks if a single condition is met."""
    if condition_config is None:
        return True # Default action condition

    cond_type = condition_config.get('type')

    if cond_type == 'adjacent_day_booked':
        day_offset = condition_config.get('day_offset')
        if day_offset is None:
            print(f"Warning: Missing 'day_offset' for 'adjacent_day_booked' condition. Rule skipped.")
            return False # Invalid condition config
        adjacent_date = utils.add_days(current_date, day_offset)
        adjacent_date_str = utils.format_date(adjacent_date)
        return (listing_id, adjacent_date_str) in booked_blocked_set
    # --- Add other condition type checks here in the future ---
    else:
        print(f"Warning: Unknown condition type '{cond_type}'. Rule skipped.")
        return False # Unknown condition type

def apply_adjustment_rules(
    current_date: datetime.date,
    listing_id: str, # Changed from listing_name
    occupancy_pct: float, # Occupancy for current_date
    rate_table_df: pd.DataFrame,
    date_tier_map: Dict[str, str],
    booked_blocked_set: Set[Tuple[str, str]], # Set now contains (ID, Date)
    booking_window_label: str, # Booking window for current_date
    property_config: dict,
    today: datetime.date # Today's date for urgency calcs
) -> Optional[float]:
    """
    Checks and applies adjustment rules defined in the property configuration.

    Args:
        current_date: The date for which the rate is being calculated.
        listing_id: The specific listing ID.
        occupancy_pct: Occupancy percentage for current_date.
        rate_table_df: Rate table DataFrame.
        date_tier_map: Map of date strings to tiers.
        booked_blocked_set: Set of ('listing_id', 'YYYY-MM-DD') for booked/blocked dates.
        booking_window_label: Booking window label for current_date.
        property_config: Property configuration including 'adjustment_rules'.
        today: Today's date.

    Returns:
        The adjusted rate if a rule applies and calculation succeeds, otherwise None.
    """
    rules = property_config.get('adjustment_rules', [])
    if not rules:
        return None # No rules defined for this property

    current_weekday = current_date.weekday() # Monday = 0, Sunday = 6

    for rule in rules:
        if rule.get('target_weekday') == current_weekday:
            # Check primary conditions for the rule
            all_conditions_met = True
            for condition_config in rule.get('conditions', []):
                if not _check_condition(condition_config, current_date, listing_id, booked_blocked_set):
                    all_conditions_met = False
                    break # Stop checking conditions for this rule

            if all_conditions_met:
                # Find the first matching action (checking nested conditions)
                selected_action = None
                for action in rule.get('actions', []):
                    nested_condition_config = action.get('condition')
                    # Check nested condition OR if it's the default action (condition: null)
                    if _check_condition(nested_condition_config, current_date, listing_id, booked_blocked_set):
                        selected_action = action
                        break # Use the first matching action

                if selected_action:
                    print(f"Applying rule '{rule.get('name', 'Unnamed Rule')}' for Listing ID {listing_id} on {utils.format_date(current_date)}")

                    # Extract parameters for get_adjusted_rate
                    multiplier = selected_action.get('multiplier')
                    ref_day_offset = selected_action.get('reference_day_offset')
                    lookup_day_group = selected_action.get('lookup_day_group')

                    # Validate required parameters
                    if multiplier is None or ref_day_offset is None or lookup_day_group is None:
                        print(f"Warning: Rule '{rule.get('name', 'Unnamed Rule')}' action is missing required parameters (multiplier, reference_day_offset, lookup_day_group). Skipping.")
                        continue # Skip to next rule if config is invalid

                    ref_date = utils.add_days(current_date, ref_day_offset)

                    adjusted_rate = get_adjusted_rate(
                        ref_date=ref_date,
                        target_day_group=lookup_day_group, # Use group from config
                        listing_id=listing_id,
                        multiplier=multiplier,
                        occupancy_pct=occupancy_pct, # Use current date's occupancy
                        rate_table_df=rate_table_df,
                        date_tier_map=date_tier_map,
                        booking_window_label=booking_window_label, # Use current date's window
                        property_config=property_config, # Pass config down for rate group mapping
                        today=today
                    )

                    # If adjustment calculation succeeded, return it immediately
                    if adjusted_rate is not None:
                        return adjusted_rate
                else:
                     print(f"Warning: Rule '{rule.get('name', 'Unnamed Rule')}' triggered, but no valid action found for Listing ID {listing_id} on {utils.format_date(current_date)}")


    # If no rules matched or calculation failed, return None
    return None
