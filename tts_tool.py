"""
Text-to-Speech Tool
A standalone utility for generating audio from text using Gemini TTS
"""

import streamlit as st
import os
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from src.services.tts_service import TextToSpeechService

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Text-to-Speech Generator",
    page_icon="🎙️",
    layout="centered"
)

# Initialize session state for TTS tool
if 'tts_generated_audio' not in st.session_state:
    st.session_state.tts_generated_audio = None
if 'tts_audio_filename' not in st.session_state:
    st.session_state.tts_audio_filename = None

def main():
    st.title("🎙️ Text-to-Speech Generator")
    st.markdown("Generate natural-sounding speech from text using Google Gemini TTS")
    
    # Check API key
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        st.error("❌ Gemini API key not configured. Please set GEMINI_API_KEY or GOOGLE_API_KEY in your .env file")
        return
    
    # Sample texts
    sample_texts = {
        "Lithuanian (Customer Service)": "Sveiki, jūs paskambinote į Registrų Centrą. Aš esu virtuali asistentė Greta. Galiu suteikti bendrą informaciją apie Registrų centro paslaugas arba patikrinti jūsų paraiškos statusą. Ką norėtumėte padaryti pirmiausia?",
        "English (Welcome)": "Hello and welcome to our customer service center. I'm your virtual assistant. How may I help you today?",
        "Lithuanian (Information)": "Dėkojame, kad kreipėtės. Jūsų paraiška buvo priimta ir šiuo metu yra nagrinėjama. Tikėtinas apdorojimo laikas yra 3-5 darbo dienos.",
        "English (Technical Support)": "I understand you're experiencing technical difficulties. Let me help you troubleshoot the issue. Can you please describe what error message you're seeing?"
    }
    
    # Sample text selector (outside form for immediate update)
    st.markdown("#### Sample Texts")
    sample_choice = st.selectbox(
        "Choose a sample text to load into the editor",
        options=[""] + list(sample_texts.keys()),
        help="Select a pre-written sample text",
        key="sample_selector"
    )
    
    # Get text value based on selection
    default_text = ""
    if sample_choice:
        default_text = sample_texts[sample_choice]
    
    # Main form
    with st.form("tts_form"):
        # Text input with default value from sample
        text_input = st.text_area(
            "Enter text to convert to speech",
            value=default_text,
            placeholder="Type or paste your text here...",
            height=200,
            help="Enter the text you want to convert to speech. Supports multiple languages.",
            key="text_input_area"
        )
        
        # Voice selection
        col1, col2 = st.columns(2)
        with col1:
            voice = st.selectbox(
                "Select Voice",
                options=["Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Aoede"],
                index=0,
                help="Choose the voice for speech generation"
            )
        
        with col2:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=1.0,
                step=0.1,
                help="Controls randomness in speech generation. Lower = more consistent, Higher = more varied"
            )
        
        # Generate button
        submitted = st.form_submit_button("🎤 Generate Audio", type="primary", use_container_width=True)
    
    # Handle generation
    if submitted and text_input:
        try:
            with st.spinner("🔄 Generating audio... This may take a few seconds..."):
                # Initialize TTS service
                tts_service = TextToSpeechService()
                
                # Generate audio
                audio_data = tts_service.generate_audio(
                    text=text_input,
                    voice=voice,
                    temperature=temperature
                )
                
                if audio_data:
                    # Store in session state
                    st.session_state.tts_generated_audio = audio_data
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.session_state.tts_audio_filename = f"tts_{voice.lower()}_{timestamp}.wav"
                    
                    st.success("✅ Audio generated successfully!")
                else:
                    st.error("❌ Failed to generate audio. Please try again.")
                    
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    # Display generated audio
    if st.session_state.tts_generated_audio:
        st.markdown("---")
        st.markdown("### 🎧 Generated Audio")
        
        # Audio player
        st.audio(st.session_state.tts_generated_audio, format="audio/wav")
        
        # Download button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.download_button(
                label="📥 Download Audio",
                data=st.session_state.tts_generated_audio,
                file_name=st.session_state.tts_audio_filename,
                mime="audio/wav",
                use_container_width=True
            )
        
        # Clear button
        if st.button("🗑️ Clear", type="secondary"):
            st.session_state.tts_generated_audio = None
            st.session_state.tts_audio_filename = None
            st.rerun()
    
    # Information section
    with st.expander("ℹ️ About Text-to-Speech"):
        st.markdown("""
        This tool uses **Google Gemini 2.5 Pro Preview TTS** to generate natural-sounding speech from text.
        
        **Features:**
        - Multiple voice options
        - Adjustable temperature for speech variation
        - Support for multiple languages
        - High-quality WAV output
        
        **Use Cases:**
        - Generate sample audio for testing
        - Create voice prompts for IVR systems
        - Generate audio content for presentations
        - Test conversation flows with different voices
        
        **Tips:**
        - Use punctuation for natural pauses
        - Adjust temperature for different use cases (lower for consistency, higher for variation)
        - Different voices work better for different languages and contexts
        """)
    
    # Footer
    st.markdown("---")
    st.caption("Text-to-Speech Generator | Powered by Google Gemini TTS")

if __name__ == "__main__":
    main()