"""
GCS Call Logs Viewer v2.0 - Master Table with Drill-Down Navigation
Enhanced navigation with session overview table and detailed view
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

# Import services
try:
    from gemini_service import get_gemini_analyzer
    from models import ComprehensiveCallAnalysis
    from src.services.transcription_service import TranscriptionService
    from src.models.transcription import TranscriptionResponse
    GEMINI_AVAILABLE = "GEMINI_API_KEY" in st.secrets["gcs"] if "gcs" in st.secrets else False
except Exception as e:
    GEMINI_AVAILABLE = False
    print(f"Gemini service not available: {e}")

st.set_page_config(
    page_title="Call Analytics Platform v2.0", 
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# GCS Configuration from Streamlit secrets
BUCKET_NAME = st.secrets["gcs"]["GCS_BUCKET_NAME"] if "gcs" in st.secrets else "livekit-logs-rc"
GOOGLE_CLOUD_PROJECT = st.secrets["gcs"]["GOOGLE_CLOUD_PROJECT"] if "gcs" in st.secrets else "voting-2024"

# Initialize session state
if 'selected_session' not in st.session_state:
    st.session_state.selected_session = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'table'  # 'table' or 'details'

@st.cache_resource
def init_gcs_client():
    """Initialize GCS client with credentials from Streamlit secrets"""
    try:
        # Always use service account credentials from secrets
        if "gcp_service_account" not in st.secrets:
            st.error("❌ GCP service account credentials not found in secrets. Please configure them in .streamlit/secrets.toml")
            return None, None
        
        # Create credentials from service account info in secrets
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        client = storage.Client(
            credentials=credentials,
            project=GOOGLE_CLOUD_PROJECT
        )
        
        bucket = client.bucket(BUCKET_NAME)
        return client, bucket
    except Exception as e:
        st.error(f"Failed to initialize GCS client: {e}")
        return None, None

@st.cache_data()  # No TTL - cache persists until manually cleared
def list_all_sessions(_bucket):
    """List all session folders from GCS with metadata - cached until manual refresh"""
    sessions_data = []
    session_ids = set()
    
    try:
        # Method 1: Use delimiter to get all session directories (like app.py)
        # This ensures we get ALL sessions, even empty ones
        blobs = _bucket.list_blobs(prefix="sessions/", delimiter="/")
        
        # Get subdirectories (sessions) from prefixes
        for page in blobs.pages:
            for prefix in page.prefixes:
                session_id = prefix.replace("sessions/", "").rstrip("/")
                if session_id and session_id not in session_ids:
                    session_ids.add(session_id)
                    # Get session metadata
                    session_info = get_session_metadata(_bucket, session_id)
                    sessions_data.append(session_info)
        
        # Method 2: Fallback - also check for any files in sessions/ that might have been missed
        # This catches edge cases where sessions might not appear as directories
        blobs_fallback = _bucket.list_blobs(prefix="sessions/")
        for blob in blobs_fallback:
            # Extract session ID from path like sessions/SESSION_ID/file.json
            parts = blob.name.split('/')
            if len(parts) >= 2 and parts[0] == 'sessions':
                session_id = parts[1]
                if session_id and session_id not in session_ids:
                    session_ids.add(session_id)
                    # Get session metadata
                    session_info = get_session_metadata(_bucket, session_id)
                    sessions_data.append(session_info)
        
        return pd.DataFrame(sessions_data)
    except Exception as e:
        st.error(f"Error listing sessions: {e}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()

def get_session_metadata(_bucket, session_id):
    """Extract metadata for a session"""
    info = {
        'Session ID': session_id,
        'Timestamp': None,
        'Has Audio': False,
        'Has Metadata': False,
        'Has Events': False,
        'Has Transcript': False,
        'Has Analysis': False,
        'Duration': None,
        'Language': None,
        'Status': 'Incomplete',
        'Needs Review': False,
        'Review Priority': None,
        'Review Reasons': []
    }
    
    try:
        # Extract timestamp from session ID if possible
        # Format: 20250822_212315_playground-ONRn-qfMR_500d244a
        if session_id.startswith('2'):  # Likely starts with year
            try:
                # Extract date and time parts
                parts = session_id.split('_')
                if len(parts) >= 2:
                    date_str = parts[0]  # 20250822
                    time_str = parts[1]  # 212315
                    # Convert to datetime
                    datetime_str = f"{date_str}_{time_str}"
                    info['Timestamp'] = pd.to_datetime(datetime_str, format='%Y%m%d_%H%M%S')
            except:
                pass
        
        # Check for different file types
        # First check for specific files
        specific_files = [
            (f"sessions/{session_id}/metadata.json", 'Has Metadata'),
            (f"sessions/{session_id}/events.json", 'Has Events'),
            (f"sessions/{session_id}/transcription.json", 'Has Transcript')
        ]
        
        for file_path, key in specific_files:
            blob = _bucket.blob(file_path)
            if blob.exists():
                info[key] = True
        
        # Check for audio files with various patterns
        audio_patterns = ['recording', 'audio', 'test_audio']
        audio_extensions = ['.wav', '.ogg', '.mp3', '.m4a', '.webm']
        
        # List all files in the session directory
        blobs = _bucket.list_blobs(prefix=f"sessions/{session_id}/")
        for blob in blobs:
            filename = blob.name.split('/')[-1].lower()
            
            # Check if it's an audio file
            for pattern in audio_patterns:
                if pattern in filename:
                    for ext in audio_extensions:
                        if filename.endswith(ext):
                            info['Has Audio'] = True
                            break
                if info['Has Audio']:
                    break
            
            # Also check for any file with audio extension
            if not info['Has Audio']:
                for ext in audio_extensions:
                    if filename.endswith(ext):
                        info['Has Audio'] = True
                        break
            
            # Check for transcript files
            if 'transcript' in filename or filename == 'transcription.json':
                info['Has Transcript'] = True
            
            # Check for analysis files
            if 'analysis' in filename:
                info['Has Analysis'] = True
        
        # Try to get additional metadata
        metadata_blob = _bucket.blob(f"sessions/{session_id}/metadata.json")
        if metadata_blob.exists():
            metadata = json.loads(metadata_blob.download_as_text())
            info['Duration'] = metadata.get('duration')
            info['Language'] = metadata.get('language', metadata.get('original_language'))
        
        # Try to get transcription metadata
        trans_blob = _bucket.blob(f"sessions/{session_id}/transcription.json")
        if trans_blob.exists():
            trans_data = json.loads(trans_blob.download_as_text())
            info['Duration'] = info['Duration'] or trans_data.get('total_duration')
            info['Language'] = info['Language'] or trans_data.get('original_language')
        
        # Check for AI analysis results and review requirements
        analysis_blob = _bucket.blob(f"sessions/{session_id}/conversation_analysis.json")
        if analysis_blob.exists():
            try:
                analysis_data = json.loads(analysis_blob.download_as_text())
                info['Has Analysis'] = True
                info['Needs Review'] = analysis_data.get('requires_review', False)
                info['Review Priority'] = analysis_data.get('review_priority', None)
                info['Review Reasons'] = analysis_data.get('review_reasons', [])
                
                # Debug logging for specific session
                if session_id == "20250904_180344_custom_empathy":
                    print(f"DEBUG: Loading {session_id} from GCS - Review Priority: {info['Review Priority']}")
                
                # Add analysis metrics
                info['Structure Score'] = analysis_data.get('structure_analysis', {}).get('structure_score', None)
                info['Pause Compliance'] = analysis_data.get('pause_compliance_score', None)
                info['Unresolved Issues'] = len(analysis_data.get('unresolved_issues', []))
                info['Politeness Score'] = analysis_data.get('politeness_score', None)
                info['Satisfaction'] = analysis_data.get('final_satisfaction', None)
                
                # Get emotional tone
                tone_eval = analysis_data.get('tone_evaluation', {})
                info['Customer Tone'] = tone_eval.get('customer_tone', None)
                info['Agent Tone'] = tone_eval.get('agent_tone', None)
            except:
                pass
        
        # Also check session state for analysis (in case it's not saved to GCS yet)
        analysis_key = f"conversation_analysis_{session_id}"
        if analysis_key in st.session_state:
            analysis = st.session_state[analysis_key]
            info['Has Analysis'] = True
            info['Needs Review'] = analysis.requires_review
            info['Review Priority'] = analysis.review_priority
            info['Review Reasons'] = analysis.review_reasons
            
            # Add analysis metrics from session state
            if hasattr(analysis, 'structure_analysis'):
                info['Structure Score'] = analysis.structure_analysis.structure_score
            info['Pause Compliance'] = analysis.pause_compliance_score
            info['Unresolved Issues'] = len(analysis.unresolved_issues)
            info['Politeness Score'] = analysis.politeness_score
            info['Satisfaction'] = analysis.final_satisfaction
            info['Customer Tone'] = analysis.tone_evaluation.customer_tone
            info['Agent Tone'] = analysis.tone_evaluation.agent_tone
        
        # Determine status
        if info['Has Audio']:
            if info['Has Transcript'] or info['Has Analysis']:
                info['Status'] = 'Analyzed'
            else:
                info['Status'] = 'Ready'
        
    except Exception as e:
        pass
    
    return info

def display_session_table(df):
    """Display the master session table with interactive features"""
    st.markdown("### 📊 Session Overview")
    
    # Add filters
    st.markdown("#### 🔍 Filters")
    
    # First row of filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_filter = st.multiselect(
            "Status",
            options=['Analyzed', 'Ready', 'Incomplete'],
            default=['Analyzed', 'Ready', 'Incomplete']  # Show all by default
        )
    
    with col2:
        review_priority_filter = st.multiselect(
            "Review Priority",
            options=['urgent', 'high', 'medium', 'low'],
            default=[]
        )
    
    with col3:
        has_filters = st.container()
        with has_filters:
            audio_filter = st.checkbox("Has Audio", value=False)  # Don't filter by default
            transcript_filter = st.checkbox("Has Transcript", value=False)
            analysis_filter = st.checkbox("Has Analysis", value=False)
    
    with col4:
        review_filter = st.checkbox("🚨 Needs Review Only", value=False, help="Show only sessions requiring review")
        
    # Second row for date filter if applicable
    if 'Timestamp' in df.columns and df['Timestamp'].notna().any():
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            date_range = st.date_input(
                "Date Range",
                value=(df['Timestamp'].min(), df['Timestamp'].max()),
                key='date_filter'
            )
        with col2:
            # Language filter
            languages = df['Language'].dropna().unique().tolist()
            if languages:
                language_filter = st.multiselect(
                    "Language",
                    options=languages,
                    default=[]
                )
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
    if audio_filter:  # Only filter if checkbox is checked
        filtered_df = filtered_df[filtered_df['Has Audio'] == True]
    if transcript_filter:  # Only filter if checkbox is checked
        filtered_df = filtered_df[filtered_df['Has Transcript'] == True]
    if review_filter:  # Only filter if checkbox is checked
        filtered_df = filtered_df[filtered_df['Needs Review'] == True]
    
    # Apply review priority filter
    if review_priority_filter:
        filtered_df = filtered_df[filtered_df['Review Priority'].isin(review_priority_filter)]
    
    # Apply analysis filter
    if analysis_filter:
        filtered_df = filtered_df[filtered_df['Has Analysis'] == True]
    
    # Apply language filter
    if 'language_filter' in locals() and language_filter:
        filtered_df = filtered_df[filtered_df['Language'].isin(language_filter)]
    
    # Apply date filter
    if 'date_range' in locals() and date_range and len(date_range) == 2:
        start_date, end_date = date_range
        if start_date and end_date and 'Timestamp' in filtered_df.columns:
            # Convert dates to datetime for comparison
            import pandas as pd
            start_datetime = pd.Timestamp(start_date)
            end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1)  # Include full end day
            filtered_df = filtered_df[
                (filtered_df['Timestamp'] >= start_datetime) & 
                (filtered_df['Timestamp'] < end_datetime)
            ]
    
    # Display metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Sessions", len(filtered_df))
    with col2:
        analyzed = len(filtered_df[filtered_df['Status'] == 'Analyzed'])
        st.metric("Analyzed", analyzed)
    with col3:
        ready = len(filtered_df[filtered_df['Status'] == 'Ready'])
        st.metric("Ready for Analysis", ready)
    with col4:
        with_audio = len(filtered_df[filtered_df['Has Audio'] == True])
        st.metric("With Audio", with_audio)
    with col5:
        needs_review = len(filtered_df[filtered_df['Needs Review'] == True])
        if needs_review > 0:
            st.metric("🚨 Needs Review", needs_review)
        else:
            st.metric("✅ Review Queue", 0)
    
    # Style the dataframe
    def style_status(val):
        if val == 'Analyzed':
            return 'background-color: #90EE90'
        elif val == 'Ready':
            return 'background-color: #FFE4B5'
        else:
            return 'background-color: #FFB6C1'
    
    def style_boolean(val):
        if val == True:
            return 'color: green; font-weight: bold'
        return 'color: gray'
    
    # Create table view options
    st.markdown("### 📋 Sessions Table")
    
    view_type = st.radio(
        "View type:",
        ["Interactive Buttons", "Compact Table"],
        horizontal=True,
        key="table_view_type"
    )
    
    if view_type == "Compact Table":
        # Use regular dataframe display
        st.info("👆 Enter a Session ID in the box below to view details")
        
        # Display compact dataframe with analysis metrics
        # Select columns to display
        columns_to_show = ['Session ID', 'Timestamp']
        
        # Add analysis columns if they exist
        if 'Structure Score' in filtered_df.columns:
            columns_to_show.append('Structure Score')
        if 'Pause Compliance' in filtered_df.columns:
            columns_to_show.append('Pause Compliance')
        if 'Unresolved Issues' in filtered_df.columns:
            columns_to_show.append('Unresolved Issues')
        if 'Politeness Score' in filtered_df.columns:
            columns_to_show.append('Politeness Score')
        if 'Satisfaction' in filtered_df.columns:
            columns_to_show.append('Satisfaction')
        if 'Customer Tone' in filtered_df.columns:
            columns_to_show.append('Customer Tone')
        
        # Always include review status
        columns_to_show.extend(['Needs Review', 'Review Priority'])
        
        # Create display dataframe with available columns
        available_columns = [col for col in columns_to_show if col in filtered_df.columns]
        display_df = filtered_df[available_columns].copy()
        
        # Add visual indicator for review priority
        def format_review_priority(row):
            raw_priority = row.get('Review Priority', 'none')
            needs_review = row.get('Needs Review', False)
            
            if needs_review:
                if raw_priority == 'urgent':
                    return f'🔴 Urgent [{raw_priority}]'
                elif raw_priority == 'high':
                    return f'🟠 High [{raw_priority}]'
                elif raw_priority == 'medium':
                    return f'🟡 Medium [{raw_priority}]'
                elif raw_priority == 'low':
                    return f'🟢 Low [{raw_priority}]'
                else:
                    # Show raw value if not matching expected values
                    return f'❓ Unknown [{raw_priority}]'
            return f'🟢 OK [none]'
        
        display_df['Review Status'] = display_df.apply(format_review_priority, axis=1)
        
        # Format satisfaction for better display
        if 'Satisfaction' in display_df.columns:
            def format_satisfaction(val):
                if pd.isna(val):
                    return '-'
                elif 'satisfied' in str(val).lower():
                    if 'very' in str(val).lower() and 'dis' not in str(val).lower():
                        return '😊 Very Satisfied'
                    elif 'dis' in str(val).lower():
                        if 'very' in str(val).lower():
                            return '😠 Very Dissatisfied'
                        return '😞 Dissatisfied'
                    return '😊 Satisfied'
                elif 'neutral' in str(val).lower():
                    return '😐 Neutral'
                return str(val)
            display_df['Satisfaction'] = display_df['Satisfaction'].apply(format_satisfaction)
        
        # Remove the separate Needs Review and Review Priority columns
        display_columns = [col for col in display_df.columns if col not in ['Needs Review', 'Review Priority']]
        display_df = display_df[display_columns]
        
        # Configure column display
        column_config = {
            "Session ID": st.column_config.TextColumn("Session ID", width="medium"),
            "Timestamp": st.column_config.DatetimeColumn("Date", format="DD/MM HH:mm"),
            "Structure Score": st.column_config.NumberColumn("Structure", format="%.0f%%"),
            "Pause Compliance": st.column_config.NumberColumn("Pause Compl.", format="%.0f%%"),
            "Unresolved Issues": st.column_config.NumberColumn("Unresolved", format="%d"),
            "Politeness Score": st.column_config.NumberColumn("Politeness", format="%.0f%%"),
            "Satisfaction": st.column_config.TextColumn("Satisfaction", width="small"),
            "Customer Tone": st.column_config.TextColumn("Customer Tone", width="small"),
            "Review Status": st.column_config.TextColumn("Review", width="small"),
        }
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        # Session selector
        selected = st.selectbox(
            "Select a session to view details:",
            options=[""] + filtered_df['Session ID'].tolist(),
            key="session_selector"
        )
        
        if selected:
            st.session_state.selected_session = selected
            st.session_state.view_mode = 'details'
            st.rerun()
    
    else:
        # Interactive button view
        st.info("👆 Click on a session ID to view details")
        
        # Add column headers for analysis metrics
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([3, 2, 1, 1, 1, 1, 2, 1])
        with col1:
            st.markdown("**Session ID**")
        with col2:
            st.markdown("**Date**")
        with col3:
            st.markdown("**Structure**")
        with col4:
            st.markdown("**Pause**")
        with col5:
            st.markdown("**Unresolved**")
        with col6:
            st.markdown("**Politeness**")
        with col7:
            st.markdown("**Satisfaction**")
        with col8:
            st.markdown("**Review**")
        
        st.markdown("---")
        
        # Display the dataframe with action buttons
        for idx, row in filtered_df.iterrows():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([3, 2, 1, 1, 1, 1, 2, 1])
            
            with col1:
                if st.button(f"📂 {row['Session ID'][:30]}...", key=f"btn_{idx}", use_container_width=True):
                    st.session_state.selected_session = row['Session ID']
                    st.session_state.view_mode = 'details'
                    st.rerun()
            
            with col2:
                if pd.notna(row['Timestamp']):
                    st.text(row['Timestamp'].strftime("%m/%d %H:%M"))
                else:
                    st.text("—")
            
            with col3:
                # Structure Score
                if 'Structure Score' in row and pd.notna(row['Structure Score']):
                    score = row['Structure Score']
                    if score >= 80:
                        st.success(f"{score:.0f}%")
                    elif score >= 60:
                        st.warning(f"{score:.0f}%")
                    else:
                        st.error(f"{score:.0f}%")
                else:
                    st.text("—")
            
            with col4:
                # Pause Compliance
                if 'Pause Compliance' in row and pd.notna(row['Pause Compliance']):
                    score = row['Pause Compliance']
                    if score >= 90:
                        st.success(f"{score:.0f}%")
                    elif score >= 70:
                        st.warning(f"{score:.0f}%")
                    else:
                        st.error(f"{score:.0f}%")
                else:
                    st.text("—")
            
            with col5:
                # Unresolved Issues
                if 'Unresolved Issues' in row and pd.notna(row['Unresolved Issues']):
                    count = row['Unresolved Issues']
                    if count == 0:
                        st.success("0")
                    elif count <= 2:
                        st.warning(str(count))
                    else:
                        st.error(str(count))
                else:
                    st.text("—")
            
            with col6:
                # Politeness Score
                if 'Politeness Score' in row and pd.notna(row['Politeness Score']):
                    score = row['Politeness Score']
                    if score >= 80:
                        st.success(f"{score:.0f}%")
                    elif score >= 60:
                        st.warning(f"{score:.0f}%")
                    else:
                        st.error(f"{score:.0f}%")
                else:
                    st.text("—")
            
            with col7:
                # Satisfaction
                if 'Satisfaction' in row and pd.notna(row['Satisfaction']):
                    sat = str(row['Satisfaction']).lower()
                    if 'very_satisfied' in sat or 'satisfied' in sat and 'dis' not in sat:
                        if 'very' in sat:
                            st.success("😊 Very Satisfied")
                        else:
                            st.success("😊 Satisfied")
                    elif 'neutral' in sat:
                        st.warning("😐 Neutral")
                    elif 'dissatisfied' in sat:
                        if 'very' in sat:
                            st.error("😠 Very Dissatisfied")
                        else:
                            st.error("😞 Dissatisfied")
                    else:
                        st.text(row['Satisfaction'][:15])
                else:
                    st.text("—")
            
            with col8:
                # Show review status with priority
                if 'Needs Review' in row and row['Needs Review']:
                    priority = row.get('Review Priority', 'low')
                    if priority == 'urgent':
                        st.error("🔴")
                    elif priority == 'high':
                        st.warning("🟠")
                    elif priority == 'medium':
                        st.warning("🟡")
                    else:
                        st.info("🟢")
                else:
                    st.info("🟢")
    
    return filtered_df

def display_session_details(bucket, session_id):
    """Display detailed view for a selected session"""
    
    # Header with navigation
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"## 📞 Session Details: `{session_id}`")
    with col2:
        if st.button("← Back to Table", type="secondary"):
            st.session_state.view_mode = 'table'
            st.session_state.selected_session = None
            st.rerun()
    
    # Import all the functions from original app
    from app_utils import (
        get_audio_url,
        transcribe_audio_with_diarization,
        analyze_audio_with_gemini,
        create_speaker_timeline_html
    )
    
    # Get session metadata
    session_info = get_session_metadata(bucket, session_id)
    
    # Display session info cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info(f"**Status:** {session_info['Status']}")
    with col2:
        if session_info['Duration']:
            st.info(f"**Duration:** {session_info['Duration']:.1f}s")
        else:
            st.info("**Duration:** Unknown")
    with col3:
        st.info(f"**Language:** {session_info['Language'] or 'Unknown'}")
    with col4:
        timestamp = session_info['Timestamp']
        if timestamp:
            st.info(f"**Date:** {timestamp.strftime('%Y-%m-%d')}")
        else:
            st.info("**Date:** Unknown")
    
    # Create tabs for different features
    tabs = st.tabs([
        "🎙️ Transcription & Translation",
        "🎵 Audio Player",
        "🤖 AI Analysis",
        "📊 Metadata",
        "📄 Raw Data"
    ])
    
    # Transcription Tab
    with tabs[0]:
        display_transcription_tab(bucket, session_id)
    
    # Audio Tab  
    with tabs[1]:
        display_audio_tab(bucket, session_id)
    
    # AI Analysis Tab
    with tabs[2]:
        display_analysis_tab(bucket, session_id)
    
    # Metadata Tab
    with tabs[3]:
        display_metadata_tab(bucket, session_id)
    
    # Raw Data Tab
    with tabs[4]:
        display_raw_data_tab(bucket, session_id)

def display_transcription_tab(bucket, session_id):
    """Display transcription with all features from v1"""
    import json
    from app_utils import transcribe_audio_with_diarization, get_audio_url, create_speaker_timeline_html
    from src.services.transcription_service import TranscriptionService
    from src.models.transcription import TranscriptionResponse
    
    st.markdown("### 🎙️ Transcription with Speaker Diarization")
    
    # Check if transcription exists
    transcription_key = f"transcription_{session_id}"
    
    # Try to load existing transcription from GCS if not in session state
    if transcription_key not in st.session_state:
        transcription_blob = bucket.blob(f"sessions/{session_id}/transcription.json")
        if transcription_blob.exists():
            try:
                trans_data = json.loads(transcription_blob.download_as_text())
                st.session_state[transcription_key] = TranscriptionResponse(**trans_data)
            except Exception as e:
                st.warning(f"Could not load existing transcription: {e}")
    
    # Transcription controls
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        # Button always forces regeneration when clicked
        button_label = "🔄 Regenerate Transcription" if transcription_key in st.session_state else "🔄 Generate Transcription"
        if st.button(button_label, type="primary", disabled=not GEMINI_AVAILABLE):
            # Force regenerate when button is clicked
            transcription = transcribe_audio_with_diarization(bucket, session_id, force_regenerate=True)
            if transcription:
                st.success("✅ Transcription completed!")
                st.rerun()
    
    with col2:
        if transcription_key in st.session_state:
            st.success("✅ Transcription available")
    
    with col3:
        if not GEMINI_AVAILABLE:
            st.warning("⚠️ Gemini API not configured")
    
    # Display transcription if available
    if transcription_key in st.session_state:
        transcription: TranscriptionResponse = st.session_state[transcription_key]
        
        # Add audio player with timeline
        st.markdown("#### 🎵 Audio Player with Speaker Timeline")
        
        # Get audio URL for the player
        audio_url = get_audio_url(bucket, session_id)
        if audio_url:
            # Create container for audio player
            audio_container = st.container()
            with audio_container:
                # Determine audio format from the stored filename
                audio_format = 'audio/wav'  # Default to WAV
                if f"audio_format_{session_id}" in st.session_state:
                    filename = st.session_state[f"audio_format_{session_id}"]
                    if filename.endswith('.ogg'):
                        audio_format = 'audio/ogg'
                    elif filename.endswith('.mp3'):
                        audio_format = 'audio/mpeg'
                    elif filename.endswith('.wav'):
                        audio_format = 'audio/wav'
                
                # Display audio player with the correct format
                st.audio(audio_url, format=audio_format)
                
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
        
        # Display full transcription with different views
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
            key=f"transcript_view_{session_id}"
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
                    key=f"text_lang_{session_id}"
                )
                use_lithuanian = text_lang == "Lithuanian"
                formatted_text = transcription_service.get_transcription_text(transcription, use_lithuanian=use_lithuanian)
                st.text_area(f"Transcription ({text_lang})", formatted_text, height=400)
            else:
                formatted_text = transcription_service.get_transcription_text(transcription)
                st.text_area("Transcription", formatted_text, height=400)
        
        # Download button
        download_data = {
            "session_id": session_id,
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
            file_name=f"{session_id}_transcription.json",
            mime="application/json"
        )

def display_audio_tab(bucket, session_id):
    """Display audio player and controls"""
    from app_utils import get_audio_url
    
    st.markdown("### 🎵 Audio Recording")
    
    audio_url = get_audio_url(bucket, session_id)
    
    if audio_url:
        # Determine audio format
        audio_format = 'audio/wav'  # Default
        if f"audio_format_{session_id}" in st.session_state:
            filename = st.session_state[f"audio_format_{session_id}"]
            if filename.endswith('.ogg'):
                audio_format = 'audio/ogg'
            elif filename.endswith('.mp3'):
                audio_format = 'audio/mpeg'
        
        st.audio(audio_url, format=audio_format)
        
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ Audio file found and ready")
        with col2:
            st.download_button(
                label="📥 Download Audio",
                data=audio_url,
                file_name=f"{session_id}_audio.{audio_format.split('/')[-1]}",
                mime=audio_format
            )
    else:
        st.warning("No audio file found for this session")
        
        # Audio upload section
        st.markdown("#### Upload Audio File")
        uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=['wav', 'mp3', 'ogg', 'm4a', 'flac', 'aac', 'wma', 'opus'],
            help="Upload an audio file for this session"
        )
        
        if uploaded_file is not None:
            # Show file details
            st.info(f"Selected file: **{uploaded_file.name}** ({uploaded_file.size / (1024*1024):.2f} MB)")
            
            if st.button("📤 Upload Audio", type="primary"):
                try:
                    with st.spinner("Uploading audio file..."):
                        # Determine the appropriate filename
                        file_extension = uploaded_file.name.split('.')[-1].lower()
                        
                        # Use standard naming convention
                        if file_extension == 'wav':
                            audio_filename = "recording.wav"
                        elif file_extension == 'ogg':
                            audio_filename = "recording.ogg"
                        elif file_extension == 'mp3':
                            audio_filename = "recording.mp3"
                        else:
                            # Keep original filename for other formats
                            audio_filename = f"recording.{file_extension}"
                        
                        # Upload to GCS
                        blob = bucket.blob(f"sessions/{session_id}/{audio_filename}")
                        blob.upload_from_string(
                            uploaded_file.read(),
                            content_type=f"audio/{file_extension}"
                        )
                        
                        st.success(f"✅ Audio file uploaded successfully as {audio_filename}")
                        
                        # Clear cache to reflect the change
                        if f"audio_format_{session_id}" in st.session_state:
                            del st.session_state[f"audio_format_{session_id}"]
                        
                        # Rerun to refresh the page
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Failed to upload audio: {e}")

def display_analysis_tab(bucket, session_id):
    """Display AI analysis results"""
    import json
    from app_utils import analyze_transcription_with_gemini
    from src.models.analysis import ConversationAnalysisResult
    
    st.markdown("### 🤖 Conversation Analysis")
    st.markdown("##### Pause Compliance & Resolution Detection")
    
    # Check if transcription exists
    transcription_key = f"transcription_{session_id}"
    analysis_key = f"conversation_analysis_{session_id}"
    
    # Try to load existing analysis from GCS if not in session state
    if analysis_key not in st.session_state:
        analysis_blob = bucket.blob(f"sessions/{session_id}/conversation_analysis.json")
        if analysis_blob.exists():
            try:
                analysis_data = json.loads(analysis_blob.download_as_text())
                st.session_state[analysis_key] = ConversationAnalysisResult(**analysis_data)
            except Exception as e:
                st.warning(f"Could not load existing analysis: {e}")
    
    # Also try to load transcription if not in session state
    if transcription_key not in st.session_state:
        transcription_blob = bucket.blob(f"sessions/{session_id}/transcription.json")
        if transcription_blob.exists():
            try:
                from src.models.transcription import TranscriptionResponse
                trans_data = json.loads(transcription_blob.download_as_text())
                st.session_state[transcription_key] = TranscriptionResponse(**trans_data)
            except Exception as e:
                pass  # Silent fail, will show warning below
    
    if GEMINI_AVAILABLE:
        if transcription_key not in st.session_state:
            st.warning("⚠️ No transcription found. Please generate a transcription first in the Transcription tab.")
            return
        
        # Analysis controls
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            button_label = "🔄 Re-analyze" if analysis_key in st.session_state else "🚀 Analyze Conversation"
            if st.button(button_label, type="primary"):
                analysis = analyze_transcription_with_gemini(session_id, force_regenerate=True)
                if analysis:
                    st.rerun()
        
        with col2:
            if analysis_key in st.session_state:
                st.success("✅ Analysis available")
        
        # Display analysis if available
        if analysis_key in st.session_state:
            analysis: ConversationAnalysisResult = st.session_state[analysis_key]
            
            # Quick Summary
            st.markdown("---")
            
            # Priority Alert Box
            if analysis.requires_review:
                st.error(f"""
                🚨 **REQUIRES REVIEW** - Priority: {analysis.review_priority.upper()}
                
                **Reasons:** {', '.join(analysis.review_reasons)}
                """)
            else:
                st.success("✅ No immediate review required")
            
            # Key Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Resolution Status", analysis.resolution_status.replace("_", " ").title())
            with col2:
                st.metric("Compliance Score", f"{analysis.pause_compliance_score:.0f}%")
            with col3:
                st.metric("Long Pauses", len(analysis.long_pauses))
            with col4:
                st.metric("Unresolved Issues", len(analysis.unresolved_issues))
            
            # Detailed Analysis Tabs
            tabs = st.tabs([
                "📋 Summary", 
                "🔄 Conversation Structure",
                "⏸️ Pause Analysis", 
                "❌ Unresolved Issues", 
                "🎩 Politeness", 
                "😊 Satisfaction", 
                "💭 Emotional Tone",
                "📊 Full Report"
            ])
            
            with tabs[0]:  # Summary
                st.markdown("#### Analysis Summary")
                st.write(analysis.analysis_summary)
                
                if analysis.key_findings:
                    st.markdown("#### Key Findings")
                    for finding in analysis.key_findings:
                        st.write(f"• {finding}")
            
            with tabs[1]:  # Conversation Structure
                st.markdown("#### Conversation Structure Analysis")
                
                if hasattr(analysis, 'structure_analysis'):
                    structure = analysis.structure_analysis
                    
                    # Overall score
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.metric("Structure Score", f"{structure.structure_score:.0f}%")
                    with col2:
                        # Show expected vs actual flow
                        st.markdown("**Expected Flow:**")
                        st.write(" → ".join(["Greeting", "Problem ID", "Analysis", "Solution", "Closure"]))
                        
                    # Missing stages alert
                    if structure.missing_stages:
                        st.warning(f"⚠️ **Missing Stages:** {', '.join(structure.missing_stages)}")
                    
                    # Flow deviations
                    if structure.flow_deviations:
                        st.error("**Flow Deviations:**")
                        for deviation in structure.flow_deviations:
                            st.write(f"• {deviation}")
                    
                    # Stage details
                    st.markdown("**Stage Details:**")
                    for stage in structure.stages_identified:
                        with st.expander(f"{stage.stage_type.replace('_', ' ').title()} ({stage.start_time:.1f}s - {stage.end_time:.1f}s)"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Completeness:** {stage.completeness}")
                                st.write(f"**Quality Score:** {stage.quality_score:.0f}%")
                                st.write(f"**Primary Speaker:** {stage.speaker}")
                            with col2:
                                if stage.deviations:
                                    st.write("**Deviations:**")
                                    for dev in stage.deviations:
                                        st.write(f"• {dev}")
                            st.write(f"**Sample Text:** {stage.text_snippet[:200]}...")
                    
                    # Recommendations
                    if structure.recommendations:
                        st.markdown("**Recommendations for Improvement:**")
                        for rec in structure.recommendations:
                            st.info(f"💡 {rec}")
                else:
                    st.info("Conversation structure analysis not available in this report. Re-analyze to include this feature.")
            
            with tabs[2]:  # Pause Analysis
                st.markdown("#### Pause Compliance Analysis")
                
                if analysis.long_pauses:
                    st.warning(f"Found {len(analysis.long_pauses)} pause(s) longer than 1 minute")
                    
                    for i, pause in enumerate(analysis.long_pauses, 1):
                        with st.expander(f"Pause {i}: {pause.duration_seconds:.1f} seconds ({pause.timestamp_start:.1f}s - {pause.timestamp_end:.1f}s)"):
                            # Compliance status
                            if pause.compliance_issue:
                                st.error(f"❌ COMPLIANCE VIOLATION - {pause.announcement_status.replace('_', ' ')}")
                            else:
                                st.success(f"✅ Properly announced - {pause.announcement_status.replace('_', ' ')}")
                            
                            # Details
                            st.markdown("**Context Before:**")
                            st.text(pause.context_before)
                            
                            if pause.announcement_text:
                                st.markdown("**Announcement:**")
                                st.info(pause.announcement_text)
                            
                            st.markdown("**Context After:**")
                            st.text(pause.context_after)
                            
                            if pause.recommendation:
                                st.markdown("**Recommendation:**")
                                st.warning(pause.recommendation)
                else:
                    st.success("✅ No long pauses detected")
                
                # Compliance Score
                st.markdown("---")
                st.metric("Overall Pause Compliance Score", f"{analysis.pause_compliance_score:.0f}%")
                if analysis.compliance_violations > 0:
                    st.error(f"⚠️ {analysis.compliance_violations} compliance violation(s) detected")
            
            with tabs[3]:  # Unresolved Issues
                st.markdown("#### Unresolved Issues Detection")
                
                if analysis.unresolved_issues:
                    st.error(f"Found {len(analysis.unresolved_issues)} unresolved issue(s)")
                    
                    for i, issue in enumerate(analysis.unresolved_issues, 1):
                        severity_color = {
                            "critical": "🔴",
                            "high": "🟠",
                            "medium": "🟡",
                            "low": "🟢"
                        }.get(issue.severity, "⚪")
                        
                        with st.expander(f"{severity_color} Issue {i}: {issue.issue_description} [{issue.timestamp:.1f}s]"):
                            st.markdown("**Customer Statement:**")
                            st.error(issue.customer_statement)
                            
                            if issue.agent_response:
                                st.markdown("**Agent Response:**")
                                st.info(issue.agent_response)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Severity", issue.severity.upper())
                            with col2:
                                if issue.requires_followup:
                                    st.error("⚠️ REQUIRES FOLLOW-UP")
                                else:
                                    st.info("No immediate follow-up needed")
                else:
                    st.success("✅ No unresolved issues detected")
                
                # Customer Satisfaction Indicators
                if analysis.customer_satisfaction_indicators:
                    st.markdown("---")
                    st.markdown("#### Satisfaction Indicators")
                    for indicator in analysis.customer_satisfaction_indicators:
                        if any(word in indicator.lower() for word in ["thank", "great", "perfect", "solved"]):
                            st.success(f"😊 {indicator}")
                        else:
                            st.warning(f"😔 {indicator}")
            
            with tabs[4]:  # Politeness Analysis
                st.markdown("#### Politeness Elements Analysis")
                
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Politeness Score", f"{analysis.politeness_score:.0f}%")
                with col2:
                    if analysis.has_greeting:
                        st.success("✅ Greeting")
                    else:
                        st.error("❌ No Greeting")
                with col3:
                    if analysis.has_farewell:
                        st.success("✅ Farewell")
                    else:
                        st.error("❌ No Farewell")
                with col4:
                    if analysis.has_thanks:
                        st.success("✅ Thanks")
                    else:
                        st.warning("⚠️ No Thanks")
                
                # Detailed elements
                if analysis.politeness_elements:
                    st.markdown("##### Detected Elements")
                    for elem in analysis.politeness_elements:
                        icon = {"greeting": "👋", "farewell": "👋", "thanks": "🙏", 
                               "apology": "😔", "courtesy_phrase": "💬"}.get(elem.element_type, "💭")
                        
                        appropriateness_color = {
                            "excellent": "🟢", "good": "🟢", "adequate": "🟡",
                            "poor": "🟠", "missing": "🔴"
                        }.get(elem.appropriateness, "⚪")
                        
                        with st.expander(f"{icon} {elem.element_type.title()} by {elem.speaker} [{elem.timestamp:.1f}s]"):
                            st.write(f"**Text:** {elem.text}")
                            st.write(f"**Appropriateness:** {appropriateness_color} {elem.appropriateness}")
                else:
                    st.info("No specific politeness elements detected")
            
            with tabs[5]:  # Satisfaction Analysis
                st.markdown("#### Customer Satisfaction Analysis")
                
                # Final satisfaction
                satisfaction_emoji = {
                    "very_satisfied": "😊", "satisfied": "🙂", "neutral": "😐",
                    "dissatisfied": "☹️", "very_dissatisfied": "😠"
                }.get(analysis.final_satisfaction, "❓")
                
                st.metric("Final Satisfaction Level", 
                         f"{satisfaction_emoji} {analysis.final_satisfaction.replace('_', ' ').title()}")
                
                # Satisfaction signals timeline
                if analysis.satisfaction_signals:
                    st.markdown("##### Satisfaction Signals Timeline")
                    
                    positive_signals = [s for s in analysis.satisfaction_signals if s.signal_type == "positive"]
                    negative_signals = [s for s in analysis.satisfaction_signals if s.signal_type == "negative"]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**😊 Positive Signals**")
                        if positive_signals:
                            for signal in positive_signals:
                                st.success(f"[{signal.timestamp:.1f}s] {signal.phrase} (confidence: {signal.confidence:.0f}%)")
                        else:
                            st.info("No positive signals detected")
                    
                    with col2:
                        st.markdown("**😔 Negative Signals**")
                        if negative_signals:
                            for signal in negative_signals:
                                st.error(f"[{signal.timestamp:.1f}s] {signal.phrase} (confidence: {signal.confidence:.0f}%)")
                        else:
                            st.info("No negative signals detected")
                else:
                    st.info("No specific satisfaction signals detected")
            
            with tabs[6]:  # Emotional Tone Evaluation
                st.markdown("#### Emotional Tone Evaluation")
                
                if analysis.tone_evaluation:
                    # Overall assessment
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        customer_emoji = {
                            "angry": "😠", "frustrated": "😤", "neutral": "😐",
                            "satisfied": "🙂", "happy": "😊"
                        }.get(analysis.tone_evaluation.customer_tone, "❓")
                        st.metric("Customer Tone", f"{customer_emoji} {analysis.tone_evaluation.customer_tone.title()}")
                    
                    with col2:
                        agent_emoji = {
                            "empathetic": "🤗", "professional": "👔", "neutral": "😐",
                            "cold": "🥶", "inappropriate": "❌"
                        }.get(analysis.tone_evaluation.agent_tone, "❓")
                        st.metric("Agent Tone", f"{agent_emoji} {analysis.tone_evaluation.agent_tone.title()}")
                    
                    with col3:
                        appropriateness_color = {
                            "excellent": "🟢", "good": "🟢", "adequate": "🟡",
                            "poor": "🟠", "very_poor": "🔴"
                        }.get(analysis.tone_evaluation.tone_appropriateness, "⚪")
                        st.metric("Appropriateness", 
                                 f"{appropriateness_color} {analysis.tone_evaluation.tone_appropriateness.replace('_', ' ').title()}")
                    
                    # Agent scores
                    st.markdown("##### Agent Performance Scores")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Empathy", f"{analysis.tone_evaluation.empathy_score:.0f}%")
                    with col2:
                        st.metric("Politeness", f"{analysis.tone_evaluation.politeness_score:.0f}%")
                    with col3:
                        st.metric("Respect", f"{analysis.tone_evaluation.respect_score:.0f}%")
                    
                    # Tone mismatches
                    if analysis.tone_evaluation.tone_mismatches:
                        st.markdown("##### ⚠️ Tone Mismatches")
                        for mismatch in analysis.tone_evaluation.tone_mismatches:
                            st.warning(mismatch)
                    else:
                        st.success("✅ No significant tone mismatches detected")
            
            with tabs[7]:  # Full Report
                st.markdown("#### Complete Analysis Report")
                
                # Export button
                if st.button("📥 Export Full Report (JSON)"):
                    report_json = json.dumps(analysis.model_dump(), indent=2, default=str)
                    st.download_button(
                        label="Download Report",
                        data=report_json,
                        file_name=f"{session_id}_analysis_report.json",
                        mime="application/json"
                    )
                
                # Display full data
                with st.expander("View Raw Analysis Data"):
                    st.json(analysis.model_dump())
    else:
        st.warning("⚠️ Gemini API not configured")

def display_metadata_tab(bucket, session_id):
    """Display session metadata"""
    st.markdown("### 📊 Session Metadata")
    
    try:
        metadata_blob = bucket.blob(f"sessions/{session_id}/metadata.json")
        if metadata_blob.exists():
            metadata = json.loads(metadata_blob.download_as_text())
            st.json(metadata)
        else:
            st.info("No metadata file found")
    except Exception as e:
        st.error(f"Error loading metadata: {e}")

def display_raw_data_tab(bucket, session_id):
    """Display raw files for the session"""
    st.markdown("### 📄 Raw Session Files")
    
    try:
        blobs = bucket.list_blobs(prefix=f"sessions/{session_id}/")
        files = []
        for blob in blobs:
            files.append({
                'File': blob.name.replace(f"sessions/{session_id}/", ""),
                'Size': f"{blob.size / 1024:.1f} KB" if blob.size else "0 KB",
                'Updated': blob.updated.strftime("%Y-%m-%d %H:%M") if blob.updated else "Unknown"
            })
        
        if files:
            df = pd.DataFrame(files)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No files found")
    except Exception as e:
        st.error(f"Error listing files: {e}")

def main():
    """Main application with master table navigation"""
    
    # Application header
    st.markdown("# 📊 Call Analytics Platform v2.0")
    st.markdown("##### Enhanced Navigation with Master Table View")
    
    # Initialize GCS
    client, bucket = init_gcs_client()
    
    if not bucket:
        st.error("❌ Failed to connect to Google Cloud Storage")
        st.stop()
    
    # Navigation based on view mode
    if st.session_state.view_mode == 'table':
        # Master table view
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            st.markdown("### 📋 Session List")
        with col2:
            if st.button("🔄 Reload Sessions", type="secondary", help="Reload session data from cloud"):
                st.cache_data.clear()
                st.rerun()
        with col3:
            if st.button("➕ New Session", type="primary", help="Create a new empty session"):
                st.session_state.show_create_dialog = True
        with col4:
            st.info(f"Bucket: {BUCKET_NAME}")
        
        # Create new session dialog
        if st.session_state.get('show_create_dialog', False):
            with st.form("create_session_form"):
                st.markdown("#### Create New Session")
                custom_name = st.text_input(
                    "Session Name", 
                    placeholder="e.g., test_call or demo_session",
                    help="Enter a custom name for your session. Only alphanumeric characters, underscores, and hyphens allowed."
                )
                
                # Generate the full session ID with timestamp
                from datetime import datetime
                now = datetime.now()
                date_str = now.strftime("%Y%m%d")  # Format: 20240104
                time_str = now.strftime("%H%M%S")  # Format: 143052
                
                if custom_name:
                    full_session_id = f"{date_str}_{time_str}_custom_{custom_name}"
                    st.info(f"Session will be created as: **{full_session_id}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Create", type="primary"):
                        if custom_name:
                            # Validate custom name
                            import re
                            if re.match(r'^[a-zA-Z0-9_-]+$', custom_name):
                                try:
                                    # Generate full session ID
                                    now = datetime.now()
                                    date_str = now.strftime("%Y%m%d")
                                    time_str = now.strftime("%H%M%S")
                                    full_session_id = f"{date_str}_{time_str}_custom_{custom_name}"
                                    
                                    # Create empty marker file in GCS
                                    marker_blob = bucket.blob(f"sessions/{full_session_id}/.keep")
                                    marker_blob.upload_from_string("", content_type='text/plain')
                                    
                                    st.success(f"✅ Created session: {full_session_id}")
                                    st.session_state.show_create_dialog = False
                                    
                                    # Clear cache to show new session
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Failed to create session: {e}")
                            else:
                                st.error("❌ Invalid session name. Use only letters, numbers, underscores, and hyphens.")
                        else:
                            st.error("❌ Please enter a session name")
                
                with col2:
                    if st.form_submit_button("Cancel", type="secondary"):
                        st.session_state.show_create_dialog = False
                        st.rerun()
            
            st.markdown("---")
        
        with st.spinner("Loading sessions..."):
            sessions_df = list_all_sessions(bucket)
        
        if not sessions_df.empty:
            # Display session count and check for specific sessions
            st.success(f"✅ Found **{len(sessions_df)}** total sessions")
            
            # Bulk operations section
            st.markdown("### 🛠️ Bulk Operations")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Check for sessions that need transcription
                sessions_needing_transcription = sessions_df[
                    (sessions_df['Has Audio'] == True) & 
                    (sessions_df['Has Transcript'] == False)
                ]
                
                # Bulk transcription section - always show
                with st.expander(f"🎙️ Bulk Transcription ({len(sessions_needing_transcription)} pending)", expanded=False):
                    st.markdown("### Generate Transcripts for All Missing Sessions")
                    st.write(f"This will generate transcripts for {len(sessions_needing_transcription)} sessions:")
                    
                    # Show list of sessions to be processed
                    session_list = sessions_needing_transcription['Session ID'].tolist()
                    if session_list:
                        st.write(", ".join(session_list[:10]))
                        if len(session_list) > 10:
                            st.write(f"... and {len(session_list) - 10} more")
                        
                        if st.button("🚀 Start Bulk Transcription", type="primary"):
                            from app_utils import transcribe_audio_with_diarization
                            
                            # Progress tracking
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            success_count = 0
                            failed_sessions = []
                            
                            for i, session_id in enumerate(session_list):
                                # Update progress
                                progress = (i + 1) / len(session_list)
                                progress_bar.progress(progress)
                                status_text.text(f"Processing {i+1}/{len(session_list)}: {session_id}")
                                
                                try:
                                    # Generate transcription
                                    transcription = transcribe_audio_with_diarization(bucket, session_id, force_regenerate=True)
                                    if transcription:
                                        success_count += 1
                                    else:
                                        failed_sessions.append(session_id)
                                except Exception as e:
                                    failed_sessions.append(session_id)
                                    st.warning(f"Failed to transcribe {session_id}: {str(e)}")
                            
                            # Clear progress indicators
                            progress_bar.empty()
                            status_text.empty()
                            
                            # Show results
                            if success_count > 0:
                                st.success(f"✅ Successfully transcribed {success_count} sessions")
                            if failed_sessions:
                                st.error(f"❌ Failed to transcribe {len(failed_sessions)} sessions: {', '.join(failed_sessions)}")
                            
                            # Clear cache and refresh
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.info("No sessions require transcription. All sessions with audio have been transcribed.")
            
            with col2:
                # Check for sessions that need analysis
                sessions_needing_analysis = sessions_df[
                    (sessions_df['Has Transcript'] == True) & 
                    (sessions_df['Has Analysis'] == False)
                ]
                
                # Bulk analysis section - always show
                with st.expander(f"🔍 Bulk Analysis ({len(sessions_needing_analysis)} pending)", expanded=False):
                    st.markdown("### Analyze All Sessions with Transcripts")
                    st.write(f"This will analyze {len(sessions_needing_analysis)} sessions that have transcripts but no analysis:")
                    
                    # Show list of sessions to be processed
                    analysis_list = sessions_needing_analysis['Session ID'].tolist()
                    st.write(", ".join(analysis_list[:10]))
                    if len(analysis_list) > 10:
                        st.write(f"... and {len(analysis_list) - 10} more")
                    
                    if st.button("🚀 Start Bulk Analysis", type="primary", key="bulk_analysis_btn"):
                        from app_utils import analyze_transcription_with_gemini
                        
                        # Progress tracking
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        success_count = 0
                        failed_sessions = []
                        
                        for i, session_id in enumerate(analysis_list):
                            # Update progress
                            progress = (i + 1) / len(analysis_list)
                            progress_bar.progress(progress)
                            status_text.text(f"Analyzing {i+1}/{len(analysis_list)}: {session_id}")
                            
                            try:
                                # Generate analysis
                                analysis = analyze_transcription_with_gemini(session_id, force_regenerate=True)
                                if analysis:
                                    success_count += 1
                                else:
                                    failed_sessions.append(session_id)
                            except Exception as e:
                                failed_sessions.append(session_id)
                                st.warning(f"Failed to analyze {session_id}: {str(e)}")
                        
                        # Clear progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        
                        # Show results
                        if success_count > 0:
                            st.success(f"✅ Successfully analyzed {success_count} sessions")
                        if failed_sessions:
                            st.error(f"❌ Failed to analyze {len(failed_sessions)} sessions: {', '.join(failed_sessions)}")
                        
                        # Clear cache and refresh
                        st.cache_data.clear()
                        st.rerun()
            
            # Debug: Check if test_transcription_001 is in the list
            session_ids = sessions_df['Session ID'].tolist()
            if 'test_transcription_001' in session_ids:
                st.info("✅ test_transcription_001 is in the list")
            else:
                st.warning("⚠️ test_transcription_001 not found in the list")
                # Show what sessions are actually found
                with st.expander("Debug: All session IDs"):
                    st.write(sorted(session_ids))
            
            display_session_table(sessions_df)
        else:
            st.warning("No sessions found in the bucket")
            st.info(f"Bucket: {BUCKET_NAME}")
    
    elif st.session_state.view_mode == 'details':
        # Detailed session view
        if st.session_state.selected_session:
            display_session_details(bucket, st.session_state.selected_session)
        else:
            st.session_state.view_mode = 'table'
            st.rerun()
    
    # Footer with tools link
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption("Call Analytics Platform v2.0 | Powered by Gemini & Google Cloud")
    with col2:
        st.markdown("[🎙️ TTS Tool](http://localhost:8504)", help="Open Text-to-Speech Generator")

if __name__ == "__main__":
    main()