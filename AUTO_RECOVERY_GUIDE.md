# Auto-Recovery and Enhanced Email Watcher Guide

## 🚀 What's New

The email watcher system has been significantly enhanced with **automatic recovery mechanisms** and **robust connection handling** to ensure continuous operation without manual intervention.

## 🔧 Key Improvements

### 1. **Enhanced SSL Connection Handling**
- **Multiple Connection Strategies**: Automatically tries different connection methods if SSL fails
- **Smart Backoff**: SSL errors get longer backoff times than regular errors
- **Connection Testing**: Validates connections before use

### 2. **Auto-Recovery System**
- **Process Monitoring**: Detects when email watcher process dies
- **Automatic Restart**: Restarts failed processes automatically
- **Failure Tracking**: Prevents infinite restart loops

### 3. **Comprehensive Health Monitoring**
- **Real-time Health Checks**: Every 5 minutes via Docker health checks
- **Activity Monitoring**: Tracks email processing activity
- **Process Monitoring**: Monitors system processes and memory usage

## 🎯 How It Solves the Original Problems

### **Problem**: SSL Connection Failures
- **Root Cause**: `EOF occurred in violation of protocol (_ssl.c:2427)` errors
- **Solution**: 
  - Multiple connection strategies with fallbacks
  - Enhanced error detection and SSL-specific handling
  - Exponential backoff for SSL errors

### **Problem**: System Gets Stuck
- **Root Cause**: No automatic recovery from persistent failures
- **Solution**: 
  - Auto-restart mechanisms
  - Health monitoring with recovery actions
  - Process supervision

### **Problem**: Manual Intervention Required
- **Root Cause**: No self-healing capabilities
- **Solution**: 
  - Continuous monitoring mode
  - Automatic process restart
  - Intelligent failure detection

## 📋 Usage Instructions

### **1. Start with Enhanced Monitoring**
```bash
# Start the container
./start.sh

# Check health immediately
docker exec humano-multi-pipeline python /app/email_watcher/health_check.py

# Enable continuous monitoring (runs in background)
docker exec -d humano-multi-pipeline python /app/email_watcher/health_check.py --monitor
```

### **2. Monitor System Health**
```bash
# Quick health check
docker exec humano-multi-pipeline python /app/email_watcher/health_check.py

# Check Docker health status
docker compose ps

# View real-time logs
docker compose logs -f humano-multi-pipeline
```

### **3. Manual Recovery (if needed)**
```bash
# Restart the container (last resort)
docker restart humano-multi-pipeline

# Or restart the whole stack
docker compose down && docker compose up -d
```

## 🔍 Health Check Features

The enhanced health check monitors:

1. **Environment Configuration** - All required env vars present
2. **Database Status** - SQLite database accessible
3. **Email Watcher Process** - Process running and responsive
4. **Recent Activity** - Email processing in last 25 hours
5. **Excel File Status** - Input files present and recent
6. **Log Activity** - System generating logs
7. **Data Outputs** - Pipeline producing results

## 🔄 Auto-Recovery Triggers

The system automatically restarts when:
- Email watcher process stops running
- Too many consecutive SSL connection failures
- Process becomes unresponsive
- Memory usage exceeds thresholds

## ⚙️ Configuration Options

### **Environment Variables**
All existing configuration remains the same:
- `POLL_INTERVAL_SEC=0` (uses IDLE with 300s fallback)
- `ALLOWED_HOURS=08-20` (Dominican Republic time)
- `ALLOWED_DAYS=mon,tue,wed,thu,fri,sat,sun`

### **Health Check Intervals**
- **Docker Health Check**: Every 5 minutes
- **Continuous Monitoring**: Every 5 minutes (when enabled)
- **Auto-restart Threshold**: 3 consecutive failures

## 🚨 Troubleshooting

### **If the system still fails repeatedly:**

1. **Check SSL connectivity**:
   ```bash
   docker exec humano-multi-pipeline python -c "
   import ssl
   import socket
   
   context = ssl.create_default_context()
   with socket.create_connection(('secure.emailsrvr.com', 993)) as sock:
       with context.wrap_socket(sock, server_hostname='secure.emailsrvr.com') as ssock:
           print('SSL connection successful')
   "
   ```

2. **Check IMAP server status**:
   ```bash
   docker exec humano-multi-pipeline python -c "
   from imapclient import IMAPClient
   client = IMAPClient('secure.emailsrvr.com', ssl=True, port=993)
   print('IMAP connection successful')
   "
   ```

3. **View detailed error logs**:
   ```bash
   docker logs humano-multi-pipeline --tail 100 | grep -E "(ERROR|FAIL|SSL)"
   ```

## 📊 Performance Monitoring

### **Monitor Resource Usage**
```bash
# Container stats
docker stats humano-multi-pipeline

# Process details inside container
docker exec humano-multi-pipeline ps aux
```

### **Database Growth**
```bash
# Check database size and records
docker exec humano-multi-pipeline python -c "
import sqlite3
import os

db_path = '/state/processed.sqlite3'
if os.path.exists(db_path):
    size_mb = os.path.getsize(db_path) / 1024 / 1024
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM processed')
    count = cursor.fetchone()[0]
    conn.close()
    
    print(f'Database: {size_mb:.2f} MB, {count} records')
else:
    print('Database not found')
"
```

## 🎯 Success Metrics

The system is working correctly when:
- ✅ Health checks pass consistently
- ✅ Emails processed within 5-10 minutes of arrival
- ✅ No manual restarts required for weeks/months
- ✅ SSL connection failures recover automatically
- ✅ Process restarts happen transparently

## 🔄 Long-term Maintenance

### **Weekly Checks**
- Review health check history
- Check disk space usage
- Monitor database growth

### **Monthly Maintenance**
- Restart container for fresh state
- Review and clean old logs
- Update if needed

The enhanced system is designed for **continuous operation** with **minimal manual intervention**. The auto-recovery mechanisms should handle most failure scenarios automatically.
