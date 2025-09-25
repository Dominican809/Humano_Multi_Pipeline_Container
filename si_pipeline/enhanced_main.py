#!/usr/bin/env python3
"""
Enhanced SI Pipeline with individual filtering and error handling.
"""

import sys
import json
import os
from pathlib import Path
from loguru import logger
from emisor_goval.utils.procesar_validacion import procesar_validacion
from Comparador_Humano.comparador_SI import comparador_SI
from emisor_goval.utils.SI_excel_to_emision import create_single_emission
from emisor_goval.utils.procesar_validacion import EmissionTracker, extract_error_details
from emisor_goval.api.auth import TokenManager
from emisor_goval.api.cotizacion import cotizar_emision
from emisor_goval.api.manager import process_manager_validation
from emisor_goval.api.payment import apply_payment

# Check if running in automated mode (Docker container)
is_automated = os.environ.get('AUTOMATED_MODE', 'false').lower() == 'true'

def extract_failed_individuals_from_api_response(api_response):
    """Extract individuals with active coverage from API response."""
    failed_individuals = []
    if api_response and 'found' in api_response and api_response['found']:
        failed_individuals = api_response['found']
    return failed_individuals

def filter_individuals_from_emission(emision, failed_individuals):
    """
    Remove failed individuals from an emission and return the filtered emission.
    
    Args:
        emision: The emission data
        failed_individuals: List of individuals that failed validation
        
    Returns:
        tuple: (filtered_emision, removed_individuals)
    """
    if not failed_individuals:
        return emision, []
    
    # Create sets of failed identifiers for quick lookup
    failed_passports = set()
    failed_identities = set()
    
    for individual in failed_individuals:
        if individual.get('passport'):
            failed_passports.add(individual['passport'])
        if individual.get('identity'):
            failed_identities.add(individual['identity'])
    
    # Filter insured individuals
    original_insured = emision["emision"]["insured"]
    filtered_insured = []
    removed_individuals = []
    
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
    filtered_emision = emision.copy()
    filtered_emision["emision"] = emision["emision"].copy()
    filtered_emision["emision"]["insured"] = filtered_insured
    
    return filtered_emision, removed_individuals

