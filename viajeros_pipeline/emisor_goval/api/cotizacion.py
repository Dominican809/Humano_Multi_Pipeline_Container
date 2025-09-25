"""
Módulo de cotización para la API Goval.
Referencia: API Goval-Web v3.7
"""

import requests
import random
import time
import json
from loguru import logger
from emisor_goval.config import (
    API_BASE, COTIZACION_URL, AGENCY_ID, SALESMAN_ID,
    PRODUCT_ID, DESTINY_ID, FECHA_INICIO, FECHA_FIN,
    DISCOUNT
)
from emisor_goval.api.auth import TokenManager
from emisor_goval.api.consultas import (
    consultar_agencias, consultar_vendedores,
    consultar_productos, consultar_producto_detalle
)
from requests_toolbelt.multipart.encoder import MultipartEncoder
from typing import Dict, Tuple, Union, Optional

# Códigos de validación del manager (p.109)
VALIDACION_CODIGOS = {
    1: "Validación de asegurados con coberturas activas",
    2: "Cálculo de tarifas",
    4: "Validación de productos de cancelación",
    8: "Validación de productos 'Niños gratis'",
    64: "Formulario de cabecera de factura",
    256: "Validación de productos 'Covid-19'"
}

def validar_datos_persona(persona):
    """
    Valida que los datos de la persona cumplan con los requisitos de la API.
    
    Args:
        persona (dict): Datos del asegurado
        
    Raises:
        ValueError: Si algún campo requerido falta o es inválido
    """
    # Validar campos requeridos
    campos_requeridos = {
        "nombre": (str, 30, "Nombres del asegurado"),
        "apellido": (str, 30, "Apellidos del asegurado"),
        "fecha_nacimiento": (str, None, "Fecha de nacimiento (yyyy-mm-dd)"),
        "sexo": (str, 1, "Género (M/F)"),
        "direccion": (str, 60, "Dirección"),
        "ciudad": (str, 50, "Ciudad"),
        "provincia": (str, 50, "Estado/Provincia"),
        "pais_id": (int, None, "Código ISO-3361 del país"),
        "telefono": (str, 100, "Teléfono"),
        "email": (str, 100, "Correo electrónico")
    }
    
    for campo, (tipo, max_len, desc) in campos_requeridos.items():
        if campo not in persona:
            raise ValueError(f"Campo requerido faltante: {desc}")
            
        valor = persona[campo]
        if not isinstance(valor, tipo):
            raise ValueError(f"Tipo inválido para {desc}: debe ser {tipo.__name__}")
            
        if max_len and isinstance(valor, str) and len(valor) > max_len:
            raise ValueError(f"{desc} excede el máximo de {max_len} caracteres")
    
    # Validar que al menos uno de cedula o pasaporte esté presente
    if not persona.get("cedula") and not persona.get("pasaporte"):
        raise ValueError("Se requiere al menos uno: cédula o pasaporte")
        
    # Validar formato de fecha
    try:
        from datetime import datetime
        datetime.strptime(persona["fecha_nacimiento"], "%Y-%m-%d")
    except ValueError:
        raise ValueError("Formato de fecha inválido. Use yyyy-mm-dd")
        
    # Validar sexo
    if persona["sexo"] not in ["M", "F"]:
        raise ValueError("Género debe ser 'M' o 'F'")

