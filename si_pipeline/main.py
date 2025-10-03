#!/usr/bin/env python3
"""
Unified SI Pipeline with Individual Filtering and Complete Error Handling.
This implementation correctly handles the SI pipeline flow:
1. File comparison (automatic old file replacement)
2. Single emission creation
3. API processing with individual filtering on errors
4. Statistics saving and error reporting
"""

import sys
import json
import os
import time
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
        
        # Filter insured individuals
        removed_individuals = []
        for factura, emision in emission_data.items():
            original_insured = emision["emision"]["insured"]
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
            
            # Update the emission with filtered insured
            emission_data[factura]["emision"]["insured"] = filtered_insured
        
        # Save filtered JSON
        filtered_json_path = json_path.replace('.json', '_filtered.json')
        with open(filtered_json_path, 'w', encoding='utf-8') as f:
            json.dump(emission_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Filtered JSON saved to: {filtered_json_path}")
        logger.info(f"📊 Removed {len(removed_individuals)} individuals")
        
        return filtered_json_path, removed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error filtering individuals: {e}")
        return json_path, []

def process_si_emission_with_retry(json_path="/app/si_pipeline/emision_unica.json"):
    """
    Process SI emission with individual filtering and retry logic.
    
    Args:
        json_path: Path to the emission JSON file
        
    Returns:
        tuple: (success, successful_emissions, failed_individuals_data, all_failed_individuals)
    """
    logger.info("🚀 Starting SI emission processing with individual filtering and retry...")
    
    try:
        # Load emissions from JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            emisiones = json.load(f)
            
        logger.info(f"📊 Total emissions to process: {len(emisiones)}")
        
        # Process emissions with the existing procesar_validacion function
        emisiones_exitosas, emisiones_fallidas = procesar_validacion(
            emisiones_path=json_path,
            output_success_path="/app/si_pipeline/data/successful_emissions.json",
            output_errors_path="/app/si_pipeline/data/failed_emissions.json"
        )
        
        # Extract failed individuals from API responses
        failed_individuals_data = []
        all_failed_individuals = []
        
        # emisiones_fallidas is a LIST, not a dict!
        for failed_emission in emisiones_fallidas:
            factura = failed_emission.get('factura')
            error_details = failed_emission.get('error_details', {})
            
            if 'api_response' in error_details:
                api_response = error_details['api_response']
                failed_individuals = extract_failed_individuals_from_api_response(api_response)
                
                if failed_individuals:
                    failed_individuals_data.append({
                        "factura": factura,
                        "api_failed_individuals": failed_individuals,
                        "error_details": error_details
                    })
                    all_failed_individuals.extend(failed_individuals)
        
        # If we have failed individuals, try filtering and retrying
        if failed_individuals_data:
            logger.info(f"🔄 Found {len(all_failed_individuals)} failed individuals, attempting retry with filtering...")
            
            # Filter individuals and create new JSON
            filtered_json_path, removed_individuals = filter_individuals_from_json(json_path, all_failed_individuals)
            
            if removed_individuals:
                logger.info(f"🔄 Retrying with filtered data...")
                
                # Process the filtered emissions
                emisiones_exitosas_filtered, emisiones_fallidas_filtered = procesar_validacion(
                    emisiones_path=filtered_json_path,
                    output_success_path="/app/si_pipeline/data/successful_emissions_filtered.json",
                    output_errors_path="/app/si_pipeline/data/failed_emissions_filtered.json"
                )
                
                # Combine results (both are LISTS, not dicts!)
                emisiones_exitosas.extend(emisiones_exitosas_filtered)
                emisiones_fallidas.extend(emisiones_fallidas_filtered)
                
                logger.info(f"✅ Retry completed. Total successful: {len(emisiones_exitosas)}")
        
        # Save statistics to the new unified system
        try:
            import sys as sys_module
            sys_module.path.append('/app/shared')
            from statistics_manager import save_pipeline_execution_stats
            
            # Calculate statistics - total people from original emissions
            total_people = sum(len(emision.get('emision', {}).get('insured', [])) for emision in emisiones.values())
            # emisiones_exitosas is a LIST, not a dict - don't call .values()!
            successful_people = 0
            for emision in emisiones_exitosas:
                if 'emision' in emision and 'emision' in emision['emision'] and 'insured' in emision['emision']['emision']:
                    successful_people += len(emision['emision']['emision']['insured'])
                elif 'emision' in emision and 'metadata' in emision['emision']:
                    successful_people += emision['emision']['metadata'].get('total_asegurados', 0)
            
            failed_people = total_people - successful_people  # All people who didn't succeed
            
            stats = {
                'run_id': f"{time.strftime('%Y%m%d_%H_%M_%S')}",
                'emisiones': {
                    'total': len(emisiones),
                    'exitosas': len(emisiones_exitosas),
                    'fallidas': len(emisiones_fallidas)
                },
                'asegurados': {
                    'total': total_people,
                    'exitosos': successful_people,
                    'fallidos': failed_people
                },
                'successful': successful_people,  # For email reports
                'failed': failed_people,          # For email reports
                'total_processed': total_people,
                'success_rate': (successful_people / total_people * 100) if total_people > 0 else 0.0,
                'errores_por_tipo': {},
                'codigos_validacion': {}
            }
            
            # Save to unified statistics system
            save_pipeline_execution_stats('si', stats)
            logger.info(f"📊 Saved unified statistics: {successful_people} successful, {failed_people} failed")
        except Exception as e:
            logger.error(f"❌ Error saving statistics: {e}")
        
        return True, emisiones_exitosas, failed_individuals_data, all_failed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error in SI emission processing: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, [], [], []

def run_si_pipeline():
    """
    Run the complete SI pipeline process with individual filtering and retry logic.
    """
    logger.info("🚀 Starting SI pipeline process with individual filtering...")
    
    # Check if it's the 1st day of the month
    from datetime import datetime
    current_day = datetime.now().day
    
    if current_day == 1:
        logger.info("📅 First day of the month detected - will only run comparison to set baseline, no emissions will be processed")
        is_first_day = True
    else:
        is_first_day = False
    
    try:
        # Clean up previous run data to ensure fresh start
        logger.info("🧹 Cleaning up previous run data...")
        data_dir = "/app/si_pipeline/data"
        if os.path.exists(data_dir):
            # Remove old failed individuals data files
            old_files = [
                "/app/si_pipeline/data/latest_failed_individuals.json",
                "/app/si_pipeline/data/failed_individuals_data.json",
                "/app/si_pipeline/data/successful_emissions.json"
            ]
            for file_path in old_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"🗑️ Removed old file: {file_path}")
        
        logger.info("✅ Cleanup completed - starting fresh process")
        # Step 1: Check if comparison has already been done by pipeline manager
        comparison_file = "/app/si_pipeline/Comparador_Humano/exceles/comparison_result.xlsx"
        
        if os.path.exists(comparison_file):
            # Check if the comparison file is recent (within last 5 minutes)
            file_age = time.time() - os.path.getmtime(comparison_file)
            if file_age < 300:  # 5 minutes
                logger.info("✅ Comparison already completed by pipeline manager - skipping comparison step")
                skip_comparison = True
                
                # If it's the 1st day and comparison was already done, exit early
                if is_first_day:
                    logger.info("✅ First day of month - comparison already completed, baseline set. Skipping emission processing.")
                    logger.info("📅 Emissions will resume starting from the 2nd day of the month")
                    return True, {}, [], []
            else:
                logger.info("⚠️ Comparison file exists but is old - will re-run comparison")
                skip_comparison = False
        else:
            logger.info("📊 No existing comparison file found - will run comparison")
            skip_comparison = False
        
        if not skip_comparison:
            # Step 1: Compare files (this automatically replaces old file with new file)
            if not is_automated:
                input("Presiona Enter para continuar... a comparar los archivo:")
            logger.info("📊 Running SI file comparison...")
            
            # List files in the SI directory - use absolute path
            si_dir = "/app/si_pipeline/Comparador_Humano/exceles"
            logger.info(f"📁 SI exceles directory: {si_dir}")
            if os.path.exists(si_dir):
                files = os.listdir(si_dir)
                logger.info(f"📂 Files in SI exceles directory: {files}")
            else:
                logger.error(f"❌ SI exceles directory not found: {si_dir}")
                return False, [], [], []
            
            try:
                comparison_result = comparador_SI()
                if comparison_result:
                    logger.info("✅ SI file comparison completed successfully")
                else:
                    logger.error("❌ SI file comparison failed")
                    return False, [], [], []
            except Exception as e:
                logger.error(f"❌ Error during comparison: {e}")
                return False, [], [], []
            
            # Save statistics to the new unified system
            try:
                import sys as sys_module
                sys_module.path.append('/app/shared')
                from statistics_manager import save_pipeline_execution_stats
                
                # Save to unified statistics system
                save_pipeline_execution_stats('si', {
                    'run_id': f"{time.strftime('%Y%m%d_%H_%M_%S')}",
                    'emisiones': {'total': 0, 'exitosas': 0, 'fallidas': 0},
                    'asegurados': {'total': 0, 'exitosos': 0, 'fallidos': 0},
                    'errores_por_tipo': {},
                    'codigos_validacion': {}
                })
                logger.info("📊 Saved comparison statistics")
            except Exception as e:
                logger.error(f"❌ Error saving comparison statistics: {e}")
        
        # If it's the 1st day of the month, stop here - only comparison needed
        if is_first_day:
            logger.info("✅ First day of month - comparison completed, baseline set. Skipping emission processing.")
            logger.info("📅 Emissions will resume starting from the 2nd day of the month")
            return True, {}, [], []
        
        # Check if comparison result file exists and has data - use absolute path
        comparison_file = "/app/si_pipeline/Comparador_Humano/exceles/comparison_result.xlsx"
        logger.info(f"📁 Checking comparison result file: {comparison_file}")
        
        if not os.path.exists(comparison_file):
            logger.error(f"❌ Comparison result file not found: {comparison_file}")
            return False, [], [], []
        
        # Check if file has data
        import pandas as pd
        try:
            df = pd.read_excel(comparison_file)
            if len(df) == 0:
                logger.warning("⚠️ Comparison result file is empty - no new people to process")
                return False, [], [], []
            logger.info(f"📊 Comparison result file has {len(df)} rows")
        except Exception as e:
            logger.error(f"❌ Error reading comparison result file: {e}")
            return False, [], [], []
        
        # Step 2: Create single emission
        if not is_automated:
            input("Presiona Enter para continuar... a crear la emision unica:")
        logger.info("📝 Creating single emission...")
        
        create_single_emission(comparison_file, "/app/si_pipeline/emision_unica.json")
        logger.info("✅ Single emission created successfully")
        
        # Step 3: Process emissions with individual filtering and retry
        logger.info("🔄 Processing emissions with individual filtering and retry...")
        success, successful_emissions, failed_individuals_data, all_failed_individuals = process_si_emission_with_retry("/app/si_pipeline/emision_unica.json")
        
        # Step 4: Save results for email reporting
        if successful_emissions:
            logger.info(f"💾 Saving {len(successful_emissions)} successful emissions...")
            os.makedirs("/app/si_pipeline/data", exist_ok=True)
            with open("/app/si_pipeline/data/successful_emissions.json", "w") as f:
                json.dump(successful_emissions, f, indent=2)
        
        # Always create latest_failed_individuals.json file for error handler
        # This ensures the error handler knows the current process completed
        logger.info("💾 Creating latest_failed_individuals.json for error handler...")
        os.makedirs("/app/si_pipeline/data", exist_ok=True)
        from datetime import datetime
        with open("/app/si_pipeline/data/latest_failed_individuals.json", "w") as f:
            json.dump({
                'failed_individuals_data': failed_individuals_data if failed_individuals_data else [],
                'all_failed_individuals': all_failed_individuals if all_failed_individuals else [],
                'timestamp': datetime.now().isoformat(),
                'process_completed': True
            }, f, indent=2)
        
        if failed_individuals_data:
            logger.info(f"💾 Saving {len(failed_individuals_data)} failed individuals data...")
            with open("/app/si_pipeline/data/failed_individuals_data.json", "w") as f:
                json.dump(failed_individuals_data, f, indent=2)
        
        # Save final statistics
        try:
            import sys as sys_module
            sys_module.path.append('/app/shared')
            from statistics_manager import save_pipeline_execution_stats
            from datetime import datetime
            
            # Calculate final statistics
            # Get total people from comparison file
            import pandas as pd
            comparison_file = "/app/si_pipeline/Comparador_Humano/exceles/comparison_result.xlsx"
            try:
                df = pd.read_excel(comparison_file)
                total_people = len(df)
            except:
                # Fallback: count from successful emissions (which is a LIST)
                fallback_successful = 0
                if successful_emissions:
                    for emision in successful_emissions:
                        if 'emision' in emision and 'emision' in emision['emision'] and 'insured' in emision['emision']['emision']:
                            fallback_successful += len(emision['emision']['emision']['insured'])
                        elif 'emision' in emision and 'metadata' in emision['emision']:
                            fallback_successful += emision['emision']['metadata'].get('total_asegurados', 0)
                total_people = fallback_successful + len(all_failed_individuals)
            
            # successful_emissions is a LIST (returned from process_si_emission_with_retry), count people properly
            successful_people = 0
            if successful_emissions:
                for emision in successful_emissions:
                    if 'emision' in emision and 'emision' in emision['emision'] and 'insured' in emision['emision']['emision']:
                        successful_people += len(emision['emision']['emision']['insured'])
                    elif 'emision' in emision and 'metadata' in emision['emision']:
                        successful_people += emision['emision']['metadata'].get('total_asegurados', 0)
            
            failed_people = total_people - successful_people  # All people who didn't succeed
            
            stats = {
                'run_id': f"{datetime.now().strftime('%Y%m%d_%H_%M_%S')}",
                'emisiones': {
                    'total': len(successful_emissions) + len(failed_individuals_data),
                    'exitosas': len(successful_emissions),
                    'fallidas': len(failed_individuals_data)
                },
                'asegurados': {
                    'total': total_people,
                    'exitosos': successful_people,
                    'fallidos': failed_people
                },
                'successful': successful_people,  # For email reports
                'failed': failed_people,          # For email reports
                'total_processed': total_people,
                'success_rate': (successful_people / total_people * 100) if total_people > 0 else 0.0,
                'errores_por_tipo': {},
                'codigos_validacion': {}
            }
            
            # Save to unified statistics system
            save_pipeline_execution_stats('si', stats)
            logger.info(f"📊 Final statistics saved: {successful_people} successful, {failed_people} failed")
        except Exception as e:
            logger.error(f"❌ Error saving final statistics: {e}")
        
        logger.info("✅ SI pipeline with individual filtering and retry completed successfully")
        return True, successful_emissions, failed_individuals_data, all_failed_individuals
        
    except Exception as e:
        logger.error(f"❌ Error in SI pipeline: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, [], [], []

def test_multiple_emissions(json_path: str = "/app/si_pipeline/emision_unica.json", num_emissions: int = 10) -> bool:
    """
    Prueba el procesamiento de múltiples emisiones.
    
    Args:
        json_path (str): Ruta al archivo de emisiones
        num_emissions (int): Número de emisiones a procesar
        
    Returns:
        bool: True si la prueba fue exitosa, False en caso contrario
    """
    try:
        # Crear directorio data si no existe
        data_dir = Path("/app/si_pipeline/data")
        data_dir.mkdir(exist_ok=True)
        
        # Crear archivo temporal con las primeras N emisiones
        with open(json_path, 'r') as f:
            emisiones = json.load(f)
            
        if not emisiones:
            logger.error("❌ No hay emisiones en el archivo")
            return False
            
        # Tomar las primeras N emisiones
        primeras_emisiones = dict(list(emisiones.items())[:num_emissions])
        logger.info(f"🔍 Procesando las primeras {len(primeras_emisiones)} emisiones")
        
        # Guardar en archivo temporal
        test_file = data_dir / "test_emissions.json"
        with open(test_file, 'w') as f:
            json.dump(primeras_emisiones, f, indent=2)
            
        # Procesar las emisiones
        emisiones_exitosas, emisiones_fallidas = procesar_validacion(
            emisiones_path=str(test_file),
            output_success_path=str(data_dir / "test_success.json"),
            output_errors_path=str(data_dir / "test_errors.json")
        )
        
        # Calcular tasa de éxito
        total = len(emisiones_exitosas) + len(emisiones_fallidas)
        tasa_exito = (len(emisiones_exitosas) / total) * 100 if total > 0 else 0
        
        logger.info("\n📊 Resumen de la prueba:")
        logger.info(f"Total procesadas: {total}")
        logger.info(f"Exitosas: {len(emisiones_exitosas)}")
        logger.info(f"Fallidas: {len(emisiones_fallidas)}")
        logger.info(f"Tasa de éxito: {tasa_exito:.2f}%")
        
        success = len(emisiones_exitosas) > 0
        if success:
            logger.success("✅ Prueba completada!")
        else:
            logger.error("❌ La prueba falló - No hubo emisiones exitosas")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {str(e)}")
        return False

def main():
    """
    Función principal que procesa el archivo de emisiones.
    """
    # Configurar logging
    logger.remove()
    logger.add("/app/si_pipeline/logs/emisor.log", rotation="500 MB", level="DEBUG")
    logger.add(lambda msg: print(msg), level="INFO")
    
    # Verificar argumentos
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Modo prueba con emisiones múltiples
            json_path = sys.argv[2] if len(sys.argv) > 2 else "/app/si_pipeline/emision_unica.json"
            num_emissions = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            return 0 if test_multiple_emissions(json_path, num_emissions) else 1
        else:
            json_path = sys.argv[1]
    else:
        json_path = "/app/si_pipeline/emision_unica.json"
        
    logger.info(f"🚀 Iniciando procesamiento de emisiones desde {json_path}")
    
    try:
        # Procesar emisiones
        emisiones_exitosas, emisiones_fallidas = procesar_validacion(emisiones_path=json_path)
        
        # El resumen ya se muestra en la función procesar_validacion
        return 0 if not emisiones_fallidas else 1
        
    except Exception as e:
        logger.error(f"❌ Error durante el procesamiento: {str(e)}")
        return 1

if __name__ == "__main__":
    # Run the complete SI pipeline process
    success, successful_emissions, failed_individuals_data, all_failed_individuals = run_si_pipeline()
    
    if success:
        logger.info(f"✅ Pipeline completed successfully!")
        logger.info(f"📊 Results:")
        logger.info(f"   - Successful emissions: {len(successful_emissions)}")
        logger.info(f"   - Failed individuals data: {len(failed_individuals_data)}")
        logger.info(f"   - Total failed individuals: {len(all_failed_individuals)}")
        
        # Then run the main processing if needed
        if len(sys.argv) > 1 and sys.argv[1] != "--test":
            sys.exit(main())
        else:
            sys.exit(0)
    else:
        logger.error("❌ SI pipeline failed, exiting")
        sys.exit(1)