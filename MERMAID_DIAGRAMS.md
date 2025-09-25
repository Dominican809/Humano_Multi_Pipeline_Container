# Mermaid Flow Diagrams

## 🏗️ Complete System Architecture

```mermaid
graph TB
    subgraph "Email Server"
        EMAIL[📧 Email with Excel Attachment]
    end
    
    subgraph "Humano Multi-Pipeline Container"
        subgraph "Email Watcher"
            IMAP[IMAP IDLE Monitoring]
            MATCH[Email Pattern Matching]
            EXTRACT[Attachment Extraction]
        end
        
        subgraph "Pipeline Coordinator"
            SESSION[Session Management]
            STATE[State Tracking]
            COORD[5-Min Coordination]
        end
        
        subgraph "Pipeline Manager"
            DETECT[Pipeline Type Detection]
            VALIDATE[File Validation]
            ROUTE[Pipeline Routing]
        end
        
        subgraph "SI Pipeline (Enhanced)"
            COMPARE[File Comparison]
            EMISSION[Single Emission Creation]
            API1[API Processing]
            FILTER[Individual Filtering]
            RETRY[Retry Logic]
        end
        
        subgraph "Viajeros Pipeline (Enhanced)"
            EXCEL[Excel Processing]
            DATE[Date Filtering]
            MULTI[Multiple Emissions]
            API2[API Processing]
            TRACK[Error Tracking]
        end
        
        subgraph "Error Handler"
            COLLECT[Data Collection]
            REPORT[Report Generation]
            SEND[Email Delivery]
        end
    end
    
    EMAIL --> IMAP
    IMAP --> MATCH
    MATCH --> EXTRACT
    EXTRACT --> DETECT
    DETECT --> VALIDATE
    VALIDATE --> ROUTE
    ROUTE --> COMPARE
    ROUTE --> EXCEL
    COMPARE --> EMISSION
    EMISSION --> API1
    API1 --> FILTER
    FILTER --> RETRY
    EXCEL --> DATE
    DATE --> MULTI
    MULTI --> API2
    API2 --> TRACK
    RETRY --> COLLECT
    TRACK --> COLLECT
    COLLECT --> REPORT
    REPORT --> SEND
    SESSION --> STATE
    STATE --> COORD
```

## 📧 Email Processing Flow

```mermaid
flowchart TD
    A[📧 Email Received] --> B[IMAP IDLE Monitoring]
    B --> C{Email Pattern Match?}
    C -->|Yes| D[Extract Excel Attachment]
    C -->|No| E[Skip Email]
    D --> F[Detect Pipeline Type]
    F --> G{SI or Viajeros?}
    G -->|SI| H[SI Pipeline Processing]
    G -->|Viajeros| I[Viajeros Pipeline Processing]
    H --> J[Generate Report]
    I --> J
    J --> K[Send Email Report]
    E --> B
    K --> B
```

## 🏥 SI Pipeline Flow (Enhanced with Individual Filtering)

```mermaid
flowchart TD
    A[📊 New Excel File<br/>Asegurados_SI.xlsx] --> B[File Comparison<br/>comparador_SI.py]
    B --> C[Create Comparison Result<br/>comparison_result.xlsx]
    C --> D[Replace Old File<br/>Asegurados_SI_old.xlsx]
    D --> E[Create Single Emission<br/>emision_unica.json]
    E --> F[First API Attempt<br/>procesar_validacion]
    F --> G{API Response?}
    G -->|Success| H[✅ Process Successfully]
    G -->|Error 417| I[Extract Failed Individuals<br/>from API Response]
    I --> J[Create Failed Individuals Sets<br/>Passport + Identity]
    J --> K[Filter JSON File<br/>Remove Failed Individuals]
    K --> L[Create Filtered JSON<br/>emision_unica_filtered.json]
    L --> M[Retry API Processing<br/>with Filtered Data]
    M --> N{Retry Success?}
    N -->|Yes| O[✅ Process Filtered Data]
    N -->|No| P[❌ Processing Failed]
    O --> Q[Store Success Results]
    P --> Q
    H --> Q
    Q --> R[Store Failed Individuals Data<br/>for Email Reporting]
    R --> S[Clean Up Temporary Files]
    S --> T[Generate Email Report<br/>with Individual Details]
```

## 🧳 Viajeros Pipeline Flow (Enhanced with Detailed Reporting)

