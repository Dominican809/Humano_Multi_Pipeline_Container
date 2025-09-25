#!/usr/bin/env python3
"""
Enhanced health check and auto-recovery script for the email watcher system.
This script monitors system health and automatically restarts failed components.
"""

import os
import sys
import sqlite3
import json
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def check_database():
    """Check if the SQLite database is accessible and has recent activity."""
    print("🔍 Checking database status...")
    
    db_path = "/state/processed.sqlite3"
    if not os.path.exists(db_path):
        print("   ⚠️  Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed'")
        if not cursor.fetchone():
            print("   ⚠️  Processed table not found")
            return False
        
        # Get recent activity
        cursor.execute("SELECT COUNT(*) FROM processed")
        total_count = cursor.fetchone()[0]
        
        # Get recent activity (last 24 hours)
        yesterday = int((datetime.now() - timedelta(days=1)).timestamp())
        cursor.execute("SELECT COUNT(*) FROM processed WHERE ts > ?", (yesterday,))
        recent_count = cursor.fetchone()[0]
        
        print(f"   ✅ Database accessible")
        print(f"   📊 Total processed emails: {total_count}")
        print(f"   📊 Recent emails (24h): {recent_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

def check_excel_file():
    """Check if the Excel file exists and is recent."""
    print("🔍 Checking Excel file...")
    
    excel_path = "/app/Exceles/Rep_Afiliados_Seguro_Viajero 16 06 2025 AL 02 07 2025.xlsx"
    
    if not os.path.exists(excel_path):
        print("   ⚠️  Excel file not found")
        return False
    
    try:
        # Check file size and modification time
        stat = os.stat(excel_path)
        size_mb = stat.st_size / (1024 * 1024)
        mod_time = datetime.fromtimestamp(stat.st_mtime)
        age_hours = (datetime.now() - mod_time).total_seconds() / 3600
        
        print(f"   ✅ Excel file found")
        print(f"   📊 File size: {size_mb:.2f} MB")
        print(f"   📊 Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   📊 Age: {age_hours:.1f} hours ago")
        
        # Check if file is recent (less than 25 hours old)
        if age_hours < 25:
            print("   ✅ File is recent")
            return True
        else:
            print("   ⚠️  File is older than 25 hours")
            return False
            
    except Exception as e:
        print(f"   ❌ Excel file error: {e}")
        return False

def check_logs():
    """Check if logs are being generated."""
    print("🔍 Checking logs...")
    
    log_dir = "/app/logs"
    if not os.path.exists(log_dir):
        print("   ⚠️  Log directory not found")
        return False
    
    try:
        # Find recent log files
        log_files = []
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir, file)
                stat = os.stat(file_path)
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                age_hours = (datetime.now() - mod_time).total_seconds() / 3600
                
                log_files.append({
                    'name': file,
                    'size': stat.st_size,
                    'age_hours': age_hours
                })
        
        if not log_files:
            print("   ⚠️  No log files found")
            return False
        
        print(f"   ✅ Found {len(log_files)} log files")
        
        # Show recent logs
        recent_logs = [f for f in log_files if f['age_hours'] < 24]
        if recent_logs:
            print("   ✅ Recent log activity found")
            for log in recent_logs[:3]:  # Show first 3
                print(f"      📄 {log['name']}: {log['size']} bytes, {log['age_hours']:.1f}h ago")
            return True
        else:
            print("   ⚠️  No recent log activity")
            return False
            
    except Exception as e:
        print(f"   ❌ Log check error: {e}")
        return False

