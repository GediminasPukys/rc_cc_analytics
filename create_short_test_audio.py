#!/usr/bin/env python3
"""
Create a SHORT test audio file using text-to-speech
"""

import os

def create_short_test_audio():
    """Create a short test audio file using system TTS"""
    
    # Short test conversation text
    text = """
    Hello, this is a test customer service call.
    I am calling about my account. Can you help me with my billing question?
    Yes, I can help you with that.
    Thank you very much.
    You're welcome. Have a great day!
    """
    
    # Use macOS 'say' command to create audio (works on Mac)
    if os.system("which say > /dev/null 2>&1") == 0:
        print("Using macOS 'say' command to generate SHORT test audio...")
        os.system(f'say -o short_test_audio.aiff "{text}"')
        
        # Convert to WAV if possible
        if os.system("which ffmpeg > /dev/null 2>&1") == 0:
            print("Converting to WAV format...")
            os.system("ffmpeg -i short_test_audio.aiff -acodec pcm_s16le -ar 16000 short_test_audio.wav -y")
            os.remove("short_test_audio.aiff")
            print("✅ Created short_test_audio.wav")
        else:
            print("✅ Created short_test_audio.aiff")
    else:
        print("⚠️ 'say' command not found (not on macOS)")

if __name__ == "__main__":
    create_short_test_audio()