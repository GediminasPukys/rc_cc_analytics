"""
Simple GCS Call Logs Viewer
Reads and displays call session data from Google Cloud Storage
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import tempfile
from google.cloud import storage
from google.oauth2 import service_account
import base64
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Gemini service if API key is available
try:
    from gemini_service import get_gemini_analyzer
    from models import ComprehensiveCallAnalysis
    from src.services.transcription_service import TranscriptionService
    from src.models.transcription import TranscriptionResponse
    GEMINI_AVAILABLE = os.getenv("GEMINI_API_KEY") is not None or os.getenv("GOOGLE_API_KEY") is not None
except Exception as e:
    GEMINI_AVAILABLE = False
    print(f"Gemini service not available: {e}")

st.set_page_config(
    page_title="GCS Call Logs Viewer", 
    page_icon="📞",
    layout="wide"
)

# GCS Configuration
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "livekit-logs-rc")
CREDENTIALS_PATH = os.getenv("GCP_CREDENTIALS_PATH")

@st.cache_resource
def init_gcs_client():
    """Initialize GCS client with credentials"""
    try:
        if CREDENTIALS_PATH and os.path.exists(CREDENTIALS_PATH):
            credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
            client = storage.Client(credentials=credentials)
        else:
            # Try default credentials
            client = storage.Client()
        
        bucket = client.bucket(BUCKET_NAME)
        return client, bucket
    except Exception as e:
        st.error(f"Failed to connect to GCS: {e}")
        return None, None

@st.cache_data(ttl=60)
def list_sessions(_bucket, prefix="sessions/", limit=100):
    """List all sessions in GCS bucket"""
    try:
        blobs = _bucket.list_blobs(prefix=prefix, delimiter="/")
        
        sessions = []
        # Get subdirectories (sessions)
        for page in blobs.pages:
            for prefix in page.prefixes:
                session_id = prefix.replace("sessions/", "").rstrip("/")
                if session_id:
                    sessions.append(session_id)
        
        return sessions[:limit]
    except Exception as e:
        st.error(f"Failed to list sessions: {e}")
        return []

def get_session_metadata(_bucket, session_id):
    """Get session metadata from GCS"""
    try:
        # Try to get session.json
        blob = _bucket.blob(f"sessions/{session_id}/session.json")
        if blob.exists():
            content = blob.download_as_text()
            return json.loads(content)
    except:
        pass
    
    # Try metadata.json as fallback
    try:
        blob = _bucket.blob(f"sessions/{session_id}/metadata.json")
        if blob.exists():
            content = blob.download_as_text()
            return json.loads(content)
    except:
        pass
    
    return None

def get_session_events(_bucket, session_id):
    """Get session events from GCS"""
    try:
        blob = _bucket.blob(f"sessions/{session_id}/session_events.jsonl")
        if blob.exists():
            content = blob.download_as_text()
            events = []
            for line in content.strip().split('\n'):
                if line:
                    events.append(json.loads(line))
            return events
    except Exception as e:
        st.error(f"Failed to load events: {e}")
    return []

def get_session_transcript(_bucket, session_id):
    """Get session transcript from GCS"""
    try:
        # Try to get transcript.json first
        blob = _bucket.blob(f"sessions/{session_id}/transcript.json")
        if blob.exists():
            content = blob.download_as_text()
            return json.loads(content)
    except:
        pass
    
    # Try transcript.txt as fallback
    try:
        blob = _bucket.blob(f"sessions/{session_id}/transcript.txt")
        if blob.exists():
            return blob.download_as_text()
    except:
        pass
    
    return None

def get_audio_url(_bucket, session_id):
    """Generate signed URL for audio playback"""
    try:
        # Try different audio file names - prioritize WAV files
        audio_files = [
            "recording.wav", "audio.wav",  # WAV files first
            "recording.ogg", "audio.ogg",  # OGG files
            "recording.mp3", "audio.mp3"   # MP3 files
        ]
        for filename in audio_files:
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
    except Exception as e:
        st.error(f"Failed to get audio URL: {e}")
    return None

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

def create_clickable_transcript(transcription: TranscriptionResponse) -> str:
    """Create transcript with clickable timestamps"""
    
    html = """
    <style>
        .transcript-segment {
            padding: 10px;
            margin: 5px 0;
            border-left: 3px solid #ddd;
            background: #f9f9f9;
            transition: all 0.3s;
        }
        .transcript-segment:hover {
            background: #e8f4f8;
            border-left-color: #2196F3;
        }
        .timestamp-link {
            color: #2196F3;
            cursor: pointer;
            font-weight: bold;
            text-decoration: none;
        }
        .timestamp-link:hover {
            text-decoration: underline;
        }
        .speaker-label {
            font-weight: bold;
            text-transform: uppercase;
            margin-right: 10px;
        }
        .speaker1 { color: #4CAF50; }
        .speaker2 { color: #2196F3; }
        .speaker3 { color: #FF9800; }
        .speaker4 { color: #9C27B0; }
        .speaker5 { color: #F44336; }
    </style>
    <div style="max-height: 500px; overflow-y: auto; padding: 10px;">
    """
    
    for segment in transcription.transcription:
        if segment.speaker_label != "silence":
            speaker_class = segment.speaker_label.replace(" ", "")
            timestamp = f"[{segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s]"
            
            html += f"""
            <div class="transcript-segment">
                <span class="timestamp-link">{timestamp}</span>
                <span class="speaker-label {speaker_class}">{segment.speaker_label}:</span>
                <span>{segment.text}</span>
            </div>
            """
        else:
            duration = segment.timestamp_end - segment.timestamp_start
            if duration > 2:  # Only show significant silences
                html += f"""
                <div style="text-align: center; color: #999; font-style: italic; margin: 10px 0;">
                    — Silence ({duration:.1f}s) —
                </div>
                """
    
    html += "</div>"
    
    return html

def transcribe_audio_with_diarization(_bucket, session_id, force_regenerate=False):
    """Transcribe audio with speaker diarization - wrapper for app_utils function"""
    from app_utils import transcribe_audio_with_diarization as _transcribe
    return _transcribe(_bucket, session_id, force_regenerate)

def analyze_audio_with_gemini(_bucket, session_id):
    """Analyze audio with Gemini 2.5 Pro"""
    
    if not GEMINI_AVAILABLE:
        st.error("❌ Gemini API key not configured. Add GEMINI_API_KEY to .env file")
        return
    
    with st.spinner("🔄 Downloading audio file..."):
        # Download audio to temp file - prioritize WAV files
        audio_blob = None
        audio_filename = None
        audio_files = [
            "recording.wav", "audio.wav",  # WAV files first
            "recording.ogg", "audio.ogg",  # OGG files
            "recording.mp3", "audio.mp3"   # MP3 files
        ]
        for filename in audio_files:
            blob = _bucket.blob(f"sessions/{session_id}/{filename}")
            if blob.exists():
                audio_blob = blob
                audio_filename = filename
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
            
            # Display results in tabs
            display_analysis_results(analysis)
            
            # Save analysis to GCS
            save_analysis_to_gcs(_bucket, session_id, analysis)
            
    except Exception as e:
        st.error(f"❌ Analysis failed: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
    finally:
        # Clean up temp file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

def display_analysis_results(analysis: ComprehensiveCallAnalysis):
    """Display comprehensive analysis results"""
    
    st.markdown("---")
    st.subheader("📊 Gemini 2.5 Pro Analysis Results")
    
    # Create tabs for different analysis sections
    tabs = st.tabs([
        "📝 Transcription",
        "🌐 Translation",
        "😊 Emotional",
        "📋 Structure",
        "😃 Satisfaction",
        "🎩 Politeness",
        "✅ Resolution",
        "⏸️ Pauses",
        "📄 Summary",
        "🏷️ Categories",
        "📈 Overall"
    ])
    
    with tabs[0]:  # Transcription
        st.markdown("### Original Transcription")
        
        # Check if we have a new diarized transcription
        transcription_key = f"transcription_{analysis.session_id}"
        if transcription_key in st.session_state:
            # Display new diarized transcription
            transcription: TranscriptionResponse = st.session_state[transcription_key]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**Duration:** {transcription.total_duration:.1f} seconds")
            with col2:
                st.info(f"**Speakers:** {transcription.num_speakers}")
            with col3:
                st.info(f"**Segments:** {len(transcription.transcription)}")
            
            # Get speaker statistics
            transcription_service = TranscriptionService()
            speaker_stats = transcription_service.get_speaker_statistics(transcription)
            
            # Display speaker statistics
            if speaker_stats:
                st.markdown("#### Speaker Statistics")
                stats_df = pd.DataFrame([
                    {
                        "Speaker": speaker.upper(),
                        "Total Time (s)": f"{stats['total_time']:.1f}",
                        "Segments": stats['num_segments'],
                        "Words": stats['words']
                    }
                    for speaker, stats in speaker_stats.items()
                ])
                st.dataframe(stats_df, hide_index=True)
            
            # Display transcription segments
            st.markdown("#### Conversation")
            for segment in transcription.transcription:
                if segment.speaker_label != "silence":
                    # Choose icon based on speaker
                    if "speaker1" in segment.speaker_label:
                        icon = "👤"
                    elif "speaker2" in segment.speaker_label:
                        icon = "🤖"
                    else:
                        icon = "💬"
                    
                    st.markdown(f"{icon} **{segment.speaker_label.upper()}** ({segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s)")
                    st.write(segment.text)
                else:
                    # Show silence periods
                    duration = segment.timestamp_end - segment.timestamp_start
                    st.markdown(f"⏸️ *[Silence: {duration:.1f}s]*")
        else:
            # Fallback to original transcription from analysis
            st.info(f"**Language:** {analysis.transcription.original_language}")
            st.info(f"**Confidence:** {analysis.transcription.transcription_confidence:.2%}")
            st.info(f"**Duration:** {analysis.transcription.total_duration_seconds:.1f} seconds")
            st.info(f"**Word Count:** {analysis.transcription.word_count}")
            
            # Display segments
            for segment in analysis.transcription.segments:
                icon = "👤" if segment.speaker == "customer" else "🤖"
                st.markdown(f"{icon} **{segment.speaker.upper()}** ({segment.start_time:.1f}s - {segment.end_time:.1f}s)")
                st.write(segment.text)
    
    with tabs[1]:  # Translation
        st.markdown("### Lithuanian Translation")
        st.text_area("Full Translation", analysis.translation.full_translated_text, height=400)
        if analysis.translation.translation_notes:
            st.info(f"Translation Notes: {analysis.translation.translation_notes}")
    
    with tabs[2]:  # Emotional Analysis
        st.markdown("### Emotional Analysis")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Customer Emotions**")
            st.metric("Overall", analysis.emotional_analysis.customer_overall_emotion)
            st.write(analysis.emotional_analysis.customer_emotion_summary)
        
        with col2:
            st.markdown("**Agent Performance**")
            st.metric("Empathy", f"{analysis.emotional_analysis.agent_empathy_score:.0f}/100")
            st.metric("Politeness", f"{analysis.emotional_analysis.agent_politeness_score:.0f}/100")
            st.metric("Respect", f"{analysis.emotional_analysis.agent_respect_score:.0f}/100")
        
        st.metric("Tone Appropriateness", f"{analysis.emotional_analysis.tone_appropriateness_score:.0f}/100")
        
        if analysis.emotional_analysis.tone_mismatches:
            st.warning("⚠️ Tone Mismatches Detected:")
            for mismatch in analysis.emotional_analysis.tone_mismatches:
                st.write(f"- {mismatch}")
    
    with tabs[3]:  # Structure Analysis
        st.markdown("### Conversation Structure")
        st.metric("Compliance Score", f"{analysis.structure_analysis.structure_compliance_score:.0f}/100")
        
        # Show stages
        stage_df = pd.DataFrame([
            {"Stage": stage.stage, "Present": "✅" if stage.present else "❌", 
             "Quality": f"{stage.quality_score:.0f}%" if stage.present else "-"}
            for stage in analysis.structure_analysis.detected_stages
        ])
        st.dataframe(stage_df, hide_index=True)
        
        if analysis.structure_analysis.missing_stages:
            st.warning(f"Missing Stages: {', '.join(analysis.structure_analysis.missing_stages)}")
        
        if analysis.structure_analysis.major_deviations:
            st.error("Major Deviations:")
            for deviation in analysis.structure_analysis.major_deviations:
                st.write(f"- {deviation}")
    
    with tabs[4]:  # Satisfaction
        st.markdown("### Customer Satisfaction")
        st.metric("Satisfaction Level", analysis.satisfaction_analysis.overall_satisfaction)
        st.metric("Satisfaction Score", f"{analysis.satisfaction_analysis.satisfaction_score:.0f}/100")
        st.metric("Trend", analysis.satisfaction_analysis.satisfaction_trend)
        
        col1, col2 = st.columns(2)
        with col1:
            if analysis.satisfaction_analysis.positive_signals:
                st.success("Positive Signals:")
                for signal in analysis.satisfaction_analysis.positive_signals[:5]:
                    st.write(f"- {signal}")
        
        with col2:
            if analysis.satisfaction_analysis.negative_signals:
                st.error("Negative Signals:")
                for signal in analysis.satisfaction_analysis.negative_signals[:5]:
                    st.write(f"- {signal}")
        
        if analysis.satisfaction_analysis.requires_follow_up:
            st.warning(f"⚠️ Follow-up Required: {analysis.satisfaction_analysis.follow_up_reason}")
    
    with tabs[5]:  # Politeness
        st.markdown("### Politeness Analysis")
        st.metric("Politeness Score", f"{analysis.politeness_analysis.politeness_score:.0f}/100")
        st.metric("Cultural Appropriateness", f"{analysis.politeness_analysis.cultural_appropriateness_score:.0f}/100")
        
        # Agent politeness checklist
        st.markdown("**Agent Politeness Elements:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"Greeting: {'✅' if analysis.politeness_analysis.agent_greeting_present else '❌'}")
        with col2:
            st.write(f"Farewell: {'✅' if analysis.politeness_analysis.agent_farewell_present else '❌'}")
        with col3:
            st.write(f"Thanks: {'✅' if analysis.politeness_analysis.agent_thanks_present else '❌'}")
        
        if analysis.politeness_analysis.missing_required_elements:
            st.warning(f"Missing Elements: {', '.join(analysis.politeness_analysis.missing_required_elements)}")
    
    with tabs[6]:  # Resolution
        st.markdown("### Problem Resolution")
        st.info(f"**Problem:** {analysis.resolution_analysis.problem_statement}")
        st.metric("Status", analysis.resolution_analysis.resolution_status)
        st.metric("Category", analysis.resolution_analysis.problem_category)
        
        if analysis.resolution_analysis.requires_escalation:
            st.error(f"⚠️ Requires Escalation: {analysis.resolution_analysis.escalation_reason}")
        
        if analysis.resolution_analysis.supervisor_review_required:
            st.warning(f"👀 Supervisor Review Required (Priority: {analysis.resolution_analysis.review_priority})")
        
        if analysis.resolution_analysis.recommended_next_steps:
            st.markdown("**Recommended Next Steps:**")
            for step in analysis.resolution_analysis.recommended_next_steps:
                st.write(f"- {step}")
    
    with tabs[7]:  # Pauses
        st.markdown("### Pause Analysis")
        st.metric("Total Long Pauses (>60s)", analysis.pause_analysis.total_pauses)
        st.metric("Unannounced Pauses", analysis.pause_analysis.unannounced_long_pauses)
        st.metric("Compliance Score", f"{analysis.pause_analysis.compliance_score:.0f}/100")
        
        if analysis.pause_analysis.long_pauses:
            st.markdown("**Long Pauses Detected:**")
            for pause in analysis.pause_analysis.long_pauses[:5]:
                announced = "✅ Announced" if pause.announced else "❌ Unannounced"
                st.write(f"- {pause.duration_seconds:.0f}s pause at {pause.start_time:.0f}s - {announced}")
    
    with tabs[8]:  # Summary
        st.markdown("### Conversation Summary (Lithuanian)")
        st.text_area("Santrauka", analysis.summary.summary_lt, height=200)
        
        st.markdown("**Pagrindiniai punktai:**")
        for point in analysis.summary.key_points_lt:
            st.write(f"- {point}")
        
        st.markdown("**Outcome:** " + analysis.summary.outcome)
        
        if analysis.summary.follow_up_required:
            st.warning("Follow-up Actions:")
            for action in analysis.summary.follow_up_actions:
                st.write(f"- {action}")
    
    with tabs[9]:  # Categories
        st.markdown("### Categorization")
        st.info(f"**Primary Category:** {analysis.categorization.primary_category}")
        st.info(f"**Customer Type:** {analysis.categorization.customer_type}")
        st.info(f"**Urgency:** {analysis.categorization.urgency_level}")
        
        if analysis.categorization.tags:
            st.markdown("**Tags:** " + ", ".join(analysis.categorization.tags[:10]))
        
        if analysis.categorization.searchable_keywords:
            st.markdown("**Keywords:** " + ", ".join(analysis.categorization.searchable_keywords[:10]))
    
    with tabs[10]:  # Overall
        st.markdown("### Overall Assessment")
        
        # Display overall quality score with color coding
        score = analysis.overall_quality_score
        if score >= 80:
            st.success(f"🎯 Overall Quality Score: {score:.0f}/100")
        elif score >= 60:
            st.warning(f"📊 Overall Quality Score: {score:.0f}/100")
        else:
            st.error(f"⚠️ Overall Quality Score: {score:.0f}/100")
        
        if analysis.critical_issues:
            st.error("🚨 Critical Issues:")
            for issue in analysis.critical_issues:
                st.write(f"- {issue}")
        
        if analysis.top_recommendations:
            st.info("💡 Top Recommendations:")
            for rec in analysis.top_recommendations:
                st.write(f"- {rec}")
        
        # Processing info
        st.markdown("---")
        st.caption(f"Analysis completed in {analysis.processing_duration_ms}ms")
        st.caption(f"Session ID: {analysis.session_id}")
        st.caption(f"Timestamp: {analysis.analysis_timestamp}")

def save_analysis_to_gcs(_bucket, session_id, analysis: ComprehensiveCallAnalysis):
    """Save analysis results to GCS"""
    try:
        # Convert to JSON
        analysis_json = analysis.model_dump_json(indent=2)
        
        # Save to GCS
        blob = _bucket.blob(f"sessions/{session_id}/gemini_analysis.json")
        blob.upload_from_string(analysis_json, content_type='application/json')
        
        st.success(f"💾 Analysis saved to GCS: sessions/{session_id}/gemini_analysis.json")
    except Exception as e:
        st.warning(f"Could not save analysis to GCS: {e}")

def main():
    st.title("📞 GCS Call Logs Viewer")
    st.markdown("---")
    
    # Initialize GCS client
    client, bucket = init_gcs_client()
    
    if not client or not bucket:
        st.error("Failed to initialize GCS client. Please check your credentials.")
        st.stop()
    
    # Sidebar for session list
    with st.sidebar:
        st.header("Sessions")
        
        # Refresh button
        if st.button("🔄 Refresh Sessions"):
            st.cache_data.clear()
        
        # Get sessions list
        sessions = list_sessions(bucket)
        
        if not sessions:
            st.warning("No sessions found in GCS")
            st.stop()
        
        st.info(f"Found {len(sessions)} sessions")
        
        # Session selector
        selected_session = st.selectbox(
            "Select Session",
            sessions,
            format_func=lambda x: f"📞 {x[:20]}..." if len(x) > 20 else f"📞 {x}"
        )
    
    # Main content area
    if selected_session:
        st.header(f"Session: {selected_session}")
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Overview", "📊 Events", "📝 Transcript", "🎧 Audio"])
        
        with tab1:
            st.subheader("Session Overview")
            
            # Get session metadata
            metadata = get_session_metadata(bucket, selected_session)
            
            if metadata:
                # Display metadata in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### Session Info")
                    for key, value in metadata.items():
                        if key not in ['events', 'transcript', 'audio']:
                            if isinstance(value, dict):
                                st.json(value)
                            else:
                                st.write(f"**{key}:** {value}")
                
                with col2:
                    st.markdown("### Files in Session")
                    # List all files in this session
                    session_blobs = bucket.list_blobs(prefix=f"sessions/{selected_session}/")
                    files = []
                    for blob in session_blobs:
                        filename = blob.name.replace(f"sessions/{selected_session}/", "")
                        if filename:
                            size = blob.size / 1024  # Convert to KB
                            files.append({"File": filename, "Size (KB)": f"{size:.2f}"})
                    
                    if files:
                        df = pd.DataFrame(files)
                        st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No metadata found for this session")
                
                # Still show files
                st.markdown("### Files in Session")
                session_blobs = bucket.list_blobs(prefix=f"sessions/{selected_session}/")
                files = []
                for blob in session_blobs:
                    filename = blob.name.replace(f"sessions/{selected_session}/", "")
                    if filename:
                        size = blob.size / 1024
                        files.append({"File": filename, "Size (KB)": f"{size:.2f}"})
                
                if files:
                    df = pd.DataFrame(files)
                    st.dataframe(df, use_container_width=True, hide_index=True)
        
        with tab2:
            st.subheader("Session Events")
            
            events = get_session_events(bucket, selected_session)
            
            if events:
                st.info(f"Found {len(events)} events")
                
                # Display events in expandable format
                for i, event in enumerate(events):
                    event_type = event.get('event_type', 'Unknown')
                    timestamp = event.get('timestamp', '')
                    
                    with st.expander(f"Event {i+1}: {event_type} - {timestamp}"):
                        st.json(event)
            else:
                st.warning("No events found for this session")
        
        with tab3:
            st.subheader("Transcript with Speaker Diarization")
            
            # Add transcription button
            col1, col2 = st.columns(2)
            with col1:
                # Check if transcription exists to change button label
                transcription_key = f"transcription_{selected_session}"
                button_label = "🔄 Regenerate Transcription" if transcription_key in st.session_state else "🎙️ Generate Transcription"
                if st.button(button_label, type="primary"):
                    # Force regenerate when button is clicked
                    transcription = transcribe_audio_with_diarization(bucket, selected_session, force_regenerate=True)
                    if transcription:
                        st.rerun()
            
            with col2:
                # Check if transcription exists in cache
                if transcription_key in st.session_state:
                    st.success("✅ Transcription available")
            
            # Display transcription if available
            if f"transcription_{selected_session}" in st.session_state:
                transcription: TranscriptionResponse = st.session_state[f"transcription_{selected_session}"]
                
                # Add audio player with timeline
                st.markdown("#### 🎵 Audio Player with Speaker Timeline")
                
                # Get audio URL for the player
                audio_url = get_audio_url(bucket, selected_session)
                if audio_url:
                    # Create container for audio player
                    audio_container = st.container()
                    with audio_container:
                        # Determine audio format from the stored filename
                        audio_format = 'audio/wav'  # Default to WAV
                        if f"audio_format_{selected_session}" in st.session_state:
                            filename = st.session_state[f"audio_format_{selected_session}"]
                            if filename.endswith('.ogg'):
                                audio_format = 'audio/ogg'
                            elif filename.endswith('.mp3'):
                                audio_format = 'audio/mpeg'
                            elif filename.endswith('.wav'):
                                audio_format = 'audio/wav'
                        
                        # Display audio player with the correct format
                        audio_element = st.audio(audio_url, format=audio_format)
                        
                        # Create visual timeline of speaker intervals
                        st.markdown("##### Speaker Timeline")
                        
                        # Try to use Plotly for better visualization
                        try:
                            from src.utils.timeline_viz import create_speaker_timeline_plotly
                            fig = create_speaker_timeline_plotly(transcription)
                            st.plotly_chart(fig, use_container_width=True)
                        except ImportError:
                            # Fallback to HTML if Plotly not available
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                timeline_html = create_speaker_timeline_html(transcription)
                                st.markdown(timeline_html, unsafe_allow_html=True)
                            with col2:
                                st.info("🎯 **Timeline Guide:**\n\n"
                                       "• Each block represents a speaker segment\n"
                                       "• Hover over blocks to see details\n"
                                       "• Colors indicate different speakers\n"
                                       "• Gray blocks show silence periods")
                else:
                    st.warning("⚠️ Audio file not found. Generate transcription to see the timeline.")
                
                # Display statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Duration", f"{transcription.total_duration:.1f}s")
                with col2:
                    st.metric("Speakers", transcription.num_speakers)
                with col3:
                    st.metric("Segments", len(transcription.transcription))
                
                # Get speaker statistics
                transcription_service = TranscriptionService()
                speaker_stats = transcription_service.get_speaker_statistics(transcription)
                
                # Display speaker breakdown
                if speaker_stats:
                    st.markdown("#### Speaker Statistics")
                    for speaker, stats in speaker_stats.items():
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.info(f"**{speaker.upper()}**")
                        with col2:
                            st.info(f"Time: {stats['total_time']:.1f}s")
                        with col3:
                            st.info(f"Words: {stats['words']}")
                
                # Display full transcription with clickable timestamps
                st.markdown("#### Full Transcription")
                
                # Check if Lithuanian transcription is available
                has_lithuanian = hasattr(transcription, 'lithuanian_transcription') and transcription.lithuanian_transcription
                
                if has_lithuanian:
                    # Display original language info
                    st.info(f"📝 Original Language: **{transcription.original_language}** | 🇱🇹 Lithuanian translation available")
                
                # Tab selection for different views
                transcript_view = st.radio(
                    "View mode:", 
                    ["Side-by-Side", "Interactive", "Expandable", "Plain Text"] if has_lithuanian else ["Interactive", "Expandable", "Plain Text"], 
                    horizontal=True,
                    key=f"transcript_view_{selected_session}"
                )
                
                if transcript_view == "Side-by-Side" and has_lithuanian:
                    # Side-by-side view with original and Lithuanian
                    col_left, col_right = st.columns(2)
                    
                    with col_left:
                        st.markdown(f"##### 🌍 Original ({transcription.original_language})")
                        # Use native Streamlit components in a container
                        with st.container():
                            for seg in transcription.transcription:
                                if seg.speaker_label != "silence":
                                    # Choose color based on speaker
                                    if "speaker1" in seg.speaker_label:
                                        color = "#4CAF50"
                                    elif "speaker2" in seg.speaker_label:
                                        color = "#2196F3"
                                    else:
                                        color = "#666666"
                                    
                                    # Format timestamp and speaker
                                    col_time, col_speaker = st.columns([2, 5])
                                    with col_time:
                                        st.caption(f"[{seg.timestamp_start:.1f}s - {seg.timestamp_end:.1f}s]")
                                    with col_speaker:
                                        st.markdown(f"<span style='color: {color}; font-weight: bold;'>{seg.speaker_label.upper()}</span>", unsafe_allow_html=True)
                                    st.write(seg.text)
                                    st.divider()
                                else:
                                    duration = seg.timestamp_end - seg.timestamp_start
                                    if duration > 2:
                                        st.caption(f"— Silence ({duration:.1f}s) —")
                    
                    with col_right:
                        st.markdown("##### 🇱🇹 Lithuanian Translation")
                        # Use native Streamlit components in a container
                        with st.container():
                            for seg in transcription.lithuanian_transcription:
                                if seg.speaker_label != "silence":
                                    # Choose color based on speaker
                                    if "speaker1" in seg.speaker_label:
                                        color = "#4CAF50"
                                    elif "speaker2" in seg.speaker_label:
                                        color = "#2196F3"
                                    else:
                                        color = "#666666"
                                    
                                    # Format timestamp and speaker
                                    col_time, col_speaker = st.columns([2, 5])
                                    with col_time:
                                        st.caption(f"[{seg.timestamp_start:.1f}s - {seg.timestamp_end:.1f}s]")
                                    with col_speaker:
                                        st.markdown(f"<span style='color: {color}; font-weight: bold;'>{seg.speaker_label.upper()}</span>", unsafe_allow_html=True)
                                    st.write(seg.text)
                                    st.divider()
                                else:
                                    duration = seg.timestamp_end - seg.timestamp_start
                                    if duration > 2:
                                        st.caption(f"— Tyla ({duration:.1f}s) —")
                    
                    st.info("💡 Tip: Both columns are synchronized by timestamps. Scroll to compare translations.")
                    
                elif transcript_view == "Interactive":
                    # Create interactive transcript using Streamlit components
                    st.markdown("---")
                    for segment in transcription.transcription:
                        if segment.speaker_label != "silence":
                            # Choose color based on speaker
                            if "speaker1" in segment.speaker_label:
                                color = "#4CAF50"
                            elif "speaker2" in segment.speaker_label:
                                color = "#2196F3"
                            elif "speaker3" in segment.speaker_label:
                                color = "#FF9800"
                            elif "speaker4" in segment.speaker_label:
                                color = "#9C27B0"
                            elif "speaker5" in segment.speaker_label:
                                color = "#F44336"
                            else:
                                color = "#666666"
                            
                            # Create columns for timestamp, speaker, and text
                            col1, col2, col3 = st.columns([1, 1, 5])
                            with col1:
                                st.markdown(f"**[{segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s]**")
                            with col2:
                                st.markdown(f"<span style='color: {color}; font-weight: bold;'>{segment.speaker_label.upper()}</span>", unsafe_allow_html=True)
                            with col3:
                                st.write(segment.text)
                        else:
                            # Show silence periods
                            duration = segment.timestamp_end - segment.timestamp_start
                            if duration > 2:  # Only show significant silences
                                st.markdown(f"*— Silence ({duration:.1f}s) —*", unsafe_allow_html=False)
                    st.markdown("---")
                    st.info("💡 Tip: Timestamps are displayed for reference. Audio seeking requires manual navigation in the player above.")
                elif transcript_view == "Expandable":
                    # Expandable view with segments grouped by speaker
                    current_speaker = None
                    segments_group = []
                    
                    for segment in transcription.transcription:
                        if segment.speaker_label != "silence":
                            if current_speaker != segment.speaker_label:
                                # Display previous group if exists
                                if segments_group and current_speaker:
                                    with st.expander(f"{current_speaker.upper()} - {len(segments_group)} segment(s)", expanded=False):
                                        for seg in segments_group:
                                            st.write(f"**[{seg.timestamp_start:.1f}s - {seg.timestamp_end:.1f}s]** {seg.text}")
                                
                                # Start new group
                                current_speaker = segment.speaker_label
                                segments_group = [segment]
                            else:
                                segments_group.append(segment)
                    
                    # Display last group
                    if segments_group and current_speaker:
                        with st.expander(f"{current_speaker.upper()} - {len(segments_group)} segment(s)", expanded=False):
                            for seg in segments_group:
                                st.write(f"**[{seg.timestamp_start:.1f}s - {seg.timestamp_end:.1f}s]** {seg.text}")
                else:
                    # Plain text view
                    if has_lithuanian:
                        # Offer choice between original and Lithuanian
                        text_lang = st.radio(
                            "Select language:",
                            ["Original", "Lithuanian"],
                            horizontal=True,
                            key=f"text_lang_{selected_session}"
                        )
                        use_lithuanian = text_lang == "Lithuanian"
                        formatted_text = transcription_service.get_transcription_text(transcription, use_lithuanian=use_lithuanian)
                        st.text_area(f"Transcription ({text_lang})", formatted_text, height=400)
                    else:
                        formatted_text = transcription_service.get_transcription_text(transcription)
                        st.text_area("Transcription", formatted_text, height=400)
                
                # Download button
                download_data = {
                    "session_id": selected_session,
                    "total_duration": transcription.total_duration,
                    "num_speakers": transcription.num_speakers,
                    "original_language": transcription.original_language if has_lithuanian else "unknown",
                    "transcription": [seg.model_dump() for seg in transcription.transcription]
                }
                
                # Add Lithuanian if available
                if has_lithuanian:
                    download_data["lithuanian_transcription"] = [seg.model_dump() for seg in transcription.lithuanian_transcription]
                content = json.dumps(download_data, indent=2)
                
                st.download_button(
                    label="📥 Download Transcription JSON",
                    data=content,
                    file_name=f"{selected_session}_transcription.json",
                    mime="application/json"
                )
            else:
                # Try to get legacy transcript
                transcript = get_session_transcript(bucket, selected_session)
                if transcript:
                    st.info("Legacy transcript available (without speaker diarization)")
                    if isinstance(transcript, dict):
                        st.json(transcript)
                        content = json.dumps(transcript, indent=2)
                        mime = "application/json"
                        ext = "json"
                    else:
                        st.text_area("Transcript", transcript, height=400)
                        content = transcript
                        mime = "text/plain"
                        ext = "txt"
                    
                    st.download_button(
                        label="📥 Download Legacy Transcript",
                        data=content,
                        file_name=f"{selected_session}_transcript.{ext}",
                        mime=mime
                    )
                else:
                    st.warning("No transcript found. Click 'Generate Transcription with Diarization' to create one.")
        
        with tab4:
            st.subheader("Audio Recording")
            
            audio_url = get_audio_url(bucket, selected_session)
            
            if audio_url:
                # Determine audio format from the stored filename
                audio_format = 'audio/wav'  # Default to WAV
                if f"audio_format_{selected_session}" in st.session_state:
                    filename = st.session_state[f"audio_format_{selected_session}"]
                    if filename.endswith('.ogg'):
                        audio_format = 'audio/ogg'
                    elif filename.endswith('.mp3'):
                        audio_format = 'audio/mpeg'
                    elif filename.endswith('.wav'):
                        audio_format = 'audio/wav'
                    format_name = filename.split('.')[-1].upper()
                else:
                    format_name = "AUDIO"
                
                st.audio(audio_url, format=audio_format)
                st.success(f"✅ {format_name} file found and ready to play")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Provide download link
                    st.markdown(f"[📥 Download Audio]({audio_url})")
                
                with col2:
                    # Gemini Analysis button
                    if st.button("🤖 Analyze with Gemini 2.5 Pro", key=f"analyze_{selected_session}", type="primary"):
                        analyze_audio_with_gemini(bucket, selected_session)
            else:
                st.warning("No audio recording found for this session")
                st.info("Supported formats: WAV, OGG, MP3 | Checked files: recording.wav, audio.wav, recording.ogg, audio.ogg, recording.mp3, audio.mp3")

if __name__ == "__main__":
    main()