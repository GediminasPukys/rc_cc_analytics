# Iteration 2: OpenAI Realtime Clinic Agent

## Overview
Modern implementation of a clinic receptionist agent using OpenAI's Realtime API with full function calling support.

## Features
- ✅ **OpenAI Realtime API** with native function calling
- ✅ **Latest LiveKit libraries** (v1.2.6+)
- ✅ **Comprehensive function logging** with transparency
- ✅ **Clean architecture** with no boilerplate
- ✅ **Full clinic functionality**:
  - Patient management (lookup, create)
  - Doctor information and availability
  - Appointment scheduling and management
  - Multi-specialty support

## Requirements
- Python 3.10+
- OpenAI API key
- LiveKit Cloud account

## Installation

1. Install dependencies:
```bash
cd iteration_2
pip install -r requirements.txt
```

2. Configure environment variables in `.env.local`:
```env
# Required
OPENAI_API_KEY=your_openai_api_key
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Optional
DATABASE_PATH=data/clinic.db
LOG_LEVEL=INFO
```

## Running the Agent

### Development Mode
```bash
cd src
python agent.py dev
```

### Production Mode
```bash
cd src
python agent.py start
```

### Test Functions
```bash
cd src
python test_functions.py
```

## Architecture

### Core Components

1. **agent.py** - Main agent with OpenAI Realtime API
   - Uses `gpt-4o-realtime-preview` model
   - Full function calling support
   - Server-side VAD for natural conversation

2. **clinic_functions.py** - Function tools with logging
   - 11 decorated functions for clinic operations
   - Comprehensive logging of all function calls
   - Maintains context across calls

3. **database.py** - Async SQLite database
   - Clean async/await implementation
   - Row factory for dictionary results
   - Automatic schema initialization

4. **logging_config.py** - Enhanced logging system
   - Separate logs for function calls
   - Structured logging with timestamps
   - Debug and production modes

## Function Calling

All functions are properly decorated and logged:

```python
@function_tool(description="Look up a patient by phone number")
async def lookup_patient(phone: str) -> str:
    # Function implementation with logging
```

### Available Functions
1. `lookup_patient` - Find patient by phone
2. `create_patient` - Register new patient
3. `list_all_doctors` - Show all doctors
4. `get_doctor_info` - Get doctor details
5. `get_specialties` - List specialties
6. `find_doctors_by_specialty` - Search doctors
7. `get_available_slots` - Check availability
8. `schedule_appointment` - Book appointment
9. `get_patient_appointments` - View appointments
10. `cancel_appointment` - Cancel booking
11. `get_current_patient_info` - Current patient

## Logging

### Function Call Logs
All function calls are logged with:
- Function name
- Input arguments
- Result/output
- Execution duration
- Timestamp
- Context state

### Log Files
- `logs/clinic_YYYYMMDD_HHMMSS.log` - All application logs
- `logs/function_calls_YYYYMMDD_HHMMSS.log` - Function calls only

## Key Differences from Iteration 1

| Feature | Iteration 1 (Gemini) | Iteration 2 (OpenAI) |
|---------|---------------------|---------------------|
| Model | gemini-2.5-flash-preview-native-audio-dialog | gpt-4o-realtime-preview |
| Function Calling | ❌ Not supported | ✅ Fully supported |
| Libraries | Mixed versions | Latest versions |
| Logging | Basic | Comprehensive |
| Architecture | Legacy patterns | Modern async/await |

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check OPENAI_API_KEY is valid
   - Verify network connectivity

2. **Function Not Called**
   - Check function_calls log file
   - Verify function decorator syntax

3. **Database Errors**
   - Check data/ directory permissions
   - Verify SQLite is installed

## Testing

The `test_functions.py` script tests all clinic functions:
- Database initialization
- Patient CRUD operations
- Doctor queries
- Appointment management
- Function call logging

## Future Enhancements
- Add appointment reminders
- Implement wait list management
- Add multi-language support
- Create analytics dashboard
- Add payment processing