"""Rules adjuster logic shared by the Streamlit app and automation scripts."""
import datetime
from pathlib import Path
import pandas as pd
import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "properties.yaml"


def load_properties_config():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("properties", {})


def _check_adjacent_weekday_los_for_target(target_date, df, property_key, listing_id, day_offset):
    """
    Check if the adjacent weekday has 1-night minimum for a specific target day.
    This function correctly identifies which adjacent weekday to check based on the target day.
    
    Args:
        target_date: The target date to check
        df: DataFrame with rate data
        property_key: Property key
        listing_id: Specific listing ID to check
        day_offset: Day offset from the rule trigger date (e.g., -2 for Thursday, -1 for Friday, +1 for Sunday)
    
    Returns:
        bool: True if the adjacent weekday has 1-night minimum
    """
    # Determine which adjacent weekday to check based on the target day
    if day_offset == -2:  # Thursday: check Wednesday (day before Thursday)
        adjacent_weekday = target_date - datetime.timedelta(days=1)
        print(f"🔍 DEBUG: Thursday target ({target_date}), checking Wednesday ({adjacent_weekday})")
    elif day_offset == -1:  # Friday: check Wednesday (two days before Friday)
        adjacent_weekday = target_date - datetime.timedelta(days=2)
        print(f"🔍 DEBUG: Friday target ({target_date}), checking Wednesday ({adjacent_weekday})")
    elif day_offset == 1:  # Sunday: check Monday (day after Sunday)
        adjacent_weekday = target_date + datetime.timedelta(days=1)
        print(f"🔍 DEBUG: Sunday target ({target_date}), checking Monday ({adjacent_weekday})")
    else:
        print(f"🔍 DEBUG: Unknown day_offset {day_offset}, cannot determine adjacent weekday")
        return False
    
    adjacent_weekday_str = adjacent_weekday.strftime('%Y-%m-%d')
    
    # Get the listing data for this adjacent weekday
    adjacent_data = df[
        (df['Date'] == adjacent_weekday_str) & 
        (df['Unit Pool'] == property_key) & 
        (df['listing_id'] == listing_id)
    ]
    
    if adjacent_data.empty:
        print(f"🔍 DEBUG: No data found for adjacent weekday {adjacent_weekday_str}")
        return False
    
    min_stay = adjacent_data.iloc[0].get('Min Stay', 1)
    if pd.isna(min_stay):
        min_stay = 1
    
    print(f"🔍 DEBUG: Adjacent weekday {adjacent_weekday_str} has min stay: {min_stay}")
    
    # Return True if the adjacent weekday has 1-night minimum
    return min_stay == 1

