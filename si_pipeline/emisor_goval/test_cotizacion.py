"""
Script para probar la validación y creación de cotización usando el módulo de consultas
"""

import json
import requests
import time
from loguru import logger
from emisor_goval.api.consultas import (
    consultar_agencias, consultar_vendedores,
    consultar_productos, consultar_producto_detalle
)
from emisor_goval.api.auth import TokenManager
from emisor_goval.config import (
    API_BASE, AGENCY_ID, SALESMAN_ID, PRODUCT_ID,
    DESTINY_ID, FECHA_INICIO, FECHA_FIN
)

# Códigos de validación del manager
VALIDACION_CODIGOS = {
    1: "Validación de asegurados con coberturas activas",
    2: "Cálculo de tarifas",
    4: "Validación de productos de cancelación",
    8: "Validación de productos 'Niños gratis'",
    64: "Formulario de cabecera de factura",
    256: "Validación de productos 'Covid-19'"
}

def validate_resources(token):
    result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }

    try:
        logger.info("🔍 Validando agencia...")
        agencies = consultar_agencias()
        agency_found = any(a["id"] == AGENCY_ID for a in agencies)
        if not agency_found:
            result["valid"] = False
            result["errors"].append(f"No se encontró la agencia {AGENCY_ID}")
        else:
            agency = next(a for a in agencies if a["id"] == AGENCY_ID)
            if agency.get("status") != 1:
                result["valid"] = False
                result["errors"].append(f"La agencia {AGENCY_ID} está inactiva")

        if agency_found:
            logger.info("🔍 Validando vendedor...")
            salesmen = consultar_vendedores(AGENCY_ID)
            salesman_found = any(s["id"] == SALESMAN_ID for s in salesmen)
            if not salesman_found:
                result["valid"] = False
                result["errors"].append(f"No se encontró el vendedor {SALESMAN_ID}")
            else:
                salesman = next(s for s in salesmen if s["id"] == SALESMAN_ID)
                if salesman.get("status") != 1:
                    result["valid"] = False
                    result["errors"].append(f"El vendedor {SALESMAN_ID} está inactivo")

        logger.info("🔍 Validando producto...")
        products = consultar_productos()
        product_found = any(p["id"] == PRODUCT_ID for p in products)
        if not product_found:
            result["valid"] = False
            result["errors"].append(f"No se encontró el producto {PRODUCT_ID}")
        else:
            product = next(p for p in products if p["id"] == PRODUCT_ID)
            if product.get("status") != 1:
                result["valid"] = False
                result["errors"].append(f"El producto {PRODUCT_ID} está inactivo")
            details = consultar_producto_detalle(PRODUCT_ID)
            allowed_destinations = details.get("validations", {}).get("destinations", [])
            if allowed_destinations and DESTINY_ID not in allowed_destinations:
                result["valid"] = False
                result["errors"].append(f"El destino {DESTINY_ID} no está permitido para el producto {PRODUCT_ID}")
                logger.info(f"ℹ️ Destinos permitidos: {allowed_destinations}")
            if details.get("requires_covid_test"):
                result["warnings"].append("Este producto requiere prueba COVID")
            if details.get("requires_covid_vaccine"):
                result["warnings"].append("Este producto requiere vacuna COVID")

        return result

    except Exception as e:
        logger.error(f"Error durante la validación: {str(e)}")
        result["valid"] = False
        result["errors"].append(str(e))
        return result

