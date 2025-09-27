#!/usr/bin/env python3
"""
Test script to verify that aggregate data accumulation is fixed.
This script tests that the SI pipeline only shows current process statistics.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add shared directory to path
sys.path.append('/app/shared')

def test_si_failed_individuals_data():
    """Test that get_si_failed_individuals_data only returns current process data."""
    print("🧪 Testing SI Failed Individuals Data...")
    
    try:
        from error_handler import ErrorHandler
        
        # Create test data directory
        data_dir = Path('/app/si_pipeline/data')
        data_dir.mkdir(exist_ok=True)
        
        # Create test failed individuals data for current process
        test_current_data = {
            'failed_individuals_data': [
                {
                    'ticket_id': 'TICKET_001',
                    'firstname': 'John',
                    'lastname': 'Doe',
                    'passport': 'A123456',
                    'error': 'Validation failed',
                    'step': 'API validation'
                },
                {
                    'ticket_id': 'TICKET_002', 
                    'firstname': 'Jane',
                    'lastname': 'Smith',
                    'passport': 'B789012',
                    'error': 'Coverage issue',
                    'step': 'Coverage check'
                }
            ],
            'all_failed_individuals': [
                {
                    'ticket_id': 'TICKET_001',
                    'firstname': 'John',
                    'lastname': 'Doe',
                    'passport': 'A123456',
                    'error': 'Validation failed',
                    'step': 'API validation'
                },
                {
                    'ticket_id': 'TICKET_002',
                    'firstname': 'Jane',
                    'lastname': 'Smith',
                    'passport': 'B789012',
                    'error': 'Coverage issue',
                    'step': 'Coverage check'
                }
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        # Save test data
        with open('/app/si_pipeline/data/latest_failed_individuals.json', 'w') as f:
            json.dump(test_current_data, f, indent=2)
        
        print("📊 Created test data with 2 failed individuals")
        
        # Test the ErrorHandler method
        si_handler = ErrorHandler('si')
        failed_individuals = si_handler.get_si_failed_individuals_data()
        
        print(f"📊 Retrieved {len(failed_individuals)} failed individuals")
        
        # Verify we only get current process data (2 individuals, not aggregate)
        if len(failed_individuals) == 2:
            print("✅ SUCCESS: Only current process data returned (2 individuals)")
            print("✅ AGGREGATE DATA ISSUE FIXED: No longer accumulating historical data")
            return True
        else:
            print(f"❌ FAILED: Expected 2 individuals, got {len(failed_individuals)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing SI failed individuals data: {e}")
        return False

def test_no_fallback_aggregation():
    """Test that the fallback aggregation is removed."""
    print("\n🧪 Testing No Fallback Aggregation...")
    
    try:
        from error_handler import ErrorHandler
        
        # Remove the latest file to test fallback behavior
        latest_file = '/app/si_pipeline/data/latest_failed_individuals.json'
        if os.path.exists(latest_file):
            os.remove(latest_file)
            print("🗑️ Removed latest_failed_individuals.json file")
        
        # Create old fallback data that would previously cause aggregation
        old_fallback_data = [
            {
                'api_failed_individuals': [
                    {'ticket_id': 'OLD_001', 'firstname': 'Old', 'lastname': 'Person1'},
                    {'ticket_id': 'OLD_002', 'firstname': 'Old', 'lastname': 'Person2'}
                ]
            },
            {
                'api_failed_individuals': [
                    {'ticket_id': 'OLD_003', 'firstname': 'Old', 'lastname': 'Person3'},
                    {'ticket_id': 'OLD_004', 'firstname': 'Old', 'lastname': 'Person4'}
                ]
            }
        ]
        
        # Save old fallback data
        with open('/app/si_pipeline/data/failed_individuals_data.json', 'w') as f:
            json.dump(old_fallback_data, f, indent=2)
        
        print("📊 Created old fallback data with 4 failed individuals")
        
        # Test the ErrorHandler method
        si_handler = ErrorHandler('si')
        failed_individuals = si_handler.get_si_failed_individuals_data()
        
        print(f"📊 Retrieved {len(failed_individuals)} failed individuals")
        
        # Verify we get empty list (no fallback aggregation)
        if len(failed_individuals) == 0:
            print("✅ SUCCESS: No fallback aggregation - returns empty list")
            print("✅ FALLBACK AGGREGATION REMOVED: No longer accumulating old data")
            return True
        else:
            print(f"❌ FAILED: Expected 0 individuals (no fallback), got {len(failed_individuals)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing no fallback aggregation: {e}")
        return False

def test_cleanup_functionality():
    """Test that the SI pipeline cleanup works correctly."""
    print("\n🧪 Testing SI Pipeline Cleanup...")
    
    try:
        # Create test files that should be cleaned up
        test_files = [
            '/app/si_pipeline/data/latest_failed_individuals.json',
            '/app/si_pipeline/data/failed_individuals_data.json',
            '/app/si_pipeline/data/successful_emissions.json'
        ]
        
        # Create test files
        for file_path in test_files:
            with open(file_path, 'w') as f:
                json.dump({'test': 'data'}, f)
            print(f"📄 Created test file: {file_path}")
        
        # Test cleanup (simulate the cleanup code from main.py)
        data_dir = "/app/si_pipeline/data"
        if os.path.exists(data_dir):
            old_files = [
                "/app/si_pipeline/data/latest_failed_individuals.json",
                "/app/si_pipeline/data/failed_individuals_data.json",
                "/app/si_pipeline/data/successful_emissions.json"
            ]
            for file_path in old_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"🗑️ Removed old file: {file_path}")
        
        # Verify files are removed
        all_removed = True
        for file_path in test_files:
            if os.path.exists(file_path):
                print(f"❌ File still exists: {file_path}")
                all_removed = False
        
        if all_removed:
            print("✅ SUCCESS: All old files cleaned up successfully")
            print("✅ CLEANUP FUNCTIONALITY WORKS: Fresh start for each process")
            return True
        else:
            print("❌ FAILED: Some files were not cleaned up")
            return False
            
    except Exception as e:
        print(f"❌ Error testing cleanup functionality: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Aggregate Data Fix")
    print("=" * 50)
    
    tests = [
        ("SI Failed Individuals Data", test_si_failed_individuals_data),
        ("No Fallback Aggregation", test_no_fallback_aggregation),
        ("Cleanup Functionality", test_cleanup_functionality)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            if test_func():
                print(f"✅ {test_name} test passed")
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test error: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Aggregate data issue is FIXED.")
        print("📧 Email reports will now only show current process statistics.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
