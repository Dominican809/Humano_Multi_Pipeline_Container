"""
Módulo de validaciones para la API Goval.
Proporciona funciones para validar elementos antes de crear una cotización.
Referencia: API Goval-Web v3.7
"""

import requests
import json
from datetime import datetime, timedelta
from loguru import logger
from emisor_goval.config import (
    API_BASE, AGENCY_ID, SALESMAN_ID, PRODUCT_ID,
    DESTINY_ID, FECHA_INICIO, FECHA_FIN
)
from emisor_goval.api.auth import TokenManager

def validate_dates(from_date, to_date, product_config):
    """
    Valida las fechas según la configuración del producto.
    
    Args:
        from_date (str): Fecha de inicio en formato YYYY-MM-DD
        to_date (str): Fecha de fin en formato YYYY-MM-DD
        product_config (dict): Configuración del producto
        
    Returns:
        tuple: (bool, list) - (es_válido, lista_de_errores)
    """
    errors = []
    try:
        start_date = datetime.strptime(from_date, "%Y-%m-%d")
        end_date = datetime.strptime(to_date, "%Y-%m-%d")
        
        # Verificar que la fecha de inicio sea futura
        if start_date <= datetime.now():
            errors.append("La fecha de inicio debe ser futura")
            
        # Verificar que la fecha de fin sea posterior a la de inicio
        if end_date <= start_date:
            errors.append("La fecha de fin debe ser posterior a la fecha de inicio")
            
        # Verificar duración mínima/máxima si está configurada
        duration = (end_date - start_date).days
        min_days = product_config.get("min_days")
        max_days = product_config.get("max_days")
        
        if min_days and duration < min_days:
            errors.append(f"La duración mínima es de {min_days} días")
        if max_days and duration > max_days:
            errors.append(f"La duración máxima es de {max_days} días")
            
    except ValueError as e:
        errors.append(f"Formato de fecha inválido: {str(e)}")
        
    return len(errors) == 0, errors

def validate_address(address):
    """
    Valida la estructura y contenido de una dirección.
    
    Args:
        address (dict): Diccionario con los datos de la dirección
        
    Returns:
        tuple: (bool, list) - (es_válido, lista_de_errores)
    """
    errors = []
    required_fields = {
        "line1": "Línea 1 de dirección",
        "city": "Ciudad",
        "state": "Estado/Provincia",
        "country_id": "ID del país",
        "phone": "Teléfono",
        "email": "Correo electrónico",
        "type": "Tipo de dirección"
    }
    
    # Verificar campos requeridos
    for field, description in required_fields.items():
        if field not in address or not address[field]:
            errors.append(f"Campo requerido: {description}")
            
    # Verificar que no se usen puntos como valores vacíos
    for key, value in address.items():
        if value == ".":
            errors.append(f"No usar '.' como valor vacío en {key}, usar ''")
            
    # Verificar tipo de dirección
    valid_types = ["HOME", "WORK", "OTHER"]
    if address.get("type") and address["type"] not in valid_types:
        errors.append(f"Tipo de dirección inválido. Valores permitidos: {', '.join(valid_types)}")
        
    return len(errors) == 0, errors

