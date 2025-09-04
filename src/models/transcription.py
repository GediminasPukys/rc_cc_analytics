#!/usr/bin/env python3
"""
Pydantic models for audio transcription with speaker diarization
"""

from typing import List, Literal
from pydantic import BaseModel, Field
from enum import Enum


class SpeakerLabel(str, Enum):
    """Speaker labels for diarization"""
    SPEAKER1 = "speaker1"
    SPEAKER2 = "speaker2"
    SPEAKER3 = "speaker3"
    SPEAKER4 = "speaker4"
    SPEAKER5 = "speaker5"
    SILENCE = "silence"


class TranscriptionSegment(BaseModel):
    """Single transcription segment with speaker and timing"""
    timestamp_start: float = Field(description="Start time in seconds")
    timestamp_end: float = Field(description="End time in seconds")
    speaker_label: str = Field(description="Speaker identifier: speaker1, speaker2, speaker3, speaker4, speaker5, or silence")
    text: str = Field(description="Transcribed text for this segment")
    interval_id: int = Field(description="Unique identifier for this interval")


class TranscriptionResponse(BaseModel):
    """Complete transcription response with optional Lithuanian translation"""
    transcription: List[TranscriptionSegment] = Field(description="List of transcription segments in original language")
    lithuanian_transcription: List[TranscriptionSegment] = Field(description="List of transcription segments translated to Lithuanian")
    total_duration: float = Field(description="Total audio duration in seconds")
    num_speakers: int = Field(description="Number of unique speakers detected (excluding silence)")
    original_language: str = Field(description="Detected original language of the audio")