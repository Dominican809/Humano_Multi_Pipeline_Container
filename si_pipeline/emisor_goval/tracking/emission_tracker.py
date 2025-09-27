"""
Módulo para el tracking de emisiones.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

class EmissionTracker:
    def __init__(self, tracking_dir: str = "/app/si_pipeline/data/tracking"):
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear subdirectorios
        self.success_dir = self.tracking_dir / "success"
        self.failure_dir = self.tracking_dir / "failures"
        self.success_dir.mkdir(exist_ok=True)
        self.failure_dir.mkdir(exist_ok=True)
        
        # Inicializar registros con formato más legible para la hora
        self.current_run = datetime.now().strftime("%Y%m%d_%H_%M_%S")
        # Track all emissions by factura to ensure no duplicates
        self.tracked_emissions = {}
        self.success_records = []
        self.failure_records = []
        
    def track_emission(self, factura: str, result: Dict) -> None:
        """
        Registra una emisión basada en su resultado.
        Si tiene tracking_id es exitosa, si no, es fallida.
        
        Args:
            factura (str): Número de factura
            result (Dict): Resultado de la emisión que debe contener:
                - En caso de éxito: 
                    {
                        "tracking_id": str,
                        "num_asegurados": int
                    }
                - En caso de fallo:
                    {
                        "error": str,
                        "step": str (cotizacion|manager|pago),
                        "num_asegurados": int,
                        "error_details": {  # Opcional - Detalles adicionales del error
                            "status_code": int,  # Código HTTP si aplica
                            "api_response": dict,  # Respuesta de la API si está disponible
                            "validation_codes": list,  # Códigos de validación que fallaron
                            "validation_messages": list  # Mensajes de validación específicos
                        }
                    }
        """
        # Si la factura ya fue tracked, no hacer nada
        if factura in self.tracked_emissions:
            logger.warning(f"Factura {factura} ya fue registrada anteriormente")
            return
            
        if "tracking_id" in result:
            # Es una emisión exitosa
            record = {
                "factura": factura,
                "tracking_id": result["tracking_id"],
                "total_asegurados": result["num_asegurados"]
            }
            self.success_records.append(record)
            self._save_success_records()
            logger.success(f"Factura {factura} ✅ - Tracking ID: {result['tracking_id']}")
        else:
            # Es una emisión fallida
            record = {
                "factura": factura,
                "step": result["step"],
                "error": result["error"],
                "num_asegurados": result["num_asegurados"]
            }
            
            # Agregar detalles del error si están disponibles
            if "error_details" in result:
                error_details = result["error_details"]
                record["error_details"] = {
                    "status_code": error_details.get("status_code"),
                    "api_response": error_details.get("api_response"),
                    "validation_codes": error_details.get("validation_codes", []),
                    "validation_messages": error_details.get("validation_messages", [])
                }
                
                # Log detalles adicionales del error
                if error_details.get("status_code"):
                    logger.error(f"Status Code: {error_details['status_code']}")
                if error_details.get("validation_codes"):
                    logger.error(f"Validation Codes: {error_details['validation_codes']}")
                if error_details.get("validation_messages"):
                    for msg in error_details["validation_messages"]:
                        logger.error(f"Validation Message: {msg}")
                if error_details.get("api_response"):
                    logger.error(f"API Response: {json.dumps(error_details['api_response'], indent=2)}")
            
            self.failure_records.append(record)
            self._save_failure_records()
            logger.error(f"Factura {factura} ❌ - Error en {result['step']}: {result['error']}")
            
        # Marcar la factura como procesada
        self.tracked_emissions[factura] = True
        
    def get_statistics(self) -> Dict:
        """
        Genera estadísticas del tracking actual.
        
        Returns:
            Dict: Estadísticas de emisiones
        """
        total_successful = len(self.success_records)
        total_failed = len(self.failure_records)
        
        # Calcular totales de asegurados
        successful_passengers = sum(
            record["total_asegurados"] 
            for record in self.success_records
        )
        
        failed_passengers = sum(
            record["num_asegurados"] 
            for record in self.failure_records
        )
        
        # Agrupar errores por tipo
        error_types = {}
        validation_codes = {}
        for record in self.failure_records:
            step = record["step"]
            error_types[step] = error_types.get(step, 0) + 1
            
            # Contar códigos de validación si están disponibles
            if "error_details" in record and "validation_codes" in record["error_details"]:
                for code in record["error_details"]["validation_codes"]:
                    validation_codes[str(code)] = validation_codes.get(str(code), 0) + 1
        
        return {
            "run_id": self.current_run,
            "emisiones": {
                "total": total_successful + total_failed,
                "exitosas": total_successful,
                "fallidas": total_failed
            },
            "asegurados": {
                "total": successful_passengers + failed_passengers,
                "exitosos": successful_passengers,
                "fallidos": failed_passengers
            },
            "errores_por_tipo": error_types,
            "codigos_validacion": validation_codes
        }
        
    def _save_success_records(self) -> None:
        """Guarda los registros exitosos en archivo JSON."""
        success_file = self.success_dir / f"success_{self.current_run}.json"
        with open(success_file, 'w', encoding='utf-8') as f:
            json.dump({
                "emisiones_exitosas": self.success_records
            }, f, ensure_ascii=False, indent=2)
            
    def _save_failure_records(self) -> None:
        """Guarda los registros fallidos en archivo JSON."""
        failure_file = self.failure_dir / f"failures_{self.current_run}.json"
        with open(failure_file, 'w', encoding='utf-8') as f:
            json.dump({
                "emisiones_fallidas": self.failure_records
            }, f, ensure_ascii=False, indent=2) 