def check_all_elements(
    token=None, 
    agency_id=AGENCY_ID, 
    salesman_id=SALESMAN_ID, 
    product_id=PRODUCT_ID,
    destiny_id=DESTINY_ID,
    from_date=FECHA_INICIO,
    to_date=FECHA_FIN
):
    """
    Verifica todos los elementos necesarios para una cotización.
    
    Args:
        token (str, optional): Token JWT. Si no se proporciona, se obtiene uno nuevo.
        agency_id (int): ID de la agencia a verificar
        salesman_id (int): ID del vendedor a verificar
        product_id (int): ID del producto a verificar
        destiny_id (int): ID del destino a verificar
        from_date (str): Fecha de inicio (YYYY-MM-DD)
        to_date (str): Fecha de fin (YYYY-MM-DD)
        
    Returns:
        dict: Resultado de las validaciones con la siguiente estructura:
            {
                "valid": bool,  # True si todo es válido
                "errors": list, # Lista de errores encontrados
                "warnings": list, # Lista de advertencias
                "product_config": dict,  # Configuración del producto si es válido
                "required_fields": list  # Campos adicionales requeridos
            }
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "product_config": None,
        "required_fields": []
    }
    
    headers = {
        "Accept": "application/json",
        **TokenManager.get_auth_header()
    }

    # 1. Verificar agencia
    logger.info("🔍 Verificando agency_id...")
    response = requests.get(f"{API_BASE}/agency/{agency_id}", headers=headers)
    logger.debug(response.text)
    
    if response.status_code != 200:
        result["valid"] = False
        result["errors"].append(f"agency_id {agency_id} inválido o no encontrado")
        logger.error("❌ agency_id inválido o no encontrado.")
    else:
        agency_data = response.json()
        # Verificar status=1 como activo (según documentación API v3.7)
        if agency_data.get("status") != 1:
            result["valid"] = False
            result["errors"].append(f"agency_id {agency_id} está inactivo")
            logger.error("❌ Agencia inactiva.")
        else:
            logger.success("✅ agency_id válido y activo.")

    # 2. Verificar vendedor y su relación con la agencia
    logger.info("🔍 Verificando salesman_id...")
    response = requests.get(f"{API_BASE}/salesman/{salesman_id}", headers=headers)
    logger.debug(response.text)
    
    if response.status_code != 200:
        result["valid"] = False
        result["errors"].append(f"salesman_id {salesman_id} inválido o no encontrado")
        logger.error("❌ salesman_id inválido o no encontrado.")
    else:
        salesman_data = response.json()
        if not salesman_data.get("active", False):
            result["valid"] = False
            result["errors"].append(f"salesman_id {salesman_id} está inactivo")
            logger.error("❌ Vendedor inactivo.")
        else:
            # Verificar si el vendedor pertenece a la agencia
            if agency_id not in salesman_data.get("agencies", []):
                result["valid"] = False
                result["errors"].append(f"El vendedor {salesman_id} no pertenece a la agencia {agency_id}")
                logger.error("❌ Vendedor no asociado a la agencia.")
            else:
                logger.success("✅ salesman_id válido, activo y asociado a la agencia.")

    # 3. Verificar producto
    logger.info("🔍 Verificando product_id...")
    response = requests.get(f"{API_BASE}/product/{product_id}", headers=headers)
    logger.debug(response.text)
    
    if response.status_code != 200:
        result["valid"] = False
        result["errors"].append(f"product_id {product_id} inválido o no encontrado")
        logger.error("❌ product_id inválido o no encontrado.")
        return result

    product_data = response.json()
    result["product_config"] = product_data.get("config", {})

    # Verificar estado activo
    status = product_data.get("status")
    if status != 1:
        result["valid"] = False
        result["errors"].append(f"Producto {product_id} inactivo (status: {status})")
        logger.error(f"❌ Producto inactivo (status: {status})")
    else:
        logger.success("✅ Producto activo.")

    # 4. Verificar destino
    logger.info("🔍 Verificando destiny_id...")
    if "destination_validation" in result["product_config"]:
        # Verificar si el destino está en la lista de permitidos
        allowed_destinations = result["product_config"].get("allowed_destinations", [])
        if allowed_destinations and destiny_id not in allowed_destinations:
            result["valid"] = False
            result["errors"].append(f"Destino {destiny_id} no permitido para este producto")
            logger.error("❌ Destino no permitido.")
        else:
            logger.success("✅ Destino válido para el producto.")

    # 5. Verificar fechas
    logger.info("🔍 Verificando fechas...")
    dates_valid, date_errors = validate_dates(from_date, to_date, result["product_config"])
    if not dates_valid:
        result["valid"] = False
        result["errors"].extend(date_errors)
        logger.error("❌ Fechas inválidas:")
        for error in date_errors:
            logger.error(f"  - {error}")
    else:
        logger.success("✅ Fechas válidas.")

    # 6. Verificar campos requeridos según configuración
    config = product_data.get("config", {})
    if config:
        logger.info("⚙️ Verificando configuración del producto:")
        logger.info(json.dumps(config, indent=2))

        # Campos adicionales requeridos
        if config.get("require_currency"):
            result["required_fields"].append("currency_id")
        if config.get("require_payment_type"):
            result["required_fields"].append("payment_type")
        if config.get("require_payment_method"):
            result["required_fields"].append("payment_method")
            
        # Verificar métodos de pago permitidos
        payment_methods = config.get("payment_methods", [])
        if payment_methods:
            logger.info(f"💳 Métodos de pago permitidos: {', '.join(payment_methods)}")
            result["warnings"].append(f"Usar solo estos métodos de pago: {', '.join(payment_methods)}")

    # 7. Verificar validaciones especiales
    validations = product_data.get("validations", [])
    if validations:
        logger.warning("⚠️ El producto requiere validaciones especiales:")
        for validation in validations:
            logger.warning(f"  - {validation}")
            result["warnings"].append(f"Validación requerida: {validation}")
            
        # Agregar campos requeridos según validaciones
        if "covid19" in validations:
            result["required_fields"].extend(["covid_test", "covid_vaccine"])
        if "cancellation" in validations:
            result["required_fields"].append("cancellation_reason")

    logger.success("🎯 Verificaciones completadas.")
    
    # Agregar recordatorio sobre campos obligatorios
    if result["required_fields"]:
        logger.warning("⚠️ Campos adicionales requeridos:")
        for field in result["required_fields"]:
            logger.warning(f"  - {field}")
            
    return result

if __name__ == "__main__":
    logger.remove()
    logger.add(lambda msg: print(msg), level="DEBUG")
    logger.info("🚦 Verificación de datos para cotización GAPI...")
    
    # Ejemplo de uso
    token = TokenManager.get_token()
    result = check_all_elements(token)
    
    if result["valid"]:
        logger.success("✅ Todos los elementos son válidos!")
    else:
        logger.error("❌ Se encontraron errores:")
        for error in result["errors"]:
            logger.error(f"  - {error}")
            
    if result["warnings"]:
        logger.warning("⚠️ Advertencias:")
        for warning in result["warnings"]:
            logger.warning(f"  - {warning}")
            
    if result["required_fields"]:
        logger.info("📝 Campos adicionales requeridos:")
        for field in result["required_fields"]:
            logger.info(f"  - {field}") 