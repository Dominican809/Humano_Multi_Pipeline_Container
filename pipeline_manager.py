#!/usr/bin/env python3
"""
Pipeline Manager for Multi-Pipeline Email Processing
Routes emails to appropriate pipelines based on content analysis.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def detect_pipeline_type(subject, from_addr):
    """
    Detect which pipeline to use based on email content.
    
    Args:
        subject (str): Email subject
        from_addr (str): Email sender address
        
    Returns:
        str: Pipeline type ('viajeros', 'si', or 'unknown')
    """
    subject_lower = subject.lower()
    
    if "asegurados viajeros" in subject_lower:
        logger.info(f"[manager] Detected Viajeros pipeline from subject: {subject}")
        return "viajeros"
    elif "asegurados salud internacional" in subject_lower:
        logger.info(f"[manager] Detected SI pipeline from subject: {subject}")
        return "si"
    else:
        logger.warning(f"[manager] Unknown pipeline type for subject: {subject}")
        return "unknown"

def run_viajeros_pipeline(excel_file_path, email_subject=None):
    """
    Run the Viajeros pipeline.
    
    Args:
        excel_file_path (str): Path to the Excel file
        email_subject (str): Original email subject for reporting
    """
    logger.info(f"[manager] Starting Viajeros pipeline with file: {excel_file_path}")
    
    # Import coordination system
    sys.path.append('/app')
    from shared.pipeline_coordinator import coordinator
    from shared.error_handler import send_pipeline_success_report, send_pipeline_failure_report, check_pipeline_excel_and_report
    
    # Start pipeline session
    session_id = coordinator.start_pipeline_session('viajeros', email_subject)
    
    try:
        # Change to viajeros pipeline directory
        viajeros_dir = "/app/viajeros_pipeline"
        os.chdir(viajeros_dir)
        
        # Copy Excel file to viajeros pipeline directory
        target_excel = f"{viajeros_dir}/Exceles/Asegurados_Viajeros.xlsx"
        os.system(f"cp '{excel_file_path}' '{target_excel}'")
        
        # Check Excel file and report
        is_valid, error_message = check_pipeline_excel_and_report('viajeros')
        if not is_valid:
            logger.error(f"[manager] ❌ Excel validation failed: {error_message}")
            # Check if this is a "no data" case vs actual error
            if "no processing needed" in error_message.lower():
                logger.info(f"[manager] ℹ️ No Viajeros data to process - completing pipeline with success")
                coordinator.complete_pipeline('viajeros', session_id, success=True, error_message=error_message)
            else:
                coordinator.complete_pipeline('viajeros', session_id, success=False, error_message=f"Excel validation failed: {error_message}")
            return
        
        # Run the complete Viajeros pipeline
        result = subprocess.run([
            "python", "-c",
            f"""
import sys
import os
sys.path.append('/app/viajeros_pipeline')
os.environ['AUTOMATED_MODE'] = 'true'
try:
    from main import run_viajeros_pipeline, main
    print('[viajeros] Starting Viajeros pipeline...')
    pipeline_success = run_viajeros_pipeline()
    if pipeline_success:
        print('[viajeros] Pipeline setup completed, running main processing...')
        exit_code = main()
        if exit_code == 0:
            print('[viajeros] Viajeros pipeline completed successfully')
        else:
            print('[viajeros] Viajeros main processing failed')
            sys.exit(1)
    else:
        print('[viajeros] Viajeros pipeline setup failed')
        sys.exit(1)
except Exception as e:
    print(f'[viajeros] ERROR in Viajeros pipeline: {{e}}')
    import traceback
    print(f'[viajeros] Traceback: {{traceback.format_exc()}}')
    sys.exit(1)
