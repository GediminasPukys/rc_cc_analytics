"""
Text-to-Speech service using Google Gemini 2.5 Pro Preview TTS
Generates audio from text input with configurable voice and language
"""

import base64
import mimetypes
import os
import struct
import tempfile
from typing import Optional, Tuple
from google import genai
from google.genai import types

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


class TextToSpeechService:
    """Service for generating audio from text using Gemini TTS"""
    
    AVAILABLE_VOICES = [
        "Zephyr",  # Default voice
        "Puck", 
        "Charon",
        "Kore",
        "Fenrir",
        "Aoede"
    ]
    
    def __init__(self):
        """Initialize the TTS service"""
        # Get API key from Streamlit secrets or environment
        if HAS_STREAMLIT and "gcs" in st.secrets and "GEMINI_API_KEY" in st.secrets["gcs"]:
            self.api_key = st.secrets["gcs"]["GEMINI_API_KEY"]
        else:
            # Fallback to environment variables
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in Streamlit secrets or environment variables")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-pro-preview-tts"
    
    def generate_audio(self, 
                      text: str, 
                      voice: str = "Zephyr",
                      temperature: float = 1.0) -> Optional[bytes]:
        """
        Generate audio from text
        
        Args:
            text: Text to convert to speech
            voice: Voice name to use (default: Zephyr)
            temperature: Generation temperature (0-2, default: 1.0)
        
        Returns:
            WAV audio data as bytes, or None if generation fails
        """
        if voice not in self.AVAILABLE_VOICES:
            voice = "Zephyr"
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=text),
                    ],
                ),
            ]
            
            generate_content_config = types.GenerateContentConfig(
                temperature=temperature,
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                ),
            )
            
            # Collect all audio chunks
            audio_chunks = []
            mime_type = None
            
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            ):
                if (chunk.candidates is None or 
                    chunk.candidates[0].content is None or 
                    chunk.candidates[0].content.parts is None):
                    continue
                
                if (chunk.candidates[0].content.parts[0].inline_data and 
                    chunk.candidates[0].content.parts[0].inline_data.data):
                    
                    inline_data = chunk.candidates[0].content.parts[0].inline_data
                    audio_chunks.append(inline_data.data)
                    if not mime_type:
                        mime_type = inline_data.mime_type
            
            if audio_chunks:
                # Concatenate all chunks
                audio_data = b''.join(audio_chunks)
                
                # Convert to WAV if necessary
                if mime_type and not mime_type.startswith("audio/wav"):
                    audio_data = self._convert_to_wav(audio_data, mime_type)
                
                return audio_data
            
        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            return None
        
        return None
    
    def _convert_to_wav(self, audio_data: bytes, mime_type: str) -> bytes:
        """
        Convert audio data to WAV format
        
        Args:
            audio_data: Raw audio data
            mime_type: MIME type of the audio data
        
        Returns:
            WAV formatted audio data
        """
        parameters = self._parse_audio_mime_type(mime_type)
        bits_per_sample = parameters["bits_per_sample"]
        sample_rate = parameters["rate"]
        num_channels = 1
        data_size = len(audio_data)
        bytes_per_sample = bits_per_sample // 8
        block_align = num_channels * bytes_per_sample
        byte_rate = sample_rate * block_align
        chunk_size = 36 + data_size
        
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",          # ChunkID
            chunk_size,       # ChunkSize (total file size - 8 bytes)
            b"WAVE",          # Format
            b"fmt ",          # Subchunk1ID
            16,               # Subchunk1Size (16 for PCM)
            1,                # AudioFormat (1 for PCM)
            num_channels,     # NumChannels
            sample_rate,      # SampleRate
            byte_rate,        # ByteRate
            block_align,      # BlockAlign
            bits_per_sample,  # BitsPerSample
            b"data",          # Subchunk2ID
            data_size         # Subchunk2Size (size of audio data)
        )
        return header + audio_data
    
    def _parse_audio_mime_type(self, mime_type: str) -> dict:
        """
        Parse audio MIME type for bits per sample and rate
        
        Args:
            mime_type: Audio MIME type string
        
        Returns:
            Dictionary with bits_per_sample and rate
        """
        bits_per_sample = 16
        rate = 24000
        
        parts = mime_type.split(";")
        for param in parts:
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
                except (ValueError, IndexError):
                    pass
            elif param.startswith("audio/L"):
                try:
                    bits_per_sample = int(param.split("L", 1)[1])
                except (ValueError, IndexError):
                    pass
        
        return {"bits_per_sample": bits_per_sample, "rate": rate}
    
    def save_audio_to_file(self, audio_data: bytes, file_path: str) -> bool:
        """
        Save audio data to a file
        
        Args:
            audio_data: Audio data to save
            file_path: Path to save the file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, "wb") as f:
                f.write(audio_data)
            return True
        except Exception as e:
            print(f"Error saving audio file: {str(e)}")
            return False