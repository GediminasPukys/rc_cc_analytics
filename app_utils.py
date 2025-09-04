"""
Shared utilities for app.py and app_v2.py
Extracted to avoid import conflicts with st.set_page_config()
"""

import streamlit as st
import tempfile
import os
from datetime import timedelta
from src.services.transcription_service import TranscriptionService
from src.models.transcription import TranscriptionResponse
from gemini_service import get_gemini_analyzer

def get_audio_url(_bucket, session_id):
    """Generate signed URL for audio playback"""
    try:
        # First try common audio file names - prioritize WAV files
        common_audio_files = [
            "recording.wav", "audio.wav",  # WAV files first
            "recording.ogg", "audio.ogg",  # OGG files
            "recording.mp3", "audio.mp3"   # MP3 files
        ]
        for filename in common_audio_files:
            blob = _bucket.blob(f"sessions/{session_id}/{filename}")
            if blob.exists():
                # Store the audio format for proper playback
                st.session_state[f"audio_format_{session_id}"] = filename
                # Generate signed URL valid for 1 hour
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(hours=1),
                    method="GET"
                )
                return url
        
        # If no common names found, search for ANY audio file
        blobs = _bucket.list_blobs(prefix=f"sessions/{session_id}/")
        for blob in blobs:
            filename = blob.name.split('/')[-1].lower()
            # Check if it's an audio file by extension
            if filename.endswith(('.wav', '.ogg', '.mp3', '.m4a', '.flac', '.aac', '.wma', '.opus')):
                # Store the original filename for format detection
                original_filename = blob.name.split('/')[-1]
                st.session_state[f"audio_format_{session_id}"] = original_filename
                # Generate signed URL valid for 1 hour
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(hours=1),
                    method="GET"
                )
                return url
                
    except Exception as e:
        st.error(f"Failed to get audio URL: {e}")
    return None

