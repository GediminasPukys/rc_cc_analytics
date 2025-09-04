#!/usr/bin/env python3
"""
Transcription service using Gemini API with structured output
"""

import os
import json
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import google.genai as genai
from google.cloud import storage

from src.models.transcription import TranscriptionResponse, TranscriptionSegment

load_dotenv()
logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for audio transcription with speaker diarization"""
    
    def __init__(self):
        """Initialize transcription service"""
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Initialize GCS client
        self.gcs_client = storage.Client()
        self.bucket_name = os.getenv("GCS_BUCKET_NAME", "livekit-logs-rc")
    
    def get_transcription_path(self, session_id: str) -> str:
        """Get GCS path for transcription file"""
        return f"sessions/{session_id}/transcription.json"
    
    def check_existing_transcription(self, session_id: str) -> Optional[TranscriptionResponse]:
        """Check if transcription already exists in GCS"""
        try:
            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(self.get_transcription_path(session_id))
            
            if blob.exists():
                logger.info(f"Found existing transcription for session {session_id}")
                data = json.loads(blob.download_as_text())
                
                # Convert to Pydantic model
                segments = [TranscriptionSegment(**seg) for seg in data["transcription"]]
                lt_segments = [TranscriptionSegment(**seg) for seg in data.get("lithuanian_transcription", [])]
                
                # If no Lithuanian transcription in cached data, return None to regenerate
                if not lt_segments:
                    logger.info("Cached transcription lacks Lithuanian translation, will regenerate")
                    return None
                    
                return TranscriptionResponse(
                    transcription=segments,
                    lithuanian_transcription=lt_segments,
                    total_duration=data.get("total_duration", 0),
                    num_speakers=data.get("num_speakers", 0),
                    original_language=data.get("original_language", "unknown")
                )
        except Exception as e:
            logger.error(f"Error checking existing transcription: {e}")
        
        return None
    
    def save_transcription(self, session_id: str, transcription: TranscriptionResponse) -> bool:
        """Save transcription to GCS"""
        try:
            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(self.get_transcription_path(session_id))
            
            # Convert to JSON
            data = {
                "transcription": [seg.model_dump() for seg in transcription.transcription],
                "lithuanian_transcription": [seg.model_dump() for seg in transcription.lithuanian_transcription],
                "total_duration": transcription.total_duration,
                "num_speakers": transcription.num_speakers,
                "original_language": transcription.original_language
            }
            
            blob.upload_from_string(
                json.dumps(data, indent=2),
                content_type="application/json"
            )
            
            logger.info(f"Saved transcription for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving transcription: {e}")
            return False
    
    def transcribe_audio(self, audio_path: str, session_id: str) -> Optional[TranscriptionResponse]:
        """
        Transcribe audio file with speaker diarization
        
        Args:
            audio_path: Path to audio file
            session_id: Session ID for caching
            
        Returns:
            TranscriptionResponse or None if failed
        """
        # Check for existing transcription
        existing = self.check_existing_transcription(session_id)
        if existing:
            return existing
        
        try:
            # Upload audio file to Gemini using Files API
            logger.info(f"Uploading audio file: {audio_path}")
            
            # Upload the file using the client
            audio_file = self.client.files.upload(file=audio_path)
            
            # Transcription prompt with Lithuanian translation
            prompt = """This is a telephone audio conversation. Transcribe it with speaker diarization and timestamps, then translate to Lithuanian.

Instructions:
1. Identify different speakers (up to 5) and label them as speaker1, speaker2, etc.
2. Include timestamps for each segment
3. Mark silence periods longer than 3 seconds with speaker_label="silence"
4. Each segment should have a unique interval_id starting from 1
5. Provide accurate timestamps in seconds
6. Keep text segments natural and complete (don't cut mid-sentence)
7. Detect the original language and store it in original_language field
8. Provide TWO transcriptions:
   - "transcription": Original language transcription
   - "lithuanian_transcription": All text translated to Lithuanian (keep same timestamps and speaker labels)
9. For silence segments, use empty string for text in both transcriptions

Analyze the entire audio and provide complete bilingual transcription."""
            
            # Create transcription request with structured output
            logger.info("Requesting transcription from Gemini...")
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[audio_file, prompt],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": TranscriptionResponse,
                }
            )
            
            # Parse response
            if response.parsed:
                transcription = response.parsed
                logger.info(f"Transcription completed: {transcription.num_speakers} speakers, {len(transcription.transcription)} segments")
                
                # Save to GCS
                self.save_transcription(session_id, transcription)
                
                return transcription
            elif response.text:
                # Try to parse JSON text if parsed object not available
                logger.info("Attempting to parse JSON from text response")
                try:
                    data = json.loads(response.text)
                    # Create TranscriptionResponse from JSON
                    segments = [TranscriptionSegment(**seg) for seg in data["transcription"]]
                    lt_segments = [TranscriptionSegment(**seg) for seg in data.get("lithuanian_transcription", [])]
                    
                    transcription = TranscriptionResponse(
                        transcription=segments,
                        lithuanian_transcription=lt_segments,
                        total_duration=data["total_duration"],
                        num_speakers=data["num_speakers"],
                        original_language=data.get("original_language", "unknown")
                    )
                    
                    logger.info(f"Successfully parsed from JSON: {transcription.num_speakers} speakers, {len(transcription.transcription)} segments")
                    
                    # Save to GCS
                    self.save_transcription(session_id, transcription)
                    
                    return transcription
                except Exception as e:
                    logger.error(f"Failed to parse JSON from text: {e}")
                    logger.error(f"Response text: {response.text[:500]}")
                    return None
            else:
                logger.error("No response from Gemini")
                return None
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
    
    def get_transcription_text(self, transcription: TranscriptionResponse, use_lithuanian: bool = False) -> str:
        """Convert transcription to readable text format
        
        Args:
            transcription: TranscriptionResponse object
            use_lithuanian: If True, use Lithuanian transcription instead of original
        """
        lines = []
        segments = transcription.lithuanian_transcription if use_lithuanian else transcription.transcription
        
        for seg in segments:
            if seg.speaker_label != "silence":
                time = f"[{seg.timestamp_start:.1f}s - {seg.timestamp_end:.1f}s]"
                speaker = seg.speaker_label.upper()
                lines.append(f"{time} {speaker}: {seg.text}")
        return "\n".join(lines)
    
    def get_speaker_statistics(self, transcription: TranscriptionResponse) -> dict:
        """Get statistics about speakers"""
        stats = {}
        
        for seg in transcription.transcription:
            if seg.speaker_label != "silence":
                if seg.speaker_label not in stats:
                    stats[seg.speaker_label] = {
                        "total_time": 0,
                        "num_segments": 0,
                        "words": 0
                    }
                
                duration = seg.timestamp_end - seg.timestamp_start
                stats[seg.speaker_label]["total_time"] += duration
                stats[seg.speaker_label]["num_segments"] += 1
                stats[seg.speaker_label]["words"] += len(seg.text.split())
        
        return stats