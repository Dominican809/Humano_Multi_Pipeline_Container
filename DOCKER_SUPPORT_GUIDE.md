# Docker Support Guide - Humano Multi-Pipeline Container

## 🐳 **Essential Docker Commands for Support**

### **1. Container Management**

#### **Start the Application**
```bash
# Navigate to project directory
cd "/Users/ismaelramirez/Desktop/Cosas_para_trabajar /AGA/Humano_Multi_Pipeline_Container"

# Start the container
docker compose up -d

# Check status
docker compose ps
```

#### **Stop the Application**
```bash
# Stop container
docker compose down

# Stop and remove volumes (CAUTION: This will delete all data)
docker compose down -v
```

#### **Restart the Application**
```bash
# Restart container
docker compose restart

# Restart with rebuild (after code changes)
docker compose down && docker compose up -d --build
```

### **2. Monitoring & Health Checks**

#### **Check Container Status**
```bash
# View container status
docker compose ps

# Check container health
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# View resource usage
docker stats humano-multi-pipeline
```

#### **View Logs**
```bash
# View all logs
docker compose logs humano-multi-pipeline

# Follow logs in real-time
docker compose logs -f humano-multi-pipeline

# View last 100 lines
docker compose logs --tail=100 humano-multi-pipeline

# View logs with timestamps
docker compose logs -t humano-multi-pipeline
```

#### **Health Check**
```bash
# Manual health check
docker exec humano-multi-pipeline python /app/health_check.py

# Check container health status
docker inspect humano-multi-pipeline | grep -A 10 "Health"
```

### **3. Debugging & Troubleshooting**

#### **Access Container Shell**
```bash
# Access container bash shell
docker exec -it humano-multi-pipeline bash

# Run commands inside container
docker exec humano-multi-pipeline ls -la /app/

# Check environment variables
docker exec humano-multi-pipeline env
```

#### **Check File System**
```bash
# List application files
docker exec humano-multi-pipeline ls -la /app/

# Check mounted volumes
docker exec humano-multi-pipeline ls -la /app/si_pipeline/data/
docker exec humano-multi-pipeline ls -la /app/viajeros_pipeline/data/

# Check logs directory
docker exec humano-multi-pipeline ls -la /app/logs/

# Check state database
docker exec humano-multi-pipeline ls -la /state/
```

#### **Database Operations**
```bash
# Connect to SQLite database
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3

# View database tables
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3 ".tables"

# Check pipeline sessions
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3 "SELECT * FROM pipeline_sessions ORDER BY created_at DESC LIMIT 5;"

# Check processed emails
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3 "SELECT * FROM processed_emails ORDER BY processed_at DESC LIMIT 5;"
```

### **4. File Management**

#### **Copy Files to Container**
```bash
# Copy Excel file to SI pipeline
docker cp local_file.xlsx humano-multi-pipeline:/app/si_pipeline/Comparador_Humano/exceles/

# Copy Excel file to Viajeros pipeline
docker cp local_file.xlsx humano-multi-pipeline:/app/viajeros_pipeline/Exceles/

# Copy configuration file
docker cp .env humano-multi-pipeline:/app/
```

#### **Copy Files from Container**
```bash
# Copy logs from container
docker cp humano-multi-pipeline:/app/logs/ ./logs/

# Copy tracking files
docker cp humano-multi-pipeline:/app/si_pipeline/data/tracking/ ./si_tracking/
docker cp humano-multi-pipeline:/app/viajeros_pipeline/data/tracking/ ./viajeros_tracking/

# Copy generated JSON files
docker cp humano-multi-pipeline:/app/si_pipeline/emision_unica.json ./
docker cp humano-multi-pipeline:/app/viajeros_pipeline/emisiones_generadas.json ./
```

### **5. Testing & Manual Operations**

#### **Test Email Processing**
```bash
# Test email connection
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

#### **Test Pipeline Processing**
```bash
# Test SI pipeline
docker exec humano-multi-pipeline python -c "
import sys
sys.path.append('/app/si_pipeline')
from main import run_si_pipeline, main
print('Testing SI pipeline...')
pipeline_success = run_si_pipeline()
if pipeline_success:
    print('✅ SI pipeline setup successful')
else:
    print('❌ SI pipeline setup failed')
"

# Test Viajeros pipeline
docker exec humano-multi-pipeline python -c "
import sys
sys.path.append('/app/viajeros_pipeline')
from main import run_viajeros_pipeline, main
print('Testing Viajeros pipeline...')
pipeline_success = run_viajeros_pipeline()
if pipeline_success:
    print('✅ Viajeros pipeline setup successful')
else:
    print('❌ Viajeros pipeline setup failed')
"
```

### **6. Maintenance Operations**

#### **Clean Up Operations**
```bash
# Clean Docker system
docker system prune -f

# Clean unused images
docker image prune -f

# Clean unused volumes
docker volume prune -f

# Clean everything (CAUTION: This removes all unused Docker resources)
docker system prune -a -f
```

#### **Backup Operations**
```bash
# Backup state database
docker cp humano-multi-pipeline:/state/processed.sqlite3 ./backup_$(date +%Y%m%d).sqlite3