def process_si_emission_with_individual_filtering(emisiones_path: str = "emision_unica.json"):
    """
    Process SI emissions with individual filtering for failed validations.
    
    Args:
        emisiones_path: Path to the emissions JSON file
        
    Returns:
        tuple: (successful_emissions, failed_individuals_data, all_failed_individuals)
    """
    logger.info("🚀 Starting SI emission processing with individual filtering...")
    
    # Initialize tracking
    tracker = EmissionTracker()
    
    # Initialize results
    successful_emissions = []
    failed_individuals_data = []
    all_failed_individuals = []
    
    try:
        # Load emissions from JSON file
        with open(emisiones_path, 'r') as f:
            emisiones = json.load(f)
            
        logger.info(f"Total emissions to process: {len(emisiones)}")
        
        # Get authentication token
        token_manager = TokenManager()
        token = token_manager.get_token()
        
        # Process each emission
        for factura, emision in emisiones.items():
            try:
                num_asegurados = len(emision["emision"]["insured"])
                logger.info(f"Processing factura {factura} with {num_asegurados} insured individuals")
                
                # 1. Create quotation
                cotizacion_result = cotizar_emision(emision["emision"])
                if not isinstance(cotizacion_result, tuple) or not cotizacion_result[0]:
                    error_details = extract_error_details(
                        cotizacion_result[2] if isinstance(cotizacion_result, tuple) and len(cotizacion_result) > 2 else None,
                        "No se pudo crear la cotización",
                        "cotizacion"
                    )
                    tracker.track_emission(factura, {
                        "error": "No se pudo crear la cotización",
                        "step": "cotizacion",
                        "num_asegurados": num_asegurados,
                        "error_details": error_details
                    })
                    continue
                
                cotizacion_id, uri_manager = cotizacion_result[:2]
                
                # 2. Process manager validation
                manager_result = process_manager_validation(cotizacion_id, token)
                if not isinstance(manager_result, tuple) or not manager_result[0]:
                    error_details = extract_error_details(
                        manager_result[3] if isinstance(manager_result, tuple) and len(manager_result) > 3 else None,
                        manager_result[1] if isinstance(manager_result, tuple) else "Error desconocido en validación",
                        "manager"
                    )
                    
                    # Extract failed individuals from API response
                    api_response = error_details.get('api_response', {})
                    failed_individuals = extract_failed_individuals_from_api_response(api_response)
                    
                    if failed_individuals:
                        logger.warning(f"Found {len(failed_individuals)} individuals with active coverage in factura {factura}")
                        
                        # Filter out failed individuals
                        filtered_emision, removed_individuals = filter_individuals_from_emission(emision, failed_individuals)
                        
                        if removed_individuals:
                            logger.info(f"Removed {len(removed_individuals)} individuals from factura {factura}")
                            
                            # Store failed individuals data
                            failed_individuals_data.append({
                                "factura": factura,
                                "removed_individuals": removed_individuals,
                                "api_failed_individuals": failed_individuals,
                                "error_details": error_details
                            })
                            
                            all_failed_individuals.extend(failed_individuals)
                            
                            # Try to process the filtered emission if it has remaining individuals
                            if len(filtered_emision["emision"]["insured"]) > 0:
                                logger.info(f"Retrying factura {factura} with {len(filtered_emision['emision']['insured'])} remaining individuals")
                                
                                # Process the filtered emission
                                success = process_filtered_emission(filtered_emision, factura, token, tracker, successful_emissions)
                                if success:
                                    logger.success(f"✅ Successfully processed filtered factura {factura}")
                                else:
                                    logger.error(f"❌ Failed to process filtered factura {factura}")
                            else:
                                logger.warning(f"All individuals removed from factura {factura}, skipping")
                                
                                tracker.track_emission(factura, {
                                    "error": f"All individuals removed due to active coverage",
                                    "step": "manager",
                                    "num_asegurados": num_asegurados,
                                    "error_details": error_details
                                })
                        else:
                            # No individuals to remove, this is a different type of error
                            tracker.track_emission(factura, {
                                "error": f"Error en validación: {manager_result[1] if isinstance(manager_result, tuple) else 'Error desconocido'}",
                                "step": "manager",
                                "num_asegurados": num_asegurados,
                                "error_details": error_details
                            })
                    else:
                        # No failed individuals found, this is a different type of error
                        tracker.track_emission(factura, {
                            "error": f"Error en validación: {manager_result[1] if isinstance(manager_result, tuple) else 'Error desconocido'}",
                            "step": "manager",
                            "num_asegurados": num_asegurados,
                            "error_details": error_details
                        })
                    
                    continue
                
                # 3. Process payment for successful validation
                success, error_msg, final_uri = manager_result[:3]
                payment_result = apply_payment(cotizacion_id, token, final_uri)
                
                if not payment_result or not isinstance(payment_result, dict) or "ticket_id" not in payment_result:
                    error_details = extract_error_details(
                        payment_result[1] if isinstance(payment_result, tuple) and len(payment_result) > 1 else None,
                        "No se generó ticket de la póliza",
                        "pago"
                    )
                    tracker.track_emission(factura, {
                        "error": "No se generó ticket de la póliza",
                        "step": "pago",
                        "num_asegurados": num_asegurados,
                        "error_details": error_details
                    })
                    continue
                
                # Successful emission
                tracker.track_emission(factura, {
                    "tracking_id": payment_result["ticket_id"],
                    "num_asegurados": num_asegurados
                })
                successful_emissions.append({
                    "factura": factura,
                    "emision": emision,
                    "ticket_id": payment_result["ticket_id"]
                })
                
                logger.success(f"✅ Successfully processed factura {factura}")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing factura {factura}: {error_msg}")
                tracker.track_emission(factura, {
                    "error": error_msg,
                    "step": "desconocido",
                    "num_asegurados": len(emision["emision"]["insured"]),
                    "error_details": {
                        "validation_messages": [error_msg]
                    }
                })
        
        # Generate summary
        total_processed = len(emisiones)
        successful_count = len(successful_emissions)
        failed_count = len(failed_individuals_data)
        
        logger.info(f"\n📊 Processing Summary:")
        logger.info(f"Total emissions processed: {total_processed}")
        logger.info(f"Successful emissions: {successful_count}")
        logger.info(f"Emissions with failed individuals: {failed_count}")
        logger.info(f"Total failed individuals: {len(all_failed_individuals)}")
        
        return successful_emissions, failed_individuals_data, all_failed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error in SI emission processing: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return [], [], []

