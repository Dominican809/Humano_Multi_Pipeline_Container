#!/usr/bin/env python3
"""
Unified Error Handling and Email Reporting Module
Handles errors, generates reports, and sends email notifications with accurate statistics.
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import resend
from loguru import logger

# Import the new statistics manager
try:
    from .statistics_manager import get_pipeline_execution_stats, get_combined_execution_stats
except ImportError:
    # Fallback if statistics_manager is not available
    def get_pipeline_execution_stats(pipeline_type: str) -> Optional[Dict]:
        return None
    def get_combined_execution_stats() -> Optional[Dict]:
        return None

class ErrorHandler:
    """Handles errors and generates reports."""
    
    def __init__(self, pipeline_type: str = None):
        self.resend_api_key = os.environ.get('RESEND_API_KEY', 're_7nu2jYdo_6zaFWM9ZdfMKM6Zcq4yrweuv')
        self.report_recipients = [
            'ismael.ramirezaybar@agassist.net'
        ]
        self.pipeline_type = pipeline_type  # 'si', 'viajeros', or None for combined
        self.logs_dir = Path('/app/logs')
        self.state_dir = Path('/state')
        
        # Set data directory based on pipeline type
        if pipeline_type == 'si':
            self.data_dir = Path('/app/si_pipeline/data')
            self.pipeline_name = "Salud Internacional (SI)"
        elif pipeline_type == 'viajeros':
            self.data_dir = Path('/app/viajeros_pipeline/data')
            self.pipeline_name = "Viajeros"
        else:
            # For combined reports, we'll check both directories
            self.data_dir = None
            self.pipeline_name = "Combined"
        
        # Initialize Resend
        resend.api_key = self.resend_api_key
    
    def check_excel_file(self, excel_path: str) -> Tuple[bool, str, int]:
        """
        Check if Excel file exists and has data.
        Returns: (is_valid, error_message, row_count)
        """
        try:
            if not os.path.exists(excel_path):
                return False, f"Excel file not found: {excel_path}", 0
            
            # Try to read the Excel file
            df = pd.read_excel(excel_path)
            
            if df.empty:
                return False, "Excel file is empty - no data rows found", 0
            
            # Pipeline-specific column validation
            if self.pipeline_type == 'si':
                required_columns = ['CODIGO_INFOPLAN', 'PRI_NOM', 'PRI_APE', 'FEC_NAC']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    return False, f"SI Excel missing required columns: {missing_columns}", len(df)
                    
            elif self.pipeline_type == 'viajeros':
                required_columns = ['FACTURA', 'PRI_NOM', 'PRI_APE', 'FEC_NAC', 'ASEGURADO']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    return False, f"Viajeros Excel missing required columns: {missing_columns}", len(df)
            else:
                # Generic validation for combined reports
                required_columns = ['nombre', 'apellido', 'cedula', 'fecha_nacimiento']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    return False, f"Missing required columns: {missing_columns}", len(df)
            
            return True, "Excel file is valid", len(df)
            
        except Exception as e:
            return False, f"Error reading Excel file: {str(e)}", 0
    
    def validate_si_comparison_result(self, comparison_file_path: str) -> Tuple[bool, str, int]:
        """
        Validate SI comparison result to check if there are new people to process.
        Returns: (has_new_people, message, new_people_count)
        """
        try:
            if not os.path.exists(comparison_file_path):
                return False, f"Comparison result file not found: {comparison_file_path}", 0
            
            # Read the comparison result Excel file
            excel_file = pd.ExcelFile(comparison_file_path)
            
            # Check if 'New in New File' sheet exists and has data
            if 'New in New File' in excel_file.sheet_names:
                new_people_df = pd.read_excel(comparison_file_path, sheet_name='New in New File')
                new_people_count = len(new_people_df)
                
                if new_people_count == 0:
                    return False, "No new people found after SI comparison - no processing needed", 0
                else:
                    return True, f"Found {new_people_count} new people to process", new_people_count
            else:
                return False, "Comparison result file missing 'New in New File' sheet", 0
                
        except Exception as e:
            return False, f"Error validating SI comparison result: {str(e)}", 0
    
    def validate_viajeros_data(self, excel_path: str) -> Tuple[bool, str, int]:
        """
        Validate Viajeros Excel data for processing.
        Returns: (is_valid, message, valid_records_count)
        """
        try:
            if not os.path.exists(excel_path):
                return False, f"Viajeros Excel file not found: {excel_path}", 0
            
            # Read Excel file
            df = pd.read_excel(excel_path, header=0)  # Viajeros uses header=0
            df.columns = df.columns.str.strip()
            
            if df.empty:
                return False, "Viajeros Excel file is empty - no data rows found", 0
            
            # Check required columns
            required_columns = ['FACTURA', 'PRI_NOM', 'PRI_APE', 'FEC_NAC', 'ASEGURADO', 'FEC_INI']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return False, f"Viajeros Excel missing required columns: {missing_columns}", 0
            
            # Filter for records after April 2025 (as per pipeline logic)
            try:
                df['fecha_inicio_dt'] = pd.to_datetime(df['FEC_INI'])
                fecha_corte = pd.to_datetime('2025-04-01')
                df_filtered = df[df['fecha_inicio_dt'] >= fecha_corte]
                valid_records = len(df_filtered)
                
                if valid_records == 0:
                    return False, "No valid Viajeros records found after April 2025 - no processing needed", 0
                else:
                    return True, f"Found {valid_records} valid Viajeros records to process", valid_records
                    
            except Exception as e:
                return False, f"Error filtering Viajeros data by date: {str(e)}", 0
                
        except Exception as e:
            return False, f"Error validating Viajeros data: {str(e)}", 0
    
    def extract_failed_data(self, date_str: str = None) -> List[Dict]:
        """Extract failed data from logs for manual handling."""
        if not date_str:
            date_str = datetime.now().strftime('%Y%m%d')
        
        failed_data = []
        
        try:
            if self.pipeline_type in ['si', 'viajeros']:
                # Single pipeline data
                failed_data = self._extract_single_pipeline_failures(date_str)
            else:
                # Combined data from both pipelines
                failed_data = self._extract_combined_pipeline_failures(date_str)
            
            return failed_data
            
        except Exception as e:
            logger.error(f"Error extracting failed data: {e}")
            return []
    
    def _extract_single_pipeline_failures(self, date_str: str) -> List[Dict]:
        """Extract failures from a single pipeline with detailed error information."""
        failed_data = []
        
        if not self.data_dir or not self.data_dir.exists():
            return failed_data
        
        # Look for failure files
        failure_files = list(self.data_dir.glob(f'tracking/failures/failures_{date_str}*.json'))
        
        for file_path in failure_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    failures_data = json.load(f)
                    
                    # Handle the EmissionTracker format: {"emisiones_fallidas": [...]}
                    if isinstance(failures_data, dict) and 'emisiones_fallidas' in failures_data:
                        failures = failures_data['emisiones_fallidas']
                    elif isinstance(failures_data, list):
                        failures = failures_data
                    else:
                        failures = [failures_data]
                    
                    # Process each failure record
                    for failure in failures:
                        # Add pipeline type and name
                        failure['pipeline_type'] = self.pipeline_type
                        failure['pipeline_name'] = self.pipeline_name
                        
                        # Ensure we have the required fields
                        if 'factura' not in failure:
                            failure['factura'] = 'Unknown'
                        if 'step' not in failure:
                            failure['step'] = 'Unknown'
                        if 'error' not in failure:
                            failure['error'] = 'Unknown error'
                        if 'num_asegurados' not in failure:
                            failure['num_asegurados'] = 0
                        
                        failed_data.append(failure)
                        
            except Exception as e:
                logger.error(f"Error reading failure file {file_path}: {e}")
        
        return failed_data
    
    def _extract_combined_pipeline_failures(self, date_str: str) -> List[Dict]:
        """Extract failures from both SI and Viajeros pipelines."""
        failed_data = []
        
        # Extract SI failures
        si_dir = Path('/app/si_pipeline/data')
        if si_dir.exists():
            # Create temporary SI handler to extract failures
            si_handler = ErrorHandler('si')
            si_failures = si_handler._extract_single_pipeline_failures(date_str)
            failed_data.extend(si_failures)
        
        # Extract Viajeros failures
        viajeros_dir = Path('/app/viajeros_pipeline/data')
        if viajeros_dir.exists():
            # Create temporary Viajeros handler to extract failures
            viajeros_handler = ErrorHandler('viajeros')
            viajeros_failures = viajeros_handler._extract_single_pipeline_failures(date_str)
            failed_data.extend(viajeros_failures)
        
        return failed_data
    
    def get_processing_stats(self, date_str: str = None) -> Dict:
        """Get processing statistics for the day."""
        if not date_str:
            date_str = datetime.now().strftime('%Y%m%d')
        
        stats = {
            'date': date_str,
            'pipeline_type': self.pipeline_type,
            'pipeline_name': self.pipeline_name,
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'success_rate': 0.0,
            'emails_received': 0,
            'excel_extracted': False,
            'pipeline_executed': False
        }
        
        try:
            # Count processed emails from database
            db_path = self.state_dir / 'processed.sqlite3'
            if db_path.exists():
                con = sqlite3.connect(str(db_path))
                cursor = con.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM processed 
                    WHERE date(ts) = date('now')
                """)
                stats['emails_received'] = cursor.fetchone()[0]
                con.close()
            
            # Handle data collection based on pipeline type
            if self.pipeline_type in ['si', 'viajeros']:
                # Single pipeline stats
                stats.update(self._get_single_pipeline_stats(date_str))
            else:
                # Combined stats from both pipelines
                stats.update(self._get_combined_pipeline_stats(date_str))
            
            stats['total_processed'] = stats['successful'] + stats['failed']
            
            if stats['total_processed'] > 0:
                stats['success_rate'] = (stats['successful'] / stats['total_processed']) * 100
            
            # Check Excel extraction based on pipeline type
            stats['excel_extracted'] = self._check_excel_extraction()
            
            # Check pipeline execution
            stats['pipeline_executed'] = self._check_pipeline_execution()
            
        except Exception as e:
            logger.error(f"Error getting processing stats: {e}")
        
        return stats
    
    def _get_single_pipeline_stats(self, date_str: str) -> Dict:
        """Get stats for a single pipeline."""
        stats = {'successful': 0, 'failed': 0}
        
        if not self.data_dir or not self.data_dir.exists():
            return stats
        
        # Count success files
        success_files = list(self.data_dir.glob(f'tracking/success/success_{date_str}*.json'))
        for file_path in success_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    success_data = json.load(f)
                    if isinstance(success_data, dict) and 'emisiones_exitosas' in success_data:
                        # Count successful emissions from the emisiones_exitosas array
                        stats['successful'] += len(success_data['emisiones_exitosas'])
                    elif isinstance(success_data, list):
                        stats['successful'] += len(success_data)
                    else:
                        stats['successful'] += 1
            except Exception as e:
                logger.error(f"Error reading success file {file_path}: {e}")
        
        # Count failure files
        failure_files = list(self.data_dir.glob(f'tracking/failures/failures_{date_str}*.json'))
        for file_path in failure_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    failure_data = json.load(f)
                    if isinstance(failure_data, dict) and 'emisiones_fallidas' in failure_data:
                        # Count failed emissions from the emisiones_fallidas array
                        stats['failed'] += len(failure_data['emisiones_fallidas'])
                    elif isinstance(failure_data, list):
                        stats['failed'] += len(failure_data)
                    else:
                        stats['failed'] += 1
            except Exception as e:
                logger.error(f"Error reading failure file {file_path}: {e}")
        
        return stats
    
    def _get_combined_pipeline_stats(self, date_str: str) -> Dict:
        """Get combined stats from both SI and Viajeros pipelines."""
        stats = {'successful': 0, 'failed': 0}
        
        # Check SI pipeline
        si_dir = Path('/app/si_pipeline/data')
        if si_dir.exists():
            # Create temporary SI handler to get stats
            si_handler = ErrorHandler('si')
            si_stats = si_handler._get_single_pipeline_stats(date_str)
            stats['successful'] += si_stats['successful']
            stats['failed'] += si_stats['failed']
        
        # Check Viajeros pipeline
        viajeros_dir = Path('/app/viajeros_pipeline/data')
        if viajeros_dir.exists():
            # Create temporary Viajeros handler to get stats
            viajeros_handler = ErrorHandler('viajeros')
            viajeros_stats = viajeros_handler._get_single_pipeline_stats(date_str)
            stats['successful'] += viajeros_stats['successful']
            stats['failed'] += viajeros_stats['failed']
        
        return stats
    
    def _check_excel_extraction(self) -> bool:
        """Check if Excel file was extracted based on pipeline type."""
        if self.pipeline_type == 'viajeros':
            excel_path = Path('/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx')
        elif self.pipeline_type == 'si':
            excel_path = Path('/app/si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx')
        else:
            # Check both for combined reports
            viajeros_excel = Path('/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx')
            si_excel = Path('/app/si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx')
            return viajeros_excel.exists() or si_excel.exists()
        
        if excel_path.exists():
            # Check if file was modified today
            file_time = datetime.fromtimestamp(excel_path.stat().st_mtime)
            today = datetime.now().date()
            return file_time.date() == today
        
        return False
    
    def _check_pipeline_execution(self) -> bool:
        """Check if pipeline was executed based on pipeline type."""
        if self.pipeline_type == 'viajeros':
            log_path = self.logs_dir / 'viajeros_emisor.log'
        elif self.pipeline_type == 'si':
            log_path = self.logs_dir / 'si_emisor.log'
        else:
            log_path = self.logs_dir / 'emisor.log'
        
        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                    return 'Pipeline completed successfully' in log_content
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
        
        return False
    
    def generate_report(self, stats: dict = None, error_message: str = None, 
                       failed_individuals: list = None) -> str:
        """Generate a comprehensive daily report."""
        
        if stats is None:
            stats = self.get_processing_stats()
        
        # Use failed_individuals if provided (from execution results), otherwise extract from tracking files
        if failed_individuals is not None:
            failed_data = failed_individuals
            logger.info(f"📊 Using provided failed individuals: {len(failed_data)} items")
        else:
            failed_data = self.extract_failed_data()
            logger.info(f"📊 Using extracted failed data: {len(failed_data)} items")
        
        # Determine overall status
        if stats['emails_received'] > 0 and stats['excel_extracted'] and stats['pipeline_executed'] and stats['failed'] == 0:
            if error_message and error_message.startswith("ℹ️"):
                status = "ℹ️ NO DATA TO PROCESS"
                status_color = "blue"
            else:
                status = "✅ SUCCESS"
                status_color = "green"
        elif stats['emails_received'] > 0 and stats['excel_extracted'] and stats['pipeline_executed']:
            status = "⚠️ PARTIAL SUCCESS"
            status_color = "orange"
        else:
            status = "❌ FAILURE"
            status_color = "red"
        
        # Generate HTML report
        html_report = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Daily Insurance Policy Processing Report - {stats['pipeline_name']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .status {{ font-size: 24px; font-weight: bold; color: {status_color}; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .pipeline-section {{ background-color: #f8f9fa; border-left: 4px solid #007bff; }}
                .si-section {{ background-color: #fff3cd; border-left: 4px solid #ffc107; }}
                .viajeros-section {{ background-color: #d1ecf1; border-left: 4px solid #17a2b8; }}
                .stats {{ display: flex; justify-content: space-around; }}
                .stat-box {{ text-align: center; padding: 10px; background-color: #f9f9f9; border-radius: 5px; }}
                .error {{ background-color: #ffe6e6; padding: 10px; border-radius: 5px; }}
                .success {{ background-color: #e6ffe6; padding: 10px; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .pipeline-badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .si-badge {{ background-color: #ffc107; color: #000; }}
                .viajeros-badge {{ background-color: #17a2b8; color: #fff; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily Insurance Policy Processing Report</h1>
                <p><strong>Pipeline:</strong> <span class="pipeline-badge {'si-badge' if stats['pipeline_type'] == 'si' else 'viajeros-badge' if stats['pipeline_type'] == 'viajeros' else ''}">{stats['pipeline_name']}</span></p>
                <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p class="status">{status}</p>
            </div>
            
            <div class="section">
                <h2>📧 Email Processing Status</h2>
                <ul>
                    <li>Email Received: {'✅ Yes' if stats['emails_received'] > 0 else '❌ No'}</li>
                    <li>Excel Extracted: {'✅ Yes' if stats['excel_extracted'] else '❌ No'}</li>
                    <li>Pipeline Executed: {'✅ Yes' if stats['pipeline_executed'] else '❌ No'}</li>
                </ul>
                {f'<div class="{"success" if error_message and error_message.startswith("ℹ️") else "error"}"><strong>{"Info" if error_message and error_message.startswith("ℹ️") else "Error"}:</strong> {error_message}</div>' if error_message else ''}
            </div>
            
            <div class="section {'si-section' if stats['pipeline_type'] == 'si' else 'viajeros-section' if stats['pipeline_type'] == 'viajeros' else 'pipeline-section'}">
                <h2>📈 Processing Statistics - {stats['pipeline_name']}</h2>
                <div class="stats">
                    <div class="stat-box">
                        <h3>{stats['total_processed']}</h3>
                        <p>{'Total Emissions' if stats['pipeline_type'] == 'viajeros' else 'Total People'}</p>
                    </div>
                    <div class="stat-box">
                        <h3>{stats['successful']}</h3>
                        <p>{'Successful Emissions' if stats['pipeline_type'] == 'viajeros' else 'Successful People'}</p>
                    </div>
                    <div class="stat-box">
                        <h3>{stats['failed']}</h3>
                        <p>{'Failed Emissions' if stats['pipeline_type'] == 'viajeros' else 'Failed People'}</p>
                    </div>
                    <div class="stat-box">
                        <h3>{stats['success_rate']:.1f}%</h3>
                        <p>Success Rate</p>
                    </div>
                    <div class="stat-box">
                        <h3>{stats.get('total_people', 0)}</h3>
                        <p>Total People</p>
                    </div>
                </div>
            </div>
        """
        
        # Add combined pipeline breakdown if this is a combined report
        if stats['pipeline_type'] is None:
            html_report += self._generate_combined_pipeline_sections()
        
        # Add failed data section if there are failures
        if failed_data:
            html_report += self._generate_failed_data_section(failed_data)
        
        # Add failed individuals section if provided
        if failed_individuals:
            html_report += f"""
            <div class="section" style="background-color: #fff3cd; border-left: 4px solid #ffc107;">
                <h2>🚨 Individuals with Active Coverage (Removed from Processing)</h2>
                <p><strong>Total Individuals Removed:</strong> {len(failed_individuals)}</p>
                <div style="margin-top: 15px;">
            """
            
            for i, individual in enumerate(failed_individuals, 1):
                name = f"{individual.get('firstname', '')} {individual.get('lastname', '')}".strip()
                passport = individual.get('passport', '')
                identity = individual.get('identity', '')
                birthdate = individual.get('birthdate', 'N/A')
                ticket_id = individual.get('ticket_id', 'N/A')
                
                html_report += f"""
                    <div style="margin-bottom: 15px; padding: 10px; background-color: #ffffff; border-radius: 5px; border: 1px solid #dee2e6;">
                        <h4 style="margin-top: 0; color: #856404;">Individual #{i}</h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div>
                                <strong>Name:</strong> {name}<br>
                                <strong>Birth Date:</strong> {birthdate}
                            </div>
                            <div>
                                {f'<strong>Passport:</strong> {passport}<br>' if passport else ''}
                                {f'<strong>Identity:</strong> {identity}<br>' if identity else ''}
                                <strong>Ticket ID:</strong> {ticket_id}
                            </div>
                        </div>
                    </div>
                """
            
            html_report += """
                </div>
            </div>
            """
        
        html_report += f"""
            <div class="section">
                <h2>🔧 System Information</h2>
                <ul>
                    <li><strong>System:</strong> Humano Insurance Policy Automation Pipeline</li>
                    <li><strong>Pipeline Type:</strong> {stats['pipeline_name']}</li>
                    <li><strong>Environment:</strong> Docker Container</li>
                    <li><strong>Report Generated:</strong> """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return html_report
    
    def _generate_combined_pipeline_sections(self) -> str:
        """Generate sections for combined pipeline reports."""
        html_sections = ""
        
        # Get individual pipeline stats
        si_handler = ErrorHandler('si')
        viajeros_handler = ErrorHandler('viajeros')
        
        si_stats = si_handler.get_processing_stats()
        viajeros_stats = viajeros_handler.get_processing_stats()
        
        # SI Pipeline Section
        html_sections += f"""
            <div class="section si-section">
                <h2>🏥 Salud Internacional (SI) Pipeline</h2>
                <div class="stats">
                    <div class="stat-box">
                        <h3>{si_stats['total_processed']}</h3>
                        <p>Total Processed</p>
                    </div>
                    <div class="stat-box">
                        <h3>{si_stats['successful']}</h3>
                        <p>Successful</p>
                    </div>
                    <div class="stat-box">
                        <h3>{si_stats['failed']}</h3>
                        <p>Failed</p>
                    </div>
                    <div class="stat-box">
                        <h3>{si_stats['success_rate']:.1f}%</h3>
                        <p>Success Rate</p>
                    </div>
                </div>
            </div>
        """
        
        # Viajeros Pipeline Section
        html_sections += f"""
            <div class="section viajeros-section">
                <h2>✈️ Viajeros Pipeline</h2>
                <div class="stats">
                    <div class="stat-box">
                        <h3>{viajeros_stats['total_processed']}</h3>
                        <p>Total Processed</p>
                    </div>
                    <div class="stat-box">
                        <h3>{viajeros_stats['successful']}</h3>
                        <p>Successful</p>
                    </div>
                    <div class="stat-box">
                        <h3>{viajeros_stats['failed']}</h3>
                        <p>Failed</p>
                    </div>
                    <div class="stat-box">
                        <h3>{viajeros_stats['success_rate']:.1f}%</h3>
                        <p>Success Rate</p>
                    </div>
                </div>
            </div>
        """
        
        return html_sections
    
    def _generate_failed_data_section(self, failed_data: List[Dict]) -> str:
        """Generate the failed data section with detailed failure information from EmissionTracker."""
        if not failed_data:
            return """
            <div class="section">
                <h2>✅ No Failed Records</h2>
                <p>All records were processed successfully!</p>
            </div>
            """
        
        # Check if this is individual-level data (from failed_individuals) or emission-level data
        is_individual_data = any('firstname' in item or 'passport' in item for item in failed_data)
        
        if is_individual_data:
            # This is individual-level data, count unique emissions/facturas
            unique_emissions = set()
            for item in failed_data:
                if 'ticket_id' in item:
                    unique_emissions.add(item['ticket_id'])
            
            html_section = f"""
            <div class="section">
                <h2>❌ Failed Emissions (Manual Handling Required)</h2>
                <p><strong>Total Failed Emissions:</strong> {len(unique_emissions)}</p>
                <p><strong>Total Failed People:</strong> {len(failed_data)}</p>
        """
        else:
            # This is emission-level data
            html_section = f"""
            <div class="section">
                <h2>❌ Failed Emissions (Manual Handling Required)</h2>
                <p><strong>Total Failed Emissions:</strong> {len(failed_data)}</p>
        """
        
        # Group failures by pipeline type
        si_failures = [f for f in failed_data if f.get('pipeline_type') == 'si']
        viajeros_failures = [f for f in failed_data if f.get('pipeline_type') == 'viajeros']
        
        # Show detailed failure information
        for i, failure in enumerate(failed_data):  # Show all failures
            factura = failure.get('factura', 'Unknown')
            step = failure.get('step', 'Unknown')
            error = failure.get('error', 'Unknown error')
            num_asegurados = failure.get('num_asegurados', 0)
            pipeline_name = failure.get('pipeline_name', 'Unknown')
            pipeline_type = failure.get('pipeline_type', 'unknown')
            
            # Get error details if available
            error_details = failure.get('error_details', {})
            status_code = error_details.get('status_code', 'N/A')
            validation_codes = error_details.get('validation_codes', [])
            validation_messages = error_details.get('validation_messages', [])
            api_response = error_details.get('api_response', {})
            
            # Extract individuals with active coverage if available
            individuals_with_active_coverage = []
            if api_response and 'found' in api_response and api_response['found']:
                individuals_with_active_coverage = api_response['found']
            
            # Determine badge class
            badge_class = 'si-badge' if pipeline_type == 'si' else 'viajeros-badge' if pipeline_type == 'viajeros' else ''
            
            html_section += f"""
                <div class="failure-detail" style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #e74c3c; background-color: #fdf2f2;">
                    <h3 style="margin-top: 0; color: #e74c3c;">
                        <span class="pipeline-badge {badge_class}">{pipeline_name}</span>
                        Factura: {factura}
                    </h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 10px;">
                        <div>
                            <strong>Error Step:</strong> {step}<br>
                            <strong>Error Message:</strong> {error}<br>
                            <strong>Affected People:</strong> {num_asegurados}
                        </div>
                        <div>
                            <strong>Status Code:</strong> {status_code}<br>
                            <strong>Validation Codes:</strong> {', '.join(map(str, validation_codes)) if validation_codes else 'N/A'}
                        </div>
                    </div>
            """
            
            # Add validation messages if available
            if validation_messages:
                html_section += f"""
                    <div style="margin-top: 10px;">
                        <strong>Validation Messages:</strong>
                        <ul style="margin: 5px 0;">
                """
                for msg in validation_messages:
                    html_section += f"<li>{msg}</li>"
                html_section += """
                        </ul>
                    </div>
                """
            
            # For Viajeros pipeline, show all people in the factura with differentiation
            if pipeline_type == 'viajeros' and 'all_people' in failure:
                all_people = failure['all_people']
                people_with_active_coverage = failure.get('people_with_active_coverage', [])
                
                html_section += f"""
                    <div style="margin-top: 15px; padding: 10px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">
                        <strong style="color: #495057;">👥 Todas las Personas en la Factura ({len(all_people)} personas):</strong>
                        <div style="margin-top: 8px;">
                """
                
                for person in all_people:
                    name = f"{person.get('firstname', '')} {person.get('lastname', '')}".strip()
                    passport = person.get('passport', '')
                    identity = person.get('identity', '')
                    birthdate = person.get('birthdate', 'N/A')
                    ticket_id = person.get('ticket_id', '')
                    status = person.get('status', 'failed')
                    
                    # Different styling based on status
                    if status == 'active_coverage':
                        bg_color = '#fff3cd'
                        border_color = '#ffeaa7'
                        status_text = '🚨 Cobertura Activa'
                        text_color = '#856404'
                    else:
                        bg_color = '#d1ecf1'
                        border_color = '#bee5eb'
                        status_text = '✅ Sin Cobertura Activa'
                        text_color = '#0c5460'
                    
                    html_section += f"""
                            <div style="margin-bottom: 8px; padding: 8px; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 3px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                                    <strong style="color: {text_color};">{status_text}</strong>
                                </div>
                                <strong>Nombre:</strong> {name}<br>
                                {f'<strong>Pasaporte:</strong> {passport}<br>' if passport else ''}
                                {f'<strong>Cédula:</strong> {identity}<br>' if identity else ''}
                                <strong>Fecha de nacimiento:</strong> {birthdate}<br>
                                {f'<strong>Ticket ID:</strong> {ticket_id}<br>' if ticket_id else ''}
                            </div>
                    """
                
                html_section += """
                        </div>
                    </div>
                """
            
            # For other pipelines or if all_people not available, show only individuals with active coverage
            elif individuals_with_active_coverage:
                html_section += f"""
                    <div style="margin-top: 15px; padding: 10px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px;">
                        <strong style="color: #856404;">🚨 Personas con Cobertura Activa:</strong>
                        <div style="margin-top: 8px;">
                """
                for person in individuals_with_active_coverage:
                    name = f"{person.get('firstname', '')} {person.get('lastname', '')}".strip()
                    passport = person.get('passport', '')
                    identity = person.get('identity', '')
                    birthdate = person.get('birthdate', 'N/A')
                    ticket_id = person.get('ticket_id', 'N/A')
                    
                    html_section += f"""
                            <div style="margin-bottom: 8px; padding: 8px; background-color: #ffffff; border-radius: 3px;">
                                <strong>Nombre:</strong> {name}<br>
                                {f'<strong>Pasaporte:</strong> {passport}<br>' if passport else ''}
                                {f'<strong>Cédula:</strong> {identity}<br>' if identity else ''}
                                <strong>Fecha de nacimiento:</strong> {birthdate}<br>
                                <strong>Ticket ID:</strong> {ticket_id}
                            </div>
                    """
                
                html_section += """
                        </div>
                    </div>
                """
            
            # Add API response details if available
            if api_response and isinstance(api_response, dict):
                message = api_response.get('message', '')
                if message:
                    html_section += f"""
                        <div style="margin-top: 10px;">
                            <strong>API Response:</strong> {message}
                        </div>
                    """
                
                # Show found people if available (for validation errors)
                found_people = api_response.get('found', [])
                if found_people and len(found_people) > 0:
                    html_section += f"""
                        <div style="margin-top: 10px;">
                            <strong>People with Active Coverage ({len(found_people)}):</strong>
                            <div style="max-height: 150px; overflow-y: auto; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
                    """
                    for person in found_people[:5]:  # Show first 5 people
                        name = f"{person.get('firstname', '')} {person.get('lastname', '')}".strip()
                        identity = person.get('identity', 'N/A')
                        html_section += f'<div style="margin-bottom: 5px;">• {name} (ID: {identity})</div>'
                    
                    if len(found_people) > 5:
                        html_section += f'<div style="font-style: italic;">... and {len(found_people) - 5} more</div>'
                    
                    html_section += """
                            </div>
                        </div>
                    """
            
            html_section += """
                </div>
            """
        
        # Add summary if there are more failures
        if len(failed_data) > 10:
            html_section += f"""
                <div style="margin-top: 15px; padding: 10px; background-color: #fff3cd; border-radius: 4px;">
                    <strong>Note:</strong> Showing first 10 failed emissions. Total failures: {len(failed_data)}. 
                    Check the tracking files for complete details.
                </div>
            """
        
        # Add pipeline-specific failure counts if this is a combined report
        if self.pipeline_type is None:
            html_section += f"""
                <div style="margin-top: 15px;">
                    <h3>Pipeline Breakdown:</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div style="padding: 10px; background-color: #e8f4fd; border-radius: 4px;">
                            <strong>SI Pipeline:</strong> {len(si_failures)} failures
                        </div>
                        <div style="padding: 10px; background-color: #e8f4fd; border-radius: 4px;">
                            <strong>Viajeros Pipeline:</strong> {len(viajeros_failures)} failures
                        </div>
                    </div>
                </div>
            """
        
        html_section += """
            </div>
        """
        
        return html_section
    
    def get_current_process_failed_data(self):
        """Get failed data from current process only (not historical)."""
        try:
            if self.pipeline_type == 'si':
                # For SI, use the latest_failed_individuals.json file
                failed_individuals_file = '/app/si_pipeline/data/latest_failed_individuals.json'
                if os.path.exists(failed_individuals_file) and os.path.getsize(failed_individuals_file) > 0:
                    with open(failed_individuals_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return data.get('all_failed_individuals', [])
                
            elif self.pipeline_type == 'viajeros':
                # For Viajeros, use the latest_detailed_failures.json file
                failed_data_file = '/app/viajeros_pipeline/data/latest_detailed_failures.json'
                if os.path.exists(failed_data_file) and os.path.getsize(failed_data_file) > 0:
                    with open(failed_data_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            
            logger.info(f"📊 No current process failed data found for {self.pipeline_type}")
            return []
            
        except Exception as e:
            logger.error(f"Error reading current process failed data: {e}")
            return []
    
    def get_si_failed_individuals_data(self):
        """Get failed individuals data from SI pipeline for current process only."""
        try:
            # Only use the latest_failed_individuals.json file for current process
            failed_individuals_file = '/app/si_pipeline/data/latest_failed_individuals.json'
            if os.path.exists(failed_individuals_file) and os.path.getsize(failed_individuals_file) > 0:
                with open(failed_individuals_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Only return failed individuals from the current process run
                current_failed_individuals = data.get('all_failed_individuals', [])
                logger.info(f"📊 Found {len(current_failed_individuals)} failed individuals from current process")
                return current_failed_individuals
            
            logger.info("📊 No failed individuals data found for current process")
            return []
            
        except Exception as e:
            logger.error(f"Error reading SI failed individuals data: {e}")
            return []
    
    def send_unified_pipeline_report(self, pipeline_type: str, email_subject: str = None, 
                                   error_message: str = None) -> bool:
        """Send a single unified report for a pipeline run with accurate statistics."""
        try:
            logger.info(f"📧 Generating unified report for {pipeline_type} pipeline")
            
            # Get the latest execution statistics
            execution_stats = get_pipeline_execution_stats(pipeline_type)
            
            if not execution_stats:
                logger.error(f"❌ No execution statistics found for {pipeline_type}")
                return False
            
            # Extract key statistics - use emissions for Viajeros, people for SI
            if pipeline_type == 'viajeros':
                # For Viajeros, use emissions-based statistics
                successful = execution_stats.get('emisiones', {}).get('exitosas', 0)
                failed = execution_stats.get('emisiones', {}).get('fallidas', 0)
                total_processed = execution_stats.get('emisiones', {}).get('total', 0)
                success_rate = (successful / total_processed * 100) if total_processed > 0 else 0.0
                logger.info(f"📊 {pipeline_type} execution stats: {successful} successful emissions, {failed} failed emissions, {total_processed} total emissions")
            else:
                # For SI, use people-based statistics
                successful = execution_stats.get('successful', 0)
                failed = execution_stats.get('failed', 0)
                total_processed = execution_stats.get('total_processed', 0)
                success_rate = execution_stats.get('success_rate', 0.0)
                logger.info(f"📊 {pipeline_type} execution stats: {successful} successful people, {failed} failed people, {total_processed} total people")
            
            # Determine pipeline name
            pipeline_name = "Salud Internacional (SI)" if pipeline_type == 'si' else "Viajeros"
            
            # Create statistics for email
            stats = {
                'date': execution_stats.get('run_date', datetime.now().strftime('%Y%m%d')),
                'pipeline_type': pipeline_type,
                'pipeline_name': pipeline_name,
                'total_processed': total_processed,
                'successful': successful,
                'failed': failed,
                'success_rate': success_rate,
                'total_people': execution_stats.get('asegurados', {}).get('total', 0) if pipeline_type == 'viajeros' else total_processed,
                'emails_received': 1,
                'excel_extracted': True,
                'pipeline_executed': True,
                'run_time': execution_stats.get('run_time', 'Unknown'),
                'run_timestamp': execution_stats.get('run_timestamp', datetime.now().isoformat())
            }
            
            # Get failed individuals if available
            failed_individuals = None
            if pipeline_type == 'si':
                failed_individuals = self.get_si_failed_individuals_data()
            else:
                # For Viajeros and other pipelines, get current process failed data
                failed_individuals = self.get_current_process_failed_data()
            
            # Generate and send the report
            return self._send_email_report(stats, error_message, email_subject, failed_individuals)
            
        except Exception as e:
            logger.error(f"❌ Error sending unified {pipeline_type} report: {e}")
            return False

    def _send_email_report(self, stats: dict, error_message: str = None, 
                          email_subject: str = None, failed_individuals: list = None) -> bool:
        """Send the email report using provided statistics."""
        try:
            # For SI pipeline, automatically get failed individuals if not provided
            if self.pipeline_type == 'si' and failed_individuals is None:
                failed_individuals = self.get_si_failed_individuals_data()
                if failed_individuals:
                    logger.info(f"Found {len(failed_individuals)} failed individuals for SI pipeline")
            
            # Generate the report content
            html_report = self.generate_report(stats, error_message, failed_individuals)
            
            # Determine subject line with pipeline type and email subject
            pipeline_prefix = f"[{stats['pipeline_name']}] " if stats['pipeline_type'] else ""
            
            # Include original email subject if available
            email_info = f" - {email_subject}" if email_subject else ""
            
            if stats['emails_received'] > 0 and stats['excel_extracted'] and stats['pipeline_executed'] and stats['failed'] == 0:
                subject = f"✅ {pipeline_prefix}Daily Report - {stats['successful']} policies processed successfully{email_info}"
            elif stats['emails_received'] > 0 and stats['excel_extracted'] and stats['pipeline_executed']:
                subject = f"⚠️ {pipeline_prefix}Daily Report - {stats['successful']} successful, {stats['failed']} failed{email_info}"
            else:
                subject = f"❌ {pipeline_prefix}Daily Report - Processing failed{email_info}"
            
            # Send the email
            return self._send_email(subject, html_report)
            
        except Exception as e:
            logger.error(f"❌ Error in _send_email_report: {e}")
            return False

    def _send_email(self, subject: str, html_content: str) -> bool:
        """Send email using Resend API."""
        try:
            # Send email using verified angelguardassist.com domain
            params = {
                "from": "info@angelguardassist.com",
                "to": self.report_recipients,
                "subject": f"[Humano Insurance] {subject}",
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            # Handle different response formats
            if hasattr(email, 'id'):
                email_id = email.id
            elif isinstance(email, dict) and 'id' in email:
                email_id = email['id']
            else:
                email_id = 'unknown'
            
            logger.info(f"📧 Daily report sent successfully. Email ID: {email_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            return False

    def send_report(self, email_received: bool = True, excel_extracted: bool = True, 
                   pipeline_success: bool = True, error_message: str = None, 
                   email_subject: str = None, failed_individuals: list = None) -> bool:
        """Send the daily report via email using daily statistics."""
        try:
            stats = self.get_processing_stats()
            return self._send_email_report(stats, error_message, email_subject, failed_individuals)
            
        except Exception as e:
            logger.error(f"❌ Error sending report: {e}")
            return False
    
    def handle_error(self, error_type: str, error_message: str, context: Dict = None) -> bool:
        """Handle errors and send appropriate notifications."""
        
        logger.error(f"🚨 Error Type: {error_type}, Message: {error_message}")
        
        # Determine what failed based on error type
        email_received = error_type not in ['email_connection', 'email_processing']
        excel_extracted = error_type not in ['email_connection', 'email_processing', 'excel_extraction']
        pipeline_success = error_type not in ['email_connection', 'email_processing', 'excel_extraction', 'pipeline_execution']
        
        # Special handling for "no data" cases - these are not failures
        if error_type == 'no_new_data':
            logger.info(f"ℹ️ No new data to process: {error_message}")
            # Send success report with informational message
            return self.send_report(email_received=True, excel_extracted=True, pipeline_success=True, error_message=f"ℹ️ {error_message}")
        
        # Send error report
        return self.send_report(email_received, excel_extracted, pipeline_success, error_message)

# Global error handler instances
error_handler = ErrorHandler()  # Default combined handler
si_error_handler = ErrorHandler('si')
viajeros_error_handler = ErrorHandler('viajeros')

# Pipeline-aware reporting functions
def send_pipeline_success_report(pipeline_type: str) -> bool:
    """Send success report for specific pipeline."""
    if pipeline_type == 'si':
        return si_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True)
    elif pipeline_type == 'viajeros':
        return viajeros_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True)
    else:
        return error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True)

def send_pipeline_failure_report(pipeline_type: str, error_message: str) -> bool:
    """Send failure report for specific pipeline."""
    if pipeline_type == 'si':
        return si_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)
    elif pipeline_type == 'viajeros':
        return viajeros_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)
    else:
        return error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)

def check_pipeline_excel_and_report(pipeline_type: str) -> Tuple[bool, str]:
    """Check Excel file and generate report for specific pipeline."""
    if pipeline_type == 'si':
        handler = si_error_handler
        
        # For SI, check if comparison result file exists and has data
        comparison_path = "/app/si_pipeline/Comparador_Humano/exceles/comparison_result.xlsx"
        has_new_people, comparison_message, new_people_count = handler.validate_si_comparison_result(comparison_path)
        
        if not has_new_people:
            logger.warning(f"⚠️ SI comparison validation: {comparison_message}")
            # This is not an error, just no new people to process
            handler.handle_error('no_new_data', comparison_message)
            return False, comparison_message
        
        logger.info(f"✅ SI Excel validated successfully: {new_people_count} new people to process")
        return True, ""
        
    elif pipeline_type == 'viajeros':
        excel_path = "/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx"
        handler = viajeros_error_handler
        
        # Use specialized Viajeros validation
        is_valid, error_message, valid_records = handler.validate_viajeros_data(excel_path)
        
        if not is_valid:
            logger.error(f"❌ Viajeros Excel validation failed: {error_message}")
            handler.handle_error('excel_validation', error_message)
            return False, error_message
        
        logger.info(f"✅ Viajeros Excel validated successfully: {valid_records} valid records to process")
        return True, ""
        
    else:
        excel_path = "/app/viajeros_pipeline/Exceles/Rep_Afiliados_Seguro_Viajero 16 06 2025 AL 02 07 2025.xlsx"
        handler = error_handler
        
        is_valid, error_message, row_count = handler.check_excel_file(excel_path)
        
        if not is_valid:
            logger.error(f"❌ Excel validation failed for {pipeline_type}: {error_message}")
            handler.handle_error('excel_validation', error_message)
            return False, error_message
        
        logger.info(f"✅ Excel file validated successfully for {pipeline_type}: {row_count} rows found")
        return True, ""

def check_excel_and_report() -> Tuple[bool, str]:
    """Check Excel file and generate report. Returns (is_valid, error_message)."""
    excel_path = "/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx"
    
    is_valid, error_message, row_count = error_handler.check_excel_file(excel_path)
    
    if not is_valid:
        logger.error(f"❌ Excel validation failed: {error_message}")
        error_handler.handle_error('excel_validation', error_message)
        
        # Send specific report for empty Excel file
        if "empty" in error_message.lower():
            logger.info("📧 Sending empty Excel file report")
            error_handler.send_report(
                email_received=True, 
                excel_extracted=True, 
                pipeline_success=False, 
                error_message="Excel file received but contains no data rows"
            )
        
        return False, error_message
    
    logger.info(f"✅ Excel file validated successfully: {row_count} rows found")
    return True, ""

def send_success_report() -> bool:
    """Send success report after successful processing."""
    return error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True)

def send_failure_report(error_message: str) -> bool:
    """Send failure report after failed processing."""
    return error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=False, error_message=error_message)
