"""
Módulo de autenticación para la API Goval.
Referencia: API Goval-Web v3.7
"""

import requests
import time
from loguru import logger
from ..config import LOGIN_URL, USUARIO, PASSWORD

class TokenManager:
    """
    Centralized manager for Goval API JWT tokens.
    Handles automatic refresh and expiration.
    """
    _token = None
    _expires_at = 0  # Unix timestamp
    _lifetime = 290  # 290 seconds (4:50min) for safety, since token is valid for 5min

    @classmethod
    def get_token(cls, force_refresh=False):
        now = time.time()
        if force_refresh or cls._token is None or now >= cls._expires_at:
            logger.info("Solicitando nuevo token JWT de Goval API...")
            try:
                # Simple multipart/form-data request
                params = {"acl": 1}
                form_data = {
                    "login": (None, USUARIO),
                    "password": (None, PASSWORD)
                }
                
                logger.debug(f"Enviando petición a {LOGIN_URL}")
                logger.debug(f"Params: {params}")
                logger.debug(f"Form data: {form_data}")
                
                # Use multipart/form-data as required by the API
                resp = requests.post(
                    LOGIN_URL, 
                    params=params, 
                    files=form_data,
                    headers={'Accept': 'application/json'}
                )
                
                logger.debug(f"Response status: {resp.status_code}")
                logger.debug(f"Response text: {resp.text}")
                
                if resp.status_code != 200:
                    raise ValueError(f"Error en la petición: {resp.status_code} - {resp.text}")
                
                data = resp.json()
                if "jwt" not in data:
                    raise ValueError("No JWT token in response")
                    
                cls._token = data["jwt"]
                cls._expires_at = now + cls._lifetime
                logger.info("Token obtenido exitosamente")
                
            except Exception as e:
                logger.error(f"Error al obtener token: {str(e)}")
                raise
        return cls._token

    @classmethod
    def get_auth_header(cls):
        """
        Returns the properly formatted authentication header for GAPI.
        """
        token = cls.get_token()
        return {'x-goval-auth': f'jwt={token}'}

# For backward compatibility
def obtener_token():
    """
    Obtiene un token JWT de autenticación de la API de Goval.
    Returns:
        str: Token JWT para autenticación
    Raises:
        requests.exceptions.RequestException: Si hay un error en la petición
    """
    return TokenManager.get_token() 