def process_filtered_emission(filtered_emision, factura, token, tracker, successful_emissions):
    """Process a filtered emission (with failed individuals removed)."""
    try:
        # 1. Create quotation for filtered emission
        cotizacion_result = cotizar_emision(filtered_emision["emision"])
        if not isinstance(cotizacion_result, tuple) or not cotizacion_result[0]:
            logger.error(f"Failed to create quotation for filtered factura {factura}")
            return False
        
        cotizacion_id, uri_manager = cotizacion_result[:2]
        
        # 2. Process manager validation
        manager_result = process_manager_validation(cotizacion_id, token)
        if not isinstance(manager_result, tuple) or not manager_result[0]:
            logger.error(f"Manager validation failed for filtered factura {factura}")
            return False
        
        # 3. Process payment
        success, error_msg, final_uri = manager_result[:3]
        payment_result = apply_payment(cotizacion_id, token, final_uri)
        
        if not payment_result or not isinstance(payment_result, dict) or "ticket_id" not in payment_result:
            logger.error(f"Payment failed for filtered factura {factura}")
            return False
        
        # Successful emission
        tracker.track_emission(factura, {
            "tracking_id": payment_result["ticket_id"],
            "num_asegurados": len(filtered_emision["emision"]["insured"])
        })
        successful_emissions.append({
            "factura": factura,
            "emision": filtered_emision,
            "ticket_id": payment_result["ticket_id"]
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing filtered emission for factura {factura}: {e}")
        return False

def run_si_pipeline_with_filtering():
    """
    Run the complete SI pipeline process with individual filtering.
    """
    logger.info("🚀 Starting SI pipeline process with individual filtering...")
    
    try:
        # Step 1: Compare files
        if not is_automated:
            input("Presiona Enter para continuar... a comparar los archivo:")
        logger.info("📊 Running SI file comparison...")
        comparador_SI()
        logger.info("✅ SI file comparison completed")
        
        # Step 2: Create single emission
        if not is_automated:
            input("Presiona Enter para continuar... a crear la emision unica:")
        logger.info("📝 Creating single emission...")
        create_single_emission("Comparador_Humano/exceles/comparison_result.xlsx", "emision_unica.json")
        logger.info("✅ Single emission created successfully")
        
        # Step 3: Process emissions with individual filtering
        logger.info("🔄 Processing emissions with individual filtering...")
        successful_emissions, failed_individuals_data, all_failed_individuals = process_si_emission_with_individual_filtering("emision_unica.json")
        
        # Step 4: Save results
        if successful_emissions:
            logger.info(f"💾 Saving {len(successful_emissions)} successful emissions...")
            with open("data/successful_emissions.json", "w") as f:
                json.dump(successful_emissions, f, indent=2)
        
        if failed_individuals_data:
            logger.info(f"💾 Saving {len(failed_individuals_data)} failed individuals data...")
            with open("data/failed_individuals_data.json", "w") as f:
                json.dump(failed_individuals_data, f, indent=2)
        
        logger.info("✅ SI pipeline with filtering completed successfully")
        return True, successful_emissions, failed_individuals_data, all_failed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error in SI pipeline with filtering: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, [], [], []

if __name__ == "__main__":
    # Run the enhanced SI pipeline
    success, successful_emissions, failed_individuals_data, all_failed_individuals = run_si_pipeline_with_filtering()
    
    if success:
        logger.info(f"✅ Pipeline completed successfully!")
        logger.info(f"📊 Results:")
        logger.info(f"   - Successful emissions: {len(successful_emissions)}")
        logger.info(f"   - Failed individuals data: {len(failed_individuals_data)}")
        logger.info(f"   - Total failed individuals: {len(all_failed_individuals)}")
    else:
        logger.error("❌ Pipeline failed")
        sys.exit(1)
