# Enhanced Error Handling and Individual Filtering System

## Overview

This document explains the comprehensive error handling, data validation, and individual filtering system implemented for both SI and Viajeros pipelines, including automatic handling of API validation errors and detailed individual reporting.

## Problem Statement

The original system had several error handling gaps:

1. **Empty File Handling**: No validation for empty Excel files
2. **SI Pipeline Validation**: No check for new people after comparison
3. **Viajeros Data Validation**: No validation for date filtering and required columns
4. **Edge Case Reporting**: Poor differentiation between errors and "no data" scenarios
5. **API Validation Errors**: No handling of error 417 (active coverage) with individual filtering
6. **Individual Data Reporting**: No detailed information about failed individuals in email reports

## Enhanced Error Handling Implementation

### 1. **Individual Filtering System** (`si_pipeline/corrected_main.py`)

#### **API Error 417 Handling**
```python
def process_si_emission_with_retry(json_path="emision_unica.json"):
    # First attempt: Process original JSON
    emisiones_exitosas, emisiones_fallidas = procesar_validacion(emisiones_path=json_path)
    
    # Check for API validation errors (417)
    api_validation_errors = [f for f in emisiones_fallidas 
                            if f.get('error_details', {}).get('status_code') == 417]
    
    if api_validation_errors:
        # Extract all failed individuals from API response
        all_failed_individuals = []
        for failure in api_validation_errors:
            api_response = failure['error_details']['api_response']
            failed_individuals = extract_failed_individuals_from_api_response(api_response)
            all_failed_individuals.extend(failed_individuals)
        
        # Filter the JSON to remove failed individuals
        filtered_json_path, removed_individuals = filter_individuals_from_json(
            json_path, all_failed_individuals
        )
        
        # Retry processing with filtered JSON
        emisiones_exitosas_retry, _ = procesar_validacion(emisiones_path=filtered_json_path)
        
        # Store failed individuals data for email reporting
        store_failed_individuals_data(failed_individuals_data, all_failed_individuals)
```

#### **Individual Data Extraction**
```python
def extract_failed_individuals_from_api_response(api_response):
    """Extract individuals with active coverage from API response."""
    failed_individuals = []
    if api_response and 'found' in api_response and api_response['found']:
        failed_individuals = api_response['found']
    return failed_individuals
```

#### **JSON Filtering Logic**
```python
def filter_individuals_from_json(json_path, failed_individuals):
    """Remove failed individuals from the emission JSON file."""
    
    # Create sets of failed identifiers for quick lookup
    failed_passports = set()
    failed_identities = set()
    
    for individual in failed_individuals:
        if individual.get('passport'):
            failed_passports.add(individual['passport'])
        if individual.get('identity'):
            failed_identities.add(individual['identity'])
    
    # Filter insured individuals
    for insured in original_insured:
        should_remove = False
        
        # Check passport
        if insured.get('passport') and insured['passport'] in failed_passports:
            should_remove = True
        
        # Check identity
        if insured.get('identity') and insured['identity'] in failed_identities:
            should_remove = True
        
        if should_remove:
            removed_individuals.append(insured)
        else:
            filtered_insured.append(insured)
```

### 2. **Enhanced Error Handler with Individual Data** (`shared/error_handler.py`)

#### **Failed Individuals Data Structure**
```json
{
  "failed_individuals_data": [
    {
      "factura": "202509221135",
      "removed_individuals": [
        {
          "firstname": "CARLOS MANUEL",
          "lastname": "DE LOS SANTOS SANTOS",
          "passport": "3150560-0",
          "birthdate": "1985-06-25"
        }
      ],
      "api_failed_individuals": [
        {
          "ticket_id": "HUM-3ED6D-3D60",
          "passport": "3150560-0",
          "firstname": "CARLOS MANUEL",
          "lastname": "DE LOS SANTOS SANTOS",
          "birthdate": "1985-06-25"
        }
      ],
      "error_details": {
        "status_code": 417,
        "api_response": {...}
      }
    }
  ],
  "all_failed_individuals": [...],
  "email_subject": "Asegurados Salud Internacional | 2025-09-22",
  "timestamp": "2025-09-22T11:35:28.892"
}
```