def transcribe_audio_with_diarization(_bucket, session_id, force_regenerate=False):
    """Transcribe audio with speaker diarization
    
    Args:
        _bucket: GCS bucket object
        session_id: Session ID to transcribe
        force_regenerate: If True, regenerate even if cached transcription exists
    """
    
    GEMINI_AVAILABLE = os.getenv("GEMINI_API_KEY") is not None or os.getenv("GOOGLE_API_KEY") is not None
    
    if not GEMINI_AVAILABLE:
        st.error("❌ Gemini API key not configured. Add GEMINI_API_KEY or GOOGLE_API_KEY to .env file")
        return
    
    # Check if transcription already exists in session state (unless forced to regenerate)
    if not force_regenerate and f"transcription_{session_id}" in st.session_state:
        st.info("Using cached transcription. Click 'Generate Transcription' to regenerate.")
        return st.session_state[f"transcription_{session_id}"]
    
    # If force_regenerate, clear the existing cache
    if force_regenerate and f"transcription_{session_id}" in st.session_state:
        del st.session_state[f"transcription_{session_id}"]
        st.info("🔄 Regenerating transcription...")
    
    with st.spinner("🔄 Downloading audio file..."):
        # Download audio to temp file - prioritize WAV files
        audio_blob = None
        audio_filename = None
        
        # First try common audio file names
        common_audio_files = [
            "recording.wav", "audio.wav",  # WAV files first
            "recording.ogg", "audio.ogg",  # OGG files
            "recording.mp3", "audio.mp3"   # MP3 files
        ]
        for filename in common_audio_files:
            blob = _bucket.blob(f"sessions/{session_id}/{filename}")
            if blob.exists():
                audio_blob = blob
                audio_filename = filename
                break
        
        # If not found, search for ANY audio file
        if not audio_blob:
            blobs = _bucket.list_blobs(prefix=f"sessions/{session_id}/")
            for blob in blobs:
                filename = blob.name.split('/')[-1].lower()
                # Check if it's an audio file by extension
                if filename.endswith(('.wav', '.ogg', '.mp3', '.m4a', '.flac', '.aac', '.wma', '.opus')):
                    audio_blob = blob
                    audio_filename = blob.name.split('/')[-1]
                    break
        
        if not audio_blob:
            st.error("No audio file found")
            return None
        
        # Create temp file with the correct extension
        file_extension = "." + audio_filename.split('.')[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            audio_blob.download_to_file(tmp_file)
            temp_audio_path = tmp_file.name
    
    try:
        with st.spinner("🎙️ Transcribing with speaker diarization... This may take a few minutes..."):
            # Initialize transcription service
            transcription_service = TranscriptionService()
            
            # Perform transcription
            transcription = transcription_service.transcribe_audio(temp_audio_path, session_id)
            
            if transcription:
                # Store in session state
                st.session_state[f"transcription_{session_id}"] = transcription
                st.success("✅ Transcription complete!")
                return transcription
            else:
                st.error("❌ Transcription failed")
                return None
                
    except Exception as e:
        st.error(f"❌ Transcription failed: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None
    finally:
        # Clean up temp file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

def analyze_transcription_with_gemini(session_id, force_regenerate=False):
    """
    Analyze transcription for pause compliance and unresolved issues
    
    Args:
        session_id: Session ID to analyze
        force_regenerate: If True, regenerate analysis even if cached
    
    Returns:
        ConversationAnalysisResult or None
    """
    from src.services.analysis_service import ConversationAnalysisService
    from src.models.analysis import ConversationAnalysisResult
    
    GEMINI_AVAILABLE = os.getenv("GEMINI_API_KEY") is not None or os.getenv("GOOGLE_API_KEY") is not None
    
    if not GEMINI_AVAILABLE:
        st.error("❌ Gemini API key not configured. Add GEMINI_API_KEY or GOOGLE_API_KEY to .env file")
        return None
    
    # Check if transcription exists
    transcription_key = f"transcription_{session_id}"
    if transcription_key not in st.session_state:
        st.error("❌ No transcription found. Please generate transcription first.")
        return None
    
    # Check if analysis already exists (unless forced to regenerate)
    analysis_key = f"conversation_analysis_{session_id}"
    if not force_regenerate and analysis_key in st.session_state:
        st.info("Using cached analysis. Click 'Analyze' to regenerate.")
        return st.session_state[analysis_key]
    
    # If force_regenerate, clear existing cache
    if force_regenerate and analysis_key in st.session_state:
        del st.session_state[analysis_key]
        st.info("🔄 Regenerating analysis...")
    
    try:
        with st.spinner("🤖 Analyzing conversation for compliance and resolution issues..."):
            # Get transcription
            transcription = st.session_state[transcription_key]
            
            # Initialize analysis service
            analysis_service = ConversationAnalysisService()
            
            # Perform analysis
            analysis = analysis_service.analyze_transcription(transcription, session_id)
            
            if analysis:
                # Store in session state
                st.session_state[analysis_key] = analysis
                
                # Save to GCS for persistence
                try:
                    import json
                    from google.cloud import storage
                    client = storage.Client()
                    bucket = client.bucket(os.getenv("GCS_BUCKET_NAME", "livekit-logs-rc"))
                    blob = bucket.blob(f"sessions/{session_id}/conversation_analysis.json")
                    analysis_json = json.dumps(analysis.model_dump(), indent=2, default=str)
                    blob.upload_from_string(analysis_json, content_type='application/json')
                    st.success("✅ Analysis complete and saved!")
                except Exception as e:
                    st.warning(f"Analysis complete but couldn't save to GCS: {e}")
                    st.success("✅ Analysis complete!")
                
                return analysis
            else:
                st.error("❌ Analysis failed")
                return None
                
    except Exception as e:
        st.error(f"❌ Analysis failed: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None


def analyze_audio_with_gemini(_bucket, session_id):
    """DEPRECATED: Use analyze_transcription_with_gemini instead"""
    st.warning("⚠️ This function is deprecated. Using new analysis method.")
    return analyze_transcription_with_gemini(session_id, force_regenerate=True)
    
    with st.spinner("🔄 Downloading audio file..."):
        # Download audio to temp file - prioritize WAV files
        audio_blob = None
        audio_filename = None
        
        # First try common audio file names
        common_audio_files = [
            "recording.wav", "audio.wav",  # WAV files first
            "recording.ogg", "audio.ogg",  # OGG files
            "recording.mp3", "audio.mp3"   # MP3 files
        ]
        for filename in common_audio_files:
            blob = _bucket.blob(f"sessions/{session_id}/{filename}")
            if blob.exists():
                audio_blob = blob
                audio_filename = filename
                break
        
        # If not found, search for ANY audio file
        if not audio_blob:
            blobs = _bucket.list_blobs(prefix=f"sessions/{session_id}/")
            for blob in blobs:
                filename = blob.name.split('/')[-1].lower()
                # Check if it's an audio file by extension
                if filename.endswith(('.wav', '.ogg', '.mp3', '.m4a', '.flac', '.aac', '.wma', '.opus')):
                    audio_blob = blob
                    audio_filename = blob.name.split('/')[-1]
                    break
        
        if not audio_blob:
            st.error("No audio file found")
            return
        
        # Create temp file with the correct extension
        file_extension = "." + audio_filename.split('.')[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            audio_blob.download_to_file(tmp_file)
            temp_audio_path = tmp_file.name
    
    try:
        with st.spinner("🤖 Analyzing with Gemini 2.5 Pro... This may take a few minutes..."):
            # Get analyzer
            analyzer = get_gemini_analyzer()
            
            # Perform analysis
            analysis = analyzer.analyze_audio(temp_audio_path, session_id)
            
            # Store in session state
            st.session_state[f"analysis_{session_id}"] = analysis
            
            st.success("✅ Analysis complete!")
            
            return analysis
            
    except Exception as e:
        st.error(f"❌ Analysis failed: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
    finally:
        # Clean up temp file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

def create_speaker_timeline_html(transcription: TranscriptionResponse) -> str:
    """Create HTML visualization of speaker timeline"""
    
    # Define colors for different speakers
    speaker_colors = {
        "speaker1": "#4CAF50",  # Green
        "speaker2": "#2196F3",  # Blue
        "speaker3": "#FF9800",  # Orange
        "speaker4": "#9C27B0",  # Purple
        "speaker5": "#F44336",  # Red
        "silence": "#E0E0E0"    # Gray
    }
    
    # Calculate timeline width
    total_duration = transcription.total_duration
    width_scale = 800  # Total width in pixels
    
    # Start with a container div
    html_parts = []
    html_parts.append('<div style="position: relative; width: 100%; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; overflow-x: auto;">')
    html_parts.append(f'<div style="position: relative; height: 60px; width: {width_scale}px; margin: 10px;">')
    
    # Add speaker segments
    for segment in transcription.transcription:
        start_pos = (segment.timestamp_start / total_duration) * width_scale
        width = ((segment.timestamp_end - segment.timestamp_start) / total_duration) * width_scale
        color = speaker_colors.get(segment.speaker_label, "#888888")
        
        # Skip very small segments for visual clarity
        if width < 2:
            width = 2
        
        label = segment.speaker_label.upper() if segment.speaker_label != "silence" else ""
        tooltip = f"{segment.speaker_label}: {segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s"
        if segment.speaker_label != "silence" and hasattr(segment, 'text'):
            # Escape HTML in tooltip text
            text_preview = segment.text[:50].replace('"', '&quot;').replace("'", '&#39;')
            tooltip += f" - {text_preview}..."
        
        segment_html = (
            f'<div style="position: absolute; left: {start_pos:.1f}px; width: {width:.1f}px; height: 40px; '
            f'background: {color}; border: 1px solid white; cursor: pointer; '
            f'display: flex; align-items: center; justify-content: center; '
            f'font-size: 10px; color: white; overflow: hidden;" '
            f'title="{tooltip}">'
            f'{label if width > 30 else ""}'
            f'</div>'
        )
        html_parts.append(segment_html)
    
    # Add time markers
    for i in range(0, int(total_duration) + 1, max(1, int(total_duration) // 10)):
        pos = (i / total_duration) * width_scale
        time_marker = (
            f'<div style="position: absolute; left: {pos:.1f}px; bottom: -20px; '
            f'font-size: 10px; color: #666;">'
            f'{i}s'
            f'</div>'
        )
        html_parts.append(time_marker)
    
    html_parts.append('</div>')
    html_parts.append('<div style="padding: 5px 10px; font-size: 12px; display: flex; flex-wrap: wrap; gap: 15px;">')
    
    # Add legend for each speaker that appears in the transcription
    speakers_in_transcript = set(seg.speaker_label for seg in transcription.transcription)
    
    for speaker in sorted(speakers_in_transcript):
        if speaker in speaker_colors:
            color = speaker_colors[speaker]
            label = speaker.upper() if speaker != "silence" else "Silence"
            legend_item = (
                f'<span style="display: flex; align-items: center;">'
                f'<span style="display: inline-block; width: 12px; height: 12px; '
                f'background: {color}; margin-right: 5px; border-radius: 2px;"></span>'
                f'{label}'
                f'</span>'
            )
            html_parts.append(legend_item)
    
    html_parts.append('</div>')
    html_parts.append('</div>')
    
    return ''.join(html_parts)