"""
Timeline visualization utilities for Streamlit
"""

import streamlit as st
import plotly.graph_objects as go
from src.models.transcription import TranscriptionResponse


def create_speaker_timeline_plotly(transcription: TranscriptionResponse):
    """Create an interactive speaker timeline using Plotly"""
    
    # Define colors for speakers
    speaker_colors = {
        "speaker1": "#4CAF50",
        "speaker2": "#2196F3",
        "speaker3": "#FF9800",
        "speaker4": "#9C27B0",
        "speaker5": "#F44336",
        "silence": "#E0E0E0"
    }
    
    fig = go.Figure()
    
    # Add bars for each segment
    for segment in transcription.transcription:
        duration = segment.timestamp_end - segment.timestamp_start
        color = speaker_colors.get(segment.speaker_label, "#888888")
        
        # Create hover text
        hover_text = f"<b>{segment.speaker_label.upper()}</b><br>"
        hover_text += f"Time: {segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s<br>"
        hover_text += f"Duration: {duration:.1f}s<br>"
        if segment.speaker_label != "silence":
            hover_text += f"Text: {segment.text[:100]}..."
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=[1],
            orientation='h',
            base=segment.timestamp_start,
            name=segment.speaker_label.upper(),
            marker=dict(color=color),
            hovertemplate=hover_text + "<extra></extra>",
            showlegend=False,
            width=0.8
        ))
    
    # Update layout
    fig.update_layout(
        barmode='overlay',
        height=100,
        margin=dict(l=0, r=0, t=10, b=30),
        xaxis=dict(
            title="Time (seconds)",
            range=[0, transcription.total_duration],
            showgrid=True,
            gridwidth=1,
            gridcolor='#E0E0E0'
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            range=[0.5, 1.5]
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified'
    )
    
    # Add legend manually
    speakers_in_transcript = set(seg.speaker_label for seg in transcription.transcription)
    for speaker in sorted(speakers_in_transcript):
        if speaker in speaker_colors:
            fig.add_trace(go.Scatter(
                x=[None],
                y=[None],
                mode='markers',
                name=speaker.upper() if speaker != "silence" else "Silence",
                marker=dict(size=10, color=speaker_colors[speaker]),
                showlegend=True
            ))
    
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="left",
            x=0
        )
    )
    
    return fig


def create_streamlit_timeline(transcription: TranscriptionResponse):
    """Create a simple timeline using Streamlit native components"""
    
    # Define colors for speakers
    speaker_colors = {
        "speaker1": "🟢",  # Green
        "speaker2": "🔵",  # Blue
        "speaker3": "🟠",  # Orange
        "speaker4": "🟣",  # Purple
        "speaker5": "🔴",  # Red
        "silence": "⚪"    # Gray
    }
    
    # Create progress bar visualization
    total_duration = transcription.total_duration
    
    # Create a visual timeline using columns
    timeline_text = ""
    for segment in transcription.transcription:
        duration = segment.timestamp_end - segment.timestamp_start
        percentage = (duration / total_duration) * 100
        
        if segment.speaker_label != "silence":
            emoji = speaker_colors.get(segment.speaker_label, "⚫")
            timeline_text += f"{emoji} "
            
    st.markdown("**Timeline Overview:**")
    st.text(timeline_text)
    
    # Show detailed segments
    st.markdown("**Detailed Segments:**")
    
    for segment in transcription.transcription:
        if segment.speaker_label != "silence":
            duration = segment.timestamp_end - segment.timestamp_start
            percentage = (duration / total_duration) * 100
            
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                st.write(f"{segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s")
            with col2:
                st.progress(percentage / 100)
            with col3:
                st.write(segment.speaker_label.upper())