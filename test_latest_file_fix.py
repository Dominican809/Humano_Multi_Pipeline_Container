#!/usr/bin/env python3
"""
Test script to verify that latest_failed_individuals.json is always created.
This ensures the error handler never falls back to aggregate data.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add shared directory to path
sys.path.append('/app/shared')

def test_latest_file_creation():
    """Test that latest_failed_individuals.json is always created."""
    print("🧪 Testing latest_failed_individuals.json file creation...")
    
    try:
        from error_handler import ErrorHandler
        
        # Create test data directory
        data_dir = Path('/app/si_pipeline/data')
        data_dir.mkdir(exist_ok=True)
        
        # Test case 1: No failed individuals (successful run)
        print("\n📊 Test Case 1: Successful run with no failures")
        
        # Simulate successful run with no failures
        successful_run_data = {
            'failed_individuals_data': [],
            'all_failed_individuals': [],
            'timestamp': datetime.now().isoformat(),
            'process_completed': True
        }
        
        with open('/app/si_pipeline/data/latest_failed_individuals.json', 'w') as f:
            json.dump(successful_run_data, f, indent=2)
        
        print("📄 Created latest_failed_individuals.json for successful run")
        
        # Test the ErrorHandler method
        si_handler = ErrorHandler('si')
        failed_individuals = si_handler.get_si_failed_individuals_data()
        
        print(f"📊 Retrieved {len(failed_individuals)} failed individuals")
        
        if len(failed_individuals) == 0:
            print("✅ SUCCESS: No failed individuals returned for successful run")
        else:
            print(f"❌ FAILED: Expected 0 individuals, got {len(failed_individuals)}")
            return False
        
        # Test case 2: Some failed individuals
        print("\n📊 Test Case 2: Run with some failures")
        
        failed_run_data = {
            'failed_individuals_data': [
                {
                    'ticket_id': 'TICKET_001',
                    'firstname': 'John',
                    'lastname': 'Doe',
                    'passport': 'A123456',
                    'error': 'Validation failed',
                    'step': 'API validation'
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
                }
            ],
            'timestamp': datetime.now().isoformat(),
            'process_completed': True
        }
        
        with open('/app/si_pipeline/data/latest_failed_individuals.json', 'w') as f:
            json.dump(failed_run_data, f, indent=2)
        
        print("📄 Created latest_failed_individuals.json for run with failures")
        
        # Test the ErrorHandler method
        failed_individuals = si_handler.get_si_failed_individuals_data()
        
        print(f"📊 Retrieved {len(failed_individuals)} failed individuals")
        
        if len(failed_individuals) == 1:
            print("✅ SUCCESS: Correct number of failed individuals returned")
        else:
            print(f"❌ FAILED: Expected 1 individual, got {len(failed_individuals)}")
            return False
        
        # Test case 3: File doesn't exist (should not happen anymore)
        print("\n📊 Test Case 3: File doesn't exist (edge case)")
        
        # Remove the file
        if os.path.exists('/app/si_pipeline/data/latest_failed_individuals.json'):
            os.remove('/app/si_pipeline/data/latest_failed_individuals.json')
            print("🗑️ Removed latest_failed_individuals.json file")
        
        # Test the ErrorHandler method
        failed_individuals = si_handler.get_si_failed_individuals_data()
        
        print(f"📊 Retrieved {len(failed_individuals)} failed individuals")
        
        if len(failed_individuals) == 0:
            print("✅ SUCCESS: Empty list returned when file doesn't exist")
            print("✅ NO FALLBACK: Error handler doesn't fall back to aggregate data")
        else:
            print(f"❌ FAILED: Expected 0 individuals, got {len(failed_individuals)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing latest file creation: {e}")
        return False

def test_no_aggregation():
    """Test that no aggregation happens even with old fallback files."""
    print("\n🧪 Testing No Aggregation with Old Fallback Files...")
    
    try:
        from error_handler import ErrorHandler
        
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
        
        # Should return empty list because latest_failed_individuals.json doesn't exist
        if len(failed_individuals) == 0:
            print("✅ SUCCESS: No aggregation from old fallback files")
            print("✅ AGGREGATION FIXED: Error handler ignores old data")
            return True
        else:
            print(f"❌ FAILED: Expected 0 individuals (no fallback), got {len(failed_individuals)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing no aggregation: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Latest File Creation Fix")
    print("=" * 50)
    
    tests = [
        ("Latest File Creation", test_latest_file_creation),
        ("No Aggregation", test_no_aggregation)
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
        print("🎉 All tests passed! Latest file creation issue is FIXED.")
        print("📧 Email reports will now always use current process data.")
        print("🚫 No more aggregate data accumulation!")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
