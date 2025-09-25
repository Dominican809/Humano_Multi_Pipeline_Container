# System Flow Diagrams

## 🏗️ Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           HUMANO MULTI-PIPELINE CONTAINER                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  📧 EMAIL WATCHER (pipeline_watcher.py)                                        │
│  ├── IMAP IDLE Monitoring (30s polling)                                        │
│  ├── Email Pattern Matching (Subject + Sender)                                 │
│  ├── Attachment Extraction (Excel files)                                       │
│  ├── Multiple Email Processing (Sequential)                                    │
│  └── Pipeline Routing (via Pipeline Manager)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  🔄 PIPELINE COORDINATOR (shared/pipeline_coordinator.py)                      │
│  ├── Session Management (SQLite)                                               │
│  ├── Pipeline State Tracking                                                   │
│  ├── 5-Minute Coordination Window                                             │
│  ├── Combined Report Generation                                                │
│  └── Timeout Handling                                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  📊 PIPELINE MANAGER (pipeline_manager.py)                                     │
│  ├── Pipeline Type Detection (Subject Analysis)                               │
│  ├── File Validation & Routing                                                 │
│  ├── SI Pipeline Execution (corrected_main.py)                                │
│  ├── Viajeros Pipeline Execution (main.py)                                     │
│  └── Error Handling & Reporting                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  🏥 SI PIPELINE (Enhanced with Individual Filtering)                           │
│  ├── File Comparison (comparador_SI.py)                                        │
│  ├── Single Emission Creation (SI_excel_to_emision.py)                        │
│  ├── API Processing with Retry Logic                                           │
│  ├── Individual Filtering (Error 417 handling)                                │
│  └── Failed Individuals Data Storage                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  🧳 VIAJEROS PIPELINE (Enhanced with Detailed Reporting)                       │
│  ├── Excel Processing (main.py)                                                │
│  ├── Date Filtering (April 2025+)                                             │
│  ├── Multiple Emissions Creation                                               │
│  ├── API Processing (procesar_validacion.py)                                  │
│  └── Error Tracking with Individual Details                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  🚨 ERROR HANDLER (shared/error_handler.py)                                   │
│  ├── Pipeline-Specific Data Collection                                         │
│  ├── Failed Individuals Data Processing                                        │
│  ├── HTML Report Generation (Individual Details)                              │
│  └── Email Delivery (Resend API)                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 📧 Email Processing Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Email Server  │───▶│  IMAP IDLE       │───▶│  Email Pattern  │
│   (IMAP)        │    │  Monitoring      │    │  Matching       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Multiple Email │◀───│  Attachment      │◀───│  Pipeline Type  │
│  Processing     │    │  Extraction      │    │  Detection      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Date-Based     │    │  Excel Files     │    │  Pipeline       │
│  Ordering       │    │  (SI/Viajeros)   │    │  Manager        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🏥 SI Pipeline Flow (Enhanced with Individual Filtering)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  New Excel      │───▶│  File Comparison │───▶│  Comparison     │
│  (Asegurados_SI)│    │  (comparador_SI) │    │  Result Excel   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Old File       │    │  Automatic File  │    │  Single Emission│
│  Replacement    │◀───│  Update          │    │  Creation       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  API Processing │◀───│  First API       │◀───│  emission_unica │
│  (procesar_     │    │  Attempt         │    │  .json          │
│  validacion)    │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐
│  Error 417?     │    │  Success         │
│  (Active        │    │  Processing      │
│  Coverage)      │    │                  │
└─────────────────┘    └──────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Extract Failed │───▶│  Filter JSON     │───▶│  Retry API      │
│  Individuals    │    │  (Remove Failed) │    │  Processing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Store Failed   │    │  Clean Up        │    │  Store Success  │
│  Individuals    │    │  Temp Files      │    │  Results        │
│  Data           │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🧳 Viajeros Pipeline Flow (Enhanced with Detailed Reporting)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Excel File     │───▶│  Excel           │───▶│  Date Filtering │
│  (Asegurados_   │    │  Processing      │    │  (April 2025+)  │
│  Viajeros)      │    │  (main.py)       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Multiple       │◀───│  JSON Generation │◀───│  Valid Records  │
│  Emissions      │    │  (Multiple)      │    │  Check          │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  API Processing │    │  Error Tracking  │    │  Success        │
│  (procesar_     │    │  (Individual     │    │  Tracking       │
│  validacion)    │    │  Details)        │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Store Results  │    │  Store Failed    │    │  Store Success  │
│  (Success +     │    │  Individuals     │    │  Results        │
│  Failures)      │    │  Data            │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔄 Pipeline Manager Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Email Data     │───▶│  Pipeline Type   │───▶│  File Validation│
│  (Subject +     │    │  Detection       │    │  & Routing      │
│  Attachment)    │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  SI Pipeline    │    │  Viajeros        │    │  Pipeline       │
│  Execution      │    │  Pipeline        │    │  Coordination   │
│  (corrected_    │    │  Execution       │    │  (Session Mgmt) │
│  main.py)       │    │  (main.py)       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Individual     │    │  Detailed Error  │    │  Error Handler  │
│  Filtering      │    │  Reporting       │    │  Integration    │
│  Results        │    │  Results         │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚨 Error Handler Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Pipeline       │───▶│  Data Collection │───▶│  Failed         │
│  Completion     │    │  (SI/Viajeros)   │    │  Individuals    │
│  Events         │    │                  │    │  Data Processing│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  HTML Report    │◀───│  Report          │◀───│  Individual     │
│  Generation     │    │  Generation      │    │  Details        │
│  (Individual    │    │  (Pipeline-      │    │  Integration    │
│  Information)   │    │  Specific)       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐
│  Email Delivery │    │  Resend API      │
│  (Resend API)   │    │  Integration     │
└─────────────────┘    └──────────────────┘
```

## 📊 Individual Filtering Process (SI Pipeline)

```
┌─────────────────┐
│  API Error 417  │
│  (Active        │
│  Coverage)      │
└─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Extract Failed │───▶│  Create Failed   │───▶│  Filter JSON    │
│  Individuals    │    │  Individuals     │    │  (Remove Failed │
│  from API       │    │  Sets (Passport  │    │  Individuals)   │
│  Response       │    │  + Identity)     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Store Failed   │    │  Create Filtered │    │  Retry API      │
│  Individuals    │    │  JSON File       │    │  Processing     │
│  Data           │    │  (emission_      │    │  (Filtered Data)│
│  (for Reports)  │    │  unica_filtered) │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Clean Up       │◀───│  Store Success   │◀───│  Success        │
│  Temp Files     │    │  Results         │    │  Processing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🗄️ Database and State Management

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Pipeline       │───▶│  Session         │───▶│  SQLite         │
│  Sessions       │    │  Management      │    │  Database       │
│  (Coordination) │    │  (State          │    │  (/state/)      │
│                 │    │  Tracking)       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Pipeline       │    │  Processed       │    │  Failed         │
│  Executions     │    │  Emails          │    │  Individuals    │
│  (Logging)      │    │  (Deduplication) │    │  Data           │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📧 Email Report Structure

