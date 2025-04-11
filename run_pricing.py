# run_pricing.py

import argparse
import datetime
import pandas as pd
import yaml
from pathlib import Path
import sys # For exiting on error

# Add src directory to Python path to allow absolute imports
# (Alternatively, run this script as a module `python -m dynamic_pricing_tool.run_pricing`)
# For simplicity in direct execution, we adjust the path:
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

try:
    from pricing_engine import dataloader, calculator, utils
except ImportError as e:
    print(f"Error importing pricing_engine modules: {e}")
    print("Ensure the script is run from the 'dynamic_pricing_tool' directory "
          "or that the 'src' directory is in the Python path.")
    sys.exit(1)

def load_config(config_path: Path) -> dict:
    """Loads YAML configuration from the specified path."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {config_path}: {e}")
        sys.exit(1)

def main():
    """Main function to run the dynamic pricing generation."""

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Generate dynamic pricing rates for a specified property.")
    parser.add_argument('-p', '--property', required=True,
                        help="Name of the property to process (must match a key in properties.yaml and a data subdirectory name)")
    # Add optional arguments for start/end date override if needed later
    # parser.add_argument('--start-date', help="Start date in YYYY-MM-DD format (overrides settings.yaml)")
    # parser.add_argument('--end-date', help="End date in YYYY-MM-DD format (overrides settings.yaml)")
    args = parser.parse_args()
    property_to_run = args.property.strip()

    print(f"Starting pricing generation for property: {property_to_run}")

    # --- Load Configurations ---
    config_dir = Path("config")
    settings = load_config(config_dir / "settings.yaml")
    properties_config = load_config(config_dir / "properties.yaml")

    # --- Validate Property ---
    if property_to_run not in properties_config.get('properties', {}):
        print(f"Error: Property '{property_to_run}' not found in config/properties.yaml.")
        sys.exit(1)
    property_config = properties_config['properties'][property_to_run]

    # --- Determine Date Range ---
    try:
        start_date_str = settings.get('start_date', '')
        end_date_str = settings.get('end_date', '')
        # Add logic here to handle CLI overrides if implemented
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        if start_date > end_date:
             raise ValueError("Start date cannot be after end date.")
    except (ValueError, TypeError) as e:
        print(f"Error: Invalid date format or range in config/settings.yaml (use YYYY-MM-DD): {e}")
        sys.exit(1)

    today = datetime.date.today()
    print(f"Processing date range: {utils.format_date(start_date)} to {utils.format_date(end_date)}")
    print(f"Reference date (today): {utils.format_date(today)}")

    # --- Load and Preprocess Data ---
    try:
        rate_table_df, date_tier_map, booked_blocked_set, occupancy_map = \
            dataloader.load_and_preprocess_data(property_to_run, property_config)
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"Error during data loading: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        sys.exit(1)


    # --- Generate Rates ---
    results = []
    listings_to_process = property_config.get('listings', [])
    if not listings_to_process:
        print(f"Warning: No listings defined for property '{property_to_run}' in configuration. Exiting.")
        sys.exit(0)

    print(f"Processing {len(listings_to_process)} listings...")

    # Generate all dates in the range once
    date_range = pd.date_range(start_date, end_date, freq='D').date

    for listing_name in listings_to_process:
        # print(f"  Processing listing: {listing_name}") # Uncomment for verbose logging
        rate_group_key = calculator._get_rate_group_for_listing(listing_name, property_config)
        if not rate_group_key:
            print(f"  Skipping listing '{listing_name}' due to missing rate group mapping.")
            continue

        for current_date in date_range:
            date_str = utils.format_date(current_date)

            # Get factors for this date/listing
            occupancy_pct = occupancy_map.get(date_str, 0.0)
            tier_group = date_tier_map.get(date_str, 'T0') # Default to T0 if date not in map
            booking_window_label = utils.get_booking_window_label(current_date, today)
            day_group = utils.get_day_group(current_date)
            occupancy_band = (occupancy_pct // 10) * 10 # Floor to nearest 10%

            # Determine if urgency calculation is needed
            urgency_band = ""
            if (tier_group in ["T10-T12", "T13-T15"]) and \
               (booking_window_label == "0-9 Days (W1)") and \
               (occupancy_pct <= 30):
               urgency_band = utils.get_urgency_band(current_date, today)

            # Look up suggested rate
            suggested_rate = calculator.lookup_rate(
                rate_table_df=rate_table_df,
                tier_group=tier_group,
                day_group=day_group,
                booking_window=booking_window_label,
                occupancy_pct=occupancy_pct,
                urgency_band=urgency_band,
                rate_group_key=rate_group_key
            )

            # Apply adjustment rules
            adjusted_rate = calculator.apply_adjustment_rules(
                current_date=current_date,
                listing_name=listing_name,
                occupancy_pct=occupancy_pct,
                rate_table_df=rate_table_df,
                date_tier_map=date_tier_map,
                booked_blocked_set=booked_blocked_set,
                booking_window_label=booking_window_label,
                property_config=property_config,
                today=today
            )

            # Append result
            results.append({
                "listing": listing_name,
                "date": date_str,
                "occupancy_percent": round(occupancy_pct, 2),
                "suggested_rate": round(suggested_rate) if pd.notna(suggested_rate) else None, # Round if not NaN/None
                "adjusted_rate": round(adjusted_rate) if pd.notna(adjusted_rate) else None, # Round if not NaN/None
                "final_tier": tier_group,
                "booking_window": booking_window_label
            })

    # --- Process and Save Output ---
    if not results:
        print("No results generated.")
        sys.exit(0)

    output_df = pd.DataFrame(results)

    # Define output path
    output_dir = Path(settings.get('output_directory', 'output/'))
    output_dir.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
    output_filename = f"generated_rates_{property_to_run}_{today.strftime('%Y%m%d')}.csv"
    output_path = output_dir / output_filename

    try:
        # Convert rate columns to nullable integers for cleaner CSV output (shows empty instead of NaN)
        output_df['suggested_rate'] = output_df['suggested_rate'].astype('Int64')
        output_df['adjusted_rate'] = output_df['adjusted_rate'].astype('Int64')

        output_df.to_csv(output_path, index=False)
        print("-" * 30)
        print(f"Successfully generated rates for {property_to_run}.")
        print(f"Output saved to: {output_path}")
        print("-" * 30)
    except Exception as e:
        print(f"Error saving output file to {output_path}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()