def check_data_outputs():
    """Check if data outputs are being generated."""
    print("🔍 Checking data outputs...")
    
    data_dir = "/app/data"
    if not os.path.exists(data_dir):
        print("   ⚠️  Data directory not found")
        return False
    
    try:
        # Check for recent output files
        output_files = []
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith(('.json', '.xlsx', '.csv')):
                    file_path = os.path.join(root, file)
                    stat = os.stat(file_path)
                    mod_time = datetime.fromtimestamp(stat.st_mtime)
                    age_hours = (datetime.now() - mod_time).total_seconds() / 3600
                    
                    output_files.append({
                        'name': file,
                        'path': file_path,
                        'size': stat.st_size,
                        'age_hours': age_hours
                    })
        
        if not output_files:
            print("   ⚠️  No output files found")
            return False
        
        print(f"   ✅ Found {len(output_files)} output files")
        
        # Show recent outputs
        recent_outputs = [f for f in output_files if f['age_hours'] < 24]
        if recent_outputs:
            print("   ✅ Recent output activity found")
            for output in recent_outputs[:3]:  # Show first 3
                print(f"      📄 {output['name']}: {output['size']} bytes, {output['age_hours']:.1f}h ago")
            return True
        else:
            print("   ⚠️  No recent output activity")
            return False
            
    except Exception as e:
        print(f"   ❌ Data output check error: {e}")
        return False

