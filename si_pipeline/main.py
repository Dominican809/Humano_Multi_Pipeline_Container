"""
Script principal para la emisión automatizada de pólizas usando los módulos refactorizados.
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

def run_si_pipeline():
    """
    Run the complete SI pipeline process.
    This function handles the comparison and emission creation steps.
    """
    logger.info("🚀 Starting SI pipeline process...")
    
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
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in SI pipeline: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_multiple_emissions(json_path: str = "emision_unica.json", num_emissions: int = 10) -> bool:
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
        data_dir = Path("data")
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
    logger.add("logs/emisor.log", rotation="500 MB", level="DEBUG")
    logger.add(lambda msg: print(msg), level="INFO")
    
    # Verificar argumentos
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Modo prueba con emisiones múltiples
            json_path = sys.argv[2] if len(sys.argv) > 2 else "emision_unica.json"
            num_emissions = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            return 0 if test_multiple_emissions(json_path, num_emissions) else 1
        else:
            json_path = sys.argv[1]
    else:
        json_path = "emision_unica.json"
        
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
    pipeline_success = run_si_pipeline()
    if pipeline_success:
        # Then run the main processing
        sys.exit(main())
    else:
        logger.error("❌ SI pipeline failed, exiting")
        sys.exit(1) 