def create_quotation(token, validation_result):
    headers = {
        "Content-Type": "application/json",
        "x-goval-auth": f"jwt={token}"
    }

    payload = {
        "agency_id": AGENCY_ID,
        "discount": 0.00,
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
                "sex": "M"
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
                "email": ["juan.persaez@example.com"],
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

def apply_payment(quotation_id, token, manager_uri=None):
    """
    Aplica el pago a una cotización usando la línea de crédito del productor.
    El proceso de emisión concluye con el pago de la póliza.
    
    Args:
        quotation_id (int): ID de la cotización
        token (str): Token de autenticación
        manager_uri (str): URI proporcionada por el manager para el proceso de pago
    """
    logger.info(f"💳 Aplicando pago para cotización ID {quotation_id}...")
    
    # Construct URL exactly as in curl
    payment_uri = f"{API_BASE}/issue/retail/apply/{quotation_id}/credit"
    
    # Headers exactly as in curl
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-goval-auth": f"jwt={token}"
    }
    
    try:
        logger.info(f"\nSending payment request to: {payment_uri}")
        logger.info("\nRequest Headers:")
        logger.info("```json")
        logger.info(json.dumps(headers, indent=2))
        logger.info("```\n")
        
        # Using requests.request to match curl's --request POST
        response = requests.request(
            method="POST",
            url=payment_uri,
            headers=headers,
            allow_redirects=True  # Equivalent to curl's --location
        )
        
        logger.info(f"Response status: {response.status_code}")
        logger.info("\nResponse JSON:")
        logger.info("```json")
        try:
            response_data = response.json()
            logger.info(json.dumps(response_data, indent=2))
        except:
            logger.info(response.text)
            response_data = {}
        logger.info("```\n")
        
        # First check if we got a certificate ID and URI, regardless of status code
        if isinstance(response_data, dict):
            if "id" in response_data and "uri" in response_data:
                logger.success("✅ Póliza emitida correctamente!")
                logger.info(f"📄 Número de certificado: {response_data['id']}")
                logger.info(f"🔗 URI del certificado: {response_data['uri']}")
                return response_data
            
            # Check if the error indicates the certificate was already created
            if response_data.get("error") and "ya fue aplicada al certificado" in str(response_data.get("message", "")):
                cert_id = str(response_data.get("message")).split("certificado ")[-1]
                logger.success(f"✅ La póliza ya fue emitida con el certificado: {cert_id}")
                return {"id": cert_id, "message": "Certificate already exists"}

        # If we get here, check normal success status codes
        if response.status_code in [200, 201, 202]:
                logger.success("✅ Pago aplicado correctamente!")
                return True
            
        if response.status_code == 401:
            logger.error("❌ Error de autenticación al aplicar pago")
            return False
            
        # Handle other error cases
        if isinstance(response_data, dict):
            error_msg = response_data.get("message", "Error desconocido")
            if isinstance(error_msg, dict):
                for field, msgs in error_msg.items():
                    if isinstance(msgs, list):
                        for msg in msgs:
                            logger.error(f"❌ Error en {field}: {msg}")
                    else:
                        logger.error(f"❌ Error en {field}: {msgs}")
            else:
                logger.error(f"❌ Error al aplicar pago: {error_msg}")
        else:
            logger.error(f"❌ Error al aplicar pago. Status code: {response.status_code}")
        return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error de conexión al aplicar pago: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado al aplicar pago: {str(e)}")
        return False

