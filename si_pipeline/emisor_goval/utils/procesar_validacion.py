"""
Módulo para procesar validaciones y emisiones de pólizas.
"""

import json
from loguru import logger
from datetime import datetime
from typing import Dict, List, Any, Tuple
import os
from pathlib import Path
from ..config import DATA_DIR
from ..api.auth import TokenManager
from ..api.cotizacion import (
    cotizar_emision,
    process_manager_validation,
    VALIDACION_CODIGOS
)
from ..api.pago import apply_payment
from ..tracking.emission_tracker import EmissionTracker

def get_next_run_number(summary_dir: Path) -> int:
    """
    Obtiene el siguiente número de ejecución basado en los archivos existentes.
    """
    existing_files = list(summary_dir.glob("emisiones_run_*.json"))
    if not existing_files:
        return 1
    
    numbers = [int(f.stem.split('_')[-1]) for f in existing_files]
    return max(numbers) + 1

def extract_error_details(response, error_msg: str = None, step: str = None) -> dict:
    """
    Extrae detalles de error de una respuesta de API.
    
    Args:
        response: Respuesta de requests
        error_msg: Mensaje de error opcional
        step: Paso en el que ocurrió el error
        
    Returns:
        dict: Detalles del error estructurados
    """
    error_details = {
        "status_code": response.status_code if hasattr(response, 'status_code') else None,
        "validation_codes": [],
        "validation_messages": [],
        "api_response": None
    }
    
    try:
        if hasattr(response, 'json'):
            api_response = response.json()
            error_details["api_response"] = api_response
            
            # Extraer mensajes de error de diferentes formatos de respuesta
            if isinstance(api_response, dict):
                # Extraer códigos de validación si están presentes
                if "code" in api_response:
                    error_details["validation_codes"].append(api_response["code"])
                    if api_response["code"] in VALIDACION_CODIGOS:
                        error_details["validation_messages"].append(
                            f"{api_response['code']}: {VALIDACION_CODIGOS[api_response['code']]}"
                        )
                
                # Extraer mensajes de error
                messages = []
                if "message" in api_response:
                    if isinstance(api_response["message"], list):
                        messages.extend(api_response["message"])
                    elif isinstance(api_response["message"], dict):
                        for field, msgs in api_response["message"].items():
                            if isinstance(msgs, list):
                                messages.extend(f"{field}: {msg}" for msg in msgs)
                            else:
                                messages.append(f"{field}: {msgs}")
                    else:
                        messages.append(str(api_response["message"]))
                
                error_details["validation_messages"].extend(messages)
                
    except Exception as e:
        logger.warning(f"No se pudieron extraer detalles adicionales del error: {str(e)}")
        if error_msg:
            error_details["validation_messages"].append(error_msg)
    
    return error_details

def guardar_resumen_emision(
    factura: str,
    emision: Dict,
    ticket_id: str,
    summary_dir: Path
) -> None:
    """
    Guarda un resumen de la emisión exitosa con información vital.
    """
    # Crear directorio si no existe
    summary_dir.mkdir(parents=True, exist_ok=True)
    
    # Obtener el siguiente número de ejecución
    run_number = get_next_run_number(summary_dir)
    summary_file = summary_dir / f"emisiones_run_{run_number}.json"
    
    # Preparar información vital
    resumen = {
        "fecha_ejecucion": datetime.now().isoformat(),
        "emisiones_exitosas": []
    }
    
    # Si el archivo ya existe, cargar su contenido
    if summary_file.exists():
        with open(summary_file, 'r', encoding='utf-8') as f:
            resumen = json.load(f)
    
    # Extraer información vital de la emisión
    info_vital = {
        "factura": factura,
        "ticket_id": ticket_id,
        "fecha_emision": emision["metadata"]["fecha_emision"],
        "plan": emision["metadata"]["plan"],
        "total_asegurados": emision["metadata"]["total_asegurados"],
        "asegurados": []
    }
    
    # Extraer información de cada asegurado
    for asegurado in emision["emision"]["insured"]:
        info_asegurado = {
            "nombre": f"{asegurado['firstname']} {asegurado['lastname']}",
            "documento": asegurado['passport'] if asegurado['passport'] else asegurado['identity'],
            "fecha_nacimiento": asegurado['birthdate']
        }
        info_vital["asegurados"].append(info_asegurado)
    
    # Agregar información de viaje
    info_vital["fecha_inicio"] = emision["emision"]["from"]
    info_vital["fecha_fin"] = emision["emision"]["to"]
    info_vital["destino_id"] = emision["emision"]["destiny_id"]
    
    # Agregar al resumen
    resumen["emisiones_exitosas"].append(info_vital)
    
    # Guardar resumen actualizado
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    
    logger.success(f"📋 Resumen guardado en: {summary_file}")