# Backup tracking files
docker cp humano-multi-pipeline:/app/si_pipeline/data/tracking/ ./backup_si_tracking_$(date +%Y%m%d)/
docker cp humano-multi-pipeline:/app/viajeros_pipeline/data/tracking/ ./backup_viajeros_tracking_$(date +%Y%m%d)/

# Backup logs
docker cp humano-multi-pipeline:/app/logs/ ./backup_logs_$(date +%Y%m%d)/
```

#### **Restore Operations**
```bash
# Restore state database
docker cp ./backup_20250920.sqlite3 humano-multi-pipeline:/state/processed.sqlite3

# Restore tracking files
docker cp ./backup_si_tracking_20250920/ humano-multi-pipeline:/app/si_pipeline/data/tracking/
docker cp ./backup_viajeros_tracking_20250920/ humano-multi-pipeline:/app/viajeros_pipeline/data/tracking/
```

### **7. Performance Monitoring**

#### **Resource Usage**
```bash
# Monitor resource usage
docker stats humano-multi-pipeline

# Check memory usage
docker exec humano-multi-pipeline free -h

# Check disk usage
docker exec humano-multi-pipeline df -h

# Check process list
docker exec humano-multi-pipeline ps aux
```

#### **Network Connectivity**
```bash
# Test network connectivity
docker exec humano-multi-pipeline ping -c 3 secure.emailsrvr.com
docker exec humano-multi-pipeline ping -c 3 humano.goval-tpa.com

# Check DNS resolution
docker exec humano-multi-pipeline nslookup secure.emailsrvr.com
```

### **8. Emergency Procedures**

#### **Container Won't Start**
```bash
# Check build logs
docker compose build --no-cache

# Check container logs
docker compose logs humano-multi-pipeline

# Check configuration
docker compose config

# Restart with fresh state
docker compose down
docker volume rm humano_multi_pipeline_container_state
docker compose up -d --build
```

#### **Application Errors**
```bash
# Check application logs
docker compose logs --tail=50 humano-multi-pipeline

# Check health status
docker exec humano-multi-pipeline python /app/health_check.py

# Restart application
docker compose restart humano-multi-pipeline

# Force restart
docker compose down && docker compose up -d
```

#### **Data Recovery**
```bash
# Check if data volumes are mounted correctly
docker inspect humano-multi-pipeline | grep -A 10 "Mounts"

# Check volume contents
docker exec humano-multi-pipeline ls -la /app/si_pipeline/data/
docker exec humano-multi-pipeline ls -la /app/viajeros_pipeline/data/

# Restore from backup
docker cp ./backup_data/ humano-multi-pipeline:/app/si_pipeline/data/
```

### **9. Configuration Management**

#### **Update Configuration**
```bash
# Update .env file
nano .env

# Restart container to apply changes
docker compose restart

# Check environment variables
docker exec humano-multi-pipeline env | grep -E "(IMAP|GOVAL|RESEND)"
```

#### **Update Code**
```bash
# After code changes, rebuild and restart
docker compose down
docker compose up -d --build

# Check if changes are applied
docker exec humano-multi-pipeline ls -la /app/
```

### **10. Support Checklist**

#### **Daily Health Check**
```bash
# 1. Check container status
docker compose ps

# 2. Check logs for errors
docker compose logs --tail=20 humano-multi-pipeline

# 3. Check health status
docker exec humano-multi-pipeline python /app/health_check.py

# 4. Check resource usage
docker stats humano-multi-pipeline --no-stream
```

#### **Weekly Maintenance**
```bash
# 1. Clean up old logs
docker exec humano-multi-pipeline find /app/logs -name "*.log" -mtime +7 -delete

# 2. Backup state database
docker cp humano-multi-pipeline:/state/processed.sqlite3 ./backup_$(date +%Y%m%d).sqlite3

# 3. Check disk usage
docker exec humano-multi-pipeline df -h

# 4. Restart container
docker compose restart
```

#### **Monthly Maintenance**
```bash
# 1. Clean Docker system
docker system prune -f

# 2. Update base image (if needed)
docker compose build --no-cache

# 3. Full backup
mkdir -p ./monthly_backup_$(date +%Y%m)
docker cp humano-multi-pipeline:/state/ ./monthly_backup_$(date +%Y%m)/
docker cp humano-multi-pipeline:/app/si_pipeline/data/ ./monthly_backup_$(date +%Y%m)/si_data/
docker cp humano-multi-pipeline:/app/viajeros_pipeline/data/ ./monthly_backup_$(date +%Y%m)/viajeros_data/
```

---

## 🚨 **Emergency Contacts**

- **Primary Support**: ismael.ramirezaybar@agassist.net
- **System Administrator**: AG Assist Team
- **Emergency**: Available 24/7 for critical issues

---

## 📚 **Additional Resources**

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Project Documentation](./DOCUMENTATION.md)
- [Data Flow Documentation](./DATA_FLOW_AND_FAILURE_LOGGING.md)

---

*Last Updated: September 2025*
*Version: 2.0*
*Maintained by: AG Assist Development Team*
