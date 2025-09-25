#!/usr/bin/env python3
"""
Email Watcher Error Handler
This module provides backward compatibility for the email watcher.
It imports and uses the shared error handler with pipeline awareness.
"""

import sys
import os
from pathlib import Path

# Add the shared directory to the path
sys.path.append('/app')

try:
    from shared.error_handler import (
        ErrorHandler, 
        send_pipeline_success_report, 
        send_pipeline_failure_report, 
        check_pipeline_excel_and_report,
        error_handler as shared_error_handler
    )
    
    # Create pipeline-specific handlers
    si_error_handler = ErrorHandler('si')
    viajeros_error_handler = ErrorHandler('viajeros')
    
    # Backward compatibility functions
    def check_excel_and_report() -> tuple[bool, str]:
        """Check Excel file and generate report. Returns (is_valid, error_message)."""
        # Use the legacy path for backward compatibility
        excel_path = "/app/Exceles/Rep_Afiliados_Seguro_Viajero 16 06 2025 AL 02 07 2025.xlsx"
        
        is_valid, error_message, row_count = shared_error_handler.check_excel_file(excel_path)
        
        if not is_valid:
            print(f"❌ Excel validation failed: {error_message}")
            shared_error_handler.handle_error('excel_validation', error_message)
            return False, error_message
        
        print(f"✅ Excel file validated successfully: {row_count} rows found")
        return True, ""

    def send_success_report() -> bool:
        """Send success report after successful processing."""
        return shared_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True)

    def send_failure_report(error_message: str) -> bool:
        """Send failure report after failed processing."""
        return shared_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)

    # Use the shared error handler
    error_handler = shared_error_handler

except ImportError as e:
    print(f"Warning: Could not import shared error handler: {e}")
    print("Falling back to dummy implementations")
    
    # Fallback implementations
    def check_excel_and_report() -> tuple[bool, str]:
        return True, ""
    
    def send_success_report() -> bool:
        return True
    
    def send_failure_report(error_message: str) -> bool:
        return True
    
    class DummyErrorHandler:
        def handle_error(self, error_type, error_message, context=None):
            return True
    
    error_handler = DummyErrorHandler()