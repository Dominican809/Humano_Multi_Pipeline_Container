# Pipeline Coordination and Data Differentiation System

## Overview

This document explains how the system handles simultaneous SI and Viajeros pipeline execution and ensures proper data differentiation in email reports.

## Problem Statement

Both SI and Viajeros emails arrive almost simultaneously, causing:
1. **Race Conditions**: Both pipelines try to send individual reports
2. **Data Confusion**: Reports don't clearly differentiate between pipeline types
3. **Missing Combined View**: No unified report showing both pipelines' results

## Solution Architecture

### 1. Pipeline Coordination System (`shared/pipeline_coordinator.py`)

#### **Session Management**
- **Session Creation**: When first pipeline starts, creates a coordination session
- **Session Joining**: Subsequent pipelines join the existing session
- **Session Timeout**: 5-minute maximum wait time for coordination

#### **State Tracking**
```sql
CREATE TABLE pipeline_sessions (
    session_id TEXT PRIMARY KEY,
    si_status TEXT DEFAULT 'pending',           -- pending, running, completed, failed
    viajeros_status TEXT DEFAULT 'pending',     -- pending, running, completed, failed
    si_started_at TIMESTAMP,
    viajeros_started_at TIMESTAMP,
    si_completed_at TIMESTAMP,
    viajeros_completed_at TIMESTAMP,
    combined_report_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### **Coordination Flow**
1. **Pipeline Start**: `coordinator.start_pipeline_session(pipeline_type)`
2. **Pipeline Completion**: `coordinator.complete_pipeline(pipeline_type, session_id, success, error_message)`
3. **Combined Report Check**: Automatically checks if both pipelines are complete
4. **Timeout Monitoring**: Background thread monitors for 5-minute timeout

### 2. Enhanced Email Watcher (`email_watcher/pipeline_watcher.py`)

#### **Simultaneous Email Processing**
- **Multiple Email Detection**: Processes ALL unseen emails, not just the most recent
- **Parallel Processing**: Uses `ThreadPoolExecutor` for concurrent email processing
- **Coordination Integration**: Each email triggers pipeline through coordination system

#### **Processing Flow**
```python
# Before: Only processed most recent email
most_recent_uid = max(unseen_uids)
process_single_email(most_recent_uid)

# After: Processes all emails simultaneously
emails_to_process = []
for uid in unseen_uids:
    if should_process_email(uid):
        emails_to_process.append(email_data)

if len(emails_to_process) > 1:
    _process_multiple_emails_coordinated(emails_to_process, con)
```

### 3. Pipeline-Aware Error Handler (`shared/error_handler.py`)

#### **Pipeline-Specific Data Paths**
- **SI Pipeline**: `/app/si_pipeline/data/tracking/`
- **Viajeros Pipeline**: `/app/viajeros_pipeline/data/tracking/`
- **Combined Reports**: Aggregates data from both directories

#### **Data Differentiation**
```python
class ErrorHandler:
    def __init__(self, pipeline_type: str = None):
        if pipeline_type == 'si':
            self.data_dir = Path('/app/si_pipeline/data')
            self.pipeline_name = "Salud Internacional (SI)"
        elif pipeline_type == 'viajeros':
            self.data_dir = Path('/app/viajeros_pipeline/data')
            self.pipeline_name = "Viajeros"
        else:
            # Combined reports
            self.data_dir = None
            self.pipeline_name = "Combined"
```

#### **Enhanced Report Generation**
- **Pipeline-Specific Sections**: Separate statistics for each pipeline
- **Color-Coded Badges**: Visual differentiation (SI: Yellow, Viajeros: Blue)
- **Failure Attribution**: Shows which pipeline each failure belongs to

### 4. Updated Pipeline Manager (`pipeline_manager.py`)

#### **Coordination Integration**
```python
def run_viajeros_pipeline(excel_file_path):
    # Start coordination session
    session_id = coordinator.start_pipeline_session('viajeros')
    
    try:
        # Run pipeline logic...
        coordinator.complete_pipeline('viajeros', session_id, success=True)
    except Exception as e:
        coordinator.complete_pipeline('viajeros', session_id, success=False, error_message=str(e))
```

## Data Differentiation Strategy

### 1. **Pipeline Detection**
```python
def detect_pipeline_type(subject, from_addr):
    subject_lower = subject.lower()
    
    if "asegurados viajeros" in subject_lower:
        return "viajeros"
    elif "asegurados salud internacional" in subject_lower:
        return "si"
    else:
        return "unknown"
