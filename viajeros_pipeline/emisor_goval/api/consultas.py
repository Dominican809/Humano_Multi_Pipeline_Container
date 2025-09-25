"""
Módulo de consultas para la API Goval.
Permite consultar información sobre agencias, productos y otros recursos.
Referencia: API Goval-Web v3.7
"""

import requests
import json
from loguru import logger
from emisor_goval.config import API_BASE
from emisor_goval.api.auth import TokenManager

def consultar_agencias():
    """
    Consulta la lista de agencias disponibles.
    
    Returns:
        list: Lista de diccionarios con información de las agencias
    """
    try:
        # Configurar request
        url = f"{API_BASE}/agency"
        headers = {
            "Accept": "application/json",
            **TokenManager.get_auth_header()
        }
        
        logger.info("Consultando agencias disponibles...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        
        # Realizar consulta
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Procesar resultado
        data = response.json()
        agencies = data.get("records", [])
        total = data.get("pagination", {}).get("total", 0)
            
        logger.success(f"✅ Se encontraron {total} agencias")
        logger.debug(f"Respuesta: {response.text}")
        
        return agencies
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al consultar agencias: {str(e)}")
        raise

def consultar_agencia_detalle(agency_id):
    """
    Consulta información detallada de una agencia específica incluyendo balance de crédito
    
    Args:
        agency_id (int): ID de la agencia a consultar
        
    Returns:
        dict: Diccionario con los detalles de la agencia
    """
    try:
        # Obtener token válido
        token = TokenManager.get_token()
        
        # Configurar request
        url = f"{API_BASE}/agency/{agency_id}"
        headers = {
            "Accept": "application/json",
            "x-goval-auth": f"jwt={token}"
        }
        
        logger.info(f"Consultando detalles de agencia {agency_id}...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        
        # Realizar consulta
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Procesar resultado
        details = response.json()
        logger.debug(f"Respuesta: {json.dumps(details)}")
        
        return details
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al consultar detalles de agencia: {str(e)}")
        raise

def consultar_productos():
    """
    Consulta la lista de productos disponibles.
    
    Returns:
        list: Lista de diccionarios con información de los productos
    """
    try:
        # Obtener token válido
        token = TokenManager.get_token()
        
        # Configurar request
        url = f"{API_BASE}/product"
        headers = {
            "Accept": "application/json",
            "x-goval-auth": f"jwt={token}"
        }
        
        logger.info("Consultando productos disponibles...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        
        # Realizar consulta
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Procesar resultado
        data = response.json()
        products = data.get("records", [])
        total = data.get("pagination", {}).get("total", 0)
            
        logger.success(f"✅ Se encontraron {total} productos")
        logger.debug(f"Respuesta: {response.text}")
        
        return products
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al consultar productos: {str(e)}")
        raise

def consultar_vendedores(agency_id):
    """
    Consulta la lista de vendedores (salesmen) para una agencia específica.

    Args:
        agency_id (int): ID de la agencia.

    Returns:
        list: Lista de vendedores con su ID y nombre.
    """
    try:
        # Obtener token válido
        token = TokenManager.get_token()
        
        # Configurar request
        url = f"{API_BASE}/salesman"
        headers = {
            "Accept": "application/json",
            "x-goval-auth": f"jwt={token}"
        }
        
        # Agregar parámetro de agencia
        params = {"agency_id": agency_id}
        
        logger.info(f"Consultando vendedores para agencia {agency_id}...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Params: {params}")
        
        # Realizar consulta
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Procesar resultado
        data = response.json()
        salesmen = data.get("records", [])
        total = data.get("pagination", {}).get("total", 0)
            
        logger.success(f"✅ Se encontraron {total} vendedores")
        logger.debug(f"Respuesta: {response.text}")
        
        return salesmen
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al consultar vendedores: {str(e)}")
        raise

def consultar_producto_detalle(product_id):
    """
    Consulta los detalles de un producto específico incluyendo sus validaciones
    """
    try:
        headers = {
            "Accept": "application/json",
            **TokenManager.get_auth_header()
        }
        
        logger.info(f"Consultando detalles del producto {product_id}...")
        logger.debug(f"URL: {API_BASE}/product/{product_id}")
        logger.debug(f"Headers: {headers}")
        
        # Primero obtener detalles básicos del producto
        response = requests.get(
            f"{API_BASE}/product/{product_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            details = response.json()
            logger.debug(f"Respuesta: {json.dumps(details)}")
            
            # Luego obtener validaciones específicas
            response = requests.get(
                f"{API_BASE}/product/{product_id}/validation",
                headers=headers
            )
            
            if response.status_code == 200:
                validations = response.json()
                logger.debug(f"Validaciones: {json.dumps(validations)}")
                details["validations"] = validations
                
            return details
        else:
            logger.error(f"❌ Error al consultar producto: {response.status_code}")
            logger.error(f"Detalle: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error de conexión: {str(e)}")
        return None

def mostrar_recursos_disponibles():
    """
    Muestra en consola la información de agencias y productos disponibles.
    """
    try:
        # Consultar agencias
        print("\n=== AGENCIAS DISPONIBLES ===")
        agencies = consultar_agencias()
        for agency in agencies:
            print(f"ID: {agency['id']} | Nombre: {agency['name']} | Código: {agency['internal_code']}")
            
            # Consultar vendedores para cada agencia
            print("\n  Vendedores de esta agencia:")
            vendedores = consultar_vendedores(agency['id'])
            for vendedor in vendedores:
                nombre_completo = f"{vendedor['firstname']} {vendedor['lastname']}".strip()
                print(f"  - ID: {vendedor['id']} | Nombre: {nombre_completo} | Código: {vendedor['internal_code']}")
            
        # Consultar productos
        print("\n=== PRODUCTOS DISPONIBLES ===")
        products = consultar_productos()
        for product in products:
            print(f"ID: {product['id']} | Nombre: {product['name']} | Código: {product['internal_code']}")
            
            # Consultar detalles del producto
            try:
                detalles = consultar_producto_detalle(product['id'])
                print(f"  Detalles:")
                print(f"  - Status: {detalles.get('status', 'N/A')}")
                print(f"  - Validaciones requeridas: {detalles.get('validations', [])}")
                print(f"  - Configuración: {detalles.get('config', {})}")
            except Exception as e:
                print(f"  ❌ No se pudieron obtener detalles: {str(e)}")
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

def mostrar_info_agencias_y_vendedores():
    """
    Muestra información detallada de todas las agencias y sus vendedores,
    incluyendo balance de crédito y datos de contacto.
    """
    try:
        agencias = consultar_agencias()
        for agencia in agencias:
            print(f"\n🧾 Agencia: {agencia['name']} (ID: {agencia['id']})")
            
            try:
                detalle = consultar_agencia_detalle(agencia["id"])
                print(f"  - Estado: {'Activa' if detalle.get('status') == 1 else 'Inactiva'}")
                print(f"  - Dirección: {detalle.get('address', 'N/A')}")
                print(f"  - Balance crédito: {detalle.get('credit_balance', 'N/D')}")
                print(f"  - Email contacto: {detalle.get('email', 'N/A')}")
                print(f"  - Teléfono: {detalle.get('phone', 'N/A')}")
            except Exception as e:
                logger.error(f"Error al obtener detalles de agencia {agencia['id']}: {str(e)}")
                continue

            try:
                vendedores = consultar_vendedores(agencia["id"])
                print("  - Vendedores asociados:")
                for vendedor in vendedores:
                    nombre = f"{vendedor.get('firstname', '')} {vendedor.get('lastname', '')}".strip()
                    print(f"    • {nombre} (ID: {vendedor['id']}) - Email: {vendedor.get('email', 'N/A')}")
            except Exception as e:
                logger.error(f"Error al obtener vendedores de agencia {agencia['id']}: {str(e)}")

    except Exception as e:
        logger.error(f"Error general: {str(e)}")

def consultar_agencia_data(agency_id=None):
    """
    Consulta información detallada de agencias incluyendo datos adicionales usando w=data{}.
    Si se proporciona agency_id, consulta una agencia específica.
    Si no se proporciona agency_id, consulta todas las agencias.
    
    Args:
        agency_id (int, optional): ID de la agencia a consultar. Por defecto None.
        
    Returns:
        dict: Diccionario con la información de la(s) agencia(s)
    """
    try:
        # Obtener token válido
        token = TokenManager.get_token()
        
        # Configurar request
        url = f"{API_BASE}/agency"
        params = {"w": "data{}"}
        
        # Si se proporciona ID, agregarlo a los parámetros
        if agency_id is not None:
            params["id"] = agency_id
            
        headers = {
            "Accept": "application/json",
            "x-goval-auth": f"jwt={token}"
        }
        
        logger.info(f"Consultando datos de agencia{'s' if agency_id is None else f' {agency_id}'}...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Params: {params}")
        
        # Realizar consulta
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Procesar resultado
        data = response.json()
        logger.debug(f"Respuesta: {json.dumps(data, indent=2)}")
        
        if agency_id is not None:
            logger.success(f"✅ Datos de agencia {agency_id} obtenidos exitosamente")
        else:
            total = data.get("pagination", {}).get("total", 0)
            logger.success(f"✅ Se encontraron datos de {total} agencias")
            
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al consultar datos de agencia: {str(e)}")
        raise

def consultar_linea_credito(agency_id):
    """
    Consulta la información de línea de crédito de una agencia específica.
    Incluye límite, balance y configuración.
    
    Args:
        agency_id (int): ID de la agencia
        
    Returns:
        dict: Diccionario con la información de la línea de crédito
    """
    try:
        # Configurar request
        url = f"{API_BASE}/agency"
        params = {
            "w": "data{}",
            "id": agency_id
        }
        
        headers = {
            "Accept": "application/json",
            **TokenManager.get_auth_header()
        }
        
        logger.info(f"Consultando línea de crédito para agencia {agency_id}...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Params: {params}")
        
        # Realizar consulta
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Procesar resultado
        data = response.json()
        logger.debug(f"Respuesta: {json.dumps(data, indent=2)}")
        
        if "records" in data and len(data["records"]) > 0:
            agency_data = data["records"][0]
            credit_info = {
                "agency_name": agency_data.get("name"),
                "agency_status": "Activa" if agency_data.get("status") == 1 else "Inactiva",
                "credit_limit": agency_data.get("data", {}).get("limit"),
                "invoice_auto": agency_data.get("data", {}).get("invoice_auto") == "1",
                "agency_type": agency_data.get("data", {}).get("agency_type"),
                "electronic": agency_data.get("data", {}).get("electronic") == "1"
            }
            logger.success(f"✅ Información de línea de crédito obtenida para agencia {agency_id}")
            return credit_info
        else:
            logger.error(f"❌ No se encontró la agencia {agency_id}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al consultar línea de crédito: {str(e)}")
        raise

def mostrar_linea_credito(agency_id):
    """
    Muestra en consola la información de línea de crédito de una agencia.
    """
    try:
        info = consultar_linea_credito(agency_id)
        if info:
            print(f"\n=== INFORMACIÓN DE LÍNEA DE CRÉDITO ===")
            print(f"🏢 Agencia: {info['agency_name']}")
            print(f"  - Estado: {info['agency_status']}")
            print(f"  - Límite de crédito: {info['credit_limit']}")
            print(f"  - Facturación automática: {'Sí' if info['invoice_auto'] else 'No'}")
            print(f"  - Tipo de agencia: {info['agency_type']}")
            print(f"  - Facturación electrónica: {'Sí' if info['electronic'] else 'No'}")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    print("\n=== INFORMACIÓN DETALLADA DE AGENCIAS Y VENDEDORES ===")
    mostrar_info_agencias_y_vendedores()
    
    print("\n=== RECURSOS DISPONIBLES ===")
    mostrar_recursos_disponibles()
    
    print("\n=== DATOS EXTENDIDOS DE AGENCIAS ===")
    try:
        # Consultar todas las agencias con datos extendidos
        print("\nConsultando todas las agencias con datos extendidos:")
        todas_agencias = consultar_agencia_data()
        for agencia in todas_agencias.get("records", []):
            print(f"\n🏢 Agencia: {agencia.get('name')} (ID: {agencia.get('id')})")
            print(f"  - Código interno: {agencia.get('internal_code', 'N/A')}")
            print(f"  - Datos adicionales: {json.dumps(agencia.get('data', {}), indent=2)}")
        
        # Consultar una agencia específica (ejemplo con ID 1)
        print("\nConsultando datos extendidos de agencia específica (ID: 1):")
        agencia_especifica = consultar_agencia_data(agency_id=1)
        if "records" in agencia_especifica:
            agencia = agencia_especifica["records"][0]
            print(f"\n🏢 Agencia: {agencia.get('name')} (ID: {agencia.get('id')})")
            print(f"  - Código interno: {agencia.get('internal_code', 'N/A')}")
            print(f"  - Datos adicionales: {json.dumps(agencia.get('data', {}), indent=2)}")
            
        # Mostrar información específica de línea de crédito
        print("\nConsultando información de línea de crédito para agencia ID 1:")
        mostrar_linea_credito(1)
            
    except Exception as e:
        print(f"\n❌ Error al consultar datos extendidos: {str(e)}") 