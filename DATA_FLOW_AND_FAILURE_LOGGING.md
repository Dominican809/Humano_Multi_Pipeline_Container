# Pipeline Data Flow and Failure Logging - Complete Analysis

## 📊 **Complete Data Flow Overview**

The Humano Multi-Pipeline Container processes data through several stages, with comprehensive failure tracking at each step. Here's the complete flow:

### **1. Email Processing Stage**
```
📧 Email Received
    ↓
📎 Attachment Extraction (Excel files)
    ↓
📁 File Routing to Pipeline Directories
    ↓
🔄 Pipeline Detection & Execution
```

### **2. SI Pipeline Data Flow**
```
📊 Asegurados_SI.xlsx (from email)
    ↓
🔍 File Comparison (comparador_SI.py)
    ├── Compare with Asegurados_SI_old.xlsx
    ├── Generate comparison_result.xlsx
    └── Identify new people/records
    ↓
📝 Single Emission Creation (SI_excel_to_emision.py)
    ├── Convert comparison_result.xlsx to JSON
    └── Generate emision_unica.json
    ↓
🚀 API Processing (procesar_validacion.py)
    ├── Process each emission through Goval API
    ├── Track successes and failures
    └── Generate detailed failure logs
    ↓
📁 File Updates
    ├── Update Asegurados_SI_old.xlsx with new data
    └── Save tracking files (success/failures)
```

### **3. Viajeros Pipeline Data Flow**
```
📊 Asegurados_Viajeros.xlsx (from email)
    ↓
🔄 Excel to JSON Conversion (excel_to_emision_v2.py)
    ├── Load Excel data
    ├── Apply date filtering
    └── Generate emisiones_generadas.json
    ↓
🚀 API Processing (procesar_validacion.py)
    ├── Process each emission through Goval API
    ├── Track successes and failures
    └── Generate detailed failure logs
    ↓
📁 File Updates
    └── Save tracking files (success/failures)
```

---

## 🔍 **JSON File Handling and Storage**

### **Where JSON Files Are Stored**

The system uses **JSON files** (not SQLite) for the actual data processing. Here's where they're located:

#### **SI Pipeline JSON Files:**
```
/app/si_pipeline/
├── emision_unica.json                    # Single emission from comparison
├── data/
│   ├── tracking/
│   │   ├── success/
│   │   │   └── success_YYYYMMDD_HH_MM_SS.json
│   │   └── failures/
│   │       └── failures_YYYYMMDD_HH_MM_SS.json
│   ├── test_emissions.json              # Test data
│   ├── test_success.json               # Test success results
│   └── test_errors.json                # Test error results
```

#### **Viajeros Pipeline JSON Files:**
```
/app/viajeros_pipeline/
├── emisiones_generadas.json             # Multiple emissions from Excel
├── data/
│   ├── tracking/
│   │   ├── success/
│   │   │   └── success_YYYYMMDD_HH_MM_SS.json
│   │   └── failures/
│   │       └── failures_YYYYMMDD_HH_MM_SS.json
│   ├── test_emissions.json              # Test data
│   ├── test_success.json               # Test success results
│   └── test_errors.json                # Test error results
```

### **SQLite vs JSON Usage**

- **SQLite Database** (`/state/processed.sqlite3`): Used for **email deduplication** and **pipeline coordination**
- **JSON Files**: Used for **actual data processing** and **failure tracking**

---

## 📋 **Failure Logging System**

### **EmissionTracker Class**

The `EmissionTracker` class in both pipelines handles comprehensive failure logging:

```python
class EmissionTracker:
    def __init__(self, tracking_dir: str = "data/tracking"):
        self.tracking_dir = Path(tracking_dir)
        self.success_dir = self.tracking_dir / "success"
        self.failure_dir = self.tracking_dir / "failures"
        self.current_run = datetime.now().strftime("%Y%m%d_%H_%M_%S")
```

### **Failure Record Structure**

Each failure is logged with detailed information:

```json
{
  "factura": "202509191427",
  "step": "manager",
  "error": "Error en validación: Error en validación: 417",
  "num_asegurados": 11,
  "error_details": {
    "status_code": 417,
    "api_response": {
      "code": 1,
      "message": "Al menos una persona entre las indicadas posee un producto básico activo",
      "found": [
        {
          "ticket_id": "HUM-6C971-F77B",
          "identity": "00118139559",
          "passport": "9936649-0",
          "firstname": "GERMAN RUBEN",
          "lastname": "FELIX SANTAMARIA",
          "birthdate": "1988-09-20"
        }
      ],
      "uri": "https://humano.goval-tpa.com/api/issue/retail/2800/confirm-insured"
    },
    "validation_codes": [1],
    "validation_messages": [
      "1: Validación de asegurados con coberturas activas",
      "Al menos una persona entre las indicadas posee un producto básico activo"
    ]
  }
}
```

### **Failure Tracking Process**

1. **API Call Failure**: When a Goval API call fails
2. **Error Extraction**: Extract error details (status code, response, validation codes)
3. **Record Creation**: Create detailed failure record
4. **File Storage**: Save to `failures_YYYYMMDD_HH_MM_SS.json`
5. **Email Integration**: Include in daily email reports

---

## 📧 **Enhanced Email Reports**

### **What's Now Included in Email Reports**

The enhanced error handler now extracts and includes:

#### **Detailed Failure Information:**
- **Factura Number**: Specific invoice that failed
- **Error Step**: Which step failed (cotizacion, manager, pago)
- **Error Message**: Detailed error description
- **Affected People**: Number of people affected
- **Status Code**: HTTP status code from API
- **Validation Codes**: Specific validation codes that failed
- **Validation Messages**: Human-readable validation messages
- **API Response**: Complete API response details
- **People with Active Coverage**: List of people causing validation failures