```

### 2. **Separate Data Storage**
- **SI Data**: Stored in `/app/si_pipeline/data/tracking/`
- **Viajeros Data**: Stored in `/app/viajeros_pipeline/data/tracking/`
- **Pipeline Metadata**: Each record tagged with `pipeline_type` and `pipeline_name`

### 3. **Combined Report Generation**
```python
def _generate_combined_pipeline_sections(self) -> str:
    # Get individual pipeline stats
    si_handler = ErrorHandler('si')
    viajeros_handler = ErrorHandler('viajeros')
    
    si_stats = si_handler.get_processing_stats()
    viajeros_stats = viajeros_handler.get_processing_stats()
    
    # Generate separate sections for each pipeline
    # with color-coded styling and clear differentiation
```

## Timing and Coordination

### **5-Minute Wait Mechanism**
1. **First Pipeline Completes**: Starts timeout monitor
2. **Second Pipeline Completes**: Triggers combined report immediately
3. **Timeout Reached**: Sends partial report with timeout notification
4. **Background Monitoring**: Checks every 30 seconds for completion

### **Timeout Handling**
```python
def _start_timeout_monitor(self, session_id: str):
    def timeout_monitor():
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            if elapsed >= self.wait_timeout:  # 5 minutes
                self._send_timeout_report(session_id)
                break
            
            if both_pipelines_complete:
                self._send_combined_report(session_id)
                break
```

## Report Examples

### **Combined Report Subject**
```
[Humano Insurance] ✅ Daily Report - 27 policies processed successfully
```

### **Pipeline-Specific Report Subject**
```
[Humano Insurance] ✅ [Salud Internacional (SI)] Daily Report - 15 policies processed successfully
[Humano Insurance] ⚠️ [Viajeros] Daily Report - 12 successful, 3 failed
```

### **Report Content Structure**
1. **Header**: Shows pipeline type with color-coded badge
2. **Email Processing Status**: Overall system status
3. **Combined Statistics**: Total counts across both pipelines
4. **Pipeline Breakdown**: Separate sections for SI and Viajeros
5. **Failed Records**: Table with pipeline attribution
6. **System Information**: Pipeline-specific details

## Benefits

### **1. Clear Data Differentiation**
- **Visual Distinction**: Color-coded badges and sections
- **Pipeline Attribution**: Every failure shows source pipeline
- **Separate Statistics**: Individual pipeline performance metrics

### **2. Coordinated Reporting**
- **Single Combined Report**: One email with both pipelines' data
- **Timeout Protection**: Never waits indefinitely
- **Race Condition Prevention**: Coordination prevents duplicate reports

### **3. Simultaneous Processing**
- **Parallel Email Processing**: Handles multiple emails concurrently
- **Session Management**: Groups related pipeline executions
- **Background Monitoring**: Non-blocking timeout handling

### **4. Backward Compatibility**
- **Legacy Support**: Existing functionality continues to work
- **Graceful Degradation**: Falls back if coordination fails
- **Incremental Enhancement**: Adds features without breaking existing code

## Configuration

### **Environment Variables**
```bash
# Coordination settings
PIPELINE_COORDINATION_TIMEOUT=300  # 5 minutes in seconds
PIPELINE_COORDINATION_CHECK_INTERVAL=30  # Check every 30 seconds

# Email processing
EMAIL_PARALLEL_PROCESSING=true
MAX_CONCURRENT_PIPELINES=2
```

### **Database Schema**
The coordination system uses SQLite database at `/state/pipeline_coordination.sqlite3` with tables for session tracking and execution logging.

## Monitoring and Debugging

### **Log Messages**
- `🚀 Started {pipeline_type} pipeline in session {session_id}`
- `✅ {pipeline_type} pipeline completed with status: {status}`
- `🎯 Both pipelines complete for session {session_id}, sending combined report`
- `⏰ Timeout reached for session {session_id}, sending partial report`

### **Session Status Query**
```python
status = coordinator.get_session_status(session_id)
print(f"SI: {status['si_status']}, Viajeros: {status['viajeros_status']}")
```

This system ensures that both SI and Viajeros pipelines are properly coordinated, data is clearly differentiated, and recipients receive comprehensive reports that show the complete picture of both pipeline executions.