def construir_payload_cotizacion_emision(emision):
    """
    Construye el payload para la cotización según la documentación de la API.
    Los campos deben seguir exactamente la estructura documentada.
    """
    # Extraer campos requeridos del diccionario de emisión
    payload = {
        "agency_id": int(emision.get("agency_id")),  # Asegurar que sea entero
        "salesman_id": int(emision.get("salesman_id")),  # Asegurar que sea entero
        "channel_id": int(emision.get("channel_id", 1)),  # Default a 1 (web)
        "discount": float(emision.get("discount", 0.00)),  # Asegurar que sea float
        "destiny_id": int(emision.get("destiny_id")),  # Asegurar que sea entero
        "destination_id": int(emision.get("destiny_id")),  # Mismo valor que destiny_id
        "from": emision.get("from"),  # Fecha en formato YYYY-MM-DD
        "to": emision.get("to"),      # Fecha en formato YYYY-MM-DD
        "terms": "",  # Siempre vacío según documentación
        "products": [],
        "insured": [],
        "addresses": []
    }

    # Procesar productos según documentación
    if emision.get("products"):
        for producto in emision["products"]:
            payload["products"].append({
                "id": int(producto.get("id"))  # Asegurar que sea entero
            })
    else:
        raise ValueError("Se requiere al menos un producto")

    # Procesar asegurados según documentación
    if emision.get("insured"):  # Cambiado de "personas" a "insured"
        for persona in emision["insured"]:
            asegurado = {
                "identity": str(persona.get("identity", "")),  # Cambiado de "cedula" a "identity"
                "passport": str(persona.get("passport", "")),  # Cambiado de "pasaporte" a "passport"
                "firstname": str(persona.get("firstname", "")).upper(),  # Cambiado de "nombre" a "firstname"
                "lastname": str(persona.get("lastname", "")).upper(),  # Cambiado de "apellido" a "lastname"
                "birthdate": str(persona.get("birthdate", "")),  # Cambiado de "fecha_nacimiento" a "birthdate"
                "gender": str(persona.get("sex", "")).upper()  # Cambiado de "sex" a "gender" pero manteniendo "sex" en el input
            }
            # Validar que al menos tenga cédula o pasaporte
            if not asegurado["identity"] and not asegurado["passport"]:
                raise ValueError("Cada asegurado debe tener al menos cédula o pasaporte")
            payload["insured"].append(asegurado)
    else:
        raise ValueError("Se requiere al menos un asegurado")

    # Procesar dirección principal según documentación
    if emision.get("addresses"):  # Cambiado para usar "addresses" directamente
        direccion = emision["addresses"][0]  # Tomar la primera dirección
        direccion_principal = {
            "line1": str(direccion.get("line1", ".")),
            "line2": str(direccion.get("line2", "")),
            "city": str(direccion.get("city", ".")),
            "state": str(direccion.get("state", ".")),
            "country_id": int(direccion.get("country_id", 214)),  # Default a República Dominicana
            "zip": str(direccion.get("zip", "00000")),
            "phone": direccion.get("phone", ["."]),  # Ya es una lista en el JSON
            "email": direccion.get("email", ["."]),  # Ya es una lista en el JSON
            "kind": str(direccion.get("kind", "Por defecto"))
        }
        payload["addresses"].append(direccion_principal)
    
    # Validar que al menos haya una dirección
    if not payload["addresses"]:
        raise ValueError("Se requiere al menos una dirección")

    return payload

def robust_post(url, max_retries=3, base_delay=0.5, **kwargs):
    """
    Makes a POST request with automatic token refresh and exponential backoff.
    Retries on token expiration, network errors, 429, and 503.
    Args:
        url (str): The URL to POST to.
        max_retries (int): Maximum number of attempts (default 3).
        base_delay (float): Base delay in seconds for exponential backoff (default 0.5).
        **kwargs: Passed to requests.post.
    Raises:
        RuntimeError: If all attempts fail.
    """
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries}")
            logger.debug(f"Headers: {kwargs.get('headers', {})}")
            resp = requests.post(url, **kwargs)
            logger.debug(f"Response status: {resp.status_code}")
            if resp.status_code in [401, 403] and 'token' in resp.text.lower():
                if attempt == 0:
                    logger.warning("Token expirado o inválido, renovando y reintentando...")
                    token = TokenManager.get_token(force_refresh=True)
                    kwargs['headers']['Authorization'] = f"Bearer {token}"
                    continue
            if resp.status_code in [429, 503]:
                logger.warning(f"API rate limit or service unavailable (status {resp.status_code}). Backing off and retrying...")
                time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 0.5))
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network/API error: {e}. Retrying ({attempt+1}/{max_retries})...")
            time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 0.5))
    raise RuntimeError(f"Failed to POST to {url} after {max_retries} attempts.")

