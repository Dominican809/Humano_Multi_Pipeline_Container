#!/usr/bin/env python3
"""
Manual Email Processor
Allows processing specific emails by UID for testing purposes
"""

import imaplib
import email
import re
import os
import sys
import tempfile
from pathlib import Path

def connect_imap():
    """Connect to IMAP server"""
    imap_host = os.environ.get('IMAP_HOST', 'secure.emailsrvr.com')
    imap_user = os.environ.get('IMAP_USER', 'ismael.ramirezaybar@agassist.net')
    imap_pass = os.environ.get('IMAP_PASS')
    imap_port = int(os.environ.get('IMAP_PORT', '993'))
    
    print(f'🔌 Connecting to {imap_host}:{imap_port}...')
    client = imaplib.IMAP4_SSL(imap_host, imap_port)
    client.login(imap_user, imap_pass)
    client.select('INBOX')
    return client

def list_trigger_emails(client, limit=20):
    """List trigger emails that match our criteria (limited to last N emails by default)"""
    print('📧 Searching for trigger emails...')
    
    # Search for emails from today
    result, data = client.search(None, 'SINCE', '22-Sep-2025')
    if result != 'OK':
        print('❌ Failed to search emails')
        return []
    
    email_ids = data[0].split()
    
    # Limit to the most recent emails (last N)
    if len(email_ids) > limit:
        email_ids = email_ids[-limit:]
        print(f'📊 Limiting search to last {limit} emails (found {len(data[0].split())} total)')
    
    trigger_emails = []
    
    subject_regex = r'(?i)^asegurados (viajeros|salud internacional)\s*\|\s*\d{4}-\d{2}-\d{2}$'
    from_regex = r'(?i)notificacionesinteligenciatecnicaSI@humano\.com\.do'
    
    for email_id in email_ids:
        result, data = client.fetch(email_id, '(RFC822)')
        if result == 'OK':
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            subject = email_message.get('Subject', '')
            from_addr = email_message.get('From', '')
            date = email_message.get('Date', '')
            
            if re.match(subject_regex, subject) and re.search(from_regex, from_addr):
                # Determine pipeline type
                if 'viajeros' in subject.lower():
                    pipeline_type = 'viajeros'
                elif 'salud internacional' in subject.lower():
                    pipeline_type = 'si'
                else:
                    pipeline_type = 'unknown'
                
                trigger_emails.append({
                    'uid': email_id.decode(),
                    'subject': subject,
                    'from_addr': from_addr,
                    'date': date,
                    'pipeline_type': pipeline_type
                })
    
    return trigger_emails

def process_email_by_uid(client, uid, pipeline_type):
    """Process a specific email by UID"""
    print(f'📧 Processing email UID {uid} for {pipeline_type} pipeline...')
    
    # Fetch the email
    result, data = client.fetch(uid, '(RFC822)')
    if result != 'OK':
        print(f'❌ Failed to fetch email {uid}')
        return False
    
    raw_email = data[0][1]
    email_message = email.message_from_bytes(raw_email)
    subject = email_message.get('Subject', '')
    
    print(f'📧 Email details: {subject}')
    
    # Extract attachments
    attachments = []
    for part in email_message.walk():
        if part.get_content_disposition() == 'attachment':
            filename = part.get_filename()
            if filename and filename.endswith(('.xlsx', '.xls')):
                content = part.get_payload(decode=True)
                attachments.append({
                    'filename': filename,
                    'content': content
                })
                print(f'📎 Found attachment: {filename}')
    
    if not attachments:
        print('❌ No Excel attachments found')
        return False
    
    # Process each attachment
    for attachment in attachments:
        print(f'📎 Processing attachment: {attachment["filename"]}')
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            temp_file.write(attachment['content'])
            temp_path = temp_file.name
        
        try:
            # Import and run the pipeline
            sys.path.append('/app')
            from pipeline_manager import process_email
            
            print(f'🚀 Running {pipeline_type} pipeline...')
            process_email(pipeline_type, temp_path, subject)
            print(f'✅ {pipeline_type} pipeline completed successfully')
            
        except Exception as e:
            print(f'❌ Pipeline execution failed: {e}')
            import traceback
            print(f'Traceback: {traceback.format_exc()}')
            return False
        finally:
            # Clean up temp file
            os.unlink(temp_path)
    
    return True

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manual_email_processor.py list [limit]           # List trigger emails (default: last 20)")
        print("  python manual_email_processor.py process <uid>          # Process specific email by UID")
        print("  python manual_email_processor.py process-all            # Process all trigger emails")
        print("  python manual_email_processor.py process-latest         # Process latest email of each type")
        return
    
    command = sys.argv[1]
    
    try:
        client = connect_imap()
        
        if command == 'list':
            # Check if limit is provided
            limit = 20  # default
            if len(sys.argv) > 2:
                try:
                    limit = int(sys.argv[2])
                except ValueError:
                    print(f'❌ Invalid limit value: {sys.argv[2]}. Using default limit of 20.')
                    limit = 20
            
            emails = list_trigger_emails(client, limit)
            print(f'\n📊 Found {len(emails)} trigger emails:')
            for i, email_info in enumerate(emails, 1):
                print(f'{i}. UID: {email_info["uid"]} | {email_info["pipeline_type"].upper()} | {email_info["subject"]} | {email_info["date"]}')
        
        elif command == 'process':
            if len(sys.argv) < 3:
                print('❌ Please provide UID to process')
                return
            
            uid = sys.argv[2]
            emails = list_trigger_emails(client)
            
            # Find the email by UID
            target_email = None
            for email_info in emails:
                if email_info['uid'] == uid:
                    target_email = email_info
                    break
            
            if not target_email:
                print(f'❌ Email with UID {uid} not found in trigger emails')
                return
            
            success = process_email_by_uid(client, uid, target_email['pipeline_type'])
            if success:
                print(f'✅ Successfully processed email UID {uid}')
            else:
                print(f'❌ Failed to process email UID {uid}')
        
        elif command == 'process-all':
            emails = list_trigger_emails(client)
            print(f'🚀 Processing all {len(emails)} trigger emails...')
            
            for i, email_info in enumerate(emails, 1):
                print(f'\n--- Processing {i}/{len(emails)} ---')
                success = process_email_by_uid(client, email_info['uid'], email_info['pipeline_type'])
                if success:
                    print(f'✅ Email {i} processed successfully')
                else:
                    print(f'❌ Email {i} failed')
        
        elif command == 'process-latest':
            emails = list_trigger_emails(client)
            
            # Group by pipeline type and get latest of each
            latest_emails = {}
            for email_info in emails:
                pipeline_type = email_info['pipeline_type']
                if pipeline_type not in latest_emails:
                    latest_emails[pipeline_type] = email_info
                else:
                    # Compare dates (simple string comparison should work for this format)
                    if email_info['date'] > latest_emails[pipeline_type]['date']:
                        latest_emails[pipeline_type] = email_info
            
            print(f'🚀 Processing latest email of each type...')
            for pipeline_type, email_info in latest_emails.items():
                print(f'\n--- Processing latest {pipeline_type.upper()} email ---')
                success = process_email_by_uid(client, email_info['uid'], pipeline_type)
                if success:
                    print(f'✅ Latest {pipeline_type} email processed successfully')
                else:
                    print(f'❌ Latest {pipeline_type} email failed')
        
        else:
            print(f'❌ Unknown command: {command}')
    
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        print(f'Traceback: {traceback.format_exc()}')
    
    finally:
        try:
            client.close()
            client.logout()
        except:
            pass

if __name__ == '__main__':
    main()
