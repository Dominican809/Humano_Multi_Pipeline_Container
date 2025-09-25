#!/usr/bin/env python3
"""
Email watcher service for Goval insurance policy automation pipeline.
Monitors IMAP mailbox for trigger emails and runs the existing pipeline.
"""

import os
import time
import email
import re
import sqlite3
import datetime as dt
from imapclient import IMAPClient
from email.header import decode_header
from zoneinfo import ZoneInfo
from subprocess import run
import logging
import mimetypes
from pathlib import Path
import sys

# Import error handling and reporting
try:
    from error_handler import check_excel_and_report, send_success_report, send_failure_report, error_handler
    from shared.error_handler import send_pipeline_success_report, send_pipeline_failure_report, check_pipeline_excel_and_report
except ImportError:
    # Fallback if error_handler is not available
    def check_excel_and_report():
        return True, ""
    
    def send_success_report():
        return True
    
    def send_failure_report(error_message):
        return True
    
    def send_pipeline_success_report(pipeline_type):
        return True
    
    def send_pipeline_failure_report(pipeline_type, error_message):
        return True
    
    def check_pipeline_excel_and_report(pipeline_type):
        return True, ""
    
    class DummyErrorHandler:
        def handle_error(self, error_type, error_message, context=None):
            return True
    
    error_handler = DummyErrorHandler()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
IMAP_HOST = os.environ["IMAP_HOST"]
IMAP_USER = os.environ["IMAP_USER"]
IMAP_PASS = os.environ["IMAP_PASS"]
IMAP_FOLDER = os.environ.get("IMAP_FOLDER", "INBOX")
USE_SSL = os.environ.get("IMAP_SSL", "true").lower() == "true"
PORT = int(os.environ.get("IMAP_PORT", "993" if USE_SSL else "143"))

MATCH_SUBJECT_REGEX = os.environ.get("MATCH_SUBJECT_REGEX", r"(?i)^run pipeline|^trigger|^execute")
MATCH_FROM_REGEX = os.environ.get("MATCH_FROM_REGEX", r".*")
ALLOWED_HOURS = os.environ.get("ALLOWED_HOURS", "00-23")
ALLOWED_DAYS = os.environ.get("ALLOWED_DAYS", "mon,tue,wed,thu,fri")
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Madrid"))
PIPELINE_CMD = os.environ.get("PIPELINE_CMD", "bash /app/run_pipeline.sh")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SEC", "0"))  # 0 => prefer IDLE
STATE_DB = os.environ.get("STATE_DB", "/state/processed.sqlite3")

# Compile regex patterns
subj_re = re.compile(MATCH_SUBJECT_REGEX)
from_re = re.compile(MATCH_FROM_REGEX)

