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

def process_all_properties(start_date=None, end_date="2027-12-31"):
    # If no start_date provided, use one month before today
    if start_date is None:
        from datetime import datetime, timedelta
        today = datetime.now()
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
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
            delay = 5 if i % 3 == 0 else 3  # Longer delay every 3rd property
            print(f"⏳ Waiting {delay} seconds before next property...")
            time.sleep(delay)
    
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
        
        # Second pass: retry failed properties with longer delays
        print(f"\n{'='*80}")
        print(f"🔄 RETRYING FAILED PROPERTIES")
        print(f"{'='*80}")
        print(f"⏳ Waiting 30 seconds before retry attempts...")
        time.sleep(30)  # Wait for rate limits to reset
        
        retry_successful = []
        still_failed = []
        
        for i, property_key in enumerate(failed_properties, 1):
            print(f"\n{'='*60}")
            print(f"🔄 Retry {i}/{len(failed_properties)}: {property_key}")
            print(f"{'='*60}")
            
            try:
                # Try to generate pl_daily data for this property again
                pl_daily_data = generate_pl_daily_for_property(property_key, start_date, end_date)
                
                if pl_daily_data:
                    # Save to CSV
                    filepath = save_pl_daily_csv(pl_daily_data, property_key)
                    retry_successful.append(property_key)
                    successful_properties.append(property_key)  # Move to successful
                    print(f"✅ Successfully retried {property_key}")
                else:
                    still_failed.append(property_key)
                    print(f"❌ Still failed to process {property_key}")
                    
            except Exception as e:
                still_failed.append(property_key)
                print(f"❌ Error retrying {property_key}: {str(e)}")
            
            # Longer delay between retry attempts
            if i < len(failed_properties):
                print(f"⏳ Waiting 10 seconds before next retry...")
                time.sleep(10)
        
        # Update failed properties list
        failed_properties = still_failed
        
        if retry_successful:
            print(f"\n✅ Successfully retried: {len(retry_successful)} properties")
            for prop in retry_successful:
                print(f"   - {prop}")
    
    # Final summary
    print(f"\n{'='*80}")
    print(f"📊 FINAL PROCESSING SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successfully processed: {len(successful_properties)} properties")
    print(f"❌ Still failed: {len(failed_properties)} properties")
    
    if successful_properties:
        print(f"\n✅ Successful properties:")
        for prop in successful_properties:
            print(f"   - {prop}")
    
    if failed_properties:
        print(f"\n❌ Still failed properties:")
        for prop in failed_properties:
            print(f"   - {prop}")
        print(f"\n💡 These properties may need manual investigation or longer delays")
    
    return successful_properties, failed_properties

if __name__ == "__main__":
    # Check if date range is provided as command line arguments
    if len(sys.argv) > 2:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
    else:
        # Default date range - start_date will be dynamic (one month before today)
        start_date = None  # Will be set to one month before today
        end_date = "2027-12-31"
    
    print(f"🎯 Generating pl_daily data for ALL properties")
    print(f"📅 Date range: {start_date} to {end_date}")
    print("=" * 80)
    
    successful, failed = process_all_properties(start_date, end_date)
    
    if failed:
        print(f"\n⚠️  Some properties still failed after retry attempts.")
        print(f"💡 You can:")
        print(f"   1. Run this script again later (rate limits reset)")
        print(f"   2. Check the specific error messages above")
        print(f"   3. Run individual properties manually if needed")
    else:
        print(f"\n🎉 All properties successfully processed!")
    
    print(f"\n📁 Check the 'data' directories for generated CSV files") 