def check_environment():
    """Check if environment variables are properly configured."""
    print("🔍 Checking environment configuration...")
    
    required_vars = [
        'IMAP_HOST', 'IMAP_USER', 'IMAP_PASS', 'IMAP_FOLDER',
        'MATCH_SUBJECT_REGEX', 'MATCH_FROM_REGEX'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"   ❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("   ✅ All required environment variables present")
    print(f"   📧 IMAP Host: {os.environ.get('IMAP_HOST')}")
    print(f"   📧 IMAP User: {os.environ.get('IMAP_USER')}")
    print(f"   📧 IMAP Folder: {os.environ.get('IMAP_FOLDER')}")
    
    return True

def check_email_watcher_process():
    """Check if the email watcher process is running and responding."""
    print("🔍 Checking email watcher process...")
    
    try:
        # Check if pipeline_watcher.py is running
        result = subprocess.run(['pgrep', '-f', 'pipeline_watcher.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"   ✅ Email watcher process found (PIDs: {', '.join(pids)})")
            
            # Check process age and memory usage
            for pid in pids:
                try:
                    stat_result = subprocess.run(['ps', '-p', pid, '-o', 'etime,rss'], 
                                               capture_output=True, text=True)
                    if stat_result.returncode == 0:
                        lines = stat_result.stdout.strip().split('\n')
                        if len(lines) > 1:
                            parts = lines[1].split()
                            elapsed_time = parts[0]
                            memory_kb = int(parts[1])
                            memory_mb = memory_kb / 1024
                            print(f"   📊 PID {pid}: Running for {elapsed_time}, Memory: {memory_mb:.1f} MB")
                except:
                    pass
            
            return True
        else:
            print("   ❌ Email watcher process not found")
            return False
            
    except Exception as e:
        print(f"   ❌ Process check error: {e}")
        return False

def check_recent_activity():
    """Check for recent email processing activity."""
    print("🔍 Checking recent activity...")
    
    try:
        db_path = "/state/processed.sqlite3"
        if not os.path.exists(db_path):
            print("   ⚠️  Database file not found")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for activity in the last 6 hours
        six_hours_ago = int((datetime.now() - timedelta(hours=6)).timestamp())
        cursor.execute("SELECT COUNT(*) FROM processed WHERE ts > ?", (six_hours_ago,))
        recent_count = cursor.fetchone()[0]
        
        # Check for activity in the last 24 hours
        yesterday = int((datetime.now() - timedelta(days=1)).timestamp())
        cursor.execute("SELECT COUNT(*) FROM processed WHERE ts > ?", (yesterday,))
        daily_count = cursor.fetchone()[0]
        
        # Get the most recent activity
        cursor.execute("SELECT ts, subject FROM processed ORDER BY ts DESC LIMIT 1")
        latest = cursor.fetchone()
        
        if latest:
            latest_time = datetime.fromtimestamp(latest[0])
            hours_since = (datetime.now() - latest_time).total_seconds() / 3600
            print(f"   📊 Recent activity (6h): {recent_count} emails")
            print(f"   📊 Daily activity (24h): {daily_count} emails")
            print(f"   📊 Last processed: {latest_time.strftime('%Y-%m-%d %H:%M:%S')} ({hours_since:.1f}h ago)")
            
            # Consider it healthy if there was activity in the last 25 hours
            # (allowing for days when no emails arrive)
            return hours_since < 25
        else:
            print("   ⚠️  No email processing history found")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Activity check error: {e}")
        return False

def restart_email_watcher():
    """Restart the email watcher process."""
    print("🔄 Attempting to restart email watcher...")
    
    try:
        # Kill existing processes
        subprocess.run(['pkill', '-f', 'pipeline_watcher.py'], capture_output=True)
        time.sleep(2)
        
        # Start new process
        cmd = ['/usr/bin/python3', '/app/email_watcher/pipeline_watcher.py']
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        time.sleep(5)  # Give it time to start
        
        # Verify it started
        result = subprocess.run(['pgrep', '-f', 'pipeline_watcher.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Email watcher restarted successfully")
            return True
        else:
            print("   ❌ Failed to restart email watcher")
            return False
            
    except Exception as e:
        print(f"   ❌ Restart error: {e}")
        return False

def health_check_only():
    """Run health check without auto-recovery."""
    print("🏥 Email Watcher Health Check")
    print("=" * 50)
    
    checks = [
        ("Environment Configuration", check_environment),
        ("Database Status", check_database),
        ("Email Watcher Process", check_email_watcher_process),
        ("Recent Activity", check_recent_activity),
        ("Excel File", check_excel_file),
        ("Log Activity", check_logs),
        ("Data Outputs", check_data_outputs)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"   ❌ Check failed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Health Check Summary:")
    
    passed = 0
    critical_failed = []
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {name}")
        if result:
            passed += 1
        else:
            # Mark critical failures
            if name in ["Environment Configuration", "Email Watcher Process"]:
                critical_failed.append(name)
    
    print(f"\n🎯 Overall Status: {passed}/{len(results)} checks passed")
    
    if passed == len(results):
        print("🎉 System is healthy and ready!")
        return 0, critical_failed
    elif passed >= len(results) * 0.6:
        print("⚠️  System is mostly healthy with some issues")
        return 1, critical_failed
    else:
        print("❌ System has significant issues")
        return 2, critical_failed

def monitor_mode():
    """Continuous monitoring mode with auto-recovery."""
    print("🔄 Starting continuous monitoring mode...")
    print("Press Ctrl+C to stop monitoring")
    
    consecutive_failures = 0
    max_consecutive_failures = 3
    
    try:
        while True:
            print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Running health check...")
            
            status_code, critical_failed = health_check_only()
            
            if status_code == 0:
                # System is healthy
                consecutive_failures = 0
                print("✅ System healthy - continuing monitoring...")
            elif critical_failed:
                # Critical components failed
                consecutive_failures += 1
                print(f"⚠️  Critical failures detected ({consecutive_failures}/{max_consecutive_failures})")
                
                if "Email Watcher Process" in critical_failed:
                    print("🔄 Attempting auto-recovery...")
                    if restart_email_watcher():
                        print("✅ Auto-recovery successful")
                        consecutive_failures = 0
                    else:
                        print("❌ Auto-recovery failed")
                
                if consecutive_failures >= max_consecutive_failures:
                    print("❌ Too many consecutive failures - manual intervention required")
                    return 2
            else:
                # Non-critical issues
                print("⚠️  Minor issues detected - continuing monitoring...")
                consecutive_failures = 0
            
            # Wait 5 minutes before next check
            print("⏳ Waiting 5 minutes before next check...")
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        return 0

def main():
    """Main function with support for different modes."""
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        return monitor_mode()
    else:
        status_code, _ = health_check_only()
        return status_code

if __name__ == "__main__":
    sys.exit(main())