def ensure_db():
    """Create SQLite database for tracking processed emails."""
    os.makedirs(os.path.dirname(STATE_DB), exist_ok=True)
    con = sqlite3.connect(STATE_DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS processed (
        message_id TEXT PRIMARY KEY,
        ts INTEGER,
        subject TEXT,
        from_addr TEXT
    )""")
    con.commit()
    return con

def decoded(hdr):
    """Decode email header with proper encoding handling."""
    if not hdr:
        return ""
    parts = decode_header(hdr)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(txt)
    return "".join(out)

def allowed_now():
    """Check if current time is within allowed hours and days."""
    now = dt.datetime.now(TZ)
    
    # Check allowed days
    if ALLOWED_DAYS.lower() != "all":
        days = [d.strip().lower() for d in ALLOWED_DAYS.split(",")]
        if now.strftime("%a").lower()[:3] not in days:
            logger.info(f"[watcher] Outside allowed days. Current day: {now.strftime('%A')}")
            return False
    
    # Check allowed hours
    start, end = ALLOWED_HOURS.split("-")
    s, e = int(start), int(end)
    if not (s <= now.hour <= e):
        logger.info(f"[watcher] Outside allowed hours. Current hour: {now.hour}")
        return False
    
    return True

def message_id_of(msg):
    """Extract Message-ID from email."""
    return (msg.get("Message-ID") or "").strip()

def already_done(con, mid):
    """Check if email has already been processed."""
    if not mid:
        return False
    cur = con.cursor()
    cur.execute("SELECT 1 FROM processed WHERE message_id=?", (mid,))
    return cur.fetchone() is not None

def mark_done(con, mid, subject="", from_addr=""):
    """Mark email as processed."""
    if not mid:
        return
    cur = con.cursor()
    cur.execute("""INSERT OR IGNORE INTO processed(message_id, ts, subject, from_addr) 
                   VALUES(?, ?, ?, ?)""",
                (mid, int(time.time()), subject, from_addr))
    con.commit()

def should_trigger(msg):
    """Check if email matches trigger criteria."""
    subj = decoded(msg.get("Subject", ""))
    from_ = decoded(msg.get("From", ""))
    
    subject_match = bool(subj_re.search(subj))
    from_match = bool(from_re.search(from_))
    
    logger.info(f"[watcher] Email check - Subject: '{subj}' (match: {subject_match}), From: '{from_}' (match: {from_match})")
    
    return subject_match and from_match

def extract_excel_attachment(msg):
    """Extract Excel attachment from email message."""
    excel_files = []
    
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            filename = part.get_filename()
            if filename:
                # Decode filename if it's encoded
                filename = decoded(filename)
                
                # Check if it's an Excel file
                if filename.lower().endswith(('.xlsx', '.xls')):
                    logger.info(f"[watcher] Found Excel attachment: {filename}")
                    
                    # Get file content
                    content = part.get_payload(decode=True)
                    if content:
                        excel_files.append({
                            'filename': filename,
                            'content': content
                        })
                        logger.info(f"[watcher] Extracted Excel file: {filename} ({len(content)} bytes)")
    
    return excel_files

def save_excel_file(excel_data, target_path):
    """Save Excel file to target path with conflict handling."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Check if file already exists and create backup
        if os.path.exists(target_path):
            backup_path = f"{target_path}.backup_{int(time.time())}"
            logger.info(f"[watcher] ⚠️  File exists, creating backup: {backup_path}")
            os.rename(target_path, backup_path)
        
        # Write file
        with open(target_path, 'wb') as f:
            f.write(excel_data['content'])
        
        logger.info(f"[watcher] Saved Excel file to: {target_path}")
        return True
    except Exception as e:
        logger.error(f"[watcher] Error saving Excel file: {e}")
        return False

def process_email_attachments(msg):
    """Process email attachments and save Excel files."""
    logger.info("[watcher] 📎 Starting attachment processing...")
    excel_files = extract_excel_attachment(msg)
    
    if not excel_files:
        logger.warning("[watcher] ⚠️  No Excel attachments found in email")
        error_handler.handle_error('excel_extraction', 'No Excel attachments found in email')
        return False
    
    logger.info(f"[watcher] 📎 Found {len(excel_files)} Excel attachments")
    
    # Detect pipeline type from email subject
    subject = decoded(msg.get("Subject", ""))
    from_addr = decoded(msg.get("From", ""))
    
    # Import pipeline manager
    sys.path.append('/app')
    from pipeline_manager import detect_pipeline_type, process_email
    
    pipeline_type = detect_pipeline_type(subject, from_addr)
    
    if pipeline_type == "unknown":
        logger.error(f"[watcher] ❌ Unknown pipeline type for subject: {subject}")
        error_handler.handle_error('pipeline_detection', f'Unknown pipeline type for subject: {subject}')
        return False
    
    # Find the appropriate Excel file based on pipeline type
    target_file = None
    for excel_file in excel_files:
        filename = excel_file['filename']
        logger.info(f"[watcher] 📎 Checking attachment: {filename}")
        
        if pipeline_type == "viajeros" and 'Asegurados_Viajeros' in filename:
            target_file = excel_file
            logger.info(f"[watcher] 🎯 Found Viajeros file: {filename}")
            break
        elif pipeline_type == "si" and 'Asegurados_SI' in filename:
            target_file = excel_file
            logger.info(f"[watcher] 🎯 Found SI file: {filename}")
            break
    
    if not target_file:
        logger.warning(f"[watcher] ⚠️  No matching Excel file found for {pipeline_type} pipeline")
        logger.info(f"[watcher] 📎 Available files: {[f['filename'] for f in excel_files]}")
        error_handler.handle_error('excel_extraction', f'No matching Excel file found for {pipeline_type} pipeline. Available: {[f["filename"] for f in excel_files]}')
        return False
    
    # Save to temporary location for pipeline manager
    temp_path = f"/tmp/{target_file['filename']}"
    logger.info(f"[watcher] 💾 Saving file to: {temp_path}")
    success = save_excel_file(target_file, temp_path)
    
    if success:
        logger.info(f"[watcher] ✅ Successfully saved Excel file: {temp_path}")
        logger.info(f"[watcher] 📊 File size: {len(target_file['content'])} bytes")
        
        # Use pipeline manager to process the email
        logger.info(f"[watcher] 🚀 Routing to {pipeline_type} pipeline...")
        try:
            process_email(pipeline_type, temp_path, subject)
            logger.info(f"[watcher] ✅ Pipeline {pipeline_type} execution completed")
        except Exception as e:
            logger.error(f"[watcher] ❌ Pipeline {pipeline_type} execution failed: {e}")
            import traceback
            logger.error(f"[watcher] Traceback: {traceback.format_exc()}")
            return False
        
        return True
    else:
        logger.error("[watcher] ❌ Failed to save Excel file")
        error_handler.handle_error('excel_extraction', 'Failed to save Excel file to temporary location')
        return False

def run_pipeline():
    """Execute the pipeline command."""
    logger.info(f"[watcher] Running pipeline: {PIPELINE_CMD}")
    try:
        result = run(PIPELINE_CMD, shell=True, capture_output=True, text=True)
        logger.info(f"[watcher] Pipeline stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"[watcher] Pipeline stderr: {result.stderr}")
        logger.info(f"[watcher] Pipeline exit code: {result.returncode}")
        
        # Send appropriate report based on pipeline result
        if result.returncode == 0:
            logger.info("[watcher] 🎉 Pipeline completed successfully - sending success report")
            # Use the legacy function for backward compatibility
            send_success_report()
        else:
            logger.error(f"[watcher] ❌ Pipeline failed with exit code {result.returncode} - sending failure report")
            # Use the legacy function for backward compatibility
            send_failure_report(f"Pipeline execution failed with exit code {result.returncode}. Stderr: {result.stderr}")
        
        return result.returncode
    except Exception as e:
        logger.error(f"[watcher] Pipeline execution error: {e}")
        # Use the legacy function for backward compatibility
        send_failure_report(f"Pipeline execution error: {str(e)}")
        return 1

def extract_date_from_subject(subject):
    """Extract date from email subject for ordering.
    
    Expected format: 'Asegurados Viajeros | 2025-09-21' or 'Asegurados Salud Internacional | 2025-09-21'
    """
    import re
    from datetime import datetime
    
    # Look for the specific pattern: | YYYY-MM-DD (with optional spaces)
    date_pattern = r'\|\s*(\d{4}-\d{2}-\d{2})'
    
    match = re.search(date_pattern, subject)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            logger.warning(f"[watcher] ⚠️  Invalid date format in subject: {date_str}")
            return datetime.now()
    
    # If no date found, return current time (will be processed last)
    logger.warning(f"[watcher] ⚠️  No date found in subject: {subject}")
    return datetime.now()

def process_new_unseen(client, con):
    """Process new unseen emails - handle multiple emails with date-based ordering."""
    try:
        unseen_uids = client.search(["UNSEEN"])
        logger.info(f"[watcher] Found {len(unseen_uids)} unseen emails")
        
        if not unseen_uids:
            logger.info("[watcher] No unseen emails to process")
            return
        
        # Process all unseen emails to handle simultaneous arrivals
        emails_to_process = []
        
        for uid in unseen_uids:
            try:
                logger.info(f"[watcher] 📧 Fetching email UID {uid}")
                raw = client.fetch([uid], ["RFC822"])[uid][b"RFC822"]
                msg = email.message_from_bytes(raw)
                mid = message_id_of(msg)
                
                # Log email details
                subject = decoded(msg.get("Subject", ""))
                from_addr = decoded(msg.get("From", ""))
                date = msg.get("Date", "")
                logger.info(f"[watcher] 📧 Email details - Subject: '{subject}', From: '{from_addr}', Date: '{date}', Message-ID: '{mid}'")
                
                if already_done(con, mid):
                    logger.info(f"[watcher] ⚠️  Email {mid} already processed, skipping")
                    continue
                
                logger.info(f"[watcher] 🔍 Checking if email matches trigger criteria...")
                if not should_trigger(msg):
                    logger.info(f"[watcher] ❌ Email {mid} doesn't match trigger criteria, skipping")
                    continue
                
                logger.info(f"[watcher] ✅ Email matches trigger criteria!")
                
                logger.info(f"[watcher] 🕐 Checking if current time is within allowed window...")
                if not allowed_now():
                    logger.info(f"[watcher] ⚠️  Matched email but outside allowed window, skipping")
                    continue
                
                logger.info(f"[watcher] ✅ Time window check passed")
                
                # Extract date from subject for ordering
                subject_date = extract_date_from_subject(subject)
                
                # Add to processing queue with date information
                emails_to_process.append({
                    'uid': uid,
                    'msg': msg,
                    'subject': subject,
                    'from_addr': from_addr,
                    'mid': mid,
                    'subject_date': subject_date
                })
                
            except Exception as e:
                logger.error(f"[watcher] ❌ Error processing email {uid}: {e}")
                continue
        
        if not emails_to_process:
            logger.info(f"[watcher] 📭 No valid emails to process")
            return
        
        # Sort emails by date (older dates first)
        emails_to_process.sort(key=lambda x: x['subject_date'])
        
        logger.info(f"[watcher] 📅 Email processing order (oldest first):")
        for i, email_data in enumerate(emails_to_process):
            logger.info(f"[watcher]   {i+1}. {email_data['subject_date'].strftime('%Y-%m-%d')} - {email_data['subject']}")
        
        # Process emails based on coordination strategy
        if len(emails_to_process) > 1:
            logger.info(f"[watcher] 🚀 Processing {len(emails_to_process)} emails in date order")
            _process_multiple_emails_coordinated(emails_to_process, con)
        elif len(emails_to_process) == 1:
            logger.info(f"[watcher] 📧 Processing single email")
            _process_single_email_coordinated(emails_to_process[0], con)
                
    except Exception as e:
        logger.error(f"[watcher] Error in process_new_unseen: {e}")

def _process_multiple_emails_coordinated(emails_to_process, con):
    """Process multiple emails sequentially to avoid conflicts."""
    logger.info(f"[watcher] 🔄 Processing {len(emails_to_process)} emails sequentially to avoid conflicts")
    
    # Import pipeline manager for type detection
    sys.path.append('/app')
    from pipeline_manager import detect_pipeline_type
    
    # Group emails by pipeline type
    pipeline_groups = {}
    for email_data in emails_to_process:
        # Detect pipeline type
        subject = email_data['subject']
        pipeline_type = detect_pipeline_type(subject, email_data['from_addr'])
        
        if pipeline_type not in pipeline_groups:
            pipeline_groups[pipeline_type] = []
        pipeline_groups[pipeline_type].append(email_data)
    
    logger.info(f"[watcher] 📊 Pipeline groups: {list(pipeline_groups.keys())}")
    
    # Process each pipeline group sequentially
    for pipeline_type, emails in pipeline_groups.items():
        logger.info(f"[watcher] 🎯 Processing {len(emails)} emails for {pipeline_type} pipeline")
        
        # Process emails for this pipeline sequentially (already sorted by date)
        for i, email_data in enumerate(emails):
            logger.info(f"[watcher] 📧 Processing email {i+1}/{len(emails)} for {pipeline_type}")
            success = _process_single_email_coordinated(email_data, con)
            
            if success:
                logger.info(f"[watcher] ✅ Email {i+1} processed successfully")
            else:
                logger.error(f"[watcher] ❌ Email {i+1} processing failed")
                
            # Add small delay between emails to prevent conflicts
            if i < len(emails) - 1:  # Don't delay after the last email
                logger.info(f"[watcher] ⏳ Waiting 2 seconds before next email...")
                time.sleep(2)

def _process_single_email_coordinated(email_data, con):
    """Process a single email with coordination."""
    uid = email_data['uid']
    msg = email_data['msg']
    subject = email_data['subject']
    from_addr = email_data['from_addr']
    mid = email_data['mid']
    
    try:
        # Process email attachments first
        logger.info(f"[watcher] 📎 Processing attachments for email {mid}")
        attachment_success = process_email_attachments(msg)
        
        if not attachment_success:
            logger.error(f"[watcher] ❌ Failed to process attachments for email {mid}")
            return False
        
        logger.info(f"[watcher] ✅ Attachments processed successfully")
        
        # Mark as processed (coordination will handle pipeline execution)
        mark_done(con, mid, subject, from_addr)
        
        logger.info(f"[watcher] ✅ Email {mid} processing completed")
        return True
        
    except Exception as e:
        logger.error(f"[watcher] ❌ Error processing email {uid}: {e}")
        import traceback
        logger.error(f"[watcher] Traceback: {traceback.format_exc()}")
        return False

def test_connection(client):
    """Test if IMAP connection is still alive."""
    try:
        # Simple NOOP command to test connection
        client.noop()
        return True
    except Exception as e:
        logger.warning(f"[watcher] ⚠️  Connection test failed: {e}")
        return False

def reconnect_imap():
    """Reconnect to IMAP server with enhanced SSL handling."""
    logger.info(f"🔄 [watcher] Reconnecting to IMAP server {IMAP_HOST}:{PORT}...")
    
    # Try multiple connection strategies
    connection_strategies = [
        {"ssl": USE_SSL, "port": PORT, "timeout": 30},
        {"ssl": USE_SSL, "port": PORT, "timeout": 60},
        {"ssl": False, "port": 143, "timeout": 30},  # Fallback to non-SSL
    ]
    
    for i, strategy in enumerate(connection_strategies):
        try:
            logger.info(f"🔄 [watcher] Attempting connection strategy {i+1}: SSL={strategy['ssl']}, Port={strategy['port']}")
            
            client = IMAPClient(
                IMAP_HOST, 
                ssl=strategy['ssl'], 
                port=strategy['port'],
                timeout=strategy['timeout']
            )
            logger.info("✅ [watcher] IMAP connection established")
            
            logger.info(f"🔐 [watcher] Logging in as {IMAP_USER}...")
            client.login(IMAP_USER, IMAP_PASS)
            logger.info("✅ [watcher] Login successful")
            
            logger.info(f"📁 [watcher] Selecting folder {IMAP_FOLDER}...")
            client.select_folder(IMAP_FOLDER, readonly=False)
            logger.info("✅ [watcher] Folder selected")
            
            # Test the connection
            client.noop()
            logger.info("✅ [watcher] Connection test successful")
            
            return client
            
        except Exception as e:
            logger.warning(f"⚠️ [watcher] Connection strategy {i+1} failed: {e}")
            if i < len(connection_strategies) - 1:
                logger.info(f"🔄 [watcher] Trying next strategy...")
                time.sleep(2)  # Brief pause between attempts
            continue
    
    logger.error(f"❌ [watcher] All reconnection strategies failed")
    return None

def idle_with_keepalive(client, con, keepalive_interval=300):
    """IDLE mode with periodic keepalive to prevent timeouts."""
    logger.info("[watcher] 🔄 Starting IDLE mode with keepalive")
    process_new_unseen(client, con)
    
    last_keepalive = time.time()
    idle_start_time = time.time()
    consecutive_idle_failures = 0
    max_idle_failures = 3
    
    while True:
        try:
            current_time = time.time()
            
            # Check if we need to send keepalive
            if current_time - last_keepalive >= keepalive_interval:
                logger.info("[watcher] 💓 Sending keepalive (NOOP)")
                client.noop()
                last_keepalive = current_time
                logger.info(f"[watcher] ✅ Keepalive sent (IDLE active for {int(current_time - idle_start_time)}s)")
            
            # Test connection before IDLE
            if not test_connection(client):
                logger.warning("[watcher] ⚠️  Connection test failed before IDLE")
                raise Exception("Connection lost")
            
            logger.info("[watcher] 🔄 Starting IDLE session")
            client.idle()
            logger.info("[watcher] ⏳ IDLE active - waiting for server notifications")
            
            # IDLE with shorter timeout and periodic checks
            idle_timeout = 60  # 1 minute timeout for IDLE checks
            idle_duration = 0
            max_idle_duration = keepalive_interval - 30  # Stop before next keepalive
            
            while idle_duration < max_idle_duration:
                try:
                    # Check for IDLE responses with short timeout
                    client.idle_check(timeout=30)  # 30 second checks
                    idle_duration += 30
                    
                    # If we get here, IDLE is still active
                    logger.debug(f"[watcher] IDLE active for {idle_duration}s")
                    
                except Exception as idle_error:
                    logger.warning(f"[watcher] ⚠️  IDLE check interrupted: {idle_error}")
                    break
            
            # End IDLE session
            try:
                client.idle_done()
                logger.info("[watcher] ✅ IDLE session ended gracefully")
            except Exception as e:
                logger.warning(f"[watcher] ⚠️  Error ending IDLE session: {e}")
            
            # Reset failure counter on successful IDLE cycle
            consecutive_idle_failures = 0
            
            # Check for new emails after IDLE
            logger.info("[watcher] 🔄 IDLE cycle complete - checking for new emails")
            process_new_unseen(client, con)
            
        except Exception as e:
            consecutive_idle_failures += 1
            logger.error(f"[watcher] ❌ IDLE error (attempt {consecutive_idle_failures}): {e}")
            
            # If too many IDLE failures, fall back to polling
            if consecutive_idle_failures >= max_idle_failures:
                logger.warning(f"[watcher] ⚠️  Too many IDLE failures ({consecutive_idle_failures}), falling back to polling")
                return False  # Signal to fall back to polling
            
            # Brief pause before retry
            logger.info("[watcher] ⏳ Brief pause before IDLE retry...")
            time.sleep(5)
    
    return True

def polling_loop(client, con):
    """Fallback polling mode with connection recovery."""
    return polling_loop_with_interval(client, con, POLL_INTERVAL)

def polling_loop_with_interval(client, con, polling_interval):
    """Fallback polling mode with connection recovery and custom interval."""
    logger.info("[watcher] 🔄 Starting polling mode")
    process_new_unseen(client, con)
    
    consecutive_polling_failures = 0
    max_polling_failures = 3
    
    while True:
        try:
            logger.info(f"[watcher] ⏰ Polling mode: sleeping {polling_interval} seconds")
            time.sleep(polling_interval)
            
            # Test connection before polling
            if not test_connection(client):
                logger.warning("[watcher] ⚠️  Connection test failed before polling")
                raise Exception("Connection lost")
            
            logger.info("[watcher] 🔄 Polling cycle - checking for new emails")
            process_new_unseen(client, con)
            
            # Reset failure counter on successful polling
            consecutive_polling_failures = 0
            
        except Exception as e:
            consecutive_polling_failures += 1
            logger.error(f"[watcher] ❌ Polling error (attempt {consecutive_polling_failures}): {e}")
            
            # If too many polling failures, we need to reconnect
            if consecutive_polling_failures >= max_polling_failures:
                logger.warning(f"[watcher] ⚠️  Too many polling failures ({consecutive_polling_failures}), need to reconnect")
                return False  # Signal to reconnect
            
            # Brief pause before retry
            logger.info("[watcher] ⏳ Brief pause before polling retry...")
            time.sleep(5)

def idle_loop(client, con, fallback_polling_interval=300):
    """Main loop for IMAP IDLE or polling with robust error handling."""
    logger.info("[watcher] 🔄 Starting main monitoring loop")
    
    # Determine initial mode
    use_idle = POLL_INTERVAL == 0
    
    while True:
        try:
            if use_idle:
                logger.info("[watcher] 🎯 Attempting IDLE mode")
                success = idle_with_keepalive(client, con)
                
                if not success:
                    logger.warning("[watcher] ⚠️  IDLE mode failed, falling back to polling")
                    use_idle = False
                    logger.info(f"[watcher] 🔄 Switching to polling mode ({fallback_polling_interval}s interval)")
                    continue
            else:
                logger.info("[watcher] 🎯 Using polling mode")
                success = polling_loop_with_interval(client, con, fallback_polling_interval)
                
                if not success:
                    logger.warning("[watcher] ⚠️  Polling mode failed, need to reconnect")
                    return False  # Signal to reconnect
                    
        except Exception as e:
            logger.error(f"[watcher] ❌ Error in idle_loop: {e}")
            logger.info("[watcher] ⏳ Brief pause before retry...")
            time.sleep(5)
            return False  # Signal to reconnect

def is_ssl_error(error_msg):
    """Check if error is SSL-related."""
    ssl_indicators = [
        "EOF occurred in violation of protocol",
        "SSL", "ssl", "TLS", "tls",
        "certificate", "handshake",
        "connection reset", "broken pipe"
    ]
    error_str = str(error_msg).lower()
    return any(indicator.lower() in error_str for indicator in ssl_indicators)

def calculate_backoff(consecutive_failures, is_ssl_error_flag=False):
    """Calculate backoff time based on failure type and count."""
    base_backoff = 3
    
    if is_ssl_error_flag:
        # SSL errors need longer backoff
        if consecutive_failures <= 3:
            return min(base_backoff * (2 ** consecutive_failures), 60)  # 3, 6, 12, 24, 48, 60
        else:
            return min(base_backoff * (2 ** consecutive_failures), 300)  # Up to 5 minutes
    else:
        # Regular errors use shorter backoff
        if consecutive_failures <= 5:
            return min(base_backoff * (1.5 ** consecutive_failures), 120)  # Up to 2 minutes
        else:
            return min(base_backoff * (2 ** consecutive_failures), 300)  # Up to 5 minutes

def main():
    """Main function with enhanced connection management and auto-recovery."""
    logger.info("🚀 [watcher] Starting enhanced email watcher service")
    logger.info(f"📧 [watcher] IMAP Host: {IMAP_HOST}")
    logger.info(f"👤 [watcher] IMAP User: {IMAP_USER}")
    logger.info(f"📁 [watcher] IMAP Folder: {IMAP_FOLDER}")
    logger.info(f"🔍 [watcher] Subject Regex: {MATCH_SUBJECT_REGEX}")
    logger.info(f"📧 [watcher] From Regex: {MATCH_FROM_REGEX}")
    logger.info(f"🕐 [watcher] Allowed Hours: {ALLOWED_HOURS}")
    logger.info(f"📅 [watcher] Allowed Days: {ALLOWED_DAYS}")
    logger.info(f"⚙️  [watcher] Pipeline Command: {PIPELINE_CMD}")
    
    logger.info("🗄️  [watcher] Initializing database...")
    con = ensure_db()
    logger.info("✅ [watcher] Database initialized")
    
    consecutive_failures = 0
    ssl_failure_count = 0
    last_successful_connection = time.time()
    client = None
    
    while True:
        try:
            # Connect or reconnect
            if client is None:
                logger.info(f"🔌 [watcher] Connecting to IMAP server {IMAP_HOST}:{PORT}...")
                client = reconnect_imap()  # Use enhanced reconnection
                
                if client is None:
                    raise Exception("Failed to establish connection with all strategies")
                
                # Check server capabilities
                capabilities = client.capabilities()
                logger.info(f"🔧 [watcher] Server capabilities: {len(capabilities)} features")
                
                if POLL_INTERVAL == 0 and b"IDLE" not in capabilities:
                    logger.warning("⚠️  [watcher] Server lacks IDLE capability, enabling polling every 5 minutes")
                else:
                    logger.info("✅ [watcher] IDLE capability confirmed")
                
                logger.info("🎯 [watcher] Connected successfully, starting monitoring...")
                consecutive_failures = 0  # Reset failure counter on successful connection
                ssl_failure_count = 0
                last_successful_connection = time.time()
            
            # Start monitoring loop
            fallback_interval = 300 if POLL_INTERVAL == 0 else POLL_INTERVAL
            monitoring_success = idle_loop(client, con, fallback_interval)
            
            if not monitoring_success:
                logger.warning("[watcher] ⚠️  Monitoring loop failed, attempting reconnection")
                # Close current connection
                try:
                    client.logout()
                except:
                    pass
                client = None
                continue
                
        except Exception as e:
            consecutive_failures += 1
            error_str = str(e)
            ssl_error = is_ssl_error(error_str)
            
            if ssl_error:
                ssl_failure_count += 1
                logger.error(f"❌ [watcher] SSL Connection error (attempt {consecutive_failures}, SSL failures: {ssl_failure_count}): {e}")
            else:
                logger.error(f"❌ [watcher] Connection error (attempt {consecutive_failures}): {e}")
            
            # Close current connection
            if client:
                try:
                    client.logout()
                except:
                    pass
                client = None
            
            # Calculate appropriate backoff
            backoff = calculate_backoff(consecutive_failures, ssl_error)
            
            # Log backoff strategy
            if ssl_error and ssl_failure_count > 3:
                logger.warning(f"⚠️ [watcher] Multiple SSL failures ({ssl_failure_count}), using extended backoff: {backoff}s")
            elif consecutive_failures > 5:
                logger.warning(f"⚠️ [watcher] Multiple consecutive failures ({consecutive_failures}), using extended backoff: {backoff}s")
            
            logger.info(f"⏳ [watcher] Retrying in {backoff} seconds...")
            time.sleep(backoff)

if __name__ == "__main__":
    main()