#### **Enhanced Report Generation**
```python
def generate_report(self, email_received=True, excel_extracted=True, 
                   pipeline_success=True, error_message=None, 
                   failed_individuals=None):
    
    # Add failed individuals section if provided
    if failed_individuals:
        html_report += f"""
        <div class="section" style="background-color: #fff3cd; border-left: 4px solid #ffc107;">
            <h2>🚨 Individuals with Active Coverage (Removed from Processing)</h2>
            <p><strong>Total Individuals Removed:</strong> {len(failed_individuals)}</p>
            <div style="margin-top: 15px;">
        """
        
        for i, individual in enumerate(failed_individuals, 1):
            name = f"{individual.get('firstname', '')} {individual.get('lastname', '')}".strip()
            passport = individual.get('passport', '')
            identity = individual.get('identity', '')
            birthdate = individual.get('birthdate', 'N/A')
            ticket_id = individual.get('ticket_id', 'N/A')
            
            html_report += f"""
                <div style="margin-bottom: 15px; padding: 10px; background-color: #ffffff; border-radius: 5px;">
                    <h4 style="margin-top: 0; color: #856404;">Individual #{i}</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div>
                            <strong>Name:</strong> {name}<br>
                            <strong>Birth Date:</strong> {birthdate}
                        </div>
                        <div>
                            {f'<strong>Passport:</strong> {passport}<br>' if passport else ''}
                            {f'<strong>Identity:</strong> {identity}<br>' if identity else ''}
                            <strong>Ticket ID:</strong> {ticket_id}
                        </div>
                    </div>
                </div>
            """
```

### 3. **Pipeline-Specific Excel Validation** (`shared/error_handler.py`)

#### **SI Pipeline Validation**
```python
def check_excel_file(self, excel_path: str) -> Tuple[bool, str, int]:
    # SI-specific required columns
    if self.pipeline_type == 'si':
        required_columns = ['CODIGO_INFOPLAN', 'PRI_NOM', 'PRI_APE', 'FEC_NAC']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"SI Excel missing required columns: {missing_columns}", len(df)
```

#### **Viajeros Pipeline Validation**
```python
def validate_viajeros_data(self, excel_path: str) -> Tuple[bool, str, int]:
    # Read Excel file with header=4 (Viajeros specific)
    df = pd.read_excel(excel_path, header=4)
    
    # Check required columns
    required_columns = ['FACTURA', 'PRI_NOM', 'PRI_APE', 'FEC_NAC', 'ASEGURADO', 'INICIO VIGENCIA']
    
    # Filter for records after April 2025
    df['fecha_inicio_dt'] = pd.to_datetime(df['INICIO VIGENCIA'])
    fecha_corte = pd.to_datetime('2025-04-01')
    df_filtered = df[df['fecha_inicio_dt'] >= fecha_corte]
    
    if valid_records == 0:
        return False, "No valid Viajeros records found after April 2025 - no processing needed", 0
```

### 2. **SI Comparison Result Validation**

#### **New People Detection**
```python
def validate_si_comparison_result(self, comparison_file_path: str) -> Tuple[bool, str, int]:
    # Read the comparison result Excel file
    excel_file = pd.ExcelFile(comparison_file_path)
    
    # Check if 'New in New File' sheet exists and has data
    if 'New in New File' in excel_file.sheet_names:
        new_people_df = pd.read_excel(comparison_file_path, sheet_name='New in New File')
        new_people_count = len(new_people_df)
        
        if new_people_count == 0:
            return False, "No new people found after SI comparison - no processing needed", 0
        else:
            return True, f"Found {new_people_count} new people to process", new_people_count
```

### 3. **Enhanced Pipeline Validation Flow**

#### **SI Pipeline Validation Process**
1. **Basic Excel Validation**: Check file exists, has data, required columns
2. **Comparison Execution**: Run `comparador_SI()` to generate comparison result
3. **New People Check**: Validate `comparison_result.xlsx` for new people
4. **Processing Decision**: Only proceed if new people are found

#### **Viajeros Pipeline Validation Process**
1. **Excel File Validation**: Check file exists, has data, required columns
2. **Date Filtering**: Filter records after April 2025
3. **Data Quality Check**: Validate required fields are present
4. **Processing Decision**: Only proceed if valid records exist

### 4. **Smart Error Classification**

#### **Error Types**
- **`excel_validation`**: File missing, empty, or missing columns
- **`no_new_data`**: Valid file but no new data to process (not an error)
- **`pipeline_execution`**: Runtime errors during processing
- **`email_processing`**: Email-related issues

#### **"No Data" vs "Error" Handling**
```python
def handle_error(self, error_type: str, error_message: str, context: Dict = None) -> bool:
    # Special handling for "no data" cases - these are not failures
    if error_type == 'no_new_data':
        logger.info(f"ℹ️ No new data to process: {error_message}")
        # Send success report with informational message
        return self.send_report(email_received=True, excel_extracted=True, pipeline_success=True, error_message=f"ℹ️ {error_message}")
```

### 5. **Enhanced Pipeline Manager Logic**

#### **SI Pipeline Manager**
```python
# Check Excel file and report
is_valid, error_message = check_pipeline_excel_and_report('si')
if not is_valid:
    # Check if this is a "no new people" case vs actual error
    if "no processing needed" in error_message.lower() or "no new people" in error_message.lower():
        logger.info(f"[manager] ℹ️ No new SI people to process - completing pipeline with success")
        coordinator.complete_pipeline('si', session_id, success=True, error_message=error_message)
    else:
        coordinator.complete_pipeline('si', session_id, success=False, error_message=f"Excel validation failed: {error_message}")
    return False
```