"""
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("[manager] ✅ Viajeros pipeline completed successfully")
            coordinator.complete_pipeline('viajeros', session_id, success=True)
        else:
            logger.error(f"[manager] ❌ Viajeros pipeline failed: {result.stderr}")
            if result.stdout:
                logger.error(f"[manager] Viajeros pipeline stdout: {result.stdout}")
            coordinator.complete_pipeline('viajeros', session_id, success=False, error_message=f"Pipeline execution failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"[manager] ❌ Error running Viajeros pipeline: {e}")
        coordinator.complete_pipeline('viajeros', session_id, success=False, error_message=f"Pipeline execution error: {str(e)}")

def run_si_pipeline(excel_file_path, email_subject=None):
    """
    Run the SI pipeline.
    
    Args:
        excel_file_path (str): Path to the Excel file
        email_subject (str): Original email subject for reporting
    """
    logger.info(f"[manager] Starting SI pipeline with file: {excel_file_path}")
    
    # Import coordination system
    sys.path.append('/app')
    from shared.pipeline_coordinator import coordinator
    from shared.error_handler import send_pipeline_success_report, send_pipeline_failure_report, check_pipeline_excel_and_report
    
    # Start pipeline session
    session_id = coordinator.start_pipeline_session('si', email_subject)
    
    try:
        # Change to SI pipeline directory
        si_dir = "/app/si_pipeline"
        os.chdir(si_dir)
        
        # SI pipeline needs both old and new files
        old_file = f"{si_dir}/Comparador_Humano/exceles/Asegurados_SI_old.xlsx"
        new_file = f"{si_dir}/Comparador_Humano/exceles/Asegurados_SI.xlsx"
        
        # Check if old file exists
        if not os.path.exists(old_file):
            logger.error(f"[manager] ❌ Old SI file not found: {old_file}")
            logger.error("[manager] SI pipeline requires Asegurados_SI_old.xlsx for comparison")
            coordinator.complete_pipeline('si', session_id, success=False, error_message=f"Old SI file not found: {old_file}")
            return False
        
        # Copy new Excel file to SI pipeline directory
        logger.info(f"[manager] 📁 Copying new file to: {new_file}")
        os.system(f"cp '{excel_file_path}' '{new_file}'")
        
        # Verify the new file was copied successfully
        if not os.path.exists(new_file):
            logger.error(f"[manager] ❌ Failed to copy new SI file to: {new_file}")
            coordinator.complete_pipeline('si', session_id, success=False, error_message=f"Failed to copy new SI file to: {new_file}")
            return False
        
        logger.info(f"[manager] ✅ New SI file copied successfully")
        
        # Check Excel file and report
        is_valid, error_message = check_pipeline_excel_and_report('si')
        if not is_valid:
            logger.error(f"[manager] ❌ Excel validation failed: {error_message}")
            # Check if this is a "no new people" case vs actual error
            if "no processing needed" in error_message.lower() or "no new people" in error_message.lower():
                logger.info(f"[manager] ℹ️ No new SI people to process - completing pipeline with success")
                coordinator.complete_pipeline('si', session_id, success=True, error_message=error_message)
            else:
                coordinator.complete_pipeline('si', session_id, success=False, error_message=f"Excel validation failed: {error_message}")
            return False
        
        # Run the corrected SI pipeline with individual filtering
        result = subprocess.run([
            "python", "-c",
            f"""
import sys
import os
import json
from datetime import datetime
sys.path.append('/app/si_pipeline')
os.environ['AUTOMATED_MODE'] = 'true'
try:
    from corrected_main import run_si_pipeline_with_corrected_filtering
    print('[si] Starting corrected SI pipeline with individual filtering...')
    success, successful_emissions, failed_individuals_data, all_failed_individuals = run_si_pipeline_with_corrected_filtering()
    
    if success:
        print(f'[si] Corrected SI pipeline completed successfully')
        print(f'[si] Results:')
        print(f'[si]   - Successful emissions: {{len(successful_emissions)}}')
        print(f'[si]   - Failed individuals data: {{len(failed_individuals_data)}}')
        print(f'[si]   - Total failed individuals: {{len(all_failed_individuals)}}')
        
        # Store failed individuals data for email reporting
        if failed_individuals_data:
            print(f'[si] Storing failed individuals data for email reporting...')
            with open('/app/si_pipeline/data/latest_failed_individuals.json', 'w') as f:
                json.dump({{
                    'failed_individuals_data': failed_individuals_data,
                    'all_failed_individuals': all_failed_individuals,
                    'email_subject': '{email_subject}',
                    'timestamp': datetime.now().isoformat()
                }}, f, indent=2)
            print(f'[si] Failed individuals data stored successfully')
    else:
        print('[si] Corrected SI pipeline failed')
        sys.exit(1)
except Exception as e:
    print(f'[si] ERROR in corrected SI pipeline: {{e}}')
    import traceback
    print(f'[si] Traceback: {{traceback.format_exc()}}')
    sys.exit(1)
"""
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("[manager] ✅ SI pipeline completed successfully")
            
            # Update the old file with the new file for next comparison
            logger.info("[manager] 🔄 Updating old file for next comparison...")
            os.system(f"cp '{new_file}' '{old_file}'")
            logger.info("[manager] ✅ Old file updated successfully")
            
            coordinator.complete_pipeline('si', session_id, success=True)
        else:
            logger.error(f"[manager] ❌ SI pipeline failed: {result.stderr}")
            if result.stdout:
                logger.error(f"[manager] SI pipeline stdout: {result.stdout}")
            coordinator.complete_pipeline('si', session_id, success=False, error_message=f"Pipeline execution failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"[manager] ❌ Error running SI pipeline: {e}")
        import traceback
        logger.error(f"[manager] Traceback: {traceback.format_exc()}")
        coordinator.complete_pipeline('si', session_id, success=False, error_message=f"Pipeline execution error: {str(e)}")

def process_email(pipeline_type, excel_file_path, email_subject=None):
    """
    Route email to appropriate pipeline.
    
    Args:
        pipeline_type (str): Type of pipeline ('viajeros' or 'si')
        excel_file_path (str): Path to the Excel file
        email_subject (str): Original email subject for reporting
    """
    logger.info(f"[manager] Processing email with pipeline type: {pipeline_type}")
    
    if pipeline_type == "viajeros":
        run_viajeros_pipeline(excel_file_path, email_subject)
    elif pipeline_type == "si":
        run_si_pipeline(excel_file_path, email_subject)
    else:
        logger.error(f"[manager] ❌ Unknown pipeline type: {pipeline_type}")

if __name__ == "__main__":
    # This can be called from the email watcher
    if len(sys.argv) >= 3:
        pipeline_type = sys.argv[1]
        excel_file_path = sys.argv[2]
        process_email(pipeline_type, excel_file_path)
    else:
        logger.error("Usage: python pipeline_manager.py <pipeline_type> <excel_file_path>")
