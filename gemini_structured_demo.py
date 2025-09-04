#!/usr/bin/env python3
"""
Essential Gemini structured output demo with Pydantic using google.genai API
"""

import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import google.genai as genai

# Load environment
load_dotenv()

# Essential Pydantic model with field descriptions
class Task(BaseModel):
    """A task with structured fields"""
    title: str = Field(description="Brief title of the task")
    description: str = Field(description="Detailed description")
    priority: str = Field(description="Priority: low, medium, high")
    hours: float = Field(description="Estimated hours to complete")

# Configure API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found in .env")
    exit(1)

# Create client
client = genai.Client(api_key=api_key)

# Simple prompt
prompt = "Create a task for building a login page for a web application."

# Make the API call
print("📤 Calling Gemini API...")
response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=prompt,
    config={
        "response_mime_type": "application/json",
        "response_schema": Task,
    }
)

# Print JSON result
print("\n📊 Response (JSON):")
print(response.text)

# Use parsed object
print("\n✅ Parsed Task:")
task = response.parsed
print(f"  Title: {task.title}")
print(f"  Priority: {task.priority}")
print(f"  Hours: {task.hours}")
print(f"  Description: {task.description[:50]}...")