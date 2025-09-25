# Humano Multi-Pipeline Container

A comprehensive insurance policy automation system for Humano Insurance, supporting both Viajeros (Travel) and Salud Internacional (International Health) insurance pipelines.

## 🚀 Features

### **Dual Pipeline Support**
- **Viajeros Pipeline**: Travel insurance policy processing
- **SI Pipeline**: International health insurance policy processing
- **Unified Email Processing**: Single email watcher handles both pipeline types

### **Advanced Email Monitoring**
- **IMAP Email Watcher**: Monitors email inbox for trigger emails
- **Automatic Excel Extraction**: Extracts and processes Excel attachments
- **Smart Pipeline Detection**: Automatically routes emails to correct pipeline
- **Enhanced Auto-Recovery**: Robust connection handling with SSL fallbacks

### **Comprehensive Error Handling**
- **Unified Statistics System**: Centralized statistics management
- **Accurate Email Reports**: Real-time processing statistics in email notifications
- **Auto-Restart Mechanisms**: Automatic recovery from failures
- **Health Monitoring**: Continuous system health checks

### **Production-Ready Features**
- **Docker Containerization**: Complete containerized deployment
- **Persistent State Management**: SQLite database for email deduplication
- **Comprehensive Logging**: Detailed logging with loguru
- **Health Checks**: Docker health check integration

## 📋 System Architecture

```
Email Watcher → Pipeline Manager → Pipeline Coordinator → Individual Pipelines
     ↓              ↓                    ↓                      ↓
IMAP Monitor → Excel Extraction → Statistics Manager → Viajeros/SI Processing
     ↓              ↓                    ↓                      ↓
Auto-Recovery → Error Handling → Email Reports → API Integration
```

## 🛠️ Installation & Setup

### **Prerequisites**
- Docker and Docker Compose
- Python 3.8+
- Access to Humano IMAP server
- Goval API credentials

### **Quick Start**

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Dominican809/Humano_Multi_Pipeline_Container.git
   cd Humano_Multi_Pipeline_Container
   ```

2. **Configure environment**:
   ```bash
   cp config.env.example .env
   # Edit .env with your actual credentials
   ```

3. **Start the system**:
   ```bash
   ./start.sh
   ```

4. **Monitor the system**:
   ```bash
   docker compose logs -f humano-multi-pipeline
   ```

## ⚙️ Configuration

### **Environment Variables**

```bash
# IMAP Configuration
IMAP_HOST=secure.emailsrvr.com
IMAP_USER=your_email@domain.com
IMAP_PASS=your_password
IMAP_FOLDER=INBOX

# Email Filtering
MATCH_SUBJECT_REGEX=(?i)^asegurados (viajeros|salud internacional)\s*\|\s*\d{4}-\d{2}-\d{2}$
MATCH_FROM_REGEX=(?i)notificacionesinteligenciatecnicaSI@humano\.com\.do

# Time Restrictions
ALLOWED_HOURS=08-20
ALLOWED_DAYS=mon,tue,wed,thu,fri,sat,sun
TZ=America/Santo_Domingo

# Goval API Configuration
GOVAL_API_URL=https://humano.goval-tpa.com/api
USUARIO=your_goval_username
PASSWORD=your_goval_password

# Email Reporting
RESEND_API_KEY=your_resend_api_key
```

## 📊 Pipeline Processing

### **Viajeros Pipeline**
- Processes travel insurance policies
- Handles multiple passengers per policy
- Supports retry logic for failed emissions
- Generates detailed success/failure reports

### **SI Pipeline**
- Processes international health insurance policies
- Compares old vs new Excel files to find new people
- Filters out individuals with active coverage
- Handles individual-level validation errors

## 🔧 Monitoring & Maintenance

### **Health Checks**
```bash
# Check system health
docker exec humano-multi-pipeline python /app/email_watcher/health_check.py

# Enable continuous monitoring
docker exec -d humano-multi-pipeline python /app/email_watcher/health_check.py --monitor
```

### **Diagnostics**
```bash
# Run SI pipeline diagnostics
docker exec humano-multi-pipeline python /app/si_pipeline_diagnostic.py

# Test email reporting system
docker exec humano-multi-pipeline python /app/test_email_reporting.py
```

### **Logs**
```bash
# View real-time logs
docker compose logs -f humano-multi-pipeline