def consultar_manager(cotizacion_id, token):
    """
    Consulta el estado de la validación con el manager.
    
    Args:
        cotizacion_id (int): ID de la cotización
        token (str): Token JWT de autenticación
        
    Returns:
        dict: Respuesta del manager con el estado de la validación
    """
    url = f"{API_BASE}/api/issue/retail/{cotizacion_id}/manager"
    headers = TokenManager.get_auth_header()
    
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al consultar manager: {str(e)}")
        raise

def enviar_datos_validacion(cotizacion_id, uri, datos, token=None):
    """
    Envía datos adicionales requeridos por el manager.
    
    Args:
        cotizacion_id (int): ID de la cotización
        uri (str): URI proporcionada por el manager
        datos (dict): Datos a enviar
        token (str): Token JWT de autenticación
        
    Returns:
        dict: Respuesta del manager
    """
    if token is None:
        token = TokenManager.get_token()
    headers = TokenManager.get_auth_header()
    
    try:
        resp = robust_post(uri, json=datos, headers=headers)
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al enviar datos de validación: {str(e)}")
        raise

def cotizar_emision(emision: Dict) -> Tuple[Optional[int], Optional[str], Optional[requests.Response]]:
    """
    Crea una cotización en la API.
    
    Args:
        emision (Dict): Datos de la emisión
        
    Returns:
        Tuple[Optional[int], Optional[str], Optional[requests.Response]]: 
            - ID de la cotización (o None si falla)
            - URI del manager (o None si falla)
            - Respuesta original de la API (para extraer detalles del error)
    """
    try:
        response = requests.post(
            f"{API_BASE}/issue/retail/new",
            json=emision,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                **TokenManager.get_auth_header()
            }
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            return data["id"], data.get("manager_uri", ""), response
        else:
            return None, None, response
            
    except Exception as e:
        logger.error(f"Error al crear cotización: {str(e)}")
        return None, None, None

def process_manager_validation(quotation_id: int, token: str) -> Tuple[bool, str, str, Optional[requests.Response]]:
    """
    Procesa las validaciones del manager para una cotización.
    
    Args:
        quotation_id (int): ID de la cotización
        token (str): Token de autenticación
        
    Returns:
        Tuple[bool, str, str, Optional[requests.Response]]: 
            - éxito
            - mensaje de error
            - URI final
            - Respuesta original de la API (para extraer detalles del error)
    """
    try:
        response = requests.get(
            f"{API_BASE}/issue/retail/{quotation_id}/manager",
            headers={
                "Accept": "application/json",
                **TokenManager.get_auth_header()
            }
        )
        
        if response.status_code in [200, 202]:  # Added 202 as success
            data = response.json()
            # For 202, we might need to wait and retry, but for now just accept it
            return True, "", data.get("uri", ""), response
        else:
            error_msg = f"Error en validación: {response.status_code}"
            return False, error_msg, "", response
            
    except Exception as e:
        logger.error(f"Error en validación: {str(e)}")
        return False, str(e), "", None

