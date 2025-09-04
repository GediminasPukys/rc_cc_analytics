#!/usr/bin/env python3
"""
OpenAI Realtime API agent for clinic management.
Clean, modern implementation with full function calling support.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import (
    AgentSession,
    JobContext,
    AutoSubscribe,
    WorkerOptions,
    WorkerType,
    RoomInputOptions,
    Agent
)
from livekit.plugins import openai, noise_cancellation
from openai.types.beta.realtime.session import TurnDetection

import clinic_functions
from logging_config import setup_logging

# Load environment variables
env_path = Path(__file__).parent.parent / ".env.local"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Set up comprehensive logging
log_dir = setup_logging()

logger = logging.getLogger("clinic.agent")


# System instructions for the agent
INSTRUCTIONS = """You are a professional and friendly receptionist at Ieva's Endocrinology Clinic.

Start each call with: "Hello, you've reached Ieva's Endocrinology Clinic. How may I assist you today?"

Your responsibilities:
1. Help patients schedule appointments with our doctors
2. Look up existing patient records or create new ones
3. Provide information about our doctors and their specialties
4. Manage appointments (view, cancel, reschedule)
5. Answer questions about clinic hours (Monday-Friday, 8 AM - 5 PM)

Always:
- Be warm, professional, and patient
- Confirm important details before taking actions
- Use the function tools to interact with the database
- Provide clear confirmations of any actions taken

Available doctors:
- Dr. Ieva Pukienė - Endocrinologist
- Dr. Jonas Petrauskas - Endocrinologist
- Dr. Giedrė Rimkutė - Thyroid Specialist
- Dr. Vytautas Bielskis - Diabetes Specialist

When scheduling appointments:
1. First look up the patient by phone number
2. If new, create their patient record
3. Check doctor availability
4. Confirm the appointment details
5. Book the appointment and provide confirmation

IMPORTANT: You have access to function tools to manage the clinic:
- lookup_patient: Find patient by phone number
- create_patient: Register new patients
- list_all_doctors: Show all doctors
- get_doctor_info: Get doctor details
- schedule_appointment: Book appointments
- get_patient_appointments: View appointments
- cancel_appointment: Cancel bookings

Use these functions whenever you need to interact with the clinic database."""


async def entrypoint(ctx: JobContext):
    """Main entry point for the LiveKit agent."""
    
    logger.info(f"Job started - Room: {ctx.room.name}, Job ID: {ctx.job.id}")
    
    # Initialize clinic database
    await clinic_functions.initialize()
    logger.info("Clinic database initialized")
    
    # Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info("Connected to room")
    
    # Wait for participant
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")
    
    try:
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        # Configure OpenAI Realtime model
        model = openai.realtime.RealtimeModel(
            model='gpt-4o-realtime-preview',
            voice='alloy',
            temperature=0.7,
            api_key=api_key,
            turn_detection=TurnDetection(
                type="server_vad",
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=500
            )
        )
        
        logger.info("Created OpenAI Realtime model: gpt-4o-realtime-preview")
        
        # Get function tools
        function_tools = [
            clinic_functions.lookup_patient,
            clinic_functions.create_patient,
            clinic_functions.list_all_doctors,
            clinic_functions.get_doctor_info,
            clinic_functions.get_specialties,
            clinic_functions.find_doctors_by_specialty,
            clinic_functions.get_available_slots,
            clinic_functions.schedule_appointment,
            clinic_functions.get_patient_appointments,
            clinic_functions.cancel_appointment,
            clinic_functions.get_current_patient_info,
        ]
        
        logger.info(f"Registered {len(function_tools)} function tools:")
        for tool in function_tools:
            logger.info(f"  - {tool.__name__}")
        
        # Create agent with instructions and function tools
        agent = Agent(
            instructions=INSTRUCTIONS,
            tools=function_tools  # Pass functions here
        )
        
        # Create and start agent session
        session = AgentSession(llm=model)
        
        # Start the session with agent
        await session.start(
            room=ctx.room,
            agent=agent,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC()
            )
        )
        
        logger.info(f"Agent session started successfully in room: {ctx.room.name}")
        
        # Generate initial greeting
        await session.generate_reply(
            instructions="Greet the caller professionally as the clinic receptionist"
        )
        
    except Exception as e:
        logger.error(f"Failed to start agent session: {e}")
        raise
    
    logger.info("Agent is ready and listening")


if __name__ == "__main__":
    # Run the agent
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=WorkerType.ROOM
        )
    )