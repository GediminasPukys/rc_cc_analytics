#!/usr/bin/env python3
"""Debug script to check session files in GCS"""

import os
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize GCS client
client = storage.Client(project=os.getenv("GCS_PROJECT_ID"))
bucket = client.bucket(os.getenv("GCS_BUCKET_NAME"))

# Session to debug
session_id = "20250904_180344_custom_empathy"

print(f"\n=== Debugging session: {session_id} ===\n")

# List all files in the session
prefix = f"sessions/{session_id}/"
blobs = bucket.list_blobs(prefix=prefix)

files = []
for blob in blobs:
    files.append(blob.name)
    print(f"  - {blob.name}")

print(f"\nTotal files: {len(files)}")

# Check specific patterns
print(f"\n=== Analysis Results ===")

has_audio = False
has_transcript = False

for file_path in files:
    filename = file_path.split('/')[-1].lower()
    
    # Check for audio files
    audio_extensions = ['.wav', '.ogg', '.mp3', '.m4a', '.webm']
    for ext in audio_extensions:
        if filename.endswith(ext):
            has_audio = True
            print(f"✅ Audio file found: {filename}")
    
    # Check for transcript
    if 'transcript' in filename or filename == 'transcription.json':
        has_transcript = True
        print(f"✅ Transcript file found: {filename}")

print(f"\nHas Audio: {has_audio}")
print(f"Has Transcript: {has_transcript}")
print(f"Should appear in bulk transcription: {has_audio and not has_transcript}")

# Also check what the metadata detection logic would find
print("\n=== Testing Current Detection Logic ===")

# Check for audio files with various patterns
audio_patterns = ['recording', 'audio', 'test_audio']
audio_extensions = ['.wav', '.ogg', '.mp3', '.m4a', '.webm']

found_audio = False
found_transcript = False

for file_path in files:
    filename = file_path.split('/')[-1].lower()
    
    # Check if it's an audio file (same logic as in app)
    for pattern in audio_patterns:
        if pattern in filename:
            for ext in audio_extensions:
                if filename.endswith(ext):
                    found_audio = True
                    print(f"Pattern match audio: {filename}")
                    break
        if found_audio:
            break
    
    # Also check for any file with audio extension
    if not found_audio:
        for ext in audio_extensions:
            if filename.endswith(ext):
                found_audio = True
                print(f"Extension match audio: {filename}")
                break
    
    # Check for transcript files
    if 'transcript' in filename or filename == 'transcription.json':
        found_transcript = True
        print(f"Transcript match: {filename}")

print(f"\nDetection Results:")
print(f"  Found Audio: {found_audio}")
print(f"  Found Transcript: {found_transcript}")