# Check specific pipeline logs
docker logs humano-multi-pipeline | grep -E "(viajeros|si)"
```

## 📧 Email Reports

The system sends detailed email reports for each pipeline execution:

### **Successful Processing**
```
Subject: [Humano Insurance] ✅ [Viajeros] Daily Report - 15 policies processed successfully

Content:
- Total People: 18
- Successful People: 15
- Failed People: 3
- Success Rate: 83.3%
- Successful Emissions: 4
- Total Emissions: 4
```

### **No New Records**
```
Subject: [Humano Insurance] ℹ️ [SI] Daily Report - No new people found

Content:
- Total People: 0
- Successful People: 0
- Failed People: 0
- Success Rate: 0.0%
- Note: No new records found in comparison
```

## 🚨 Troubleshooting

### **Common Issues**

1. **Email Watcher Not Processing Emails**
   ```bash
   # Check IMAP connection
   docker logs humano-multi-pipeline | grep -E "(IMAP|connection)"
   
   # Restart email watcher
   docker restart humano-multi-pipeline
   ```

2. **SI Pipeline Showing 0 Processed**
   ```bash
   # Run diagnostics
   docker exec humano-multi-pipeline python /app/si_pipeline_diagnostic.py
   
   # Check if Excel file has new people
   docker exec humano-multi-pipeline ls -la /app/si_pipeline/Comparador_Humano/exceles/
   ```

3. **Statistics Showing Zeros in Email Reports**
   ```bash
   # Test statistics system
   docker exec humano-multi-pipeline python /app/test_email_reporting.py
   
   # Check statistics files
   docker exec humano-multi-pipeline ls -la /app/shared/stats/
   ```

### **Debug Commands**
```bash
# Check container status
docker compose ps

# View container stats
docker stats humano-multi-pipeline

# Access container shell
docker exec -it humano-multi-pipeline bash

# Check database
docker exec humano-multi-pipeline sqlite3 /state/processed.sqlite3 "SELECT * FROM processed ORDER BY ts DESC LIMIT 10;"
```

## 📁 Project Structure

```
Humano_Multi_Pipeline_Container/
├── email_watcher/              # Email monitoring and processing
│   ├── pipeline_watcher.py     # Main email watcher
│   ├── health_check.py         # Health monitoring
│   └── error_handler.py        # Error handling
├── shared/                     # Shared utilities
│   ├── statistics_manager.py   # Statistics management
│   ├── error_handler.py       # Unified error handling
│   └── pipeline_coordinator.py # Pipeline coordination
├── viajeros_pipeline/         # Travel insurance pipeline
│   ├── main.py                # Main processing logic
│   └── emisor_goval/          # Goval API integration
├── si_pipeline/               # International health pipeline
│   ├── corrected_main.py      # Main processing logic
│   ├── Comparador_Humano/     # File comparison logic
│   └── emisor_goval/          # Goval API integration
├── docker-compose.yml         # Docker configuration
├── Dockerfile                 # Container definition
├── start.sh                   # Startup script
└── README.md                  # This file
```

## 🔄 Recent Improvements

### **Enhanced Email Reporting**
- ✅ **Accurate Statistics**: Real processing numbers instead of zeros
- ✅ **Single Email Per Run**: One email per pipeline execution
- ✅ **Unified Statistics System**: Centralized statistics management
- ✅ **Better Error Handling**: Clear success/failure reporting

### **Robust Email Watcher**
- ✅ **SSL Connection Handling**: Multiple connection strategies
- ✅ **Auto-Recovery**: Automatic restart on failures
- ✅ **Health Monitoring**: Continuous health checks
- ✅ **Smart Backoff**: Intelligent retry logic

### **SI Pipeline Debugging**
- ✅ **Comprehensive Logging**: Detailed step-by-step logging
- ✅ **File Validation**: Checks file existence and content
- ✅ **Diagnostic Tools**: Complete diagnostic script
- ✅ **Error Detection**: Better error identification

## 📞 Support

For issues and questions:
- Check the troubleshooting section above
- Run the diagnostic scripts
- Review the logs for specific errors
- Create an issue in this repository

## 📄 License

This project is proprietary software for Humano Insurance.

---

**Built with ❤️ for Humano Insurance**