#### **Viajeros Pipeline Manager**
```python
# Check Excel file and report
is_valid, error_message = check_pipeline_excel_and_report('viajeros')
if not is_valid:
    # Check if this is a "no data" case vs actual error
    if "no processing needed" in error_message.lower():
        logger.info(f"[manager] ℹ️ No Viajeros data to process - completing pipeline with success")
        coordinator.complete_pipeline('viajeros', session_id, success=True, error_message=error_message)
    else:
        coordinator.complete_pipeline('viajeros', session_id, success=False, error_message=f"Excel validation failed: {error_message}")
    return
```

### 6. **Enhanced HTML Report Generation**

#### **Status Classification**
```python
# Determine overall status
if email_received and excel_extracted and pipeline_success and stats['failed'] == 0:
    if error_message and error_message.startswith("ℹ️"):
        status = "ℹ️ NO DATA TO PROCESS"
        status_color = "blue"
    else:
        status = "✅ SUCCESS"
        status_color = "green"
```

#### **Message Display**
```html
{f'<div class="{"success" if error_message and error_message.startswith("ℹ️") else "error"}"><strong>{"Info" if error_message and error_message.startswith("ℹ️") else "Error"}:</strong> {error_message}</div>' if error_message else ''}
```

## Error Scenarios and Handling

### **Scenario 1: Empty Excel File**
- **Detection**: `df.empty` check
- **Response**: Pipeline marked as failed with clear error message
- **Report**: Red status with "Excel file is empty" message

### **Scenario 2: Missing Required Columns**
- **Detection**: Column existence validation
- **Response**: Pipeline marked as failed with specific missing columns
- **Report**: Red status with detailed column information

### **Scenario 3: SI - No New People After Comparison**
- **Detection**: Empty "New in New File" sheet
- **Response**: Pipeline marked as successful with informational message
- **Report**: Blue status with "No new people found" message

### **Scenario 4: Viajeros - No Valid Records After Date Filter**
- **Detection**: No records after April 2025
- **Response**: Pipeline marked as successful with informational message
- **Report**: Blue status with "No valid records found" message

### **Scenario 5: File Not Found**
- **Detection**: `os.path.exists()` check
- **Response**: Pipeline marked as failed
- **Report**: Red status with file path information

## Benefits of Enhanced Error Handling

### **1. Clear Error Classification**
- **Errors**: Actual problems that need attention
- **No Data**: Valid scenarios where no processing is needed
- **Warnings**: Issues that don't prevent processing

### **2. Appropriate Pipeline Completion**
- **Success with Info**: When no data to process (not a failure)
- **Failure**: When actual errors occur
- **Partial Success**: When some processing succeeds

### **3. Detailed Error Messages**
- **Specific Column Names**: Exact missing columns listed
- **Data Counts**: Number of records found/processed
- **File Paths**: Exact locations of problematic files

### **4. Visual Report Differentiation**
- **Green**: Successful processing with data
- **Blue**: Successful processing with no data
- **Orange**: Partial success
- **Red**: Complete failure

## Configuration and Monitoring

### **Log Messages**
- `✅ SI Excel validated successfully: 150 rows, 25 new people to process`
- `ℹ️ No new SI people to process - completing pipeline with success`
- `❌ SI Excel missing required columns: ['CODIGO_INFOPLAN', 'PRI_NOM']`
- `⚠️ No valid Viajeros records found after April 2025 - no processing needed`

### **Report Examples**

#### **Success with Data**
```
Subject: ✅ [Salud Internacional (SI)] Daily Report - 25 policies processed successfully
Status: ✅ SUCCESS
```

#### **Success with No Data**
```
Subject: ℹ️ [Viajeros] Daily Report - No valid records found after April 2025
Status: ℹ️ NO DATA TO PROCESS
Info: No valid Viajeros records found after April 2025 - no processing needed
```

#### **Failure**
```
Subject: ❌ [Salud Internacional (SI)] Daily Report - Processing failed
Status: ❌ FAILURE
Error: SI Excel missing required columns: ['CODIGO_INFOPLAN']
```

## Testing Scenarios

### **Test Cases**
1. **Empty Excel File**: Should fail with clear message
2. **Missing Columns**: Should fail with specific column names
3. **SI No New People**: Should succeed with informational message
4. **Viajeros No Valid Dates**: Should succeed with informational message
5. **File Not Found**: Should fail with file path
6. **Valid Data**: Should process normally

This enhanced error handling system ensures that both pipelines properly validate data before processing, clearly differentiate between errors and "no data" scenarios, and provide comprehensive reporting for all edge cases.