def avanzar_manager(uri: str, token: str) -> Tuple[bool, str, str, Optional[requests.Response]]:
    """
    Maneja el flujo de validaciones del manager hasta que todas estén completas.
    
    Args:
        uri (str): URI del manager proporcionada en la cotización
        token (str): JWT token válido
        
    Returns:
        Tuple[bool, str, str, Optional[requests.Response]]:
            - éxito
            - mensaje de error
            - URI final
            - Respuesta original de la API
    """
    headers = {
        "Accept": "application/json",
        **TokenManager.get_auth_header()
    }
    
    last_response = None
    
    try:
        while True:
            logger.info(f"Consultando manager: {uri}")
            response = requests.get(uri, headers=headers)
            last_response = response
            response.raise_for_status()
            data = response.json()
            
            # Si no hay código, el proceso está completo
            if "code" not in data:
                logger.success("✅ Validaciones completadas")
                return True, "", data.get("uri", ""), response
                
            code = data.get("code")
            message = data.get("message", "")
            next_uri = data.get("uri")
            
            logger.warning(f"⚠️ Validación pendiente (código {code}): {message}")
            
            # Manejar cada tipo de validación según el código
            if code == 1:  # Validación de asegurados
                payload = {"accept": True}
            elif code == 2:  # Cálculo de tarifas
                payload = {"accept": True}
            elif code == 4:  # Productos de cancelación
                payload = {
                    "accept": True,
                    "cancellation": {"accept": True}
                }
            elif code == 8:  # Niños gratis
                payload = {"accept": True}
            elif code == 64:  # Cabecera de factura
                payload = {
                    "invoice": {
                        "type": "F",
                        "name": "JUAN PEREZ",
                        "document": "00116454378",
                        "address": "CALLE PRINCIPAL 123"
                    }
                }
            elif code == 256:  # Covid-19
                payload = {
                    "accept": True,
                    "covid_test": True,
                    "covid_vaccine": True
                }
            else:
                payload = {"accept": True}
                
            # Enviar datos de validación
            if next_uri:
                logger.info(f"Enviando datos a {next_uri}")
                response = requests.post(
                    next_uri,
                    headers={"Content-Type": "application/json", **headers},
                    json=payload
                )
                last_response = response
                
                if response.status_code != 200:
                    error_msg = f"Error en validación {code}: {response.status_code}"
                    return False, error_msg, "", response
                    
                response.raise_for_status()
            else:
                error_msg = f"URI no proporcionada para código {code}"
                return False, error_msg, "", last_response
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en la comunicación con el manager: {str(e)}")
        return False, str(e), "", last_response
    except Exception as e:
        logger.error(f"Error inesperado en el manager: {str(e)}")
        return False, str(e), "", last_response

def simular_pago(cotizacion_id, token):
    """
    Realiza el pago de la póliza usando la línea de crédito.
    
    Args:
        cotizacion_id: ID de la cotización
        token: JWT token válido
        
    Returns:
        dict: Datos de la póliza emitida
    """
    url = f"{API_BASE}/issue/retail/apply/{cotizacion_id}/credit"
    headers = {
        "Accept": "application/json",
        **TokenManager.get_auth_header()
    }
    
    logger.info("Procesando pago...")
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    logger.success(f"🎉 Póliza emitida exitosamente (ID: {data.get('id')})")
    return data 

