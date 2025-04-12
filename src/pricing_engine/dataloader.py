# src/pricing_engine/dataloader.py

import pandas as pd
from pathlib import Path
import datetime
from typing import Dict, Set, Tuple, Any

# Assuming utils.py is in the same directory or Python path is set correctly
from . import utils # Use relative import within the package

def _parse_mixed_date(date_val: Any) -> pd.Timestamp:
    """Attempts to parse a date string in M/D/YY format first,
       then falls back to parsing as an Excel serial number if the first fails.
    """
    if pd.isna(date_val):
        return pd.NaT
    try:
        # Attempt standard M/D/YY format first
        # Use errors='raise' to trigger the except block if format is wrong
        return pd.to_datetime(date_val, format='%m/%d/%y', errors='raise')
    except (ValueError, TypeError):
        try:
            # If standard parse fails, attempt Excel serial number format
            # Convert to numeric first, coercing errors (like non-numeric strings)
            numeric_val = pd.to_numeric(date_val, errors='coerce')
            if pd.isna(numeric_val):
                return pd.NaT # Value wasn't a valid number
            # Origin for Excel serial dates (adjust if using Mac 1904 base)
            return pd.to_datetime(numeric_val, unit='D', origin='1899-12-30')
        except (ValueError, TypeError):
            # If both attempts fail, return NaT
            return pd.NaT

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
        # UPDATED: Hardcode for fb1 comma separator and column names
        dates_tiers_df = pd.read_csv(
            dates_tiers_path,
            sep=',',              # fb1 uses comma
            usecols=['Date', 'Tier'], # Use column names matching fb1
            parse_dates=['Date'],   # Parse the 'Date' column
            header=0             # Assumes first row IS a header
        )
        # Rename columns for clarity after loading
        # Ensure internal code uses consistent names ('date', 'tier_group')
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
        # UPDATED: Hardcode column names for fb1 pl_daily
        pl_df = pd.read_csv(
            pl_daily_path,
            parse_dates=['Date'], # Use the actual 'Date' column name from CSV
            # Ensure 'Listing ID' column exists in your CSV and is used here
            usecols=['Date', 'Listing ID', 'No. Booked', 'No. Blocked'], # Use fb1 names
            dtype={'Listing ID': str} # Ensure Listing ID is read as string
        )

        # Convert numeric columns, coercing errors to NaN
        # UPDATED: Use actual fb1 column names
        pl_df['No. Booked'] = pd.to_numeric(pl_df['No. Booked'], errors='coerce').fillna(0)
        pl_df['No. Blocked'] = pd.to_numeric(pl_df['No. Blocked'], errors='coerce').fillna(0)

        # Use 'Date' column for validation
        if not pd.api.types.is_datetime64_any_dtype(pl_df['Date']):
             raise ValueError("Could not parse 'Date' column as datetime.")

        # Filter for relevant rows
        # UPDATED: Use actual fb1 column names
        relevant_pl = pl_df[ (pl_df['No. Booked'] > 0) | (pl_df['No. Blocked'] > 0) ].copy()

        # Process into the set
        for _, row in relevant_pl.iterrows():
            # Use 'Date' column for date processing
            if pd.notna(row['Date']) and pd.notna(row['Listing ID']):
                date_str = utils.format_date(row['Date'].date())
                listing_id = str(row['Listing ID']).strip()
                # Directly add the ID to the set
                booked_blocked_set.add((listing_id, date_str))

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
        # UPDATED: Load date columns as object/string first
        res_df = pd.read_csv(
            resdata_path,
            usecols=['Start Date', 'End Date'],     # Use fb1 names
            dtype={'Start Date': object, 'End Date': object} # Read as generic object/string
        )

        # Apply the custom parsing function to each date column
        res_df['Start Date_dt'] = res_df['Start Date'].apply(_parse_mixed_date)
        res_df['End Date_dt'] = res_df['End Date'].apply(_parse_mixed_date)

        # Identify rows that failed parsing (are NaT after apply)
        failed_parse_mask = res_df['Start Date_dt'].isnull() | res_df['End Date_dt'].isnull()
        if failed_parse_mask.any():
            print("--- Warning: Rows with unparseable date formats found in resdata_fb1.csv ---")
            print("Original Start/End Date strings for failed rows:")
            # Show original strings for rows that failed BOTH parsing attempts
            print(res_df.loc[failed_parse_mask, ['Start Date', 'End Date']])
            print("---------------------------------------------------------------------")
            # Drop rows with invalid dates before proceeding
            res_df = res_df[~failed_parse_mask].copy()
        else:
             print("All resdata dates parsed successfully using custom parser.")

        # Now 'Start Date_dt' and 'End Date_dt' columns contain datetime objects
        confirmed_res = res_df.copy() # Use the cleaned dataframe

        # No need to check dtype again here
        print(f"Found {len(confirmed_res)} valid reservations in {resdata_path} after handling date errors.")

        # Expand reservations into daily stays (one row per occupied night)
        daily_stays_list = []
        for _, row in confirmed_res.iterrows(): # Use _ if index not needed
            # Check-out date is the morning after the last night stayed
            # Need date range from check_in up to, but not including, check_out
            # UPDATED: Use the _dt columns which contain datetime objects
            start_date_obj = row['Start Date_dt']
            end_date_obj = row['End Date_dt']

            if pd.notna(start_date_obj) and pd.notna(end_date_obj) and end_date_obj > start_date_obj:
                # Generate dates for each night stayed
                # Exclude the check-out date since it's not a night stayed
                # UPDATED: Use the _dt objects
                date_range = pd.date_range(start_date_obj, end_date_obj - pd.Timedelta(days=1), freq='D')
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
