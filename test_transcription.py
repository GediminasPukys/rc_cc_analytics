#!/usr/bin/env python3
"""
Test the transcription service with speaker diarization
"""

import os
import sys
import json
from dotenv import load_dotenv
from src.services.transcription_service import TranscriptionService
from src.models.transcription import TranscriptionResponse

# Load environment variables
load_dotenv()


def test_transcription():
    """Test transcription functionality"""
    print("=" * 60)
    print("TRANSCRIPTION SERVICE TEST")
    print("=" * 60)
    
    # Check for audio file
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    else:
        # Try to find test audio
        possible_files = [
            "test_audio.wav",
            "test_audio.mp3",
            "sample_audio.wav",
            "sample_audio.mp3",
        ]
        
        audio_path = None
        for file in possible_files:
            if os.path.exists(file):
                audio_path = file
                break
        
        if not audio_path:
            print("\n❌ No audio file provided")
            print("Usage: python test_transcription.py <audio_file>")
            print("\nOr create test_audio.wav using: python create_test_audio.py")
            return
    
    if not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return
    
    print(f"✅ Audio file: {audio_path}")
    print(f"   File size: {os.path.getsize(audio_path) / 1024:.1f} KB")
    
    # Initialize service
    try:
        service = TranscriptionService()
        print("✅ Transcription service initialized")
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return
    
    # Test transcription
    test_session_id = "test_transcription_001"
    print(f"\n🎙️ Starting transcription for session: {test_session_id}")
    print("This may take a minute...")
    
    try:
        transcription = service.transcribe_audio(audio_path, test_session_id)
        
        if transcription:
            print("\n✅ Transcription successful!")
            print(f"\n📊 Results:")
            print(f"   Total duration: {transcription.total_duration:.1f} seconds")
            print(f"   Number of speakers: {transcription.num_speakers}")
            print(f"   Total segments: {len(transcription.transcription)}")
            
            # Get speaker statistics
            stats = service.get_speaker_statistics(transcription)
            
            print(f"\n👥 Speaker Statistics:")
            for speaker, info in stats.items():
                print(f"   {speaker.upper()}:")
                print(f"     - Speaking time: {info['total_time']:.1f}s")
                print(f"     - Segments: {info['num_segments']}")
                print(f"     - Words: {info['words']}")
            
            print(f"\n📝 First 5 segments:")
            for i, segment in enumerate(transcription.transcription[:5]):
                if segment.speaker_label != "silence":
                    print(f"   [{segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s] {segment.speaker_label.upper()}: {segment.text[:100]}")
                else:
                    duration = segment.timestamp_end - segment.timestamp_start
                    print(f"   [{segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s] [SILENCE {duration:.1f}s]")
            
            # Save to file
            output_file = f"{test_session_id}_transcription.json"
            with open(output_file, "w") as f:
                data = {
                    "session_id": test_session_id,
                    "total_duration": transcription.total_duration,
                    "num_speakers": transcription.num_speakers,
                    "transcription": [seg.model_dump() for seg in transcription.transcription]
                }
                json.dump(data, f, indent=2)
            
            print(f"\n✅ Saved transcription to: {output_file}")
            
            # Test formatted output
            print(f"\n📄 Formatted transcript (first 500 chars):")
            formatted = service.get_transcription_text(transcription)
            print(formatted[:500])
            
        else:
            print("\n❌ Transcription failed - no result returned")
            
    except Exception as e:
        print(f"\n❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_transcription()
    print("\n" + "=" * 60)
    print("Test complete!")