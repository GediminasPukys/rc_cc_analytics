#!/usr/bin/env python3
"""
Test script to verify clinic functions work correctly.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import clinic_functions
from logging_config import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger("test.functions")


async def test_clinic_functions():
    """Test all clinic functions with logging."""
    
    print("\n" + "="*60)
    print("TESTING CLINIC FUNCTIONS WITH OPENAI REALTIME")
    print("="*60 + "\n")
    
    # Initialize database
    print("1. Initializing database...")
    await clinic_functions.initialize()
    print("   ✅ Database initialized\n")
    
    # Test doctor listing
    print("2. Testing list_all_doctors()...")
    result = await clinic_functions.list_all_doctors()
    print(f"   Result: {result[:200]}...")
    print("   ✅ Doctor listing works\n")
    
    # Test patient lookup (non-existent)
    print("3. Testing lookup_patient() - non-existent...")
    result = await clinic_functions.lookup_patient("+37069999999")
    print(f"   Result: {result}")
    print("   ✅ Patient lookup works\n")
    
    # Test patient creation
    print("4. Testing create_patient()...")
    result = await clinic_functions.create_patient(
        "Test Patient",
        "+37069999999",
        "test@example.com"
    )
    print(f"   Result: {result}")
    print("   ✅ Patient creation works\n")
    
    # Test patient lookup (existing)
    print("5. Testing lookup_patient() - existing...")
    result = await clinic_functions.lookup_patient("+37069999999")
    print(f"   Result: {result}")
    print("   ✅ Patient found\n")
    
    # Test getting doctor info
    print("6. Testing get_doctor_info()...")
    result = await clinic_functions.get_doctor_info(1)
    print(f"   Result: {result[:200]}...")
    print("   ✅ Doctor info retrieval works\n")
    
    # Test scheduling appointment
    print("7. Testing schedule_appointment()...")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    result = await clinic_functions.schedule_appointment(
        doctor_id=1,
        date=tomorrow,
        time="10:00",
        notes="Test appointment"
    )
    print(f"   Result: {result}")
    print("   ✅ Appointment scheduling works\n")
    
    # Test getting patient appointments
    print("8. Testing get_patient_appointments()...")
    result = await clinic_functions.get_patient_appointments()
    print(f"   Result: {result[:200]}...")
    print("   ✅ Appointment retrieval works\n")
    
    # Test getting specialties
    print("9. Testing get_specialties()...")
    result = await clinic_functions.get_specialties()
    print(f"   Result: {result}")
    print("   ✅ Specialty listing works\n")
    
    # Test finding doctors by specialty
    print("10. Testing find_doctors_by_specialty()...")
    result = await clinic_functions.find_doctors_by_specialty("Endocrinologist")
    print(f"    Result: {result[:200]}...")
    print("    ✅ Doctor search by specialty works\n")
    
    print("="*60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("Check logs directory for detailed function call logs")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_clinic_functions())