```
┌─────────────────┐
│  Email Subject  │
│  (Pipeline +    │
│  Status +       │
│  Email Subject) │
└─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Processing     │    │  Pipeline        │    │  Failed         │
│  Statistics     │    │  Breakdown       │    │  Individuals    │
│  (Success/      │    │  (SI/Viajeros)   │    │  Details        │
│  Failed Counts) │    │  (Color-coded)   │    │  (Individual    │
│                 │    │                  │    │  Information)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  System         │    │  HTML Report     │    │  Email Delivery │
│  Information    │    │  Generation      │    │  (Resend API)   │
│  (Pipeline      │    │  (Professional   │    │                 │
│  Type + Env)    │    │  Styling)        │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔧 Configuration and Environment

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Environment    │───▶│  Docker          │───▶│  Volume Mounts  │
│  Variables      │    │  Configuration   │    │  (Persistent    │
│  (.env file)    │    │  (docker-        │    │  Data)          │
│                 │    │  compose.yml)    │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  IMAP Settings  │    │  Health Checks   │    │  Log Management │
│  (Email Server) │    │  (Container      │    │  (Rotation +    │
│                 │    │  Monitoring)     │    │  Cleanup)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🎯 Key Data Flows

### **1. Email → Pipeline Processing:**
```
Email → IMAP → Pattern Match → Extract Excel → Detect Pipeline → 
Validate File → Execute Pipeline → Process API → Handle Errors → 
Generate Report → Send Email
```

### **2. SI Pipeline with Individual Filtering:**
```
Excel → Compare Files → Create Emission → API Call → Error 417? → 
Extract Individuals → Filter JSON → Retry API → Store Results → 
Generate Report
```

### **3. Viajeros Pipeline with Error Reporting:**
```
Excel → Process Data → Filter Dates → Create Emissions → API Calls → 
Track Errors → Store Individual Details → Generate Report
```

### **4. Error Handling and Reporting:**
```
Pipeline Completion → Collect Data → Process Failed Individuals → 
Generate HTML Report → Send Email → Update Database
```

## 📈 Monitoring and Health Checks

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Container      │───▶│  Health Check    │───▶│  Log Analysis   │
│  Status         │    │  (60s interval)  │    │  (Pattern       │
│  (Docker)       │    │                  │    │  Matching)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Resource       │    │  Database        │    │  Error          │
│  Monitoring     │    │  Monitoring      │    │  Alerting       │
│  (CPU/Memory)   │    │  (SQLite Queries)│    │  (Email Reports)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

This comprehensive flow diagram shows the complete system architecture, data flows, and processes for both pipelines with the enhanced individual filtering and error handling capabilities.
