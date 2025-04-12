# src/pricing_engine/dataloader.py

import pandas as pd
from pathlib import Path
import datetime
from typing import Dict, Set, Tuple, Any

# Assuming utils.py is in the same directory or Python path is set correctly
from . import utils # Use relative import within the package

def load_and_preprocess_data(property_name: str, property_config: dict) -> Tuple[pd.DataFrame, Dict[str, str], Set[Tuple[str, str]], Dict[str, float]]:
    """
    Loads and preprocesses all necessary data for a given property.

    Args:
        property_name: The identifier of the property (e.g., 'fb1'),
                       corresponding to the data subdirectory name.
        property_config: The configuration dictionary for this specific property
                         loaded from properties.yaml.

    Returns:
        A tuple containing:
        - rate_table_df: DataFrame of the property's rate table.
        - date_tier_map: Dictionary mapping 'YYYY-MM-DD' -> tier_group string.
        - booked_blocked_set: Set of tuples ('listing_id', 'YYYY-MM-DD')
                              for dates that are booked or blocked.
        - occupancy_map: Dictionary mapping 'YYYY-MM-DD' -> occupancy percentage (0-100).

    Raises:
        FileNotFoundError: If any required CSV file is missing.
        KeyError: If expected columns are missing in the CSV files.
        ValueError: If critical data cannot be processed (e.g., date parsing).
    """
    print(f"--- Loading data for property: {property_name} ---")
    base_path = Path("data") / property_name
    total_listings_for_property = len(property_config.get('listings', []))
    if total_listings_for_property == 0:
        raise ValueError(f"No listings found in configuration for property '{property_name}'. Cannot calculate occupancy.")

    # Create a mapping from listing ID to listing name
    listing_id_map = {
        str(listing['id']): listing['name']
        for listing in property_config.get('listings', [])
        if 'id' in listing and 'name' in listing # Basic validation
    }
    if not listing_id_map:
        print(f"Warning: Could not create listing ID to name map for property '{property_name}'. Check configuration.")


    # --- Load Rate Table ---
    rate_table_path = base_path / f"rate_table_{property_name}.csv"
    try:
        rate_table_df = pd.read_csv(rate_table_path)
        # Basic validation (add more checks as needed)
        required_rate_cols = ['tier_group', 'day_group', 'booking_window', 'Occupancy Band', 'occupancy_min_pct', 'occupancy_max_pct']
        # Add expected rate group columns based on config
        for rate_col in property_config.get('rate_group_mapping', {}).keys():
             required_rate_cols.append(rate_col) # Assumes column names match keys directly

        if not all(col in rate_table_df.columns for col in required_rate_cols):
             raise KeyError(f"Rate table missing one or more required columns: {required_rate_cols}")

        # Clean rate columns by removing dollar signs and extra spaces
        for rate_col in property_config.get('rate_group_mapping', {}).keys():
            rate_table_df[rate_col] = rate_table_df[rate_col].str.replace('$', '').str.strip()

        print(f"Loaded Rate Table: {rate_table_path}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Rate table file not found: {rate_table_path}")
    except Exception as e:
        raise ValueError(f"Error loading or validating rate table {rate_table_path}: {e}")


    # --- Load Date Tiers ---
    dates_tiers_path = base_path / f"dates_tiers_{property_name}.csv"
    date_tier_map: Dict[str, str] = {}
    try:
        # Specify column names if CSV has no header or different names
        # Assuming columns are 'Date', 'Day', 'Tier' (index 0, 1, 2)
        dates_tiers_df = pd.read_csv(
            dates_tiers_path,
            parse_dates=['Date'], # Attempt to parse the first column as date
            usecols=[0, 2], # Assuming Date is col 0, Tier is col 2
            header=0 # Assumes first row IS a header
        )
        # Rename columns for clarity if needed after loading based on index
        if len(dates_tiers_df.columns) == 2:
            dates_tiers_df.columns = ['date', 'tier_group']

        if not pd.api.types.is_datetime64_any_dtype(dates_tiers_df['date']):
             raise ValueError("Could not parse 'date' column as datetime.")

        for _, row in dates_tiers_df.iterrows():
             # Ensure date is valid and format it; handle potential NaT dates
             if pd.notna(row['date']) and pd.notna(row['tier_group']):
                  date_str = utils.format_date(row['date'].date())
                  date_tier_map[date_str] = str(row['tier_group']).strip() # Ensure tier is string
        print(f"Loaded Date Tiers: {dates_tiers_path}, {len(date_tier_map)} entries processed.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Dates tiers file not found: {dates_tiers_path}")
    except Exception as e:
        raise ValueError(f"Error loading or processing date tiers {dates_tiers_path}: {e}")


    # --- Load PL Daily (for Booked/Blocked Status) ---
    pl_daily_path = base_path / f"pl_daily_{property_name}.csv"
    booked_blocked_set: Set[Tuple[str, str]] = set()
    try:
        # Adjust column names to match your CSV ('Date', 'Listing ID', etc.)
        pl_df = pd.read_csv(
            pl_daily_path,
            parse_dates=['Date'], # Use the actual 'Date' column name from CSV
            # Ensure 'Listing ID' column exists in your CSV and is used here
            usecols=['Date', 'Listing ID', 'no_booked', 'no_blocked'], # Use Listing ID and Date
            dtype={'Listing ID': str} # Ensure Listing ID is read as string
        )

        # Convert numeric columns, coercing errors to NaN
        pl_df['no_booked'] = pd.to_numeric(pl_df['no_booked'], errors='coerce').fillna(0)
        pl_df['no_blocked'] = pd.to_numeric(pl_df['no_blocked'], errors='coerce').fillna(0)

        # Use 'Date' column for validation
        if not pd.api.types.is_datetime64_any_dtype(pl_df['Date']):
             raise ValueError("Could not parse 'Date' column as datetime.")

        # Filter for relevant rows
        relevant_pl = pl_df[ (pl_df['no_booked'] > 0) | (pl_df['no_blocked'] > 0) ].copy()

        # Process into the set
        for _, row in relevant_pl.iterrows():
            # Use 'Date' column for date processing
            if pd.notna(row['Date']) and pd.notna(row['Listing ID']):
                date_str = utils.format_date(row['Date'].date())
                listing_id = str(row['Listing ID']).strip()
                # No longer need to convert ID to Name here
                # Directly add the ID to the set
                booked_blocked_set.add((listing_id, date_str))
                # Remove the old conversion and warning logic
                # listing_name = listing_id_map.get(listing_id)
                # if listing_name:
                #     booked_blocked_set.add((listing_name, date_str))
                # else:
                #     print(f"Warning: Listing ID '{listing_id}' from {pl_daily_path} not found in properties.yaml configuration for {property_name}.")

        print(f"Loaded PL Daily: {pl_daily_path}, {len(booked_blocked_set)} booked/blocked entries processed.")
    except FileNotFoundError:
        raise FileNotFoundError(f"PL Daily file not found: {pl_daily_path}")
    except KeyError as e:
         raise KeyError(f"Missing expected column in {pl_daily_path}: {e}. Check usecols.")
    except Exception as e:
        raise ValueError(f"Error loading or processing PL Daily {pl_daily_path}: {e}")


    # --- Load Resdata (for Occupancy Calculation) ---
    resdata_path = base_path / f"resdata_{property_name}.csv"
    occupancy_map: Dict[str, float] = {}
    try:
        # Adjust column names as necessary ('check_in_date', 'check_out_date')
        res_df = pd.read_csv(
            resdata_path,
            parse_dates=['check_in_date', 'check_out_date'], # Actual names
            usecols=['check_in_date', 'check_out_date'] # No status column
        )

        # Since there's no status column, we'll assume all reservations are confirmed
        confirmed_res = res_df.copy()

        if not pd.api.types.is_datetime64_any_dtype(confirmed_res['check_in_date']):
             raise ValueError("Could not parse 'check_in_date' column as datetime.")
        if not pd.api.types.is_datetime64_any_dtype(confirmed_res['check_out_date']):
             raise ValueError("Could not parse 'check_out_date' column as datetime.")

        print(f"Found {len(confirmed_res)} reservations in {resdata_path}.")

        # Expand reservations into daily stays (one row per occupied night)
        daily_stays_list = []
        for _, row in confirmed_res.iterrows():
            # Check-out date is the morning after the last night stayed
            # Need date range from check_in up to, but not including, check_out
            if pd.notna(row['check_in_date']) and pd.notna(row['check_out_date']) and row['check_out_date'] > row['check_in_date']:
                # Generate dates for each night stayed
                # Exclude the check-out date since it's not a night stayed
                date_range = pd.date_range(row['check_in_date'], row['check_out_date'] - pd.Timedelta(days=1), freq='D')
                for stay_date in date_range:
                    daily_stays_list.append({'stay_date': stay_date.date()}) # Store only date part

        if not daily_stays_list:
            print("Warning: No valid daily stays generated from reservation data.")
            # Occupancy map will remain empty, which is handled later
        else:
            daily_stays_df = pd.DataFrame(daily_stays_list)

            # Count stays per date
            daily_counts = daily_stays_df.groupby('stay_date').size()

            # Calculate occupancy percentage
            occupancy_percentage = (daily_counts / total_listings_for_property) * 100

            # Convert to dictionary: 'YYYY-MM-DD' -> percentage
            occupancy_map = {utils.format_date(idx): val for idx, val in occupancy_percentage.items()}
            print(f"Processed Resdata: Occupancy calculated for {len(occupancy_map)} dates.")

    except FileNotFoundError:
        raise FileNotFoundError(f"Resdata file not found: {resdata_path}")
    except KeyError as e:
        raise KeyError(f"Missing expected column in {resdata_path}: {e}. Check column names.")
    except Exception as e:
        raise ValueError(f"Error loading or processing Resdata {resdata_path}: {e}")


    print(f"--- Data loading complete for {property_name} ---")
    return rate_table_df, date_tier_map, booked_blocked_set, occupancy_map
