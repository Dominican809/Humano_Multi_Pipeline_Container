# Single Pipeline Handling - Test Scenarios

## Overview

This document demonstrates how the enhanced pipeline coordination system correctly handles scenarios where only one of the two pipelines receives an email and activates.

## Problem Statement

**Original Issue**: If only one pipeline receives an email (e.g., only SI email arrives, but no Viajeros email), the system would:
1. Wait indefinitely for the second pipeline
2. Never send a report
3. Leave the session in a pending state

**Enhanced Solution**: The system now properly handles single pipeline scenarios with appropriate timeout and reporting.

## Test Scenarios

### **Scenario 1: Only SI Pipeline Activates**

#### **Timeline:**
```
T+0:00  - SI email arrives
T+0:01  - SI pipeline starts, creates session "session_20250101_120000"
T+0:02  - SI pipeline completes successfully
T+0:03  - System detects only SI is active and complete
T+0:04  - Sends SI-specific success report immediately
```

#### **Database State:**
```sql
session_id: "session_20250101_120000"
si_status: "completed"
viajeros_status: "pending"
si_started_at: "2025-01-01 12:00:01"
viajeros_started_at: NULL
si_completed_at: "2025-01-01 12:00:02"
viajeros_completed_at: NULL
combined_report_sent: TRUE
```

#### **Email Report:**
```
Subject: ✅ [Salud Internacional (SI)] Daily Report - 15 policies processed successfully
Status: ✅ SUCCESS
Info: SI pipeline completed successfully. Viajeros pipeline did not activate.
```

### **Scenario 2: Only Viajeros Pipeline Activates**

#### **Timeline:**
```
T+0:00  - Viajeros email arrives
T+0:01  - Viajeros pipeline starts, creates session "session_20250101_120000"
T+0:02  - Viajeros pipeline completes successfully
T+0:03  - System detects only Viajeros is active and complete
T+0:04  - Sends Viajeros-specific success report immediately
```

#### **Database State:**
```sql
session_id: "session_20250101_120000"
si_status: "pending"
viajeros_status: "completed"
si_started_at: NULL
viajeros_started_at: "2025-01-01 12:00:01"
si_completed_at: NULL
viajeros_completed_at: "2025-01-01 12:00:02"
combined_report_sent: TRUE
```

#### **Email Report:**
```
Subject: ✅ [Viajeros] Daily Report - 12 policies processed successfully
Status: ✅ SUCCESS
Info: Viajeros pipeline completed successfully. SI pipeline did not activate.
```

### **Scenario 3: SI Pipeline Activates, Viajeros Times Out**

#### **Timeline:**
```
T+0:00  - SI email arrives
T+0:01  - SI pipeline starts, creates session "session_20250101_120000"
T+0:02  - SI pipeline completes successfully
T+0:03  - System starts timeout monitor (5 minutes)
T+5:03  - Timeout reached, sends SI-specific report
```

#### **Database State:**
```sql
session_id: "session_20250101_120000"
si_status: "completed"
viajeros_status: "pending"
si_started_at: "2025-01-01 12:00:01"
viajeros_started_at: NULL
si_completed_at: "2025-01-01 12:00:02"
viajeros_completed_at: NULL
combined_report_sent: TRUE
```

#### **Email Report:**
```
Subject: ✅ [Salud Internacional (SI)] Daily Report - 15 policies processed successfully
Status: ✅ SUCCESS
Info: SI pipeline completed successfully. Viajeros pipeline did not activate within 5 minutes.
```

### **Scenario 4: Both Pipelines Activate, One Completes, Other Times Out**

#### **Timeline:**
```
T+0:00  - SI email arrives
T+0:01  - SI pipeline starts, creates session "session_20250101_120000"
T+0:30  - Viajeros email arrives
T+0:31  - Viajeros pipeline joins session
T+0:32  - SI pipeline completes successfully
T+5:32  - Viajeros pipeline still running, timeout reached
T+5:33  - Sends timeout report indicating coordination failure
```

#### **Email Report:**
```
Subject: ❌ Daily Report - Processing failed
Status: ❌ FAILURE
Error: Pipeline coordination timeout reached (5 minutes). Both pipelines were active but coordination failed.
```

## Implementation Details

### **1. Immediate Single Pipeline Detection**

