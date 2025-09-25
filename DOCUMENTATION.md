# Humano Multi-Pipeline Container - Complete Documentation

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Pipeline Types](#pipeline-types)
4. [Email Processing Flow](#email-processing-flow)
5. [Docker Setup & Commands](#docker-setup--commands)
6. [Configuration](#configuration)
7. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
8. [Development Guide](#development-guide)
9. [API Integration](#api-integration)
10. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## 🏗️ System Overview

The Humano Multi-Pipeline Container is an automated system that processes insurance data from Humano emails. It handles two distinct pipelines:

- **SI Pipeline (Salud Internacional)**: Processes international health insurance data
- **Viajeros Pipeline**: Processes travel insurance data

### Key Features

- ✅ **Dual Pipeline Support**: Handles both SI and Viajeros simultaneously
- ✅ **Email Automation**: Monitors IMAP for new emails and processes attachments
- ✅ **Pipeline Coordination**: Manages simultaneous pipeline execution with 5-minute coordination window
- ✅ **Error Handling**: Comprehensive error detection and reporting
- ✅ **Data Validation**: Pipeline-specific validation for Excel files and processing results
- ✅ **Automated Reporting**: Sends detailed email reports with pipeline differentiation
- ✅ **State Management**: SQLite database tracks pipeline sessions and prevents duplicate processing

---

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HUMANO MULTI-PIPELINE CONTAINER              │
├─────────────────────────────────────────────────────────────────┤
│  📧 EMAIL WATCHER                                               │
│  ├── IMAP IDLE Monitoring                                       │
│  ├── Email Pattern Detection                                    │
│  ├── Attachment Extraction                                      │
│  └── Pipeline Routing                                           │
├─────────────────────────────────────────────────────────────────┤
│  🔄 PIPELINE COORDINATOR                                        │
│  ├── Session Management                                         │
│  ├── State Tracking (SQLite)                                    │
│  ├── Timeout Management (5 min)                                │
│  └── Report Coordination                                        │
├─────────────────────────────────────────────────────────────────┤
│  📊 PIPELINE MANAGER                                            │
│  ├── Pipeline Type Detection                                    │
│  ├── File Routing                                               │
│  ├── Execution Management                                       │
│  └── Error Handling                                             │
├─────────────────────────────────────────────────────────────────┤
│  🏥 SI PIPELINE                    🧳 VIAJEROS PIPELINE          │
│  ├── File Comparison             ├── Excel Processing            │
│  ├── New Data Detection          ├── Date Filtering             │
│  ├── Emission Creation           ├── JSON Generation            │
│  └── Goval API Integration       └── Goval API Integration      │
├─────────────────────────────────────────────────────────────────┤
│  📧 ERROR HANDLER & REPORTING                                   │
│  ├── Pipeline-Aware Reports                                     │
│  ├── Success/Failure Detection                                  │
│  ├── HTML Email Generation                                       │
│  └── Resend API Integration                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
/app/
├── email_watcher/                    # Email monitoring system
│   ├── pipeline_watcher.py          # Main email processing
│   ├── health_check.py              # Container health monitoring
│   └── error_handler.py             # Backward compatibility
├── pipeline_manager.py              # Pipeline routing and execution
├── error_handler.py                 # Main error handling and reporting
├── shared/
│   ├── pipeline_coordinator.py     # Pipeline coordination system
│   ├── database/state/            # SQLite state database
│   └── logs/                      # Application logs
├── si_pipeline/                    # SI (Salud Internacional) pipeline
│   ├── main.py                     # SI pipeline entry point
│   ├── Comparador_Humano/
│   │   ├── comparador_SI.py       # File comparison logic
│   │   └── exceles/               # SI Excel files
│   │       ├── Asegurados_SI_old.xlsx  # Previous data
│   │       └── Asegurados_SI.xlsx      # New data from email
│   ├── emisor_goval/              # Goval API integration
│   └── data/                      # SI processing outputs
└── viajeros_pipeline/             # Viajeros pipeline
    ├── main.py                    # Viajeros pipeline entry point
    ├── Exceles/
    │   └── Asegurados_Viajeros.xlsx  # Viajeros data from email
    ├── emisor_goval/              # Goval API integration
    └── data/                      # Viajeros processing outputs
```

---

## 🔄 Pipeline Types

### SI Pipeline (Salud Internacional) - Enhanced with Individual Filtering

**Purpose**: Processes international health insurance data with automatic individual filtering

**Email Detection**:
- **Subject Pattern**: `"Asegurados Salud Internacional | YYYY-MM-DD"`
- **Sender**: `notificacionesInteligenciaTecnicaSI@humano.com.do`
- **Attachment**: `Asegurados_SI.xlsx`

**Enhanced Processing Flow**:
1. **File Comparison**: Compares new `Asegurados_SI.xlsx` with `Asegurados_SI_old.xlsx`
2. **New Data Detection**: Identifies new people/records
3. **Emission Creation**: Creates single emission JSON for new data
4. **API Integration**: Sends data to Goval API
5. **Error Handling**: If API error 417 (active coverage):
   - Extracts individuals with active coverage from API response
   - Filters JSON to remove failed individuals
   - Retries API processing with filtered data
   - Stores failed individuals data for email reporting
6. **File Update**: Updates `Asegurados_SI_old.xlsx` with new data

**Enhanced Validation**:
- Checks for Excel file existence and format
- Validates comparison results for new people
- Handles API validation errors automatically
- Reports "No new people" as informational success
- **NEW**: Automatically filters individuals with active coverage

### Viajeros Pipeline - Enhanced with Detailed Error Reporting

**Purpose**: Processes travel insurance data with comprehensive error reporting

**Email Detection**:
- **Subject Pattern**: `"Asegurados Viajeros | YYYY-MM-DD"`
- **Sender**: `notificacionesInteligenciaTecnicaSI@humano.com.do`
- **Attachment**: `Asegurados_Viajeros.xlsx`

**Enhanced Processing Flow**:
1. **Excel Processing**: Loads data from `Asegurados_Viajeros.xlsx`
2. **Date Filtering**: Filters records based on date criteria
3. **JSON Generation**: Converts Excel data to JSON format
4. **API Integration**: Sends data to Goval API
5. **Multiple Emissions**: Creates multiple emission files
6. **Error Tracking**: Tracks failed emissions with detailed individual information

**Enhanced Validation**:
- Checks for Excel file existence and format
- Validates date filtering results
- Reports "No valid records" as informational success
- **NEW**: Detailed error reporting with individual information from API responses

---

## 📧 Email Processing Flow

### 1. Email Detection & Monitoring

```python
# IMAP IDLE monitoring
client = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
client.login(IMAP_USER, IMAP_PASS)
client.select(IMAP_FOLDER)
client.idle()  # Continuous monitoring
```

### 2. Email Pattern Matching

```python
# Subject regex pattern
MATCH_SUBJECT_REGEX = r"(?i)^asegurados (viajeros|salud internacional)\s*\|\s*\d{4}-\d{2}-\d{2}$"

# Sender regex pattern  
MATCH_FROM_REGEX = r"(?i)notificacionesinteligenciatecnicaSI@humano\.com\.do"
```

### 3. Pipeline Detection & Routing

```python
def detect_pipeline_type(subject, from_addr):
    if "asegurados viajeros" in subject.lower():
        return "viajeros"
    elif "asegurados salud internacional" in subject.lower():
        return "si"
    else:
        return "unknown"
```

### 4. Pipeline Coordination

```python
# Session management
session_id = coordinator.start_pipeline_session(pipeline_type)

# Pipeline execution
success = run_pipeline(excel_file_path)

# Completion reporting
coordinator.complete_pipeline(pipeline_type, session_id, success, error_message)
```

### 5. Report Generation

- **Single Pipeline**: Immediate pipeline-specific report
- **Dual Pipeline**: Combined report after 5-minute coordination window
- **Timeout**: Partial report if coordination fails

---

## 🐳 Docker Setup & Commands

### Prerequisites

- Docker and Docker Compose installed
- Access to Humano email server
- Goval API credentials
- Resend API key for email reporting

### Initial Setup

```bash
# 1. Clone and navigate to project
cd Humano_Multi_Pipeline_Container

# 2. Copy configuration template
cp config.env.example .env

# 3. Edit configuration
nano .env
```

### Essential Docker Commands

#### **Container Management**

```bash
# Build and start container
docker compose up -d --build

# Stop container
docker compose down

# Restart container
docker compose restart

# View container status
docker compose ps

# View container logs
docker compose logs -f humano-multi-pipeline

# View recent logs
docker compose logs --tail=100 humano-multi-pipeline
```

#### **Container Interaction**

```bash
# Execute commands inside container
docker exec -it humano-multi-pipeline bash

# Run Python scripts
docker exec humano-multi-pipeline python /app/pipeline_manager.py

# Check container health
docker exec humano-multi-pipeline python /app/health_check.py

# View database state
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3 ".tables"
```

#### **File Management**

```bash
# Copy files to container
docker cp local_file.xlsx humano-multi-pipeline:/app/si_pipeline/Comparador_Humano/exceles/

# Copy files from container
docker cp humano-multi-pipeline:/app/logs/error.log ./logs/

# View mounted volumes
docker inspect humano-multi-pipeline | grep -A 10 "Mounts"
```

#### **Debugging Commands**

```bash
# Check container resources
docker stats humano-multi-pipeline

# View container environment variables
docker exec humano-multi-pipeline env

# Check network connectivity
docker exec humano-multi-pipeline ping secure.emailsrvr.com

# View container filesystem
docker exec humano-multi-pipeline ls -la /app/
```

### Volume Mounts

The container uses several volume mounts for persistent data:

```yaml
volumes:
  - ./shared/database/state:/state                    # SQLite state database
  - ./viajeros_pipeline/Exceles:/app/viajeros_pipeline/Exceles
  - ./si_pipeline/Comparador_Humano/exceles:/app/si_pipeline/Comparador_Humano/exceles
  - ./shared/logs:/app/logs                          # Application logs
  - ./viajeros_pipeline/data:/app/viajeros_pipeline/data
  - ./si_pipeline/data:/app/si_pipeline/data
```

---

## ⚙️ Configuration

### Environment Variables (.env file)

```bash
# IMAP Configuration
IMAP_HOST=secure.emailsrvr.com
IMAP_USER=ismael.ramirezaybar@agassist.net
IMAP_PASS=@bcD1234#
IMAP_FOLDER=INBOX
IMAP_SSL=true
IMAP_PORT=993

# Email Filtering
MATCH_SUBJECT_REGEX=(?i)^asegurados (viajeros|salud internacional)\s*\|\s*\d{4}-\d{2}-\d{2}$
MATCH_FROM_REGEX=(?i)notificacionesinteligenciatecnicaSI@humano\.com\.do

# Time Restrictions
ALLOWED_HOURS=08-20
ALLOWED_DAYS=mon,tue,wed,thu,fri,sat,sun
TZ=America/Santo_Domingo

# Pipeline Configuration
AUTOMATED_MODE=true
STATE_DB=/state/processed.sqlite3

# Goval API Configuration
GOVAL_API_URL=https://humano.goval-tpa.com/api
USUARIO=your_goval_username
PASSWORD=your_goval_password

# Email Reporting
RESEND_API_KEY=re_7nu2jYdo_6zaFWM9ZdfMKM6Zcq4yrweuv
```

### Pipeline-Specific Configuration

#### SI Pipeline Configuration
- **Required Files**: `Asegurados_SI_old.xlsx` (must exist for comparison)
- **Output Directory**: `/app/si_pipeline/data/`
- **Log Pattern**: `[si]` prefix in logs

#### Viajeros Pipeline Configuration  
- **Required Files**: `Asegurados_Viajeros.xlsx` (from email)
- **Output Directory**: `/app/viajeros_pipeline/data/`
- **Log Pattern**: `[viajeros]` prefix in logs

---

## 📊 Monitoring & Troubleshooting

### Health Monitoring

```bash
# Check container health status
docker compose ps

# Manual health check
docker exec humano-multi-pipeline python /app/health_check.py

# View health check logs
docker logs humano-multi-pipeline | grep "health"
```

### Log Analysis

#### **Log Locations**
- **Container Logs**: `docker compose logs humano-multi-pipeline`
- **Application Logs**: `./shared/logs/`
- **Pipeline Logs**: Embedded in container logs with prefixes

#### **Log Patterns**

```bash
# Email processing logs
grep "Email processing" ./shared/logs/*.log

# Pipeline execution logs
grep "\[si\]\|\[viajeros\]" ./shared/logs/*.log

# Error logs
grep "ERROR\|Exception" ./shared/logs/*.log

# Success logs
grep "SUCCESS\|completed successfully" ./shared/logs/*.log
```

### Database Monitoring

```bash
# Connect to SQLite database
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3

# View pipeline sessions
SELECT * FROM pipeline_sessions ORDER BY created_at DESC LIMIT 10;

# Check session status
SELECT session_id, si_status, viajeros_status, combined_report_sent 
FROM pipeline_sessions 
WHERE created_at > datetime('now', '-1 day');

# View processed emails
SELECT * FROM processed_emails ORDER BY processed_at DESC LIMIT 10;
```

### Performance Monitoring

```bash
# Container resource usage
docker stats humano-multi-pipeline

# Disk usage
docker exec humano-multi-pipeline df -h

# Memory usage
docker exec humano-multi-pipeline free -h

# Process monitoring
docker exec humano-multi-pipeline ps aux
```

---

## 🛠️ Development Guide

### Local Development Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Set up environment
cp config.env.example .env
# Edit .env with your credentials

# 3. Run individual components
python email_watcher/pipeline_watcher.py
python pipeline_manager.py
python si_pipeline/main.py
python viajeros_pipeline/main.py
```

### Testing Individual Pipelines

#### **Test SI Pipeline**
```bash
# Copy test file
cp test_data/Asegurados_SI.xlsx ./si_pipeline/Comparador_Humano/exceles/

# Run SI pipeline
docker exec humano-multi-pipeline python -c "
import sys
sys.path.append('/app/si_pipeline')
from main import run_si_pipeline, main
run_si_pipeline()
main()
"
```

#### **Test Viajeros Pipeline**
```bash
# Copy test file
cp test_data/Asegurados_Viajeros.xlsx ./viajeros_pipeline/Exceles/

# Run Viajeros pipeline
docker exec humano-multi-pipeline python -c "
import sys
sys.path.append('/app/viajeros_pipeline')
from main import run_viajeros_pipeline, main
run_viajeros_pipeline()
main()
"
```

### Manual Email Testing

```bash
# Test email processing manually
docker exec humano-multi-pipeline python -c "
import sys
sys.path.append('/app')
from pipeline_watcher import process_email_attachments
import imaplib
import email

# Connect and get latest email
mail = imaplib.IMAP4_SSL('secure.emailsrvr.com', 993)
mail.login('ismael.ramirezaybar@agassist.net', '@bcD1234#')
mail.select('INBOX')

# Get latest email
status, msg_data = mail.fetch(b'LATEST', '(RFC822)')
email_message = email.message_from_bytes(msg_data[0][1])

# Process email
success = process_email_attachments(email_message)
print(f'Processing result: {success}')

mail.close()
mail.logout()
"
```

---

## 🔌 API Integration

### Goval API Integration

Both pipelines integrate with the Goval API for policy processing:

```python
# API Configuration
GOVAL_API_URL = "https://humano.goval-tpa.com/api"
USUARIO = "your_username"
PASSWORD = "your_password"

# Authentication
auth_response = requests.post(f"{GOVAL_API_URL}/auth", {
    "usuario": USUARIO,
    "password": PASSWORD
})

# Policy Processing
policy_response = requests.post(f"{GOVAL_API_URL}/policies", {
    "data": policy_data,
    "headers": {"Authorization": f"Bearer {token}"}
})
```

### Resend API Integration

Email reports are sent using the Resend API:

```python
# Email Configuration
RESEND_API_KEY = "re_7nu2jYdo_6zaFWM9ZdfMKM6Zcq4yrweuv"

# Report Recipients
report_recipients = [
    'ismael.ramirezaybar@agassist.net'
]

# Send Report
resend.api_key = RESEND_API_KEY
resend.Emails.send({
    "from": "noreply@agassist.net",
    "to": report_recipients,
    "subject": f"✅ [{pipeline_name}] Daily Report",
    "html": html_report
})
```

---

## 🚨 Troubleshooting Common Issues

### Container Won't Start

```bash
# Check Docker daemon
docker --version
docker compose --version

# Check configuration
docker compose config

# View build logs
docker compose build --no-cache

# Check port conflicts
netstat -tulpn | grep :993
```

### Email Connection Issues

```bash
# Test IMAP connection
docker exec humano-multi-pipeline python -c "
import imaplib
try:
    mail = imaplib.IMAP4_SSL('secure.emailsrvr.com', 993)
    mail.login('ismael.ramirezaybar@agassist.net', '@bcD1234#')
    print('✅ IMAP connection successful')
    mail.logout()
except Exception as e:
    print(f'❌ IMAP connection failed: {e}')
"

# Check network connectivity
docker exec humano-multi-pipeline ping -c 3 secure.emailsrvr.com
```

### Pipeline Execution Failures

```bash
# Check pipeline logs
docker exec humano-multi-pipeline python -c "
import sys
sys.path.append('/app')
from pipeline_manager import run_si_pipeline, run_viajeros_pipeline

# Test SI pipeline
print('Testing SI pipeline...')
result = run_si_pipeline('/tmp/test_si.xlsx')
print(f'SI result: {result}')

# Test Viajeros pipeline  
print('Testing Viajeros pipeline...')
result = run_viajeros_pipeline('/tmp/test_viajeros.xlsx')
print(f'Viajeros result: {result}')
"
```

### File Permission Issues

```bash
# Check file permissions
docker exec humano-multi-pipeline ls -la /app/si_pipeline/Comparador_Humano/exceles/
docker exec humano-multi-pipeline ls -la /app/viajeros_pipeline/Exceles/

# Fix permissions
docker exec humano-multi-pipeline chmod 755 /app/si_pipeline/Comparador_Humano/exceles/
docker exec humano-multi-pipeline chmod 755 /app/viajeros_pipeline/Exceles/
```

### Database Issues

```bash
# Check database file
docker exec humano-multi-pipeline ls -la /state/

# Repair database
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3 ".schema"

# Reset database (CAUTION: This will clear all state)
docker exec humano-multi-pipeline rm /state/processed.sqlite3
```

### Memory Issues

```bash
# Check memory usage
docker stats humano-multi-pipeline

# Increase memory limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G  # Increase from 1G
      cpus: '2.0'  # Increase from 1.0
```

### Email Report Issues

```bash
# Test Resend API
docker exec humano-multi-pipeline python -c "
import resend
resend.api_key = 're_7nu2jYdo_6zaFWM9ZdfMKM6Zcq4yrweuv'
try:
    result = resend.Emails.send({
        'from': 'noreply@agassist.net',
        'to': ['ismael.ramirezaybar@agassist.net'],
        'subject': 'Test Email',
        'html': '<p>Test email from container</p>'
    })
    print(f'✅ Email sent: {result}')
except Exception as e:
    print(f'❌ Email failed: {e}')
"
```

---

## 📞 Support & Maintenance

### Regular Maintenance Tasks

```bash
# Weekly log cleanup
docker exec humano-multi-pipeline find /app/logs -name "*.log" -mtime +7 -delete

# Database backup
docker exec humano-multi-pipeline cp /state/processed.sqlite3 /state/backup_$(date +%Y%m%d).sqlite3

# Container restart (weekly)
docker compose restart humano-multi-pipeline

# Resource monitoring
docker stats humano-multi-pipeline --no-stream
```

### Emergency Procedures

```bash
# Stop all processing
docker compose down

# Restart with fresh state
docker compose down
docker volume rm humano-multi-pipeline_state
docker compose up -d --build

# Manual pipeline execution
docker exec humano-multi-pipeline python /app/pipeline_manager.py
```

### Contact Information

- **Primary Contact**: ismael.ramirezaybar@agassist.net
- **System Administrator**: AG Assist Team
- **Emergency Contact**: Available 24/7 for critical issues

---

## 📚 Additional Resources

- [Pipeline Coordination Documentation](./PIPELINE_COORDINATION.md)
- [Enhanced Error Handling](./ENHANCED_ERROR_HANDLING.md)
- [Single Pipeline Handling](./SINGLE_PIPELINE_HANDLING.md)
- [Docker Documentation](https://docs.docker.com/)
- [IMAP Protocol Reference](https://tools.ietf.org/html/rfc3501)
- [Resend API Documentation](https://resend.com/docs)

---

*Last Updated: January 2025*
*Version: 2.0*
*Maintained by: AG Assist Development Team*