```mermaid
flowchart TD
    A[📊 Excel File<br/>Asegurados_Viajeros.xlsx] --> B[Excel Processing<br/>main.py]
    B --> C[Date Filtering<br/>April 2025+]
    C --> D{Valid Records?}
    D -->|Yes| E[Create Multiple Emissions<br/>JSON Files]
    D -->|No| F[ℹ️ No Data to Process]
    E --> G[API Processing<br/>procesar_validacion]
    G --> H{API Response?}
    H -->|Success| I[✅ Track Success<br/>with Individual Details]
    H -->|Error| J[❌ Track Error<br/>with Individual Details]
    I --> K[Store Success Results]
    J --> L[Store Error Results<br/>with Individual Information]
    K --> M[Generate Email Report<br/>with Detailed Information]
    L --> M
    F --> N[Generate Info Report<br/>No Data Message]
    M --> O[Send Email Report]
    N --> O
```

## 🔄 Pipeline Manager Flow

```mermaid
flowchart TD
    A[📧 Email Data<br/>Subject + Attachment] --> B[Pipeline Type Detection<br/>Subject Analysis]
    B --> C{Pipeline Type?}
    C -->|SI| D[SI Pipeline Execution<br/>corrected_main.py]
    C -->|Viajeros| E[Viajeros Pipeline Execution<br/>main.py]
    D --> F[File Validation<br/>Excel Check]
    E --> G[File Validation<br/>Excel Check]
    F --> H{Validation Success?}
    G --> I{Validation Success?}
    H -->|Yes| J[Execute SI Pipeline<br/>with Individual Filtering]
    H -->|No| K[❌ SI Validation Failed]
    I -->|Yes| L[Execute Viajeros Pipeline<br/>with Error Tracking]
    I -->|No| M[❌ Viajeros Validation Failed]
    J --> N[Store SI Results<br/>+ Failed Individuals Data]
    L --> O[Store Viajeros Results<br/>+ Error Details]
    K --> P[Generate Error Report]
    M --> P
    N --> Q[Generate Success Report<br/>with Individual Details]
    O --> R[Generate Success Report<br/>with Error Details]
    P --> S[Send Email Report]
    Q --> S
    R --> S
```

## 🚨 Error Handler Flow

```mermaid
flowchart TD
    A[Pipeline Completion Event] --> B[Collect Pipeline Data<br/>SI/Viajeros Specific]
    B --> C{SI Pipeline?}
    C -->|Yes| D[Get Failed Individuals Data<br/>from latest_failed_individuals.json]
    C -->|No| E[Get Standard Error Data<br/>from tracking files]
    D --> F[Process Individual Information<br/>Name, Passport, Birth Date, etc.]
    E --> G[Process Error Information<br/>Standard Error Details]
    F --> H[Generate HTML Report<br/>with Individual Details Section]
    G --> I[Generate HTML Report<br/>with Standard Error Section]
    H --> J[Create Email Subject<br/>Pipeline + Status + Email Subject]
    I --> J
    J --> K[Send Email via Resend API<br/>info@angelguardassist.com]
    K --> L[Update Database<br/>Mark Report as Sent]
    L --> M[Log Report Status<br/>Success/Failure]
```

## 📊 Individual Filtering Process (SI Pipeline)

```mermaid
flowchart TD
    A[API Error 417<br/>Active Coverage] --> B[Parse API Response<br/>Extract 'found' Array]
    B --> C[Create Failed Individuals List<br/>Name, Passport, Identity, etc.]
    C --> D[Create Lookup Sets<br/>Passport Set + Identity Set]
    D --> E[Read Original JSON<br/>emision_unica.json]
    E --> F[Filter Insured Individuals<br/>Remove Failed Ones]
    F --> G[Create Filtered JSON<br/>emision_unica_filtered.json]
    G --> H[Update Metadata<br/>Total Asegurados Count]
    H --> I[Retry API Processing<br/>with Filtered Data]
    I --> J{Retry Success?}
    J -->|Yes| K[✅ Process Successfully<br/>Store Results]
    J -->|No| L[❌ Retry Failed<br/>Store Error]
    K --> M[Store Failed Individuals Data<br/>for Email Reporting]
    L --> M
    M --> N[Clean Up Filtered File<br/>Remove Temporary JSON]
    N --> O[Generate Email Report<br/>with Individual Details]
```

## 🗄️ Database and State Management

```mermaid
erDiagram
    PIPELINE_SESSIONS {
        string session_id PK
        string si_status
        string viajeros_status
        datetime si_started_at
        datetime viajeros_started_at
        datetime si_completed_at
        datetime viajeros_completed_at
        boolean combined_report_sent
        datetime created_at
        datetime updated_at
    }
    
    PIPELINE_EXECUTIONS {
        int id PK
        string session_id FK
        string pipeline_type
        string status
        datetime started_at
        datetime completed_at
        string error_message
    }
    
    PROCESSED_EMAILS {
        string message_id PK
        string subject
        string from_addr
        datetime processed_at
        string pipeline_type
    }
    
    FAILED_INDIVIDUALS_DATA {
        string factura
        json removed_individuals
        json api_failed_individuals
        json error_details
        string email_subject
        datetime timestamp
    }
    
    PIPELINE_SESSIONS ||--o{ PIPELINE_EXECUTIONS : "has"
    PIPELINE_SESSIONS ||--o{ FAILED_INDIVIDUALS_DATA : "contains"
```

