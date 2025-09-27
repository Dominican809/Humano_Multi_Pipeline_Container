"""
Script principal para la emisión automatizada de pólizas usando los módulos refactorizados.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from loguru import logger
from emisor_goval.utils.procesar_validacion import procesar_validacion
from emisor_goval.utils.excel_to_emision_v2 import cargar_emisiones_desde_excel
import os

# Check if running in automated mode (Docker container)
is_automated = os.environ.get('AUTOMATED_MODE', 'false').lower() == 'true'

def run_viajeros_pipeline():
    """
    Run the complete Viajeros pipeline process.
    This function handles the Excel to JSON conversion step.
    """
    logger.info("🚀 Starting Viajeros pipeline process...")
    
    try:
        # Step 1: Load emissions from Excel
        if not is_automated:
            input("Presiona Enter para empezar a cargar las emisiones desde excel:")
        logger.info("📊 Loading emissions from Excel...")
        cargar_emisiones_desde_excel("/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx", "/app/viajeros_pipeline/emisiones_generadas.json")
        logger.info("✅ Excel to JSON conversion completed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in Viajeros pipeline: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_multiple_emissions(json_path: str = "/app/viajeros_pipeline/emisiones_generadas.json", num_emissions: int = 1) -> bool:
    """
    Prueba el procesamiento de emisiones (puede ser una sola o múltiples).
    
    Args:
        json_path (str): Ruta al archivo de emisiones
        num_emissions (int): Número de emisiones a procesar (default: 1)
        
    Returns:
        bool: True si la prueba fue exitosa, False en caso contrario
    """
    try:
        # Crear directorio data si no existe
        data_dir = Path("/app/viajeros_pipeline/data")
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
    logger.add("/app/viajeros_pipeline/logs/emisor.log", rotation="500 MB", level="DEBUG")
    logger.add(lambda msg: print(msg), level="INFO")
    
    # Verificar argumentos
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Modo prueba con emisiones (default: 1 emisión)
            json_path = sys.argv[2] if len(sys.argv) > 2 else "/app/viajeros_pipeline/emisiones_generadas.json"
            num_emissions = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            return 0 if test_multiple_emissions(json_path, num_emissions) else 1
        else:
            json_path = sys.argv[1]
    else:
        json_path = "/app/viajeros_pipeline/emisiones_generadas.json"
        
    logger.info(f"🚀 Iniciando procesamiento de emisiones desde {json_path}")
    
    try:
        # Procesar emisiones
        emisiones_exitosas, emisiones_fallidas = procesar_validacion(emisiones_path=json_path)
        
        # Save statistics for the coordinator to read
        # Calculate statistics from the actual execution results
        total_emissions = len(emisiones_exitosas) + len(emisiones_fallidas)
        successful_emissions = len(emisiones_exitosas)
        failed_emissions = len(emisiones_fallidas)
        
        # Count people in successful emissions
        successful_people = 0
        for emission in emisiones_exitosas:
            if 'emision' in emission and 'insured' in emission['emision']:
                successful_people += len(emission['emision']['insured'])
            elif 'metadata' in emission and 'total_asegurados' in emission['metadata']:
                successful_people += emission['metadata']['total_asegurados']
        
        # Count people in failed emissions using the original JSON file
        failed_people = 0
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                original_emisiones = json.load(f)
            
            for emission in emisiones_fallidas:
                if 'factura' in emission:
                    factura = emission['factura']
                    if factura in original_emisiones:
                        original_emision = original_emisiones[factura]
                        if 'emision' in original_emision and 'insured' in original_emision['emision']:
                            people_count = len(original_emision['emision']['insured'])
                            failed_people += people_count
                            logger.info(f"📊 Found {people_count} people in failed emission {factura}")
                        else:
                            logger.warning(f"📊 Could not find insured data in original emission {factura}")
                    else:
                        logger.warning(f"📊 Factura {factura} not found in original emissions")
        except Exception as e:
            logger.error(f"📊 Error loading original emissions for people counting: {e}")
            # Fallback to old method
            for emission in emisiones_fallidas:
                if 'emision' in emission:
                    emision_data = emission['emision']
                    if 'emision' in emision_data and 'insured' in emision_data['emision']:
                        people_count = len(emision_data['emision']['insured'])
                        failed_people += people_count
                        logger.info(f"📊 Found {people_count} people in failed emission {emission.get('factura', 'unknown')} (fallback)")
        
        # Create statistics dictionary with correct people counts
        stats = {
            "run_id": f"{datetime.now().strftime('%Y%m%d_%H_%M_%S')}",
            "emisiones": {
                "total": total_emissions,
                "exitosas": successful_emissions,
                "fallidas": failed_emissions
            },
            "asegurados": {
                "total": successful_people + failed_people,
                "exitosos": successful_people,
                "fallidos": failed_people
            },
            "successful": successful_people,  # For email reports
            "failed": failed_people,          # For email reports
            "total_processed": successful_people + failed_people,
            "success_rate": (successful_people / (successful_people + failed_people) * 100) if (successful_people + failed_people) > 0 else 0.0,
            "errores_por_tipo": {},
            "codigos_validacion": {}
        }
        
        # Save statistics to the new unified system
        try:
            import sys as sys_module
            sys_module.path.append('/app/shared')
            from statistics_manager import save_pipeline_execution_stats
            
            # Save to unified statistics system
            save_pipeline_execution_stats('viajeros', stats)
            logger.info(f"📊 Saved unified statistics: {successful_people} successful, {failed_people} failed")
        except Exception as e:
            logger.error(f"❌ Error saving unified statistics: {e}")
        
        # Save statistics to a file that the coordinator can read (legacy)
        stats_file = "/app/viajeros_pipeline/data/latest_execution_stats.json"
        os.makedirs(os.path.dirname(stats_file), exist_ok=True)
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # Save detailed failure data for email reporting
        # Read the original emisiones_generadas.json to get the complete people data
        detailed_failures = []
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                original_emisiones = json.load(f)
            logger.info(f"📊 Loaded original emissions data: {len(original_emisiones)} facturas")
        except Exception as e:
            logger.error(f"📊 Error loading original emissions: {e}")
            original_emisiones = {}
        
        for emission in emisiones_fallidas:
            if 'factura' in emission:
                factura = emission['factura']
                
                # Get all people from the original emissions data
                all_people = []
                if factura in original_emisiones:
                    original_emision = original_emisiones[factura]
                    if 'emision' in original_emision and 'insured' in original_emision['emision']:
                        insured_data = original_emision['emision']['insured']
                        for person in insured_data:
                            all_people.append({
                                'firstname': person.get('firstname', ''),
                                'lastname': person.get('lastname', ''),
                                'passport': person.get('passport', ''),
                                'identity': person.get('identity', ''),
                                'birthdate': person.get('birthdate', ''),
                                'status': 'failed'  # Default status
                            })
                        logger.info(f"📊 Found {len(all_people)} people in factura {factura}")
                    else:
                        logger.warning(f"📊 Could not find insured data in original emission {factura}")
                else:
                    logger.warning(f"📊 Factura {factura} not found in original emissions")
                
                # Get people with active coverage from error details
                people_with_active_coverage = []
                if 'error_details' in emission and 'api_response' in emission['error_details']:
                    api_response = emission['error_details']['api_response']
                    if 'found' in api_response and api_response['found']:
                        for person in api_response['found']:
                            people_with_active_coverage.append({
                                'firstname': person.get('firstname', ''),
                                'lastname': person.get('lastname', ''),
                                'passport': person.get('passport', ''),
                                'identity': person.get('identity', ''),
                                'birthdate': person.get('birthdate', ''),
                                'ticket_id': person.get('ticket_id', ''),
                                'status': 'active_coverage'
                            })
                
                # Mark people with active coverage in the all_people list
                for person in all_people:
                    for active_person in people_with_active_coverage:
                        if (person.get('passport') == active_person.get('passport') and 
                            person.get('firstname') == active_person.get('firstname') and
                            person.get('lastname') == active_person.get('lastname')):
                            person['status'] = 'active_coverage'
                            person['ticket_id'] = active_person.get('ticket_id', '')
                            break
                
                detailed_failures.append({
                    'factura': factura,
                    'pipeline_type': 'viajeros',
                    'pipeline_name': 'Viajeros',
                    'step': 'manager',
                    'error': emission.get('error', 'Error en validación: 417'),
                    'num_asegurados': len(all_people),
                    'error_details': emission.get('error_details', {}),
                    'all_people': all_people,
                    'people_with_active_coverage': people_with_active_coverage
                })
        
        # Save detailed failure data
        detailed_failures_file = "/app/viajeros_pipeline/data/latest_detailed_failures.json"
        with open(detailed_failures_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_failures, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📊 Statistics saved to {stats_file}: {successful_emissions}/{total_emissions} emissions, {successful_people}/{successful_people + failed_people} people")
        logger.info(f"📊 Detailed failures saved to {detailed_failures_file}: {len(detailed_failures)} facturas")
        
        # El resumen ya se muestra en la función procesar_validacion
        return 0 if not emisiones_fallidas else 1
        
    except Exception as e:
        logger.error(f"❌ Error durante el procesamiento: {str(e)}")
        return 1

if __name__ == "__main__":
    # Run the complete Viajeros pipeline process
    pipeline_success = run_viajeros_pipeline()
    if pipeline_success:
        # Then run the main processing
        sys.exit(main())
    else:
        logger.error("❌ Viajeros pipeline failed, exiting")
        sys.exit(1) 