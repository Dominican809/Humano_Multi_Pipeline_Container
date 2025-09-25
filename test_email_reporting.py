#!/usr/bin/env python3
"""
Test script for the improved email reporting system.
This script tests the unified statistics and email reporting functionality.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add shared directory to path
sys.path.append('/app/shared')

def test_statistics_manager():
    """Test the statistics manager functionality."""
    print("🧪 Testing Statistics Manager...")
    
    try:
        from statistics_manager import save_pipeline_execution_stats, get_pipeline_execution_stats, get_combined_execution_stats
        
        # Test Viajeros statistics
        viajeros_stats = {
            "successful": 15,
            "failed": 3,
            "total_processed": 18,
            "success_rate": 83.33,
            "successful_emissions": 4,
            "failed_emissions": 0
        }
        
        print("📊 Saving Viajeros statistics...")
        success = save_pipeline_execution_stats('viajeros', viajeros_stats)
        if success:
            print("✅ Viajeros statistics saved successfully")
        else:
            print("❌ Failed to save Viajeros statistics")
            return False
        
        # Test SI statistics
        si_stats = {
            "successful": 8,
            "failed": 2,
            "total_processed": 10,
            "success_rate": 80.0,
            "successful_emissions": 8,
            "failed_individuals": 2
        }
        
        print("📊 Saving SI statistics...")
        success = save_pipeline_execution_stats('si', si_stats)
        if success:
            print("✅ SI statistics saved successfully")
        else:
            print("❌ Failed to save SI statistics")
            return False
        
        # Test retrieving statistics
        print("📊 Retrieving Viajeros statistics...")
        retrieved_viajeros = get_pipeline_execution_stats('viajeros')
        if retrieved_viajeros:
            print(f"✅ Retrieved Viajeros stats: {retrieved_viajeros['successful']} successful, {retrieved_viajeros['failed']} failed")
        else:
            print("❌ Failed to retrieve Viajeros statistics")
            return False
        
        print("📊 Retrieving SI statistics...")
        retrieved_si = get_pipeline_execution_stats('si')
        if retrieved_si:
            print(f"✅ Retrieved SI stats: {retrieved_si['successful']} successful, {retrieved_si['failed']} failed")
        else:
            print("❌ Failed to retrieve SI statistics")
            return False
        
        # Test combined statistics
        print("📊 Retrieving combined statistics...")
        combined = get_combined_execution_stats()
        if combined:
            totals = combined['totals']
            print(f"✅ Combined stats: {totals['successful']} successful, {totals['failed']} failed, {totals['total_processed']} total")
        else:
            print("❌ Failed to retrieve combined statistics")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing statistics manager: {e}")
        return False

def test_email_reporting():
    """Test the unified email reporting functionality."""
    print("\n🧪 Testing Email Reporting...")
    
    try:
        from error_handler import ErrorHandler
        
        # Test Viajeros email report
        print("📧 Testing Viajeros email report...")
        viajeros_handler = ErrorHandler('viajeros')
        
        # This would normally send an email, but we'll just test the generation
        success = viajeros_handler.send_unified_pipeline_report(
            pipeline_type='viajeros',
            email_subject='Test Viajeros Email | 2025-09-25'
        )
        
        if success:
            print("✅ Viajeros email report generated successfully")
        else:
            print("❌ Failed to generate Viajeros email report")
            return False
        
        # Test SI email report
        print("📧 Testing SI email report...")
        si_handler = ErrorHandler('si')
        
        success = si_handler.send_unified_pipeline_report(
            pipeline_type='si',
            email_subject='Test SI Email | 2025-09-25'
        )
        
        if success:
            print("✅ SI email report generated successfully")
        else:
            print("❌ Failed to generate SI email report")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing email reporting: {e}")
        return False

def test_statistics_files():
    """Test that statistics files are created correctly."""
    print("\n🧪 Testing Statistics Files...")
    
    try:
        stats_dir = Path('/app/shared/stats')
        
        # Check if stats directory exists
        if not stats_dir.exists():
            print("❌ Statistics directory does not exist")
            return False
        
        print(f"✅ Statistics directory exists: {stats_dir}")
        
        # Check for individual pipeline files
        viajeros_file = stats_dir / 'viajeros_latest_stats.json'
        si_file = stats_dir / 'si_latest_stats.json'
        combined_file = stats_dir / 'combined_latest_stats.json'
        
        files_to_check = [
            (viajeros_file, 'Viajeros'),
            (si_file, 'SI'),
            (combined_file, 'Combined')
        ]
        
        for file_path, name in files_to_check:
            if file_path.exists():
                print(f"✅ {name} statistics file exists: {file_path}")
                
                # Check file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if name == 'Combined':
                    totals = data.get('totals', {})
                    print(f"   📊 Combined totals: {totals.get('successful', 0)} successful, {totals.get('failed', 0)} failed")
                else:
                    print(f"   📊 {name} stats: {data.get('successful', 0)} successful, {data.get('failed', 0)} failed")
            else:
                print(f"❌ {name} statistics file does not exist: {file_path}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing statistics files: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Email Reporting System Tests")
    print("=" * 50)
    
    tests = [
        ("Statistics Manager", test_statistics_manager),
        ("Email Reporting", test_email_reporting),
        ("Statistics Files", test_statistics_files)
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
        print("🎉 All tests passed! Email reporting system is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
