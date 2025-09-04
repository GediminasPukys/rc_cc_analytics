"""
Async SQLite database module for clinic management.
Clean, transparent implementation with no boilerplate.
"""

import aiosqlite
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path

logger = logging.getLogger("clinic.database")

@dataclass
class Doctor:
    id: int
    name: str
    specialty: str
    available_slots: List[str]

@dataclass
class Patient:
    id: int
    name: str
    phone: str
    email: Optional[str] = None

@dataclass
class Appointment:
    id: int
    patient_id: int
    doctor_id: int
    date: str
    time: str
    status: str
    notes: Optional[str] = None


class ClinicDatabase:
    """Async database manager for clinic operations."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv("DATABASE_PATH", "data/clinic.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database path: {self.db_path}")

    @asynccontextmanager
    async def connection(self):
        """Context manager for database connections."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def init(self):
        """Initialize database schema and sample data."""
        async with self.connection() as conn:
            # Create tables
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS doctors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    specialty TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    email TEXT
                );
                
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    doctor_id INTEGER,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients (id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors (id)
                );
                
                CREATE TABLE IF NOT EXISTS available_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id INTEGER,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    is_available BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (doctor_id) REFERENCES doctors (id),
                    UNIQUE(doctor_id, date, time)
                );
            """)
            
            # Check if we need to add sample doctors
            cursor = await conn.execute("SELECT COUNT(*) as count FROM doctors")
            row = await cursor.fetchone()
            
            if row['count'] == 0:
                doctors = [
                    ("Dr. Ieva Pukienė", "Endocrinologist"),
                    ("Dr. Jonas Petrauskas", "Endocrinologist"),
                    ("Dr. Giedrė Rimkutė", "Thyroid Specialist"),
                    ("Dr. Vytautas Bielskis", "Diabetes Specialist")
                ]
                await conn.executemany(
                    "INSERT INTO doctors (name, specialty) VALUES (?, ?)",
                    doctors
                )
                logger.info(f"Added {len(doctors)} sample doctors")
                
                # Generate available slots for next 30 days
                today = datetime.now().date()
                slots = []
                
                for doctor_id in range(1, len(doctors) + 1):
                    for day in range(30):
                        slot_date = today + timedelta(days=day)
                        if slot_date.weekday() < 5:  # Monday-Friday
                            for hour in range(8, 17):  # 8 AM to 5 PM
                                slots.append((
                                    doctor_id,
                                    slot_date.strftime("%Y-%m-%d"),
                                    f"{hour:02d}:00",
                                    1
                                ))
                
                await conn.executemany(
                    "INSERT OR IGNORE INTO available_slots (doctor_id, date, time, is_available) VALUES (?, ?, ?, ?)",
                    slots
                )
                logger.info(f"Generated {len(slots)} appointment slots")
            
            await conn.commit()
            logger.info("Database initialized successfully")

    async def find_patient_by_phone(self, phone: str) -> Optional[Patient]:
        """Find a patient by phone number."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM patients WHERE phone = ?", (phone,)
            )
            row = await cursor.fetchone()
            
            if row:
                return Patient(
                    id=row['id'],
                    name=row['name'],
                    phone=row['phone'],
                    email=row['email']
                )
            return None

    async def create_patient(self, name: str, phone: str, email: Optional[str] = None) -> Patient:
        """Create a new patient record."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO patients (name, phone, email) VALUES (?, ?, ?)",
                (name, phone, email)
            )
            await conn.commit()
            
            return Patient(
                id=cursor.lastrowid,
                name=name,
                phone=phone,
                email=email
            )

    async def get_all_doctors(self) -> List[Doctor]:
        """Get all doctors with their next available slots."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, specialty FROM doctors ORDER BY name"
            )
            doctors = []
            
            async for row in cursor:
                # Get next 5 available slots for this doctor
                slots_cursor = await conn.execute(
                    """SELECT date, time FROM available_slots 
                       WHERE doctor_id = ? AND is_available = 1
                       ORDER BY date, time LIMIT 5""",
                    (row['id'],)
                )
                slots = [f"{s['date']} {s['time']}" async for s in slots_cursor]
                
                doctors.append(Doctor(
                    id=row['id'],
                    name=row['name'],
                    specialty=row['specialty'],
                    available_slots=slots
                ))
            
            return doctors

    async def get_doctor_by_id(self, doctor_id: int) -> Optional[Doctor]:
        """Get a specific doctor by ID."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, specialty FROM doctors WHERE id = ?",
                (doctor_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                # Get next 10 available slots
                slots_cursor = await conn.execute(
                    """SELECT date, time FROM available_slots 
                       WHERE doctor_id = ? AND is_available = 1
                       ORDER BY date, time LIMIT 10""",
                    (doctor_id,)
                )
                slots = [f"{s['date']} {s['time']}" async for s in slots_cursor]
                
                return Doctor(
                    id=row['id'],
                    name=row['name'],
                    specialty=row['specialty'],
                    available_slots=slots
                )
            return None

    async def get_available_slots(
        self, 
        doctor_id: Optional[int] = None, 
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available appointment slots."""
        query = """
            SELECT s.id, d.name as doctor_name, d.specialty, s.date, s.time
            FROM available_slots s
            JOIN doctors d ON s.doctor_id = d.id
            WHERE s.is_available = 1
        """
        params = []
        
        if doctor_id:
            query += " AND s.doctor_id = ?"
            params.append(doctor_id)
        
        if date:
            query += " AND s.date = ?"
            params.append(date)
        
        query += " ORDER BY s.date, s.time LIMIT 20"
        
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            return [dict(row) async for row in cursor]

    async def create_appointment(
        self,
        patient_id: int,
        doctor_id: int,
        date: str,
        time: str,
        notes: Optional[str] = None
    ) -> Optional[Appointment]:
        """Create a new appointment."""
        async with self.connection() as conn:
            # Check if slot is available
            cursor = await conn.execute(
                """SELECT id FROM available_slots 
                   WHERE doctor_id = ? AND date = ? AND time = ? AND is_available = 1""",
                (doctor_id, date, time)
            )
            slot = await cursor.fetchone()
            
            if not slot:
                return None
            
            # Create appointment
            cursor = await conn.execute(
                """INSERT INTO appointments (patient_id, doctor_id, date, time, status, notes)
                   VALUES (?, ?, ?, ?, 'scheduled', ?)""",
                (patient_id, doctor_id, date, time, notes)
            )
            appointment_id = cursor.lastrowid
            
            # Mark slot as unavailable
            await conn.execute(
                "UPDATE available_slots SET is_available = 0 WHERE id = ?",
                (slot['id'],)
            )
            
            await conn.commit()
            
            return Appointment(
                id=appointment_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                date=date,
                time=time,
                status='scheduled',
                notes=notes
            )

    async def get_patient_appointments(self, patient_id: int) -> List[Dict[str, Any]]:
        """Get all appointments for a patient."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """SELECT a.id, a.date, a.time, a.status, a.notes,
                          d.name as doctor_name, d.specialty
                   FROM appointments a
                   JOIN doctors d ON a.doctor_id = d.id
                   WHERE a.patient_id = ?
                   ORDER BY a.date DESC, a.time DESC""",
                (patient_id,)
            )
            return [dict(row) async for row in cursor]

    async def cancel_appointment(self, appointment_id: int) -> bool:
        """Cancel an appointment and free up the slot."""
        async with self.connection() as conn:
            # Get appointment details
            cursor = await conn.execute(
                "SELECT doctor_id, date, time FROM appointments WHERE id = ?",
                (appointment_id,)
            )
            appointment = await cursor.fetchone()
            
            if not appointment:
                return False
            
            # Update appointment status
            await conn.execute(
                "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
                (appointment_id,)
            )
            
            # Free up the slot
            await conn.execute(
                """UPDATE available_slots SET is_available = 1 
                   WHERE doctor_id = ? AND date = ? AND time = ?""",
                (appointment['doctor_id'], appointment['date'], appointment['time'])
            )
            
            await conn.commit()
            return True

    async def get_specialties(self) -> List[str]:
        """Get all unique specialties."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT DISTINCT specialty FROM doctors ORDER BY specialty"
            )
            return [row['specialty'] async for row in cursor]

    async def get_doctors_by_specialty(self, specialty: str) -> List[Doctor]:
        """Get all doctors with a specific specialty."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, specialty FROM doctors WHERE specialty = ?",
                (specialty,)
            )
            doctors = []
            
            async for row in cursor:
                # Get next 5 available slots
                slots_cursor = await conn.execute(
                    """SELECT date, time FROM available_slots 
                       WHERE doctor_id = ? AND is_available = 1
                       ORDER BY date, time LIMIT 5""",
                    (row['id'],)
                )
                slots = [f"{s['date']} {s['time']}" async for s in slots_cursor]
                
                doctors.append(Doctor(
                    id=row['id'],
                    name=row['name'],
                    specialty=row['specialty'],
                    available_slots=slots
                ))
            
            return doctors