def apply_rules_to_live_rates(df, selected_properties):
    """
    Apply property-specific rules to live rates and return adjusted rates.
    
    Args:
        df: DataFrame with rate data
        selected_properties: List of selected property keys
    
    Returns:
        Dict with results of rule application
    """
    if df is None or df.empty:
        return {
            'success': False,
            'message': 'No data available for rule application',
            'adjusted_rates': [],
            'total_rates': 0
        }
    
    # Load property configurations
    properties_config = load_properties_config()
    if not properties_config:
        return {
            'success': False,
            'message': 'Could not load property configurations',
            'adjusted_rates': [],
            'total_rates': 0
        }
    
    adjusted_rates = []
    total_rates = 0
    adjusted_dates = set()  # Track which dates have been adjusted to prevent double adjustments
    
    # Process each property
    for property_key in selected_properties:
        if property_key not in properties_config:
            continue
            
        prop_config = properties_config[property_key]
        property_df = df[df['Unit Pool'] == property_key].copy()
        
        if property_df.empty:
            continue
            
        # Get adjustment rules for this property
        adjustment_rules = prop_config.get('adjustment_rules', [])
        
        if not adjustment_rules:
            continue
            
        print(f"🔍 DEBUG: Processing {property_key} with {len(adjustment_rules)} rules")
        
        # Apply each rule
        for rule in adjustment_rules:
            rule_name = rule.get('name', 'Unnamed Rule')
            target_weekday = rule.get('target_weekday')
            conditions = rule.get('conditions', [])
            actions = rule.get('actions', [])
            
            if target_weekday is None:
                continue
                
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            print(f"🔍 DEBUG: Rule '{rule_name}' targets {weekday_names[target_weekday]} (weekday {target_weekday})")
            print(f"🔍 DEBUG: Conditions: {conditions}")
            
            # Filter for the target weekday
            weekday_dates = []
            for date_str in property_df['Date'].unique():
                try:
                    # Handle potential NaN values in date strings
                    if pd.isna(date_str):
                        continue
                    date_obj = datetime.datetime.strptime(str(date_str), '%Y-%m-%d').date()
                    if date_obj.weekday() == target_weekday:
                        weekday_dates.append(date_str)
                except (ValueError, TypeError):
                    continue
            
            print(f"🔍 DEBUG: Found {len(weekday_dates)} {weekday_names[target_weekday]} dates: {weekday_dates[:5]}...")
            
            if not weekday_dates:
                continue
                
            # Apply rule to each date
            for date_str in weekday_dates:
                try:
                    # Handle potential NaN values in date strings
                    if pd.isna(date_str):
                        continue
                    date_obj = datetime.datetime.strptime(str(date_str), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    continue
                
                print(f"🔍 DEBUG: Checking date {date_str} for rule '{rule_name}'")
                
                # Check if this date has already been adjusted (prevent double adjustments)
                date_key = f"{property_key}_{rule_name}_{date_str}"
                if date_key in adjusted_dates:
                    continue
                
                # Apply ALL actions defined for this rule
                if not actions:
                    continue

                # Apply to all listings for this property on this date
                date_listings = property_df[property_df['Date'] == date_str]

                for _, row in date_listings.iterrows():
                    # Do not skip booked rows outright: booked rows can TRIGGER adjacent-day LOS rules
                    is_booked = (row['Flag'] == '🔒 Booked')

                    for selected_action in actions:
                        multiplier = selected_action.get('multiplier', 1.0)
                        ref_day_offset = selected_action.get('reference_day_offset', 0)
                        los_adjustment = selected_action.get('los_adjustment')
                        check_adjacent_weekday_los = selected_action.get('check_adjacent_weekday_los', False)
                        target_adjacent_days = selected_action.get('target_adjacent_days')
                        min_stay_adjustment = selected_action.get('min_stay_adjustment')

                        # Compute reference date for this action
                        ref_date = date_obj + datetime.timedelta(days=ref_day_offset)
                        ref_date_str = ref_date.strftime('%Y-%m-%d')

                        # Apply to all listings for this property on this date (action scope)
                        # Note: reuse current row context below
                    
                        # Check if conditions are met for this specific listing
                        conditions_met = True
                        for i, condition in enumerate(conditions):
                            condition_result = _check_rule_condition(condition, date_obj, property_df, property_key, row['listing_id'])
                            print(f"🔍 DEBUG: Condition {i+1}: {condition} -> {condition_result} for listing {row['listing_id']}")
                            if not condition_result:
                                conditions_met = False
                                break

                        if not conditions_met:
                            print(f"🔍 DEBUG: Conditions not met for {date_str}, listing {row['listing_id']}, skipping")
                            continue

                        print(f"🔍 DEBUG: ✅ Conditions met for {date_str}, listing {row['listing_id']}, applying rule")

                        # Get reference day's live rate for this listing (for price adjustments)
                        ref_date_listings = property_df[
                            (property_df['Date'] == ref_date_str) &
                            (property_df['listing_id'] == row['listing_id'])
                        ]

                        # Initialize accumulators for this listing/date combination
                        current_min_stay = row.get('Min Stay', 1)
                        current_live_rate = row.get('Live Rate $', 0)

                        # Handle NaN values
                        if pd.isna(current_min_stay):
                            current_min_stay = 1
                        if pd.isna(current_live_rate):
                            current_live_rate = 0

                        acc_price = float(current_live_rate)
                        acc_min_stay = int(current_min_stay)
                        overall_change_applied = False
                        overall_reasons = []
                        last_ref_date_str = 'N/A'
                        last_ref_live_rate = 'N/A'
                        
                        # Store original values for comparison
                        original_price = float(current_live_rate)
                        original_min_stay = int(current_min_stay)

                        # Apply price adjustment if multiplier is specified and reference data exists
                        if not is_booked and multiplier != 1.0:
                            ref_live_rate = None

                            # Primary reference (e.g., Thu uses Wed, Sun uses Mon)
                            if not ref_date_listings.empty:
                                ref_live_rate = ref_date_listings.iloc[0].get('Live Rate $', 0)
                                if pd.isna(ref_live_rate):
                                    ref_live_rate = 0

                            # Fallback: one more day in the same direction (Thu→Tue, Sun→Tue)
                            if (ref_live_rate is None or ref_live_rate <= 0):
                                fallback_offset = ref_day_offset - 1 if ref_day_offset < 0 else ref_day_offset + 1
                                fb_date = date_obj + datetime.timedelta(days=fallback_offset)
                                fb_date_str = fb_date.strftime('%Y-%m-%d')
                                fb_listings = property_df[
                                    (property_df['Date'] == fb_date_str) &
                                    (property_df['listing_id'] == row['listing_id'])
                                ]
                                if not fb_listings.empty:
                                    fb_live = fb_listings.iloc[0].get('Live Rate $', 0)
                                    if not pd.isna(fb_live):
                                        ref_live_rate = float(fb_live)

                            if not ref_live_rate or ref_live_rate <= 0:
                                overall_reasons.append("reference rate missing (primary & fallback)")
                            else:
                                calculated_new_price = round(ref_live_rate * multiplier, 2)
                                # Guard: do not raise prices via rules; only reduce or keep the same
                                if calculated_new_price < acc_price:
                                    acc_price = calculated_new_price
                                    overall_change_applied = True
                                    last_ref_date_str = ref_date_str
                                    last_ref_live_rate = ref_live_rate
                                else:
                                    overall_reasons.append("would increase price; kept original")
                                    last_ref_date_str = ref_date_str
                                    last_ref_live_rate = ref_live_rate

                        # NEW: Handle min stay adjustment rules with target_adjacent_days
                        if min_stay_adjustment is not None and target_adjacent_days is not None:
                            print(f"🔍 DEBUG: Processing min stay reduction rule with target_adjacent_days: {target_adjacent_days}")
                            if is_booked:
                                print(f"🔍 DEBUG: Saturday (or target) listing {row['listing_id']} is booked, processing adjacent days for this listing only")
                                # Process other target days (Thursday/Friday) for this specific listing
                                for day_offset in target_adjacent_days:
                                    if day_offset == 0:  # Skip current date (already processed above)
                                        continue

                                    target_date = date_obj + datetime.timedelta(days=day_offset)
                                    target_date_str = target_date.strftime('%Y-%m-%d')

                                    print(f"🔍 DEBUG: Processing target date {target_date_str} (offset {day_offset}) for Saturday listing {row['listing_id']}")

                                    # Check if target date exists in data
                                    target_date_listings = property_df[property_df['Date'] == target_date_str]
                                    if target_date_listings.empty:
                                        print(f"🔍 DEBUG: Target date {target_date_str} not found in data, skipping")
                                        continue

                                    # CRITICAL FIX: Only process the specific listing that was booked on Saturday
                                    target_listing_data = target_date_listings[target_date_listings['listing_id'] == row['listing_id']]
                                    if target_listing_data.empty:
                                        print(f"🔍 DEBUG: Target listing {row['listing_id']} not found on target date {target_date_str}, skipping")
                                        continue

                                    target_row = target_listing_data.iloc[0]
                                    if target_row['Flag'] == '🔒 Booked':
                                        overall_reasons.append(f"target {target_date_str} booked; skipped")
                                        continue

                                    target_current_min_stay = target_row.get('Min Stay', 1)
                                    if pd.isna(target_current_min_stay):
                                        target_current_min_stay = 1

                                    target_new_min_stay = target_current_min_stay

                                    if check_adjacent_weekday_los:
                                        # Check if adjacent weekday has 1-night minimum for this target day
                                        adjacent_has_1night = _check_adjacent_weekday_los_for_target(
                                            target_date, property_df, property_key, target_row['listing_id'], day_offset
                                        )
                                        if adjacent_has_1night:
                                            target_new_min_stay = min_stay_adjustment
                                        else:
                                            overall_reasons.append(f"prereq failed for {target_date_str} (weekday not 1-night)")
                                            continue
                                    else:
                                        target_new_min_stay = min_stay_adjustment

                                    # Only append a target adjustment when it actually changes something
                                    if target_new_min_stay != target_current_min_stay:
                                        adjusted_rates.append({
                                            'listing_id': target_row['listing_id'],
                                            'listing_name': target_row['listing_name'],
                                            'date': target_date_str,
                                            'original_price': target_row.get('Live Rate $', 0),
                                            'new_price': target_row.get('Live Rate $', 0),  # No price change in this path
                                            'original_min_stay': target_current_min_stay,
                                            'new_min_stay': target_new_min_stay,
                                            'rule_applied': rule_name,
                                            'multiplier': 1.0,
                                            'property': property_key,
                                            'reference_date': 'N/A',
                                            'reference_rate': 'N/A',
                                            'change_applied': True,
                                            'reason': ''
                                        })
                                    else:
                                        overall_reasons.append(f"no LOS change needed on {target_date_str} (already {target_current_min_stay}n)")
                            else:
                                print(f"🔍 DEBUG: Saturday listing {row['listing_id']} is NOT booked, skipping adjacent day processing")

                        # Apply traditional LOS adjustment if specified (for backward compatibility)
                        elif los_adjustment is not None:
                            if check_adjacent_weekday_los:
                                adjacent_has_2night = _check_adjacent_weekday_los(date_obj, property_df, property_key, row['listing_id'])
                                if adjacent_has_2night:
                                    if los_adjustment != acc_min_stay:
                                        acc_min_stay = los_adjustment
                                        overall_change_applied = True
                                else:
                                    overall_reasons.append("LOS prerequisite failed; skipped")
                            else:
                                if los_adjustment != acc_min_stay:
                                    acc_min_stay = los_adjustment
                                    overall_change_applied = True

                        # Only mark as changed if there were actual modifications by rules
                        if acc_price != original_price or acc_min_stay != original_min_stay:
                            overall_change_applied = True
                            
                        # Debug logging
                        print(f"🔍 DEBUG: {date_str} {row['listing_name']}: price {original_price}→{acc_price}, min_stay {original_min_stay}→{acc_min_stay}, change_applied={overall_change_applied}, reasons={overall_reasons}")

                        adjusted_rates.append({
                            'listing_id': row['listing_id'],
                            'listing_name': row['listing_name'],
                            'date': date_str,
                            'original_price': current_live_rate,
                            'new_price': acc_price,
                            'original_min_stay': current_min_stay,
                            'new_min_stay': acc_min_stay,
                            'rule_applied': rule_name,  # aggregated
                            'multiplier': 1.0,          # aggregated
                            'property': property_key,
                            'reference_date': last_ref_date_str,
                            'reference_rate': last_ref_live_rate,
                            'change_applied': overall_change_applied,
                            'reason': "; ".join(overall_reasons) if overall_reasons else ''
                        })

                # Mark this date as adjusted
                adjusted_dates.add(date_key)
    
    total_rates = len(adjusted_rates)
    
    # Count actual changes
    actual_changes = sum(1 for rate in adjusted_rates if rate.get('change_applied', False))
    
    return {
        'success': True,
        'adjusted_rates': adjusted_rates,
        'total_rates': total_rates,
        'actual_changes': actual_changes,
        'message': f'Applied rules to {len(adjusted_rates)} rates across {len(selected_properties)} properties ({actual_changes} with actual changes)',
    }

def _check_rule_condition(condition, date_obj, df, property_key, listing_id=None):
    """
    Check if a rule condition is met.
    
    Args:
        condition: Condition configuration dict
        date_obj: Date to check
        df: DataFrame with rate data
        property_key: Property key
        listing_id: Specific listing ID to check (optional)
    
    Returns:
        bool: True if condition is met
    """
    if condition is None:
        return True
        
    condition_type = condition.get('type')
    
    if condition_type == 'adjacent_day_booked':
        day_offset = condition.get('day_offset', 0)
        adjacent_date = date_obj + datetime.timedelta(days=day_offset)
        adjacent_date_str = adjacent_date.strftime('%Y-%m-%d')
        
        # Check if the specific listing is booked on the adjacent date
        if listing_id:
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key) &
                (df['listing_id'] == listing_id)
            ]
            is_booked = any(adjacent_data['Flag'] == '🔒 Booked')
        else:
            # Fallback to property-wide check if no specific listing provided
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key)
            ]
            is_booked = any(adjacent_data['Flag'] == '🔒 Booked')
        
        print(f"🔍 DEBUG: adjacent_day_booked check for {adjacent_date_str}: {is_booked}")
        print(f"🔍 DEBUG: Found {len(adjacent_data)} rows for {adjacent_date_str}")
        if not adjacent_data.empty:
            print(f"🔍 DEBUG: Flag values: {adjacent_data['Flag'].unique()}")
            print(f"🔍 DEBUG: Listing IDs for {adjacent_date_str}: {adjacent_data['listing_id'].unique()}")
            print(f"🔍 DEBUG: Listing names for {adjacent_date_str}: {adjacent_data['listing_name'].unique()}")
        
        return is_booked
    
    elif condition_type == 'adjacent_day_not_booked':
        day_offset = condition.get('day_offset', 0)
        adjacent_date = date_obj + datetime.timedelta(days=day_offset)
        adjacent_date_str = adjacent_date.strftime('%Y-%m-%d')
        
        # Check if the specific listing is NOT booked on the adjacent date
        if listing_id:
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key) &
                (df['listing_id'] == listing_id)
            ]
            is_not_booked = not any(adjacent_data['Flag'] == '🔒 Booked')
        else:
            # Fallback to property-wide check if no specific listing provided
            adjacent_data = df[
                (df['Date'] == adjacent_date_str) & 
                (df['Unit Pool'] == property_key)
            ]
            is_not_booked = not any(adjacent_data['Flag'] == '🔒 Booked')
        
        print(f"🔍 DEBUG: adjacent_day_not_booked check for {adjacent_date_str}: {is_not_booked}")
        print(f"🔍 DEBUG: Found {len(adjacent_data)} rows for {adjacent_date_str}")
        if not adjacent_data.empty:
            print(f"🔍 DEBUG: Flag values: {adjacent_data['Flag'].unique()}")
            print(f"🔍 DEBUG: Listing IDs for {adjacent_date_str}: {adjacent_data['listing_id'].unique()}")
            print(f"🔍 DEBUG: Listing names for {adjacent_date_str}: {adjacent_data['listing_name'].unique()}")
        
        return is_not_booked
    
    elif condition_type == 'upcoming_weekend':
        # Check if this is the immediate upcoming weekend
        today = datetime.datetime.now().date()
        
        # Calculate days until this Friday
        current_weekday = date_obj.weekday()
        days_until_friday = (4 - today.weekday()) % 7  # 4 = Friday
        if days_until_friday == 0:  # Today is Friday
            days_until_friday = 7  # Next Friday
        
        # Calculate the immediate upcoming Friday
        upcoming_friday = today + datetime.timedelta(days=days_until_friday)
        upcoming_saturday = upcoming_friday + datetime.timedelta(days=1)
        
        # Return True only if current_date is the upcoming Friday or Saturday
        is_upcoming_weekend = date_obj in [upcoming_friday, upcoming_saturday]
        print(f"🔍 DEBUG: upcoming_weekend condition for {date_obj}: {is_upcoming_weekend}")
        print(f"🔍 DEBUG: Today: {today}, Upcoming Friday: {upcoming_friday}, Upcoming Saturday: {upcoming_saturday}")
        return is_upcoming_weekend
    
    return False

