#!/usr/bin/env python3
"""
Script to generate pl_daily files for ALL properties defined in the config file.
This will process every property automatically without needing to specify them individually.
"""

import yaml
import sys
import time
from datetime import datetime, timedelta
from generate_pl_daily_comprehensive import generate_pl_daily_for_property, save_pl_daily_csv

def get_all_properties_from_config():
    """Get all property keys from the config file."""
    with open('config/properties.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    return list(config['properties'].keys())

def process_all_properties(start_date="2025-01-01", end_date="2026-12-31"):
    """Process all properties defined in the config file."""
    
    # Get all property keys
    property_keys = get_all_properties_from_config()
    
    print(f"🚀 Processing ALL properties from config file")
    print(f"📅 Date range: {start_date} to {end_date}")
    print(f"🏢 Total properties found: {len(property_keys)}")
    print("=" * 80)
    
    successful_properties = []
    failed_properties = []
    
    for i, property_key in enumerate(property_keys, 1):
        print(f"\n{'='*80}")
        print(f"📋 Processing Property {i}/{len(property_keys)}: {property_key}")
        print(f"{'='*80}")
        
        try:
            # Generate pl_daily data for this property
            pl_daily_data = generate_pl_daily_for_property(property_key, start_date, end_date)
            
            if pl_daily_data:
                # Save to CSV
                filepath = save_pl_daily_csv(pl_daily_data, property_key)
                successful_properties.append(property_key)
                print(f"✅ Successfully processed {property_key}")
            else:
                failed_properties.append(property_key)
                print(f"❌ Failed to process {property_key}")
                
        except Exception as e:
            failed_properties.append(property_key)
            print(f"❌ Error processing {property_key}: {str(e)}")
        
        # Add delay between properties to avoid rate limiting
        if i < len(property_keys):  # Don't delay after the last property
            print(f"⏳ Waiting 3 seconds before next property...")
            time.sleep(3)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 PROCESSING SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successfully processed: {len(successful_properties)} properties")
    print(f"❌ Failed to process: {len(failed_properties)} properties")
    
    if successful_properties:
        print(f"\n✅ Successful properties:")
        for prop in successful_properties:
            print(f"   - {prop}")
    
    if failed_properties:
        print(f"\n❌ Failed properties:")
        for prop in failed_properties:
            print(f"   - {prop}")
    
    return successful_properties, failed_properties

if __name__ == "__main__":
    # Check if date range is provided as command line arguments
    if len(sys.argv) > 2:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
    else:
        # Default date range
        start_date = "2025-01-01"
        end_date = "2026-12-31"
    
    print(f"🎯 Generating pl_daily data for ALL properties")
    print(f"📅 Date range: {start_date} to {end_date}")
    print("=" * 80)
    
    successful, failed = process_all_properties(start_date, end_date)
    
    print(f"\n🎉 Processing complete!")
    print(f"📁 Check the 'data' directories for generated CSV files") 