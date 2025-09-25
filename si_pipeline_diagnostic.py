#!/usr/bin/env python3
"""
SI Pipeline Diagnostic Script
This script helps diagnose issues with the SI pipeline by checking files, 
comparing data, and testing each step of the process.
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

def check_si_files():
    """Check if SI files exist and their properties."""
    logger.info("🔍 Checking SI files...")
    
    # Define file paths
    old_file = 'si_pipeline/Comparador_Humano/exceles/Asegurados_SI_old.xlsx'
    new_file = 'si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx'
    comparison_file = 'si_pipeline/Comparador_Humano/exceles/comparison_result.xlsx'
    
    files_to_check = [
        (old_file, "Old SI file"),
        (new_file, "New SI file"),
        (comparison_file, "Comparison result file")
    ]
    
    results = {}
    
    for file_path, description in files_to_check:
        logger.info(f"📁 Checking {description}: {file_path}")
        
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            logger.info(f"   ✅ EXISTS - Size: {size:,} bytes, Modified: {mod_time}")
            
            # Try to read Excel file
            try:
                df = pd.read_excel(file_path)
                logger.info(f"   📊 Excel data: {len(df)} rows, {len(df.columns)} columns")
                logger.info(f"   📋 Columns: {list(df.columns)}")
                
                if 'CODIGO_INFOPLAN' in df.columns:
                    unique_codes = df['CODIGO_INFOPLAN'].nunique()
                    logger.info(f"   🔢 Unique CODIGO_INFOPLAN: {unique_codes}")
                    
                    # Show sample data
                    sample_codes = df['CODIGO_INFOPLAN'].head().tolist()
                    logger.info(f"   📋 Sample codes: {sample_codes}")
                else:
                    logger.warning(f"   ⚠️ CODIGO_INFOPLAN column not found")
                
                results[file_path] = {
                    'exists': True,
                    'size': size,
                    'rows': len(df),
                    'columns': list(df.columns),
                    'has_codigo_infoplan': 'CODIGO_INFOPLAN' in df.columns
                }
                
            except Exception as e:
                logger.error(f"   ❌ Error reading Excel file: {e}")
                results[file_path] = {'exists': True, 'error': str(e)}
        else:
            logger.warning(f"   ❌ MISSING")
            results[file_path] = {'exists': False}
    
    return results

def test_si_comparison():
    """Test the SI comparison process."""
    logger.info("🧪 Testing SI comparison process...")
    
    try:
        # Change to SI pipeline directory
        original_dir = os.getcwd()
        si_dir = os.path.join(original_dir, 'si_pipeline')
        
        if not os.path.exists(si_dir):
            logger.error(f"❌ SI pipeline directory not found: {si_dir}")
            return False
        
        os.chdir(si_dir)
        logger.info(f"📁 Changed to SI directory: {os.getcwd()}")
        
        # Import and run comparison
        from Comparador_Humano.comparador_SI import comparador_SI
        
        logger.info("🔄 Running SI comparison...")
        result = comparador_SI()
        
        if result is False:
            logger.error("❌ SI comparison failed")
            return False
        elif isinstance(result, tuple):
            success, new_count, removed_count = result
            logger.info(f"✅ SI comparison completed: {new_count} new, {removed_count} removed")
            
            if new_count == 0:
                logger.warning("⚠️ No new records found - this explains why SI pipeline shows 0 processed")
                return "no_new_records"
            else:
                logger.info(f"✅ Found {new_count} new records - SI pipeline should process these")
                return "has_new_records"
        else:
            logger.warning("⚠️ Unexpected comparison result")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing SI comparison: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
    finally:
        # Return to original directory
        os.chdir(original_dir)

def check_si_pipeline_execution():
    """Check if SI pipeline has been executed recently."""
    logger.info("🔍 Checking SI pipeline execution history...")
    
    # Check for recent execution files
    execution_files = [
        'si_pipeline/data/successful_emissions.json',
        'si_pipeline/data/failed_individuals_data.json',
        'si_pipeline/data/latest_failed_individuals.json',
        'si_pipeline/emision_unica.json'
    ]
    
    for file_path in execution_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            age_hours = (datetime.now() - mod_time).total_seconds() / 3600
            
            logger.info(f"📄 {file_path}")
            logger.info(f"   Size: {size:,} bytes, Age: {age_hours:.1f} hours")
            
            # Try to read JSON files
            if file_path.endswith('.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if isinstance(data, list):
                        logger.info(f"   📊 Contains {len(data)} items")
                    elif isinstance(data, dict):
                        logger.info(f"   📊 Contains {len(data)} keys: {list(data.keys())}")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ Error reading JSON: {e}")
        else:
            logger.info(f"📄 {file_path} - Not found")

def check_email_attachments():
    """Check if SI email attachments are being processed correctly."""
    logger.info("📧 Checking SI email attachment processing...")
    
    # Check if there are any SI Excel files in the container
    si_excel_dir = 'si_pipeline/Comparador_Humano/exceles'
    
    if os.path.exists(si_excel_dir):
        files = os.listdir(si_excel_dir)
        logger.info(f"📂 Files in SI exceles directory: {files}")
        
        # Check for Asegurados_SI.xlsx (the new file from email)
        si_file = os.path.join(si_excel_dir, 'Asegurados_SI.xlsx')
        if os.path.exists(si_file):
            size = os.path.getsize(si_file)
            mod_time = datetime.fromtimestamp(os.path.getmtime(si_file))
            age_hours = (datetime.now() - mod_time).total_seconds() / 3600
            
            logger.info(f"📄 SI Excel file found: {si_file}")
            logger.info(f"   Size: {size:,} bytes, Age: {age_hours:.1f} hours")
            
            # Check if it's recent (less than 24 hours)
            if age_hours < 24:
                logger.info("✅ SI Excel file is recent - should be processed")
            else:
                logger.warning(f"⚠️ SI Excel file is {age_hours:.1f} hours old - may be stale")
        else:
            logger.warning("❌ Asegurados_SI.xlsx not found - email attachment may not have been processed")
    else:
        logger.error(f"❌ SI exceles directory not found: {si_excel_dir}")

def run_si_pipeline_test():
    """Run a test of the SI pipeline."""
    logger.info("🧪 Running SI pipeline test...")
    
    try:
        # Change to SI pipeline directory
        original_dir = os.getcwd()
        si_dir = os.path.join(original_dir, 'si_pipeline')
        
        if not os.path.exists(si_dir):
            logger.error(f"❌ SI pipeline directory not found: {si_dir}")
            return False
        
        os.chdir(si_dir)
        logger.info(f"📁 Changed to SI directory: {os.getcwd()}")
        
        # Import and run the corrected SI pipeline
        from corrected_main import run_si_pipeline_with_corrected_filtering
        
        logger.info("🚀 Running SI pipeline with corrected filtering...")
        success, successful_emissions, failed_individuals_data, all_failed_individuals = run_si_pipeline_with_corrected_filtering()
        
        if success:
            logger.info("✅ SI pipeline test completed successfully")
            logger.info(f"📊 Results:")
            logger.info(f"   Successful emissions: {len(successful_emissions)}")
            logger.info(f"   Failed individuals data: {len(failed_individuals_data)}")
            logger.info(f"   Total failed individuals: {len(all_failed_individuals)}")
            return True
        else:
            logger.error("❌ SI pipeline test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error running SI pipeline test: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
    finally:
        # Return to original directory
        os.chdir(original_dir)

def main():
    """Run comprehensive SI pipeline diagnostics."""
    logger.info("🚀 Starting SI Pipeline Diagnostics")
    logger.info("=" * 60)
    
    # Step 1: Check files
    logger.info("\n1️⃣ Checking SI Files")
    file_results = check_si_files()
    
    # Step 2: Check email attachments
    logger.info("\n2️⃣ Checking Email Attachments")
    check_email_attachments()
    
    # Step 3: Check execution history
    logger.info("\n3️⃣ Checking Execution History")
    check_si_pipeline_execution()
    
    # Step 4: Test comparison
    logger.info("\n4️⃣ Testing SI Comparison")
    comparison_result = test_si_comparison()
    
    # Step 5: Run pipeline test (optional)
    logger.info("\n5️⃣ Running SI Pipeline Test")
    pipeline_result = run_si_pipeline_test()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    
    # File status
    old_file_exists = file_results.get('si_pipeline/Comparador_Humano/exceles/Asegurados_SI_old.xlsx', {}).get('exists', False)
    new_file_exists = file_results.get('si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx', {}).get('exists', False)
    
    logger.info(f"📁 Old SI file exists: {'✅ YES' if old_file_exists else '❌ NO'}")
    logger.info(f"📁 New SI file exists: {'✅ YES' if new_file_exists else '❌ NO'}")
    
    if comparison_result == "no_new_records":
        logger.info("🔍 Comparison result: ⚠️ NO NEW RECORDS FOUND")
        logger.info("💡 This explains why SI pipeline shows 0 processed")
        logger.info("💡 Possible causes:")
        logger.info("   - No new people in the latest Excel file")
        logger.info("   - Excel file hasn't been updated")
        logger.info("   - Comparison logic issue")
    elif comparison_result == "has_new_records":
        logger.info("🔍 Comparison result: ✅ NEW RECORDS FOUND")
        logger.info("💡 SI pipeline should process these records")
    else:
        logger.info("🔍 Comparison result: ❌ COMPARISON FAILED")
    
    logger.info(f"🧪 Pipeline test: {'✅ PASSED' if pipeline_result else '❌ FAILED'}")
    
    # Recommendations
    logger.info("\n💡 RECOMMENDATIONS:")
    
    if not new_file_exists:
        logger.info("   - Check if SI email attachment is being processed correctly")
        logger.info("   - Verify email watcher is extracting SI Excel files")
    
    if comparison_result == "no_new_records":
        logger.info("   - Check if the SI Excel file contains new people")
        logger.info("   - Verify the comparison logic is working correctly")
        logger.info("   - Consider if this is expected (no new people to process)")
    
    if not pipeline_result:
        logger.info("   - Check SI pipeline logs for specific errors")
        logger.info("   - Verify all dependencies are installed")
        logger.info("   - Check file permissions and paths")

if __name__ == "__main__":
    main()