def _check_adjacent_weekday_los(date_obj, df, property_key, listing_id):
    """
    DEPRECATED: This function is hardcoded to check Mon-Wed and should not be used for new rules.
    Use _check_adjacent_weekday_los_for_target() instead for proper adjacent weekday checking.
    
    Check if adjacent weekdays (Mon-Wed) have 2-night minimum for a specific listing.
    
    Args:
        date_obj: Date to check
        df: DataFrame with rate data
        property_key: Property key
        listing_id: Specific listing ID to check
    
    Returns:
        bool: True if adjacent weekdays have 2-night minimum
    """
    # DEPRECATED: This function is hardcoded to check Mon-Wed regardless of target day
    # Check Monday, Tuesday, Wednesday (weekdays 0, 1, 2)
    adjacent_weekdays = []
    for i in range(3):  # Mon, Tue, Wed
        weekday_date = date_obj + datetime.timedelta(days=i)
        adjacent_weekdays.append(weekday_date)
    
    for weekday_date in adjacent_weekdays:
        weekday_date_str = weekday_date.strftime('%Y-%m-%d')
        
        # Get the listing data for this weekday
        listing_data = df[
            (df['Date'] == weekday_date_str) & 
            (df['Unit Pool'] == property_key) & 
            (df['listing_id'] == listing_id)
        ]
        
        if not listing_data.empty:
            min_stay = listing_data.iloc[0].get('Min Stay', 1)
            if pd.isna(min_stay):
                min_stay = 1
            
            # If any weekday has 2-night minimum, return True
            if min_stay >= 2:
                return True
    
    # If no weekdays have 2-night minimum, return False
    return False

