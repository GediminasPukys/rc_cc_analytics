"""
Clinic function tools with comprehensive logging.
Clean implementation with full transparency.
"""

import json
import logging
from typing import Annotated, Optional
from datetime import datetime
from livekit.agents import function_tool

from database import ClinicDatabase, Patient, Doctor, Appointment

# Set up structured logging for function calls
logger = logging.getLogger("clinic.functions")
call_logger = logging.getLogger("function.calls")
call_logger.setLevel(logging.INFO)

# Initialize database
db = ClinicDatabase()

# Context for maintaining state across function calls
class ClinicContext:
    """Maintains state across function calls."""
    def __init__(self):
        self.current_patient: Optional[Patient] = None
        self.current_doctor: Optional[Doctor] = None
        self.last_appointment: Optional[Appointment] = None
        
context = ClinicContext()


def log_function_call(func_name: str, args: dict, result: any, duration_ms: float = 0):
    """Log function call with full transparency."""
    call_logger.info(
        "FUNCTION_CALL",
        extra={
            "function": func_name,
            "arguments": args,
            "result": str(result)[:500] if result else None,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
            "has_patient_context": context.current_patient is not None,
            "has_doctor_context": context.current_doctor is not None
        }
    )


@function_tool(description="Look up a patient by their phone number")
async def lookup_patient(
    phone: Annotated[str, "The patient's phone number (e.g., +37061234567)"]
) -> str:
    """Find a patient in the database by phone number."""
    start = datetime.now()
    
    try:
        patient = await db.find_patient_by_phone(phone)
        
        if patient:
            context.current_patient = patient
            result = f"Found patient: {patient.name} (Phone: {patient.phone}, Email: {patient.email or 'Not provided'})"
        else:
            context.current_patient = None
            result = f"No patient found with phone number {phone}. Would you like to create a new patient record?"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("lookup_patient", {"phone": phone}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in lookup_patient: {e}")
        return f"Error looking up patient: {str(e)}"


@function_tool(description="Create a new patient record in the system")
async def create_patient(
    name: Annotated[str, "The patient's full name"],
    phone: Annotated[str, "The patient's phone number"],
    email: Annotated[Optional[str], "The patient's email address (optional)"] = None
) -> str:
    """Register a new patient in the clinic database."""
    start = datetime.now()
    
    try:
        # Check if patient already exists
        existing = await db.find_patient_by_phone(phone)
        if existing:
            context.current_patient = existing
            result = f"Patient already exists: {existing.name} (Phone: {existing.phone})"
        else:
            patient = await db.create_patient(name, phone, email)
            context.current_patient = patient
            result = f"Successfully created new patient record for {patient.name} (ID: {patient.id}, Phone: {patient.phone})"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("create_patient", {"name": name, "phone": phone, "email": email}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in create_patient: {e}")
        return f"Error creating patient: {str(e)}"


@function_tool(description="Get a list of all doctors at the clinic")
async def list_all_doctors() -> str:
    """Retrieve all doctors with their specialties and availability."""
    start = datetime.now()
    
    try:
        doctors = await db.get_all_doctors()
        
        if not doctors:
            result = "No doctors found in the system."
        else:
            result = "Our clinic doctors:\n\n"
            for doctor in doctors:
                result += f"• {doctor.name} - {doctor.specialty}\n"
                if doctor.available_slots:
                    result += f"  Next available: {', '.join(doctor.available_slots[:3])}\n"
                result += "\n"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("list_all_doctors", {}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in list_all_doctors: {e}")
        return f"Error retrieving doctors: {str(e)}"


@function_tool(description="Get detailed information about a specific doctor")
async def get_doctor_info(
    doctor_id: Annotated[int, "The doctor's ID number"]
) -> str:
    """Get detailed information about a specific doctor."""
    start = datetime.now()
    
    try:
        doctor = await db.get_doctor_by_id(doctor_id)
        
        if not doctor:
            result = f"No doctor found with ID {doctor_id}"
        else:
            context.current_doctor = doctor
            result = f"Doctor Information:\n"
            result += f"Name: {doctor.name}\n"
            result += f"Specialty: {doctor.specialty}\n"
            result += f"\nAvailable appointment times:\n"
            
            if doctor.available_slots:
                for slot in doctor.available_slots[:10]:
                    result += f"  • {slot}\n"
            else:
                result += "  No available slots at this time.\n"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("get_doctor_info", {"doctor_id": doctor_id}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in get_doctor_info: {e}")
        return f"Error retrieving doctor information: {str(e)}"


@function_tool(description="Get all available medical specialties at the clinic")
async def get_specialties() -> str:
    """List all medical specialties available at the clinic."""
    start = datetime.now()
    
    try:
        specialties = await db.get_specialties()
        
        if not specialties:
            result = "No specialties found in the system."
        else:
            result = f"Available specialties at our clinic: {', '.join(specialties)}"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("get_specialties", {}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in get_specialties: {e}")
        return f"Error retrieving specialties: {str(e)}"


@function_tool(description="Find doctors who specialize in a specific medical area")
async def find_doctors_by_specialty(
    specialty: Annotated[str, "The medical specialty to search for"]
) -> str:
    """Find all doctors with a specific specialty."""
    start = datetime.now()
    
    try:
        doctors = await db.get_doctors_by_specialty(specialty)
        
        if not doctors:
            result = f"No doctors found with specialty: {specialty}"
        else:
            result = f"Doctors specializing in {specialty}:\n\n"
            for doctor in doctors:
                result += f"• {doctor.name} (ID: {doctor.id})\n"
                if doctor.available_slots:
                    result += f"  Next available: {', '.join(doctor.available_slots[:3])}\n"
                result += "\n"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("find_doctors_by_specialty", {"specialty": specialty}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in find_doctors_by_specialty: {e}")
        return f"Error finding doctors: {str(e)}"


@function_tool(description="Get available appointment slots for a doctor")
async def get_available_slots(
    doctor_id: Annotated[int, "The doctor's ID number"],
    date: Annotated[Optional[str], "Specific date in YYYY-MM-DD format (optional)"] = None
) -> str:
    """Check available appointment slots for a doctor."""
    start = datetime.now()
    
    try:
        slots = await db.get_available_slots(doctor_id, date)
        
        if not slots:
            result = f"No available slots found for doctor ID {doctor_id}"
            if date:
                result += f" on {date}"
        else:
            result = "Available appointment slots:\n\n"
            current_date = None
            for slot in slots:
                if slot['date'] != current_date:
                    current_date = slot['date']
                    result += f"\n{slot['date']} ({slot['doctor_name']}):\n"
                result += f"  • {slot['time']}\n"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("get_available_slots", {"doctor_id": doctor_id, "date": date}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in get_available_slots: {e}")
        return f"Error retrieving available slots: {str(e)}"


@function_tool(description="Schedule an appointment for a patient with a doctor")
async def schedule_appointment(
    doctor_id: Annotated[int, "The doctor's ID number"],
    date: Annotated[str, "Appointment date in YYYY-MM-DD format"],
    time: Annotated[str, "Appointment time in HH:MM format"],
    notes: Annotated[Optional[str], "Additional notes about the appointment"] = None
) -> str:
    """Book an appointment for the current patient."""
    start = datetime.now()
    
    try:
        if not context.current_patient:
            result = "No patient selected. Please look up or create a patient first."
        else:
            appointment = await db.create_appointment(
                context.current_patient.id,
                doctor_id,
                date,
                time,
                notes
            )
            
            if appointment:
                context.last_appointment = appointment
                doctor = await db.get_doctor_by_id(doctor_id)
                result = f"✅ Appointment confirmed!\n\n"
                result += f"Patient: {context.current_patient.name}\n"
                result += f"Doctor: {doctor.name if doctor else 'Unknown'}\n"
                result += f"Date: {date}\n"
                result += f"Time: {time}\n"
                result += f"Appointment ID: {appointment.id}\n"
                if notes:
                    result += f"Notes: {notes}\n"
            else:
                result = f"Unable to book appointment. The slot {date} at {time} may not be available."
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call(
            "schedule_appointment", 
            {"doctor_id": doctor_id, "date": date, "time": time, "notes": notes},
            result,
            duration
        )
        return result
        
    except Exception as e:
        logger.error(f"Error in schedule_appointment: {e}")
        return f"Error scheduling appointment: {str(e)}"


@function_tool(description="Get all appointments for the current patient")
async def get_patient_appointments() -> str:
    """Retrieve all appointments for the current patient."""
    start = datetime.now()
    
    try:
        if not context.current_patient:
            result = "No patient selected. Please look up a patient first."
        else:
            appointments = await db.get_patient_appointments(context.current_patient.id)
            
            if not appointments:
                result = f"No appointments found for {context.current_patient.name}"
            else:
                result = f"Appointments for {context.current_patient.name}:\n\n"
                for appt in appointments:
                    result += f"• {appt['date']} at {appt['time']}\n"
                    result += f"  Doctor: {appt['doctor_name']} ({appt['specialty']})\n"
                    result += f"  Status: {appt['status']}\n"
                    result += f"  ID: {appt['id']}\n"
                    if appt['notes']:
                        result += f"  Notes: {appt['notes']}\n"
                    result += "\n"
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("get_patient_appointments", {}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in get_patient_appointments: {e}")
        return f"Error retrieving appointments: {str(e)}"


@function_tool(description="Cancel an existing appointment")
async def cancel_appointment(
    appointment_id: Annotated[int, "The appointment ID to cancel"]
) -> str:
    """Cancel a scheduled appointment."""
    start = datetime.now()
    
    try:
        success = await db.cancel_appointment(appointment_id)
        
        if success:
            result = f"✅ Appointment {appointment_id} has been successfully cancelled. The time slot is now available for other patients."
        else:
            result = f"Unable to cancel appointment {appointment_id}. It may not exist or may have already been cancelled."
        
        duration = (datetime.now() - start).total_seconds() * 1000
        log_function_call("cancel_appointment", {"appointment_id": appointment_id}, result, duration)
        return result
        
    except Exception as e:
        logger.error(f"Error in cancel_appointment: {e}")
        return f"Error cancelling appointment: {str(e)}"


@function_tool(description="Get information about the currently selected patient")
async def get_current_patient_info() -> str:
    """Get details about the current patient in context."""
    start = datetime.now()
    
    if context.current_patient:
        result = f"Current patient:\n"
        result += f"Name: {context.current_patient.name}\n"
        result += f"Phone: {context.current_patient.phone}\n"
        result += f"Email: {context.current_patient.email or 'Not provided'}\n"
        result += f"Patient ID: {context.current_patient.id}"
    else:
        result = "No patient currently selected. Use lookup_patient or create_patient first."
    
    duration = (datetime.now() - start).total_seconds() * 1000
    log_function_call("get_current_patient_info", {}, result, duration)
    return result


# Initialize database on module import
async def initialize():
    """Initialize the clinic database."""
    await db.init()
    logger.info("Clinic functions initialized with database")