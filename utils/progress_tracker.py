"""
Progress tracking utility for scheduler operations
Provides real-time progress updates and status monitoring
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class SchedulerProgressTracker:
    """Tracks and reports progress for scheduler operations"""
    
    def __init__(self):
        self.status_file = Path("logs/scheduler_status.json")
        self.start_time = None
        self.current_step = None
        self.total_steps = 0
        self.current_step_progress = 0
        self.total_progress = 0
        self.estimated_completion = None
        self.properties_to_process = []
        self.completed_properties = []
        self.failed_properties = []
        self.api_calls_made = 0
        self.total_api_calls = 0
        self.current_operation = None
        self.error_messages = []
        
    def start_refresh(self, properties: List[str], total_api_calls: int):
        """Start a new refresh operation"""
        self.start_time = datetime.now()
        self.properties_to_process = properties
        self.total_api_calls = total_api_calls
        self.completed_properties = []
        self.failed_properties = []
        self.api_calls_made = 0
        self.error_messages = []
        self.total_steps = 2  # Nightly pull + PL daily generation
        
        logger.info("🔄 SCHEDULER REFRESH STARTED")
        logger.info(f"📊 Properties to refresh: {len(properties)} ({', '.join(properties)})")
        logger.info(f"📈 Total API calls estimated: {total_api_calls}")
        
        # Estimate duration (1.5 seconds per API call + overhead)
        estimated_seconds = (total_api_calls * 1.5) + (len(properties) * 30)  # 30s overhead per property
        self.estimated_completion = self.start_time + timedelta(seconds=estimated_seconds)
        
        logger.info(f"⏱️ Started at: {self.start_time.strftime('%H:%M:%S')}")
        logger.info(f"⏱️ Estimated completion: {self.estimated_completion.strftime('%H:%M:%S')}")
        logger.info(f"⏱️ Estimated duration: {estimated_seconds/60:.1f} minutes")
        
        self._update_status_file()
        
    def start_step(self, step_name: str, step_number: int):
        """Start a new step in the refresh process"""
        self.current_step = step_name
        self.current_step_progress = 0
        self.current_operation = None
        
        logger.info(f"🔄 STEP {step_number}/{self.total_steps}: {step_name.upper()}")
        self._update_status_file()
        
    def update_step_progress(self, progress_percent: float, operation: str = None):
        """Update progress for current step"""
        self.current_step_progress = progress_percent
        self.current_operation = operation
        
        # Calculate overall progress
        step_weight = 100 / self.total_steps
        completed_steps = (self.current_step or "").count("nightly") + (self.current_step or "").count("pl_daily")
        self.total_progress = (completed_steps * step_weight) + (progress_percent * step_weight / 100)
        
        if operation:
            logger.info(f"📊 {operation} - {progress_percent:.1f}% complete")
        
        self._update_status_file()
        
    def complete_property(self, property_name: str, success: bool, duration_seconds: float = None, api_calls: int = 0):
        """Mark a property as completed"""
        if success:
            self.completed_properties.append(property_name)
            if duration_seconds:
                logger.info(f"✅ Property {property_name} completed in {duration_seconds/60:.1f}m ({len(self.completed_properties)}/{len(self.properties_to_process)} properties)")
            else:
                logger.info(f"✅ Property {property_name} completed ({len(self.completed_properties)}/{len(self.properties_to_process)} properties)")
        else:
            self.failed_properties.append(property_name)
            logger.error(f"❌ Property {property_name} failed ({len(self.failed_properties)} failures)")
        
        self.api_calls_made += api_calls
        
        # Update progress based on completed properties
        total_properties = len(self.properties_to_process)
        completed_count = len(self.completed_properties) + len(self.failed_properties)
        progress = (completed_count / total_properties) * 100 if total_properties > 0 else 0
        
        self.update_step_progress(progress, f"Processing {property_name}")
        self._update_status_file()
        
    def add_error(self, error_message: str):
        """Add an error message"""
        self.error_messages.append({
            'timestamp': datetime.now().isoformat(),
            'message': error_message
        })
        logger.error(f"❌ Error: {error_message}")
        self._update_status_file()
        
    def complete_refresh(self, success: bool):
        """Mark the refresh as completed"""
        end_time = datetime.now()
        duration = end_time - self.start_time if self.start_time else timedelta(0)
        
        if success:
            logger.info("✅ SCHEDULER REFRESH COMPLETED")
            logger.info(f"📊 Summary: {len(self.completed_properties)}/{len(self.properties_to_process)} properties successful")
            logger.info(f"📊 API calls made: {self.api_calls_made}/{self.total_api_calls}")
            logger.info(f"⏱️ Duration: {duration.total_seconds()/60:.1f} minutes")
            
            if self.failed_properties:
                logger.warning(f"⚠️ Failed properties: {', '.join(self.failed_properties)}")
        else:
            logger.error("❌ SCHEDULER REFRESH FAILED")
            logger.error(f"📊 Completed: {len(self.completed_properties)}/{len(self.properties_to_process)} properties")
            logger.error(f"⏱️ Duration before failure: {duration.total_seconds()/60:.1f} minutes")
        
        self._update_status_file()
        
    def _update_status_file(self):
        """Update the JSON status file"""
        try:
            # Ensure logs directory exists
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            
            status = {
                'refresh_active': self.start_time is not None,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'current_step': self.current_step,
                'current_operation': self.current_operation,
                'total_progress': round(self.total_progress, 1),
                'step_progress': round(self.current_step_progress, 1),
                'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
                'properties_total': len(self.properties_to_process),
                'properties_completed': len(self.completed_properties),
                'properties_failed': len(self.failed_properties),
                'properties_remaining': len(self.properties_to_process) - len(self.completed_properties) - len(self.failed_properties),
                'api_calls_made': self.api_calls_made,
                'api_calls_total': self.total_api_calls,
                'api_calls_remaining': self.total_api_calls - self.api_calls_made,
                'completed_properties': self.completed_properties,
                'failed_properties': self.failed_properties,
                'error_count': len(self.error_messages),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating status file: {e}")

# Global progress tracker instance
progress_tracker = SchedulerProgressTracker()

def get_scheduler_status() -> Dict:
    """Get current scheduler status from the status file"""
    status_file = Path("logs/scheduler_status.json")
    if status_file.exists():
        try:
            with open(status_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading status file: {e}")
    
    return {
        'refresh_active': False,
        'current_step': None,
        'total_progress': 0,
        'last_updated': None
    }