```python
def _check_and_send_combined_report(self, session_id: str):
    # Check if only one pipeline is active and complete
    si_complete = si_status in ['completed', 'failed']
    viajeros_complete = viajeros_status in ['completed', 'failed']
    si_active = si_status in ['running', 'completed', 'failed']
    viajeros_active = viajeros_status in ['running', 'completed', 'failed']
    
    # If only one pipeline is active and complete, send single pipeline report
    if si_complete and not viajeros_active:
        logger.info(f"🎯 Only SI pipeline was active and completed for session {session_id}")
        self._send_single_pipeline_report(session_id, 'si')
    elif viajeros_complete and not si_active:
        logger.info(f"🎯 Only Viajeros pipeline was active and completed for session {session_id}")
        self._send_single_pipeline_report(session_id, 'viajeros')
```

### **2. Timeout Monitor Enhancement**

```python
def timeout_monitor():
    # Check if only one pipeline is active and completed
    if si_complete and not viajeros_active:
        logger.info(f"🎯 Only SI pipeline was active and completed for session {session_id}")
        self._send_single_pipeline_report(session_id, 'si')
        break
    elif viajeros_complete and not si_active:
        logger.info(f"🎯 Only Viajeros pipeline was active and completed for session {session_id}")
        self._send_single_pipeline_report(session_id, 'viajeros')
        break
```

### **3. Smart Timeout Reporting**

```python
def _send_timeout_report(self, session_id: str):
    # Determine what happened and send appropriate report
    si_active = si_started is not None and si_completed is not None
    viajeros_active = viajeros_started is not None and viajeros_completed is not None
    
    if si_active and not viajeros_active:
        # Only SI pipeline was active
        si_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True, 
                                   error_message=f"SI pipeline completed successfully. Viajeros pipeline did not activate within {self.wait_timeout/60:.0f} minutes.")
    elif viajeros_active and not si_active:
        # Only Viajeros pipeline was active
        viajeros_error_handler.send_report(email_received=True, excel_extracted=True, pipeline_success=True,
                                         error_message=f"Viajeros pipeline completed successfully. SI pipeline did not activate within {self.wait_timeout/60:.0f} minutes.")
```

## Key Benefits

### **1. Immediate Response**
- **No Waiting**: Single pipeline scenarios are detected immediately
- **Fast Reports**: Reports sent as soon as the active pipeline completes
- **No Hanging**: System doesn't wait indefinitely for non-existent second pipeline

### **2. Appropriate Reporting**
- **Pipeline-Specific**: Reports are sent using the correct pipeline's error handler
- **Clear Messaging**: Reports clearly indicate which pipeline was active
- **Success Status**: Single pipeline completion is treated as success, not failure

### **3. Robust Timeout Handling**
- **5-Minute Timeout**: Maximum wait time for coordination
- **Smart Detection**: Distinguishes between single pipeline and coordination failure
- **Appropriate Reports**: Different report types based on what actually happened

### **4. Database Consistency**
- **Session Tracking**: All pipeline activities are properly tracked
- **Report Sent Flag**: Prevents duplicate reports
- **Status Accuracy**: Database accurately reflects what happened

## Log Messages

### **Single Pipeline Detection:**
```
🎯 Only SI pipeline was active and completed for session session_20250101_120000
📧 Sending SI-specific report for session session_20250101_120000
✅ SI-specific report sent successfully for session session_20250101_120000
```

### **Timeout Scenarios:**
```
⏰ Timeout reached - only SI pipeline was active, sending SI-specific report
⏰ Timeout reached - only Viajeros pipeline was active, sending Viajeros-specific report
⏰ Timeout reached - both pipelines were active but coordination failed
```

## Testing Commands

### **Test Single SI Pipeline:**
```bash
# Send only SI email (simulate missing Viajeros email)
# System should detect and send SI report within seconds
```

### **Test Single Viajeros Pipeline:**
```bash
# Send only Viajeros email (simulate missing SI email)
# System should detect and send Viajeros report within seconds
```

### **Test Timeout Scenario:**
```bash
# Send SI email, wait 6 minutes
# System should send timeout report after 5 minutes
```

## Conclusion

The enhanced system now properly handles all single pipeline scenarios:

1. **✅ Immediate Detection**: Single pipeline completion is detected immediately
2. **✅ Appropriate Reporting**: Pipeline-specific reports are sent correctly
3. **✅ Success Status**: Single pipeline completion is treated as success
4. **✅ Timeout Protection**: 5-minute maximum wait prevents hanging
5. **✅ Clear Messaging**: Reports clearly indicate what happened

The system ensures that if only one pipeline receives an email, it will still function correctly, process the data, and send an appropriate report without waiting indefinitely for the second pipeline.
