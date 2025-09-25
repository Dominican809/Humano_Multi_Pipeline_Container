#!/usr/bin/env python3
"""
Corrected SI Pipeline with Individual Filtering.
This implementation correctly handles the SI pipeline flow:
1. File comparison (automatic old file replacement)
2. Single emission creation
3. API processing with individual filtering on errors
"""

import sys
import json
import os
from pathlib import Path
from loguru import logger
from emisor_goval.utils.procesar_validacion import procesar_validacion
from Comparador_Humano.comparador_SI import comparador_SI
from emisor_goval.utils.SI_excel_to_emision import create_single_emission

# Check if running in automated mode (Docker container)
is_automated = os.environ.get('AUTOMATED_MODE', 'false').lower() == 'true'

def extract_failed_individuals_from_api_response(api_response):
    """Extract individuals with active coverage from API response."""
    failed_individuals = []
    if api_response and 'found' in api_response and api_response['found']:
        failed_individuals = api_response['found']
    return failed_individuals

def filter_individuals_from_json(json_path, failed_individuals):
    """
    Remove failed individuals from the emission JSON file.
    
    Args:
        json_path: Path to the emission JSON file
        failed_individuals: List of individuals that failed validation
        
    Returns:
        tuple: (filtered_json_path, removed_individuals)
    """
    if not failed_individuals:
        return json_path, []
    
    try:
        # Read the current JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            emission_data = json.load(f)
        
        # Create sets of failed identifiers for quick lookup
        failed_passports = set()
        failed_identities = set()
        
        for individual in failed_individuals:
            if individual.get('passport'):
                failed_passports.add(individual['passport'])
            if individual.get('identity'):
                failed_identities.add(individual['identity'])
        
        # Process each emission in the JSON
        removed_individuals = []
        filtered_emissions = {}
        
        for policy_number, emission in emission_data.items():
            original_insured = emission["emision"]["insured"]
            filtered_insured = []
            
            for insured in original_insured:
                should_remove = False
                
                # Check passport
                if insured.get('passport') and insured['passport'] in failed_passports:
                    should_remove = True
                
                # Check identity
                if insured.get('identity') and insured['identity'] in failed_identities:
                    should_remove = True
                
                if should_remove:
                    removed_individuals.append(insured)
                else:
                    filtered_insured.append(insured)
            
            # Create filtered emission
            filtered_emission = emission.copy()
            filtered_emission["emision"] = emission["emision"].copy()
            filtered_emission["emision"]["insured"] = filtered_insured
            
            # Update metadata
            filtered_emission["metadata"]["total_asegurados"] = len(filtered_insured)
            
            filtered_emissions[policy_number] = filtered_emission
        
        # Save filtered JSON
        filtered_json_path = json_path.replace('.json', '_filtered.json')
        with open(filtered_json_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_emissions, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Filtered JSON saved to: {filtered_json_path}")
        logger.info(f"📊 Removed {len(removed_individuals)} individuals from {len(original_insured)} total")
        
        return filtered_json_path, removed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error filtering JSON: {e}")
        return json_path, []

def process_si_emission_with_retry(json_path="emision_unica.json"):
    """
    Process SI emission with individual filtering and retry logic.
    
    Args:
        json_path: Path to the emission JSON file
        
    Returns:
        tuple: (success, successful_emissions, failed_individuals_data, all_failed_individuals)
    """
    logger.info("🚀 Starting SI emission processing with retry logic...")
    
    successful_emissions = []
    failed_individuals_data = []
    all_failed_individuals = []
    current_json_path = json_path
    
    try:
        # First attempt: Process original JSON
        logger.info(f"📄 Processing original JSON: {current_json_path}")
        emisiones_exitosas, emisiones_fallidas = procesar_validacion(emisiones_path=current_json_path)
        
        # Check if we have API validation errors (417) with failed individuals
        api_validation_errors = []
        for failure in emisiones_fallidas:
            if (failure.get('error_details', {}).get('status_code') == 417 and 
                'api_response' in failure.get('error_details', {})):
                api_validation_errors.append(failure)
        
        if api_validation_errors:
            logger.warning(f"🚨 Found {len(api_validation_errors)} API validation errors (417)")
            
            # Extract all failed individuals from all errors
            for failure in api_validation_errors:
                api_response = failure['error_details']['api_response']
                failed_individuals = extract_failed_individuals_from_api_response(api_response)
                
                if failed_individuals:
                    logger.info(f"📋 Extracting {len(failed_individuals)} failed individuals from factura {failure['factura']}")
                    
                    # Store failed individuals data
                    failed_individuals_data.append({
                        "factura": failure['factura'],
                        "api_failed_individuals": failed_individuals,
                        "error_details": failure['error_details']
                    })
                    
                    all_failed_individuals.extend(failed_individuals)
            
            if all_failed_individuals:
                logger.info(f"🔄 Filtering JSON to remove {len(all_failed_individuals)} failed individuals...")
                
                # Filter the JSON to remove failed individuals
                filtered_json_path, removed_individuals = filter_individuals_from_json(current_json_path, all_failed_individuals)
                
                if removed_individuals:
                    logger.info(f"✅ Successfully removed {len(removed_individuals)} individuals")
                    
                    # Update failed individuals data with removed individuals
                    for i, data in enumerate(failed_individuals_data):
                        data["removed_individuals"] = removed_individuals
                    
                    # Retry processing with filtered JSON
                    logger.info(f"🔄 Retrying processing with filtered JSON: {filtered_json_path}")
                    emisiones_exitosas_retry, emisiones_fallidas_retry = procesar_validacion(emisiones_path=filtered_json_path)
                    
                    # Combine results
                    successful_emissions = emisiones_exitosas_retry
                    logger.info(f"✅ Retry completed: {len(successful_emissions)} successful emissions")
                    
                    # Clean up filtered file
                    if os.path.exists(filtered_json_path):
                        os.remove(filtered_json_path)
                        logger.info("🧹 Cleaned up filtered JSON file")
                else:
                    logger.warning("⚠️ No individuals were removed from JSON")
                    successful_emissions = emisiones_exitosas
            else:
                logger.warning("⚠️ No failed individuals found in API responses")
                successful_emissions = emisiones_exitosas
        else:
            logger.info("✅ No API validation errors found, using original results")
            successful_emissions = emisiones_exitosas
        
        # Generate summary
        logger.info(f"\n📊 Final Processing Summary:")
        logger.info(f"Successful emissions: {len(successful_emissions)}")
        logger.info(f"Failed individuals data: {len(failed_individuals_data)}")
        logger.info(f"Total failed individuals: {len(all_failed_individuals)}")
        
        return True, successful_emissions, failed_individuals_data, all_failed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error in SI emission processing: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, [], [], []

def run_si_pipeline_with_corrected_filtering():
    """
    Run the complete SI pipeline process with corrected individual filtering.
    """
    logger.info("🚀 Starting SI pipeline process with corrected individual filtering...")
    
    try:
        # Step 1: Compare files (this automatically replaces old file with new file)
        if not is_automated:
            input("Presiona Enter para continuar... a comparar los archivo:")
        logger.info("📊 Running SI file comparison...")
        
        # Check current working directory and files
        current_dir = os.getcwd()
        logger.info(f"📁 Current working directory: {current_dir}")
        
        # List files in the SI directory
        si_dir = os.path.join(current_dir, "Comparador_Humano", "exceles")
        logger.info(f"📁 SI exceles directory: {si_dir}")
        if os.path.exists(si_dir):
            files = os.listdir(si_dir)
            logger.info(f"📂 Files in SI exceles directory: {files}")
        else:
            logger.error(f"❌ SI exceles directory not found: {si_dir}")
            return False, [], [], []
        
        # Run comparison with enhanced logging
        comparison_result = comparador_SI()
        
        if comparison_result is False:
            logger.error("❌ SI file comparison failed")
            return False, [], [], []
        elif isinstance(comparison_result, tuple):
            success, new_count, removed_count = comparison_result
            logger.info(f"✅ SI file comparison completed: {new_count} new records, {removed_count} removed records")
            
            if new_count == 0:
                logger.info("ℹ️ No new records found in SI comparison - no processing needed")
                # Still save statistics to show 0 processed
                from datetime import datetime
                try:
                    import sys
                    sys.path.append('/app/shared')
                    from statistics_manager import save_pipeline_execution_stats
                    
                    stats = {
                        "run_id": f"{datetime.now().strftime('%Y%m%d_%H_%M_%S')}",
                        "successful": 0,
                        "failed": 0,
                        "total_processed": 0,
                        "success_rate": 0.0,
                        "successful_emissions": 0,
                        "failed_individuals": 0,
                        "pipeline_type": "si",
                        "note": "No new records found in comparison"
                    }
                    
                    save_pipeline_execution_stats('si', stats)
                    logger.info("📊 Saved SI statistics: 0 processed (no new records)")
                    
                except Exception as e:
                    logger.error(f"❌ Error saving SI statistics: {e}")
                
                return True, [], [], []
        else:
            logger.warning("⚠️ Unexpected comparison result format")
        
        # Step 2: Create single emission from comparison result
        if not is_automated:
            input("Presiona Enter para continuar... a crear la emision unica:")
        logger.info("📝 Creating single emission from comparison result...")
        
        # Check if comparison result file exists and has data
        comparison_file = "Comparador_Humano/exceles/comparison_result.xlsx"
        logger.info(f"📁 Checking comparison result file: {comparison_file}")
        
        if not os.path.exists(comparison_file):
            logger.error(f"❌ Comparison result file not found: {comparison_file}")
            return False, [], [], []
        
        # Check file size and content
        file_size = os.path.getsize(comparison_file)
        logger.info(f"📊 Comparison result file size: {file_size:,} bytes")
        
        # Check if the file has data
        import pandas as pd
        try:
            logger.info("📖 Reading comparison result file...")
            df = pd.read_excel(comparison_file, sheet_name='New in New File')
            logger.info(f"📊 Comparison result contains {len(df)} new records")
            
            if df.empty:
                logger.info("ℹ️ Comparison result file is empty - no new individuals to process")
                # Save statistics for empty result
                from datetime import datetime
                try:
                    import sys
                    sys.path.append('/app/shared')
                    from statistics_manager import save_pipeline_execution_stats
                    
                    stats = {
                        "run_id": f"{datetime.now().strftime('%Y%m%d_%H_%M_%S')}",
                        "successful": 0,
                        "failed": 0,
                        "total_processed": 0,
                        "success_rate": 0.0,
                        "successful_emissions": 0,
                        "failed_individuals": 0,
                        "pipeline_type": "si",
                        "note": "Comparison result file is empty"
                    }
                    
                    save_pipeline_execution_stats('si', stats)
                    logger.info("📊 Saved SI statistics: 0 processed (empty comparison result)")
                    
                except Exception as e:
                    logger.error(f"❌ Error saving SI statistics: {e}")
                
                return True, [], [], []
            else:
                logger.info("✅ Comparison result file contains new records - proceeding with emission creation")
                
        except Exception as e:
            logger.error(f"❌ Error reading comparison result file: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, [], [], []
        
        create_single_emission(comparison_file, "emision_unica.json")
        logger.info("✅ Single emission created successfully")
        
        # Step 3: Process emissions with individual filtering and retry
        logger.info("🔄 Processing emissions with individual filtering and retry...")
        success, successful_emissions, failed_individuals_data, all_failed_individuals = process_si_emission_with_retry("emision_unica.json")
        
        # Step 4: Save results for email reporting
        if successful_emissions:
            logger.info(f"💾 Saving {len(successful_emissions)} successful emissions...")
            os.makedirs("data", exist_ok=True)
            with open("data/successful_emissions.json", "w") as f:
                json.dump(successful_emissions, f, indent=2)
        
        if failed_individuals_data:
            logger.info(f"💾 Saving {len(failed_individuals_data)} failed individuals data...")
            os.makedirs("data", exist_ok=True)
            with open("data/failed_individuals_data.json", "w") as f:
                json.dump(failed_individuals_data, f, indent=2)
            
            # Store for error handler
            with open("data/latest_failed_individuals.json", "w") as f:
                json.dump({
                    'failed_individuals_data': failed_individuals_data,
                    'all_failed_individuals': all_failed_individuals,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
        
        # Step 5: Save statistics to unified system
        try:
            import sys
            sys.path.append('/app/shared')
            from statistics_manager import save_pipeline_execution_stats
            
            # Calculate statistics
            successful_people = len(successful_emissions)  # Each successful emission represents 1 person
            failed_people = len(all_failed_individuals)
            total_processed = successful_people + failed_people
            
            stats = {
                "run_id": f"{datetime.now().strftime('%Y%m%d_%H_%M_%S')}",
                "successful": successful_people,
                "failed": failed_people,
                "total_processed": total_processed,
                "success_rate": (successful_people / total_processed * 100) if total_processed > 0 else 0.0,
                "successful_emissions": len(successful_emissions),
                "failed_individuals": len(all_failed_individuals),
                "pipeline_type": "si"
            }
            
            # Save to unified statistics system
            save_pipeline_execution_stats('si', stats)
            logger.info(f"📊 Saved SI unified statistics: {successful_people} successful, {failed_people} failed")
            
        except Exception as e:
            logger.error(f"❌ Error saving SI unified statistics: {e}")
        
        logger.info("✅ SI pipeline with corrected filtering completed successfully")
        return True, successful_emissions, failed_individuals_data, all_failed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error in SI pipeline with corrected filtering: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, [], [], []

if __name__ == "__main__":
    # Run the corrected SI pipeline
    success, successful_emissions, failed_individuals_data, all_failed_individuals = run_si_pipeline_with_corrected_filtering()
    
    if success:
        logger.info(f"✅ Pipeline completed successfully!")
        logger.info(f"📊 Results:")
        logger.info(f"   - Successful emissions: {len(successful_emissions)}")
        logger.info(f"   - Failed individuals data: {len(failed_individuals_data)}")
        logger.info(f"   - Total failed individuals: {len(all_failed_individuals)}")
    else:
        logger.error("❌ Pipeline failed")
        sys.exit(1)