def process_manager_validation(quotation_id):
    """
    Procesa todas las validaciones requeridas por el manager.
    Códigos de validación:
    1: Validación de asegurados con coberturas activas
    2: Cálculo de tarifas
    4: Validación de productos de cancelación
    8: Validación de productos "Niños gratis"
    64: Formulario de cabecera de factura
    256: Validación de productos "Covid-19"
    
    Retorna:
        - (True, None, uri) si todo está OK
        - (False, error_message, None) si hay error
    """
    url = f"{API_BASE}/issue/retail/{quotation_id}/manager"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **TokenManager.get_auth_header()
    }

    max_retries = 3
    retry_count = 0
    last_uri = None

    while retry_count < max_retries:
        logger.info("🔄 Inicializando manager...")
        try:
            response = requests.get(url, headers=headers)
            logger.info(f"Manager validation request to: {url}")
            logger.info(f"Response status: {response.status_code}")
            logger.info("Response JSON:")
            logger.info("```json")
            try:
                logger.info(json.dumps(response.json(), indent=2))
            except:
                logger.info(response.text)
            logger.info("```")
            
            # Si hay error 500, mostrar el mensaje y reintentar
            if response.status_code == 500:
                error_data = response.json()
                error_msg = error_data.get("message", ["Error desconocido"])[0]
                logger.warning(f"⚠️ Error del manager: {error_msg}")
                
                # Si el error indica que no hay tarifas disponibles, retornar inmediatamente
                if "No existen tarifas disponibles" in error_msg:
                    return False, error_msg, None
                
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Reintentando validación ({retry_count}/{max_retries})...")
                    time.sleep(2)
                continue

            response.raise_for_status()
            data = response.json()

            # Guardar la última URI proporcionada por el manager
            if "uri" in data:
                last_uri = data["uri"]
                logger.info(f"🔗 URI del manager actualizada: {last_uri}")

            # Si no hay código, la validación está completa
            if "code" not in data:
                logger.success("✅ Validaciones del manager completadas")
                return True, None, last_uri

            code = data.get("code")
            message = data.get("message", "")
            next_uri = data.get("uri")

            logger.warning(f"⚠️ Validación pendiente (código {code}): {message}")
            logger.info(f"Tipo de validación: {VALIDACION_CODIGOS.get(code, 'Desconocido')}")

            if not next_uri:
                return False, f"URI no proporcionada para código {code}", None

            # Preparar payload según el tipo de validación
            payload = {}
            
            if code == 1:  # Validación de asegurados con coberturas activas
                logger.info("📋 Procesando validación de asegurados...")
                payload = {"accept": True}
                
            elif code == 2:  # Cálculo de tarifas
                logger.info("💰 Procesando cálculo de tarifas...")
                payload = {"accept": True}
                
            elif code == 4:  # Productos de cancelación
                logger.info("🔄 Procesando validación de producto de cancelación...")
                payload = {
                    "accept": True,
                    "cancellation": {
                        "accept": True
                    }
                }
                
            elif code == 8:  # Niños gratis
                logger.info("👶 Procesando validación de niños gratis...")
                payload = {"accept": True}
                
            elif code == 64:  # Cabecera de factura
                logger.info("📄 Procesando datos de factura...")
                payload = {
                    "invoice": {
                        "type": "F",
                        "name": "JUAN PEREZ",
                        "document": "00116454378",
                        "address": "CALLE PRINCIPAL 123"
                    }
                }
                
            elif code == 256:  # Covid-19
                logger.info("🦠 Procesando validación de Covid-19...")
                payload = {
                    "accept": True,
                    "covid_test": True,
                    "covid_vaccine": True
                }

            # Enviar respuesta al manager
            logger.info(f"\nSending validation response to: {next_uri}")
            logger.info("\nRequest JSON:")
            logger.info("```json")
            logger.info(json.dumps(payload, indent=2))
            logger.info("```\n")
            
            response = requests.post(
                next_uri,
                headers=headers,
                json=payload
            )
            logger.info(f"Response status: {response.status_code}")
            logger.info("\nResponse JSON:")
            logger.info("```json")
            try:
                logger.info(json.dumps(response.json(), indent=2))
            except:
                logger.info(response.text)
            logger.info("```\n")
            
            if response.status_code == 500:
                error_data = response.json()
                error_msg = error_data.get("message", ["Error desconocido"])[0]
                return False, error_msg, None
                
            response.raise_for_status()
            
            # Reset URL for next iteration
            url = f"{API_BASE}/issue/retail/{quotation_id}/manager"

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error en la comunicación con el manager: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Reintentando validación ({retry_count}/{max_retries})...")
                time.sleep(2)
            else:
                return False, str(e), None
        except Exception as e:
            logger.error(f"❌ Error inesperado en el manager: {str(e)}")
            return False, str(e), None

    logger.error("❌ Se agotaron los reintentos de validación")
    return False, "Se agotaron los reintentos de validación", None

def main():
    logger.info("🚀 Iniciando prueba de cotización...")
    token = TokenManager.get_token()
    if not token:
        logger.error("❌ No se pudo obtener el token")
        return

    logger.info("🔍 Ejecutando validaciones...")
    validation_result = validate_resources(token)

    if not validation_result["valid"]:
        logger.error("❌ La validación falló:")
        for error in validation_result["errors"]:
            logger.error(f"  - {error}")
        return

    if validation_result["warnings"]:
        logger.warning("⚠️ Advertencias encontradas:")
        for warning in validation_result["warnings"]:
            logger.warning(f"  - {warning}")

    logger.info("✨ Validación exitosa, creando cotización...")
    quotation_result = create_quotation(token, validation_result)

    if quotation_result and "id" in quotation_result:
        quotation_id = quotation_result["id"]
        logger.info(f"🔗 ID de cotización obtenida: {quotation_id}")
        
        # Procesar validaciones del manager
        logger.info("🔄 Iniciando proceso de validación con el manager...")
        manager_success, manager_error, manager_uri = process_manager_validation(quotation_id)
        
        if manager_success:
            # Obtener la URI del manager para el pago
            logger.info("➡️ Procediendo a aplicar pago...")
            policy_result = apply_payment(quotation_id, token, manager_uri)
            if policy_result:
                logger.info("📄 Detalles de la póliza emitida:")
                logger.info(json.dumps(policy_result, indent=2))
            else:
                logger.error("❌ El pago no se aplicó correctamente, no se emitió la póliza.")
        else:
            logger.error(f"❌ Las validaciones del manager fallaron: {manager_error}")
    else:
        logger.error("❌ No se obtuvo ID de cotización, no se puede continuar con el pago.")

if __name__ == "__main__":
    logger.remove()
    logger.add(lambda msg: print(msg), level="DEBUG")
    main()