#### **Visual Enhancement:**
- **Pipeline Badges**: Color-coded badges for SI vs Viajeros
- **Detailed Cards**: Each failure shown in a detailed card format
- **Scrollable Lists**: Long lists of people are scrollable
- **Pipeline Breakdown**: Summary of failures by pipeline type

### **Example Email Report Section**

```html
❌ Failed Emissions (Manual Handling Required)
Total Failed Emissions: 3

[SI Pipeline Badge] Factura: 202509191427
Error Step: manager
Error Message: Error en validación: 417
Affected People: 11
Status Code: 417
Validation Codes: 1

Validation Messages:
• 1: Validación de asegurados con coberturas activas
• Al menos una persona entre las indicadas posee un producto básico activo

API Response: Al menos una persona entre las indicadas posee un producto básico activo

People with Active Coverage (5):
• GERMAN RUBEN FELIX SANTAMARIA (ID: 00118139559)
• LINA ELENA HENRIQUEZ MATOS (ID: 40200443170)
• LINA MARIA MATOS MATOS (ID: 00111194577)
• MARCO JOSE HENRIQUEZ MATOS (ID: 40200606230)
• MARCOS AURELIO HENRIQUEZ ROBIOU (ID: 00100692433)
```

---

## 🔄 **Complete Processing Pipeline**

### **SI Pipeline Complete Flow**

```python
# 1. Email Processing
email_attachment = extract_excel_attachment(email)
save_to = "/app/si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx"

# 2. File Comparison
comparador_SI()  # Compares with Asegurados_SI_old.xlsx
# Output: comparison_result.xlsx

# 3. Single Emission Creation
create_single_emission("comparison_result.xlsx", "emision_unica.json")
# Output: emision_unica.json

# 4. API Processing
emisiones_exitosas, emisiones_fallidas = procesar_validacion(
    emisiones_path="emision_unica.json"
)
# Output: Detailed success/failure tracking

# 5. File Updates
# Update Asegurados_SI_old.xlsx with new data
# Save tracking files to data/tracking/
```

### **Viajeros Pipeline Complete Flow**

```python
# 1. Email Processing
email_attachment = extract_excel_attachment(email)
save_to = "/app/viajeros_pipeline/Exceles/Asegurados_Viajeros.xlsx"

# 2. Excel to JSON Conversion
cargar_emisiones_desde_excel("Asegurados_Viajeros.xlsx", "emisiones_generadas.json")
# Output: emisiones_generadas.json

# 3. API Processing
emisiones_exitosas, emisiones_fallidas = procesar_validacion(
    emisiones_path="emisiones_generadas.json"
)
# Output: Detailed success/failure tracking

# 4. File Updates
# Save tracking files to data/tracking/
```

---

## 🛠️ **Key Components**

### **1. EmissionTracker**
- **Location**: `si_pipeline/emisor_goval/tracking/emission_tracker.py`
- **Purpose**: Track all emissions (success/failure) with detailed error information
- **Output**: JSON files with comprehensive failure details

### **2. procesar_validacion**
- **Location**: `si_pipeline/emisor_goval/utils/procesar_validacion.py`
- **Purpose**: Process emissions through Goval API and track results
- **Integration**: Uses EmissionTracker for detailed logging

### **3. ErrorHandler (Enhanced)**
- **Location**: `shared/error_handler.py`
- **Purpose**: Extract failure data from tracking files and generate detailed email reports
- **Enhancement**: Now includes detailed failure information in email reports

### **4. Pipeline Coordination**
- **Location**: `shared/pipeline_coordinator.py`
- **Purpose**: Coordinate between SI and Viajeros pipelines
- **Database**: Uses SQLite for session management

---

## 📁 **File Structure Summary**

```
/app/
├── si_pipeline/
│   ├── Comparador_Humano/exceles/
│   │   ├── Asegurados_SI_old.xlsx      # Previous data (for comparison)
│   │   └── Asegurados_SI.xlsx          # New data (from email)
│   ├── emision_unica.json              # Single emission JSON
│   ├── data/tracking/
│   │   ├── success/success_*.json      # Success tracking
│   │   └── failures/failures_*.json     # Failure tracking
│   └── emisor_goval/
│       ├── tracking/emission_tracker.py
│       └── utils/procesar_validacion.py
├── viajeros_pipeline/
│   ├── Exceles/Asegurados_Viajeros.xlsx # New data (from email)
│   ├── emisiones_generadas.json         # Multiple emissions JSON
│   ├── data/tracking/
│   │   ├── success/success_*.json       # Success tracking
│   │   └── failures/failures_*.json    # Failure tracking
│   └── emisor_goval/
│       ├── tracking/emission_tracker.py
│       └── utils/procesar_validacion.py
└── shared/
    ├── error_handler.py                 # Enhanced error handling
    ├── pipeline_coordinator.py         # Pipeline coordination
    └── database/state/processed.sqlite3 # Email deduplication
```

---

## ✅ **Summary**

The system now provides **comprehensive failure logging** and **detailed email reports** that include:

1. **Complete Data Flow**: From Excel files to JSON processing to API calls
2. **Detailed Failure Tracking**: Every API failure is logged with full context
3. **Enhanced Email Reports**: Include factura details, error steps, validation codes, and affected people
4. **Pipeline Differentiation**: Clear separation between SI and Viajeros failures
5. **Visual Enhancement**: Color-coded badges and detailed failure cards

The **JSON files** are the core of the data processing system, while **SQLite** is used only for email deduplication and pipeline coordination. All failure information is now automatically included in the daily email reports, providing complete visibility into what failed and why.
