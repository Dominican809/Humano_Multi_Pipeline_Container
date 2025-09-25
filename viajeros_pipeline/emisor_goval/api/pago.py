"""
Módulo de pago para la API Goval.
"""

import json
import requests
import time
import random
from loguru import logger
from ..config import PAGO_URL, API_BASE
from ..api.auth import TokenManager
from typing import Dict, Optional, Tuple, Union

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
            resp = requests.post(url, **kwargs)
            if resp.status_code in [401, 403] and 'token' in resp.text.lower():
                if attempt == 0:
                    logger.warning("Token expirado o inválido, renovando y reintentando...")
                    kwargs['headers'] = {**kwargs.get('headers', {}), **TokenManager.get_auth_header()}
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

def aplicar_pago(cotizacion_id, token=None):
    """
    Aplica el pago para una cotización.
    
    Args:
        cotizacion_id (str): ID de la cotización
        token (str): Token JWT de autenticación
        
    Returns:
        requests.Response: Respuesta de la API
        
    Raises:
        requests.exceptions.RequestException: Si hay un error en la petición
    """
    if token is None:
        token = TokenManager.get_token()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = robust_post(PAGO_URL.format(id=cotizacion_id), headers=headers)
        logger.info(f"Pago aplicado exitosamente para cotización {cotizacion_id}")
        return resp
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al aplicar pago para cotización {cotizacion_id}: {str(e)}")
        raise 

def apply_payment(quotation_id: int, token: str, manager_uri: str = None) -> Union[Dict, Tuple[None, requests.Response]]:
    """
    Aplica el pago a una cotización usando la línea de crédito del productor.
    
    Args:
        quotation_id (int): ID de la cotización
        token (str): Token de autenticación
        manager_uri (str): URI proporcionada por el manager
        
    Returns:
        Union[Dict, Tuple[None, requests.Response]]: 
            - Dict con información del ticket si fue exitoso
            - Tuple[None, Response] si falló, incluyendo la respuesta para extraer detalles del error
    """
    try:
        response = requests.post(
            f"{API_BASE}/issue/retail/apply/{quotation_id}/credit",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                **TokenManager.get_auth_header()
            }
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            if "ticket_id" in data or "id" in data:
                return {
                    "ticket_id": data.get("ticket_id") or data.get("id"),
                    "url": data.get("url") or data.get("uri")
                }
        
        return None, response
        
    except Exception as e:
        logger.error(f"Error al aplicar pago: {str(e)}")
        return None, None 