def process_emissions_from_file(json_path, token):
    """
    Procesa múltiples emisiones desde un archivo JSON.
    
    Args:
        json_path (str): Ruta al archivo JSON con las emisiones
        token (str): Token JWT válido
        
    Returns:
        dict: Resumen del procesamiento con la siguiente estructura:
        {
            "total": int,  # Total de emisiones procesadas
            "success": int,  # Emisiones exitosas
            "failed": int,  # Emisiones fallidas
            "results": {
                "factura_id": {
                    "status": str,  # "success" o "error"
                    "message": str,  # Mensaje de éxito o error
                    "policy_id": str,  # ID de la póliza si fue exitosa
                    "error_details": str  # Detalles del error si falló
                }
            }
        }
    """
    try:
        # Cargar emisiones del archivo JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            emisiones = json.load(f)
            
        results = {
            "total": len(emisiones),
            "success": 0,
            "failed": 0,
            "results": {}
        }
        
        logger.info(f"🔄 Procesando {len(emisiones)} emisiones...")
        
        for factura, data in emisiones.items():
            logger.info(f"\n📄 Procesando factura: {factura}")
            try:
                # Extraer datos de emisión
                emision = data["emision"]
                
                # Crear cotización
                logger.info("✨ Creando cotización...")
                quotation_result = create_quotation(token, emision)
                
                if not quotation_result or "id" not in quotation_result:
                    raise ValueError("No se pudo crear la cotización")
                    
                quotation_id = quotation_result["id"]
                logger.info(f"🔗 ID de cotización obtenida: {quotation_id}")
                
                # Procesar validaciones del manager
                logger.info("🔄 Iniciando proceso de validación con el manager...")
                manager_success, manager_error, final_manager_uri, manager_response = process_manager_validation(quotation_id, token)
                
                if not manager_success:
                    raise ValueError(f"Fallo en validación del manager: {manager_error}")
                
                # Aplicar pago
                logger.info("💳 Aplicando pago...")
                from emisor_goval.api.pago import apply_payment
                policy_result = apply_payment(quotation_id, token, final_manager_uri)
                
                if not policy_result:
                    raise ValueError("El pago no se pudo aplicar")
                
                # Registrar éxito
                results["success"] += 1
                results["results"][factura] = {
                    "status": "success",
                    "message": "Póliza emitida correctamente",
                    "policy_id": policy_result.get("id", "unknown"),
                    "error_details": None
                }
                
                logger.success(f"✅ Emisión completada para factura {factura}")
                
            except Exception as e:
                # Registrar error
                results["failed"] += 1
                results["results"][factura] = {
                    "status": "error",
                    "message": "Error en el proceso de emisión",
                    "policy_id": None,
                    "error_details": str(e)
                }
                logger.error(f"❌ Error procesando factura {factura}: {str(e)}")
                
            # Esperar un poco entre emisiones para no sobrecargar la API
            time.sleep(1)
        
        # Guardar resultados
        output_path = json_path.replace('.json', '_results.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info("\n📊 Resumen del procesamiento:")
        logger.info(f"Total procesadas: {results['total']}")
        logger.info(f"Exitosas: {results['success']}")
        logger.info(f"Fallidas: {results['failed']}")
        logger.info(f"Resultados guardados en: {output_path}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error procesando archivo de emisiones: {str(e)}")
        raise

def create_quotation(token, validation_result=None):
    """
    Crea una cotización usando los datos validados según API v3.7
    
    Args:
        token (str): Token JWT válido
        validation_result (dict, optional): Resultado de validaciones previas
        
    Returns:
        dict|None: Datos de la cotización si es exitosa, None si hay error
    """
    headers = {
        "Content-Type": "application/json",
        "x-goval-auth": f"jwt={token}"
    }
    
    payload = {
        "agency_id": AGENCY_ID,
        "discount": DISCOUNT,
        "salesman_id": SALESMAN_ID,
        "products": [{"id": PRODUCT_ID}],
        "destiny_id": DESTINY_ID,
        "destination_id": DESTINY_ID,
        "from": FECHA_INICIO,
        "to": FECHA_FIN,
        "terms": "",
        "insured": [
            {
                "identity": "",
                "passport": "RD6062517",
                "firstname": "JUAN",
                "lastname": "PEREZ",
                "birthdate": "1990-01-01",
                "gender": "M"
            }
        ],
        "addresses": [
            {
                "line1": "CALLE PRINCIPAL 123",
                "line2": "",
                "city": "SANTO DOMINGO",
                "state": "DISTRITO NACIONAL",
                "country_id": 214,
                "zip": "00000",
                "phone": ["8091234567"],
                "email": ["juan.perez@example.com"],
                "kind": "Por defecto"
            }
        ]
    }
    
    logger.info("📤 Enviando solicitud de cotización...")
    logger.info("\nRequest JSON:")
    logger.info("```json")
    logger.info(json.dumps(payload, indent=2))
    logger.info("```\n")
    
    try:
        response = requests.post(f"{API_BASE}/issue/retail/new", headers=headers, json=payload)
        logger.info(f"Response status: {response.status_code}")
        logger.info("\nResponse JSON:")
        logger.info("```json")
        try:
            logger.info(json.dumps(response.json(), indent=2))
        except:
            logger.info(response.text)
        logger.info("```\n")
        
        if response.status_code in [200, 201]:
            logger.success("✅ Cotización creada exitosamente!")
            return response.json()
        else:
            logger.error(f"❌ Error al crear cotización: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error de conexión: {str(e)}")
        return None 