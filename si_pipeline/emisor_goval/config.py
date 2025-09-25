"""
Configuración del emisor de pólizas Goval.
Referencia: API Goval-Web v3.7-1.pdf
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# URLs de la API
#API_BASE = "https://qa-humano.goval-tpa.com/api"  # Cambiar a .govalseguros.com en producción
# Credenciales PRUEBA
#USUARIO = "gapi-user_es"
#PASSWORD = "KhQH^M*wQw07Ybsg"


API_BASE="https://humano.goval-tpa.com/api"
# Credenciales Produccion
USUARIO = "es-humano_usr"
PASSWORD = "R41*Ri4GVgzGuBKdMGjy"




# IDs de configuración
AGENCY_ID = 1     # ID de la agencia
SALESMAN_ID = 10   # ID del vendedor
PRODUCT_ID = 1      # ID del producto de seguro
DESTINY_ID = 840       # ID del destino (ej: 840 = USA)



# Descuento (decimal 5,2)
DISCOUNT = 0.00    # Porcentaje de descuento a aplicar

# Fechas de vigencia
FECHA_INICIO = "2025-11-11" #yyyy-mm-dd
FECHA_FIN = "2025-11-15" #yyyy-mm-dd

# URLs de endpoints (según documentación p.104)
LOGIN_URL = f"{API_BASE}/auth/token/jwt?acl=1"                    # p.13-14 (actualizado)
COTIZACION_URL = f"{API_BASE}/issue/retail/new"            # p.112-113
PAGO_URL = f"{API_BASE}/issue/retail/apply/{{id}}/credit"  # p.122

# Configuración de logs
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configuración de datos
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
ASEGURADOS_FILE = os.path.join(DATA_DIR, "asegurados.xlsx") 