#!/usr/bin/env python3
"""
Manual test script to trigger pipeline and send test email with current data.
"""

import sys
import os
import json
from datetime import datetime

# Add the app directory to Python path
sys.path.append('/app')

def test_viajeros_pipeline():
    """Test Viajeros pipeline and extract failure data."""
    print("🧪 Testing Viajeros Pipeline...")
    
    try:
        # Import pipeline manager
        from pipeline_manager import run_viajeros_pipeline
        
        # Run the pipeline
        result = run_viajeros_pipeline('/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx', 
                                     'Test Email Subject: Asegurados Viajeros | 2025-09-22')
        
        print(f"✅ Viajeros pipeline completed: {result}")
        
        # Extract failure data from the latest failure file
        failure_files = []
        failure_dir = '/app/viajeros_pipeline/data/tracking/failures'
        
        if os.path.exists(failure_dir):
            for file in os.listdir(failure_dir):
                if file.startswith('failures_') and file.endswith('.json'):
                    failure_files.append(os.path.join(failure_dir, file))
        
        # Get the most recent failure file
        if failure_files:
            latest_failure_file = max(failure_files, key=os.path.getctime)
            print(f"📄 Latest failure file: {latest_failure_file}")
            
            with open(latest_failure_file, 'r', encoding='utf-8') as f:
                failure_data = json.load(f)
            
            # Extract individuals with active coverage
            failed_individuals = []
            for failure in failure_data.get('emisiones_fallidas', []):
                if 'error_details' in failure and 'api_response' in failure['error_details']:
                    api_response = failure['error_details']['api_response']
                    if 'found' in api_response and api_response['found']:
                        failed_individuals.extend(api_response['found'])
            
            return failed_individuals
        
        return []
        
    except Exception as e:
        print(f"❌ Error testing Viajeros pipeline: {e}")
        return []

def test_si_pipeline():
    """Test SI pipeline and extract failure data."""
    print("🧪 Testing SI Pipeline...")
    
    try:
        # Import pipeline manager
        from pipeline_manager import run_si_pipeline
        
        # Run the pipeline
        result = run_si_pipeline('/app/si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx', 
                               'Test Email Subject: Asegurados Salud Internacional | 2025-09-22')
        
        print(f"✅ SI pipeline completed: {result}")
        
        # Extract failure data from the latest failure file
        failure_files = []
        failure_dir = '/app/si_pipeline/data/tracking/failures'
        
        if os.path.exists(failure_dir):
            for file in os.listdir(failure_dir):
                if file.startswith('failures_') and file.endswith('.json'):
                    failure_files.append(os.path.join(failure_dir, file))
        
        # Get the most recent failure file
        if failure_files:
            latest_failure_file = max(failure_files, key=os.path.getctime)
            print(f"📄 Latest failure file: {latest_failure_file}")
            
            with open(latest_failure_file, 'r', encoding='utf-8') as f:
                failure_data = json.load(f)
            
            # Extract individuals with active coverage
            failed_individuals = []
            for failure in failure_data.get('emisiones_fallidas', []):
                if 'error_details' in failure and 'api_response' in failure['error_details']:
                    api_response = failure['error_details']['api_response']
                    if 'found' in api_response and api_response['found']:
                        failed_individuals.extend(api_response['found'])
            
            return failed_individuals
        
        return []
        
    except Exception as e:
        print(f"❌ Error testing SI pipeline: {e}")
        return []

def send_test_email(pipeline_type, failed_individuals):
    """Send test email with failure data."""
    print(f"📧 Sending test email for {pipeline_type} pipeline...")
    
    try:
        from error_handler import ErrorHandler
        
        # Create error handler for the specific pipeline
        handler = ErrorHandler(pipeline_type)
        
        # Send report with failed individuals
        success = handler.send_report(
            email_received=True,
            excel_extracted=True,
            pipeline_success=False,  # Set to False to show failures
            error_message=f"Manual test run - {pipeline_type} pipeline processed with API validation errors",
            email_subject=f"Test Email Subject: Asegurados {'Viajeros' if pipeline_type == 'viajeros' else 'Salud Internacional'} | 2025-09-22",
            failed_individuals=failed_individuals
        )
        
        if success:
            print(f"✅ Test email sent successfully for {pipeline_type}")
        else:
            print(f"❌ Failed to send test email for {pipeline_type}")
            
        return success
        
    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Starting Manual Pipeline Test")
    print("=" * 50)
    
    # Test Viajeros pipeline
    print("\n1️⃣ Testing Viajeros Pipeline")
    print("-" * 30)
    viajeros_failed_individuals = test_viajeros_pipeline()
    
    if viajeros_failed_individuals:
        print(f"📋 Found {len(viajeros_failed_individuals)} individuals with active coverage in Viajeros")
        for individual in viajeros_failed_individuals:
            name = f"{individual.get('firstname', '')} {individual.get('lastname', '')}"
            passport = individual.get('passport', 'N/A')
            print(f"   - {name} (Passport: {passport})")
    
    # Test SI pipeline
    print("\n2️⃣ Testing SI Pipeline")
    print("-" * 30)
    si_failed_individuals = test_si_pipeline()
    
    if si_failed_individuals:
        print(f"📋 Found {len(si_failed_individuals)} individuals with active coverage in SI")
        for individual in si_failed_individuals:
            name = f"{individual.get('firstname', '')} {individual.get('lastname', '')}"
            passport = individual.get('passport', 'N/A')
            print(f"   - {name} (Passport: {passport})")
    
    # Send test emails
    print("\n3️⃣ Sending Test Emails")
    print("-" * 30)
    
    if viajeros_failed_individuals:
        send_test_email('viajeros', viajeros_failed_individuals)
    
    if si_failed_individuals:
        send_test_email('si', si_failed_individuals)
    
    print("\n✅ Manual test completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()
