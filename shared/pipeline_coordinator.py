#!/usr/bin/env python3
"""
Pipeline Coordination Module
Handles coordination between SI and Viajeros pipelines to ensure combined reporting.
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sqlite3
from loguru import logger

class PipelineCoordinator:
    """Coordinates pipeline execution and reporting."""
    
    def __init__(self):
        self.state_dir = Path('/state')
        self.coordination_db = self.state_dir / 'pipeline_coordination.sqlite3'
        self.wait_timeout = 5 * 60  # 5 minutes in seconds
        self.check_interval = 30  # Check every 30 seconds
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize the coordination database."""
        try:
            self.state_dir.mkdir(exist_ok=True)
            
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_sessions (
                        session_id TEXT PRIMARY KEY,
                        si_status TEXT DEFAULT 'pending',
                        viajeros_status TEXT DEFAULT 'pending',
                        si_started_at TIMESTAMP,
                        viajeros_started_at TIMESTAMP,
                        si_completed_at TIMESTAMP,
                        viajeros_completed_at TIMESTAMP,
                        combined_report_sent BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        pipeline_type TEXT,
                        status TEXT,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT,
                        FOREIGN KEY (session_id) REFERENCES pipeline_sessions (session_id)
                    )
                """)
                
                conn.commit()
                logger.info("✅ Pipeline coordination database initialized")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize coordination database: {e}")
    
    def start_pipeline_session(self, pipeline_type: str, email_subject: str = None) -> str:
        """Start a new pipeline session or join existing one."""
        session_id = self._get_or_create_session()
        
        try:
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                
                # Update pipeline status
                cursor.execute("""
                    UPDATE pipeline_sessions 
                    SET {}_status = 'running', {}_started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """.format(pipeline_type, pipeline_type), (session_id,))
                
                # Log execution with email subject
                cursor.execute("""
                    INSERT INTO pipeline_executions (session_id, pipeline_type, status, started_at, error_message)
                    VALUES (?, ?, 'running', CURRENT_TIMESTAMP, ?)
                """, (session_id, pipeline_type, f"Email subject: {email_subject}" if email_subject else None))
                
                conn.commit()
                
                logger.info(f"🚀 Started {pipeline_type} pipeline in session {session_id}")
                if email_subject:
                    logger.info(f"📧 Processing email: {email_subject}")
                return session_id
                
        except Exception as e:
            logger.error(f"❌ Failed to start pipeline session: {e}")
            return session_id
    
    def complete_pipeline(self, pipeline_type: str, session_id: str, success: bool = True, error_message: str = None):
        """Mark a pipeline as completed."""
        try:
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                
                status = 'completed' if success else 'failed'
                
                # Update session status
                cursor.execute("""
                    UPDATE pipeline_sessions 
                    SET {}_status = ?, {}_completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """.format(pipeline_type, pipeline_type), (status, session_id))
                
                # Update execution log
                cursor.execute("""
                    UPDATE pipeline_executions 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP, error_message = ?
                    WHERE session_id = ? AND pipeline_type = ? AND completed_at IS NULL
                """, (status, error_message, session_id, pipeline_type))
                
                conn.commit()
                
                logger.info(f"✅ {pipeline_type} pipeline completed with status: {status}")
                
                # Check if we should send combined report
                self._check_and_send_combined_report(session_id)
                
        except Exception as e:
            logger.error(f"❌ Failed to complete pipeline: {e}")
    
    def _get_or_create_session(self) -> str:
        """Get existing active session or create new one."""
        try:
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                
                # Look for active session within the last 10 minutes
                cursor.execute("""
                    SELECT session_id FROM pipeline_sessions 
                    WHERE created_at > datetime('now', '-10 minutes')
                    AND combined_report_sent = FALSE
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    session_id = result[0]
                    logger.info(f"🔄 Joining existing session: {session_id}")
                    return session_id
                
                # Create new session
                session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                cursor.execute("""
                    INSERT INTO pipeline_sessions (session_id)
                    VALUES (?)
                """, (session_id,))
                
                conn.commit()
                logger.info(f"🆕 Created new session: {session_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"❌ Failed to get/create session: {e}")
            return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _check_and_send_combined_report(self, session_id: str):
        """Check if both pipelines are complete and send combined report."""
        try:
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                
                # Get session status
                cursor.execute("""
                    SELECT si_status, viajeros_status, combined_report_sent, created_at
                    FROM pipeline_sessions 
                    WHERE session_id = ?
                """, (session_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.error(f"❌ Session {session_id} not found")
                    return
                
                si_status, viajeros_status, report_sent, created_at = result
                
                if report_sent:
                    logger.info(f"📧 Combined report already sent for session {session_id}")
                    return
                
                # Check if both pipelines are complete
                both_complete = (si_status in ['completed', 'failed'] and 
                               viajeros_status in ['completed', 'failed'])
                
                if both_complete:
                    logger.info(f"🎯 Both pipelines complete for session {session_id}, sending combined report")
                    self._send_combined_report(session_id)
                else:
                    # Check if only one pipeline is active and complete
                    si_complete = si_status in ['completed', 'failed']
                    viajeros_complete = viajeros_status in ['completed', 'failed']
                    si_active = si_status in ['running', 'completed', 'failed']
                    viajeros_active = viajeros_status in ['running', 'completed', 'failed']
                    
                    # If only one pipeline is active and complete, send single pipeline report
                    if si_complete and not viajeros_active:
                        logger.info(f"🎯 Only SI pipeline was active and completed for session {session_id}")
                        self._send_single_pipeline_report(session_id, 'si')
                    elif viajeros_complete and not si_active:
                        logger.info(f"🎯 Only Viajeros pipeline was active and completed for session {session_id}")
                        self._send_single_pipeline_report(session_id, 'viajeros')
                    else:
                        logger.info(f"⏳ Waiting for pipelines to complete in session {session_id}")
                        logger.info(f"   SI: {si_status}, Viajeros: {viajeros_status}")
                        
                        # Start timeout monitoring if not already started
                        self._start_timeout_monitor(session_id)
                
        except Exception as e:
            logger.error(f"❌ Failed to check combined report status: {e}")
    
    def _start_timeout_monitor(self, session_id: str):
        """Start a background thread to monitor timeout."""
        def timeout_monitor():
            try:
                start_time = datetime.now()
                
                while True:
                    time.sleep(self.check_interval)
                    
                    # Check if session is still active
                    with sqlite3.connect(str(self.coordination_db)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT si_status, viajeros_status, combined_report_sent, created_at
                            FROM pipeline_sessions 
                            WHERE session_id = ?
                        """, (session_id,))
                        
                        result = cursor.fetchone()
                        if not result:
                            logger.info(f"⏰ Session {session_id} no longer exists, stopping timeout monitor")
                            break
                        
                        si_status, viajeros_status, report_sent, created_at = result
                        
                        if report_sent:
                            logger.info(f"📧 Combined report sent for session {session_id}, stopping timeout monitor")
                            break
                        
                        # Check timeout
                        elapsed = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds()
                        
                        if elapsed >= self.wait_timeout:
                            logger.warning(f"⏰ Timeout reached for session {session_id}, sending partial report")
                            self._send_timeout_report(session_id)
                            break
                        
                        # Check if both pipelines are now complete
                        both_complete = (si_status in ['completed', 'failed'] and 
                                       viajeros_status in ['completed', 'failed'])
                        
                        if both_complete:
                            logger.info(f"🎯 Both pipelines completed during timeout monitoring for session {session_id}")
                            self._send_combined_report(session_id)
                            break
                        
                        # Check if only one pipeline is active and completed
                        si_complete = si_status in ['completed', 'failed']
                        viajeros_complete = viajeros_status in ['completed', 'failed']
                        si_active = si_status in ['running', 'completed', 'failed']
                        viajeros_active = viajeros_status in ['running', 'completed', 'failed']
                        
                        # If only one pipeline is active and it's complete, send single pipeline report
                        if si_complete and not viajeros_active:
                            logger.info(f"🎯 Only SI pipeline was active and completed for session {session_id}")
                            self._send_single_pipeline_report(session_id, 'si')
                            break
                        elif viajeros_complete and not si_active:
                            logger.info(f"🎯 Only Viajeros pipeline was active and completed for session {session_id}")
                            self._send_single_pipeline_report(session_id, 'viajeros')
                            break
                        
                        logger.info(f"⏳ Timeout monitor: {elapsed:.0f}s elapsed, SI: {si_status}, Viajeros: {viajeros_status}")
                
            except Exception as e:
                logger.error(f"❌ Error in timeout monitor for session {session_id}: {e}")
        
        # Start timeout monitor in background
        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
        monitor_thread.start()
        logger.info(f"🕐 Started timeout monitor for session {session_id}")
    
    def _send_combined_report(self, session_id: str):
        """Send combined report for both pipelines."""
        try:
            # Import here to avoid circular imports
            from error_handler import error_handler
            
            # Mark report as sent
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pipeline_sessions 
                    SET combined_report_sent = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """, (session_id,))
                conn.commit()
            
            # Send combined report
            logger.info(f"📧 Sending combined report for session {session_id}")
            success = error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True)
            
            if success:
                logger.info(f"✅ Combined report sent successfully for session {session_id}")
            else:
                logger.error(f"❌ Failed to send combined report for session {session_id}")
                
        except Exception as e:
            logger.error(f"❌ Error sending combined report for session {session_id}: {e}")
    
    def _send_single_pipeline_report(self, session_id: str, pipeline_type: str):
        """Send report for a single pipeline that completed using unified reporting."""
        try:
            # Get email subject from the session
            email_subject = self._get_email_subject_from_session(session_id, pipeline_type)
            
            # Mark report as sent
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pipeline_sessions 
                    SET combined_report_sent = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """, (session_id,))
                conn.commit()
            
            # Use the new unified email reporting system
            from .error_handler import ErrorHandler
            
            error_handler = ErrorHandler(pipeline_type)
            success = error_handler.send_unified_pipeline_report(
                pipeline_type=pipeline_type,
                email_subject=email_subject
            )
            
            if success:
                logger.info(f"✅ Unified report sent successfully for {pipeline_type} pipeline")
            else:
                logger.error(f"❌ Failed to send unified report for {pipeline_type} pipeline")
            
            return success
                
        except Exception as e:
            logger.error(f"❌ Error sending unified report for {pipeline_type} pipeline: {e}")
            return False
    
    def _get_execution_results(self, session_id: str, pipeline_type: str) -> dict:
        """Get execution results for a specific pipeline session."""
        try:
            # Look for the most recent success and failure files for this pipeline type
            from pathlib import Path
            import json
            from datetime import datetime
            
            # For Viajeros pipeline, try to read from the latest execution stats file first
            if pipeline_type == 'viajeros':
                stats_file = Path('/app/viajeros_pipeline/data/latest_execution_stats.json')
                if stats_file.exists():
                    try:
                        with open(stats_file, 'r', encoding='utf-8') as f:
                            stats = json.load(f)
                        
                        # Extract statistics from the pipeline execution
                        successful_emissions = stats['emisiones']['exitosas']
                        failed_emissions = stats['emisiones']['fallidas']
                        successful_people = stats['asegurados']['exitosos']
                        failed_people = stats['asegurados']['fallidos']
                        total_emissions = stats['emisiones']['total']
                        
                        logger.info(f"📊 VIAJEROS Pipeline: {successful_people} people from {successful_emissions} emissions (from execution stats)")
                        
                        # Try to read detailed failure data
                        detailed_failures = []
                        detailed_failures_file = Path('/app/viajeros_pipeline/data/latest_detailed_failures.json')
                        if detailed_failures_file.exists():
                            try:
                                with open(detailed_failures_file, 'r', encoding='utf-8') as f:
                                    detailed_failures = json.load(f)
                                logger.info(f"📊 Loaded detailed failure data: {len(detailed_failures)} facturas")
                            except Exception as e:
                                logger.error(f"Error reading detailed failures file: {e}")
                        
                        return {
                            'successful': successful_people,
                            'successful_emissions': successful_emissions,
                            'failed': failed_people,
                            'total_processed': successful_people + failed_people,
                            'total_emissions': total_emissions,
                            'success_rate': (successful_people / (successful_people + failed_people) * 100) if (successful_people + failed_people) > 0 else 0.0,
                            'pipeline_type': pipeline_type,
                            'execution_time': datetime.now().isoformat(),
                            'failed_individuals': detailed_failures  # Include detailed failure data
                        }
                    except Exception as e:
                        logger.error(f"Error reading execution stats file: {e}")
                        # Fall back to old method
                
            # Get the data directory for this pipeline type
            if pipeline_type == 'si':
                data_dir = Path('/app/si_pipeline/data')
            elif pipeline_type == 'viajeros':
                data_dir = Path('/app/viajeros_pipeline/data')
            else:
                return {'successful': 0, 'failed': 0, 'total_processed': 0}
            
            if not data_dir.exists():
                return {'successful': 0, 'failed': 0, 'total_processed': 0}
            
            # Get today's date string
            today = datetime.now().strftime('%Y%m%d')
            
            # Find the most recent success and failure files
            success_files = list(data_dir.glob(f'tracking/success/success_{today}*.json'))
            failure_files = list(data_dir.glob(f'tracking/failures/failures_{today}*.json'))
            
            # Sort by modification time to get the most recent
            success_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            failure_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            successful = 0
            failed = 0
            
            # Count successful emissions from the most recent success file
            successful_emissions = 0
            successful_people = 0
            
            if success_files:
                try:
                    with open(success_files[0], 'r', encoding='utf-8') as f:
                        success_data = json.load(f)
                        if isinstance(success_data, dict) and 'emisiones_exitosas' in success_data:
                            successful_emissions = len(success_data['emisiones_exitosas'])
                            
                            # Count actual people in successful emissions for both pipelines
                            for emission in success_data['emisiones_exitosas']:
                                if 'emision_data' in emission and 'metadata' in emission['emision_data']:
                                    successful_people += emission['emision_data']['metadata'].get('total_asegurados', 0)
                                elif 'emision' in emission and 'insured' in emission['emision']:
                                    successful_people += len(emission['emision']['insured'])
                                elif 'insured' in emission:
                                    # Direct emission format
                                    successful_people += len(emission['insured'])
                                else:
                                    # Fallback: assume 1 person per emission
                                    successful_people += 1
                                    
                        elif isinstance(success_data, list):
                            successful_emissions = len(success_data)
                            
                            # Count actual people in successful emissions for both pipelines
                            for emission in success_data:
                                if 'emision_data' in emission and 'metadata' in emission['emision_data']:
                                    successful_people += emission['emision_data']['metadata'].get('total_asegurados', 0)
                                elif 'emision' in emission and 'insured' in emission['emision']:
                                    successful_people += len(emission['emision']['insured'])
                                elif 'insured' in emission:
                                    # Direct emission format
                                    successful_people += len(emission['insured'])
                                else:
                                    # Fallback: assume 1 person per emission
                                    successful_people += 1
                                    
                        logger.info(f"📊 {pipeline_type.upper()} Pipeline: {successful_people} people from {successful_emissions} emissions")
                        
                except Exception as e:
                    logger.error(f"Error reading success file {success_files[0]}: {e}")
            
            # Use people count for the main successful count
            successful = successful_people
            
            # Count failed emissions and extract failed individuals data from the most recent failure file
            failed_individuals_data = []
            if failure_files:
                try:
                    with open(failure_files[0], 'r', encoding='utf-8') as f:
                        failure_data = json.load(f)
                        if isinstance(failure_data, dict) and 'emisiones_fallidas' in failure_data:
                            failed_emissions_count = len(failure_data['emisiones_fallidas'])
                            
                            # Count actual people in failed emissions for both pipelines
                            failed = 0
                            for failed_emission in failure_data['emisiones_fallidas']:
                                if 'emision_data' in failed_emission and 'metadata' in failed_emission['emision_data']:
                                    failed += failed_emission['emision_data']['metadata'].get('total_asegurados', 0)
                                elif 'emision' in failed_emission and 'insured' in failed_emission['emision']:
                                    failed += len(failed_emission['emision']['insured'])
                                elif 'insured' in failed_emission:
                                    # Direct emission format
                                    failed += len(failed_emission['insured'])
                                else:
                                    # Fallback: assume 1 person per emission
                                    failed += 1
                            
                            # Extract failed individuals data for email reporting
                            for failed_emission in failure_data['emisiones_fallidas']:
                                error_details = failed_emission.get('error_details', {})
                                api_response = error_details.get('api_response', {})
                                
                                # Check if this is a 417 error with found individuals
                                if (error_details.get('status_code') == 417 and 
                                    api_response and 'found' in api_response):
                                    failed_individuals_data.extend(api_response['found'])
                        elif isinstance(failure_data, list):
                            # Count actual people in failed emissions for both pipelines
                            failed = 0
                            for failed_emission in failure_data:
                                if 'emision_data' in failed_emission and 'metadata' in failed_emission['emision_data']:
                                    failed += failed_emission['emision_data']['metadata'].get('total_asegurados', 0)
                                elif 'emision' in failed_emission and 'insured' in failed_emission['emision']:
                                    failed += len(failed_emission['emision']['insured'])
                                elif 'insured' in failed_emission:
                                    # Direct emission format
                                    failed += len(failed_emission['insured'])
                                else:
                                    # Fallback: assume 1 person per emission
                                    failed += 1
                except Exception as e:
                    logger.error(f"Error reading failure file {failure_files[0]}: {e}")
            
            # For SI pipeline, also check the stored failed individuals JSON file
            if pipeline_type == 'si':
                try:
                    si_failed_file = Path('/app/si_pipeline/data/latest_failed_individuals.json')
                    if si_failed_file.exists():
                        with open(si_failed_file, 'r', encoding='utf-8') as f:
                            si_failed_data = json.load(f)
                            # Get the all_failed_individuals from the SI pipeline
                            si_failed_individuals = si_failed_data.get('all_failed_individuals', [])
                            if si_failed_individuals:
                                failed_individuals_data.extend(si_failed_individuals)
                                logger.info(f"📊 Added {len(si_failed_individuals)} SI failed individuals from stored data")
                except Exception as e:
                    logger.error(f"Error reading SI failed individuals file: {e}")
            
            total_processed = successful + failed
            
            # Calculate total emissions
            if pipeline_type == 'viajeros':
                # For Viajeros: total emissions = successful + failed (1 emission = 1 person)
                total_emissions = successful_emissions + failed
            else:
                # For SI: count actual emissions from both success and failure files
                total_emissions = successful_emissions + failed
            
            return {
                'successful': successful,  # People count
                'successful_emissions': successful_emissions,  # Emissions count
                'failed': failed,
                'total_processed': total_processed,
                'total_emissions': total_emissions,  # Total emissions count
                'success_rate': (successful / total_processed * 100) if total_processed > 0 else 0.0,
                'pipeline_type': pipeline_type,
                'execution_time': datetime.now().isoformat(),
                'failed_individuals': failed_individuals_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting execution results for session {session_id}: {e}")
            return {'successful': 0, 'failed': 0, 'total_processed': 0}
    
    def _send_timeout_report(self, session_id: str):
        """Send timeout report when waiting period expires."""
        try:
            # Import here to avoid circular imports
            from error_handler import error_handler
            
            # Get session status to determine what happened
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT si_status, viajeros_status, si_started_at, viajeros_started_at,
                           si_completed_at, viajeros_completed_at
                    FROM pipeline_sessions 
                    WHERE session_id = ?
                """, (session_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.error(f"❌ Session {session_id} not found for timeout report")
                    return
                
                si_status, viajeros_status, si_started, viajeros_started, si_completed, viajeros_completed = result
                
                # Mark report as sent
                cursor.execute("""
                    UPDATE pipeline_sessions 
                    SET combined_report_sent = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """, (session_id,))
                conn.commit()
            
            # Determine what happened and send appropriate report
            si_active = si_started is not None and si_completed is not None
            viajeros_active = viajeros_started is not None and viajeros_completed is not None
            
            if si_active and not viajeros_active:
                # Only SI pipeline was active
                logger.info(f"⏰ Timeout reached - only SI pipeline was active, sending SI-specific report")
                from error_handler import si_error_handler
                si_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True, 
                                           error_message=f"SI pipeline completed successfully. Viajeros pipeline did not activate within {self.wait_timeout/60:.0f} minutes.")
                
            elif viajeros_active and not si_active:
                # Only Viajeros pipeline was active
                logger.info(f"⏰ Timeout reached - only Viajeros pipeline was active, sending Viajeros-specific report")
                from error_handler import viajeros_error_handler
                viajeros_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True,
                                                 error_message=f"Viajeros pipeline completed successfully. SI pipeline did not activate within {self.wait_timeout/60:.0f} minutes.")
                
            elif si_active and viajeros_active:
                # Both pipelines were active but one didn't complete
                logger.warning(f"⏰ Timeout reached - both pipelines were active but coordination failed")
                error_message = f"Pipeline coordination timeout reached ({self.wait_timeout/60:.0f} minutes). Both pipelines were active but coordination failed."
                error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)
                
            else:
                # Neither pipeline was active (shouldn't happen)
                logger.error(f"⏰ Timeout reached but no pipelines were active - this shouldn't happen")
                error_message = f"Pipeline coordination timeout reached ({self.wait_timeout/60:.0f} minutes) but no pipelines were active."
                error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)
                
        except Exception as e:
            logger.error(f"❌ Error sending timeout report for session {session_id}: {e}")
    
    def _get_email_subject_from_session(self, session_id: str, pipeline_type: str) -> str:
        """Extract email subject from session execution log."""
        try:
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT error_message FROM pipeline_executions 
                    WHERE session_id = ? AND pipeline_type = ? AND error_message LIKE 'Email subject:%'
                    ORDER BY started_at DESC LIMIT 1
                """, (session_id, pipeline_type))
                
                result = cursor.fetchone()
                if result and result[0]:
                    # Extract subject from "Email subject: Asegurados Viajeros | 2025-09-21"
                    error_message = result[0]
                    if error_message.startswith("Email subject: "):
                        return error_message[15:]  # Remove "Email subject: " prefix
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get email subject from session: {e}")
            return None

    def get_session_status(self, session_id: str) -> Dict:
        """Get current status of a pipeline session."""
        try:
            with sqlite3.connect(str(self.coordination_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT si_status, viajeros_status, si_started_at, viajeros_started_at,
                           si_completed_at, viajeros_completed_at, combined_report_sent, created_at
                    FROM pipeline_sessions 
                    WHERE session_id = ?
                """, (session_id,))
                
                result = cursor.fetchone()
                if not result:
                    return {}
                
                return {
                    'session_id': session_id,
                    'si_status': result[0],
                    'viajeros_status': result[1],
                    'si_started_at': result[2],
                    'viajeros_started_at': result[3],
                    'si_completed_at': result[4],
                    'viajeros_completed_at': result[5],
                    'combined_report_sent': result[6],
                    'created_at': result[7]
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get session status: {e}")
            return {}

# Global coordinator instance
coordinator = PipelineCoordinator()