def cargar_emisiones_previas(output_success_path: str) -> Dict[str, Any]:
    """
    Carga las emisiones previamente procesadas para evitar duplicados.
    
    Args:
        output_success_path (str): Ruta al archivo de emisiones exitosas
        
    Returns:
        Dict[str, Any]: Diccionario de emisiones previas indexado por factura
    """
    emisiones_previas = {}
    try:
        if os.path.exists(output_success_path):
            with open(output_success_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    factura = item.get("factura")
                    if factura:
                        emisiones_previas[factura] = item.get("emision", {})
                logger.info(f"📋 Cargadas {len(emisiones_previas)} emisiones previas")
    except Exception as e:
        logger.warning(f"⚠️ Error cargando emisiones previas: {str(e)}")
    
    return emisiones_previas

def verificar_emision_previa(factura: str, emision: Dict, emisiones_previas: Dict) -> bool:
    """
    Verifica si una emisión ya fue procesada exitosamente.
    
    Args:
        factura (str): Número de factura
        emision (Dict): Datos de la emisión
        emisiones_previas (Dict): Diccionario de emisiones previas
        
    Returns:
        bool: True si la emisión ya existe, False en caso contrario
    """
    if factura not in emisiones_previas:
        return False
        
    emision_previa = emisiones_previas[factura]
    metadata_previa = emision_previa.get("metadata", {})
    
    # Verificar si la emisión previa fue exitosa
    if metadata_previa.get("estado") == "emitido":
        respuesta_api = metadata_previa.get("respuesta_api", {})
        if isinstance(respuesta_api, dict) and respuesta_api.get("id"):
            logger.info(f"✅ La factura {factura} ya fue emitida previamente")
            logger.info(f"📄 Certificado: {respuesta_api.get('id')}")
            return True
    
    return False

def procesar_validacion(
    emisiones_path: str = None,
    output_success_path: str = None,
    output_errors_path: str = None,
    delay_between_calls: float = 1.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Procesa las emisiones a través de la API de Goval.
    
    Args:
        emisiones_path (str): Ruta al archivo JSON con las emisiones
        output_success_path (str): Ruta para guardar emisiones exitosas
        output_errors_path (str): Ruta para guardar emisiones fallidas
        delay_between_calls (float): Tiempo de espera entre llamadas a la API
        
    Returns:
        Tuple[List[Dict], List[Dict]]: (emisiones_exitosas, emisiones_fallidas)
    """
    # Inicializar tracking
    tracker = EmissionTracker()
    
    # Inicializar listas de resultados
    emisiones_exitosas = []
    emisiones_fallidas = []
    
    try:
        # Cargar emisiones del archivo JSON
        with open(emisiones_path, 'r') as f:
            emisiones = json.load(f)
            
        logger.info(f"Total emisiones a procesar: {len(emisiones)}")
        
        # Obtener token de autenticación
        token_manager = TokenManager()
        token = token_manager.get_token()
        
        # Procesar cada emisión
        for factura, emision in emisiones.items():
            try:
                num_asegurados = len(emision["emision"]["insured"])
                
                # 1. Crear cotización y procesar
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
                    emisiones_fallidas.append({
                        "factura": factura,
                        "emision": emision,
                        "error": "No se pudo crear la cotización",
                        "error_details": error_details
                    })
                    continue
                
                cotizacion_id, uri_manager = cotizacion_result[:2]
                
                # 2. Procesar validación del manager
                manager_result = process_manager_validation(cotizacion_id, token)
                if not isinstance(manager_result, tuple) or not manager_result[0]:
                    error_details = extract_error_details(
                        manager_result[3] if isinstance(manager_result, tuple) and len(manager_result) > 3 else None,
                        manager_result[1] if isinstance(manager_result, tuple) else "Error desconocido en validación",
                        "manager"
                    )
                    tracker.track_emission(factura, {
                        "error": f"Error en validación: {manager_result[1] if isinstance(manager_result, tuple) else 'Error desconocido'}",
                        "step": "manager",
                        "num_asegurados": num_asegurados,
                        "error_details": error_details
                    })
                    emisiones_fallidas.append({
                        "factura": factura,
                        "emision": emision,
                        "error": f"Error en validación: {manager_result[1] if isinstance(manager_result, tuple) else 'Error desconocido'}",
                        "error_details": error_details
                    })
                    continue
                
                success, error_msg, final_uri = manager_result[:3]
                
                # 3. Aplicar pago
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
                    emisiones_fallidas.append({
                        "factura": factura,
                        "emision": emision,
                        "error": "No se generó ticket de la póliza",
                        "error_details": error_details
                    })
                    continue
                
                # Emisión exitosa
                tracker.track_emission(factura, {
                    "tracking_id": payment_result["ticket_id"],
                    "num_asegurados": num_asegurados
                })
                emisiones_exitosas.append({
                    "factura": factura,
                    "emision": emision,
                    "ticket_id": payment_result["ticket_id"]
                })
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error procesando factura {factura}: {error_msg}")
                tracker.track_emission(factura, {
                    "error": error_msg,
                    "step": "desconocido",
                    "num_asegurados": len(emision["emision"]["insured"]),
                    "error_details": {
                        "validation_messages": [error_msg]
                    }
                })
                emisiones_fallidas.append({
                    "factura": factura,
                    "emision": emision,
                    "error": error_msg
                })
                
        # Guardar resultados si se especificaron rutas
        if output_success_path:
            with open(output_success_path, 'w', encoding='utf-8') as f:
                json.dump(emisiones_exitosas, f, ensure_ascii=False, indent=2)
                
        if output_errors_path:
            with open(output_errors_path, 'w', encoding='utf-8') as f:
                json.dump(emisiones_fallidas, f, ensure_ascii=False, indent=2)
                
        # Mostrar estadísticas
        stats = tracker.get_statistics()
        logger.info("\n📊 Estadísticas de la ejecución:")
        logger.info(f"Total procesadas: {stats['emisiones']['total']}")
        logger.info(f"Exitosas: {stats['emisiones']['exitosas']}")
        logger.info(f"Fallidas: {stats['emisiones']['fallidas']}")
        
        if stats['errores_por_tipo']:
            logger.info("\nErrores por tipo:")
            for step, count in stats['errores_por_tipo'].items():
                logger.info(f"- {step}: {count}")
                
        if stats['codigos_validacion']:
            logger.info("\nCódigos de validación:")
            for code, count in stats['codigos_validacion'].items():
                if code in VALIDACION_CODIGOS:
                    logger.info(f"- {code} ({VALIDACION_CODIGOS[code]}): {count}")
                else:
                    logger.info(f"- {code}: {count}")
        
        return emisiones_exitosas, emisiones_fallidas
        
    except Exception as e:
        logger.error(f"Error general en el proceso: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        exitosas, fallidas = procesar_validacion(
            delay_between_calls=1.0  # 1 segundo entre llamadas
        )
    except Exception as e:
        logger.error(f"Error ejecutando el procesamiento: {str(e)}") 