## 📧 Email Report Structure

```mermaid
graph TB
    subgraph "Email Report Structure"
        A[Email Subject<br/>Pipeline + Status + Original Subject]
        B[Processing Statistics<br/>Success/Failed Counts]
        C[Pipeline Breakdown<br/>SI/Viajeros Sections]
        D[Failed Individuals Details<br/>Individual Information]
        E[System Information<br/>Pipeline Type + Environment]
    end
    
    subgraph "Individual Details Section"
        F[Individual #1<br/>Name + Passport + Birth Date]
        G[Individual #2<br/>Name + Identity + Birth Date]
        H[Individual #N<br/>Name + Ticket ID + Birth Date]
    end
    
    subgraph "Error Details Section"
        I[Factura Information<br/>Error Step + Message]
        J[API Response Details<br/>Status Code + Validation]
        K[Individual Attribution<br/>Which Pipeline Failed]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    D --> F
    F --> G
    G --> H
    C --> I
    I --> J
    J --> K
```

## 🔧 Configuration and Environment

```mermaid
graph TB
    subgraph "Environment Configuration"
        A[.env File<br/>Environment Variables]
        B[Docker Compose<br/>Container Configuration]
        C[Volume Mounts<br/>Persistent Data]
    end
    
    subgraph "IMAP Configuration"
        D[IMAP_HOST<br/>secure.emailsrvr.com]
        E[IMAP_USER<br/>ismael.ramirezaybar@agassist.net]
        F[IMAP_PASS<br/>@bcD1234#]
        G[IMAP_FOLDER<br/>INBOX]
    end
    
    subgraph "Pipeline Configuration"
        H[AUTOMATED_MODE<br/>true]
        I[STATE_DB<br/>/state/processed.sqlite3]
        J[POLL_INTERVAL_SEC<br/>30]
    end
    
    subgraph "API Configuration"
        K[GOVAL_API_URL<br/>https://humano.goval-tpa.com/api]
        L[USUARIO<br/>Goval Username]
        M[PASSWORD<br/>Goval Password]
        N[RESEND_API_KEY<br/>Email Delivery]
    end
    
    A --> D
    A --> E
    A --> F
    A --> G
    A --> H
    A --> I
    A --> J
    A --> K
    A --> L
    A --> M
    A --> N
    B --> C
```

## 📈 Monitoring and Health Checks

```mermaid
flowchart TD
    A[Container Health Check<br/>60s interval] --> B{Health Status?}
    B -->|Healthy| C[Continue Processing]
    B -->|Unhealthy| D[Restart Container]
    C --> E[Log Analysis<br/>Pattern Matching]
    E --> F[Database Monitoring<br/>SQLite Queries]
    F --> G[Resource Monitoring<br/>CPU/Memory Usage]
    G --> H[Error Alerting<br/>Email Reports]
    H --> I[Performance Metrics<br/>Processing Statistics]
    I --> A
    D --> A
```

## 🎯 Key Data Flows Summary

### **1. Email Processing Flow:**
```mermaid
graph LR
    A[Email] --> B[IMAP] --> C[Pattern Match] --> D[Extract Excel] --> E[Detect Pipeline] --> F[Validate File] --> G[Execute Pipeline] --> H[Process API] --> I[Handle Errors] --> J[Generate Report] --> K[Send Email]
```

### **2. SI Pipeline with Individual Filtering:**
```mermaid
graph LR
    A[Excel] --> B[Compare] --> C[Create Emission] --> D[API Call] --> E{Error 417?} --> F[Extract Individuals] --> G[Filter JSON] --> H[Retry API] --> I[Store Results] --> J[Generate Report]
    E -->|No| I
```

### **3. Viajeros Pipeline with Error Reporting:**
```mermaid
graph LR
    A[Excel] --> B[Process] --> C[Filter Dates] --> D[Create Emissions] --> E[API Calls] --> F[Track Errors] --> G[Store Details] --> H[Generate Report]
```

### **4. Error Handling and Reporting:**
```mermaid
graph LR
    A[Pipeline Complete] --> B[Collect Data] --> C[Process Individuals] --> D[Generate HTML] --> E[Send Email] --> F[Update Database]
```

These Mermaid diagrams provide a comprehensive visual representation of the complete system flow, including the enhanced individual filtering capabilities and detailed error handling for both SI and Viajeros pipelines.
