"""
Service for analyzing conversation transcriptions using Gemini
Focuses on pause compliance and unresolved issues
"""

import os
import json
from datetime import datetime
from typing import Optional
import google.genai as genai
from src.models.analysis import ConversationAnalysisResult
from src.models.transcription import TranscriptionResponse

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


class ConversationAnalysisService:
    def __init__(self):
        """Initialize the analysis service"""
        # Get API key from Streamlit secrets or environment
        if HAS_STREAMLIT and "gcs" in st.secrets and "GEMINI_API_KEY" in st.secrets["gcs"]:
            self.api_key = st.secrets["gcs"]["GEMINI_API_KEY"]
        else:
            # Fallback to environment variables
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in Streamlit secrets or environment variables")
        
        self.client = genai.Client(api_key=self.api_key)
    
    def analyze_transcription(self, transcription: TranscriptionResponse, session_id: str) -> Optional[ConversationAnalysisResult]:
        """
        Analyze a transcription for pause compliance and unresolved issues
        
        Args:
            transcription: The transcription to analyze
            session_id: Session ID for tracking
        
        Returns:
            ConversationAnalysisResult with detailed analysis
        """
        
        # Convert transcription to text format for analysis
        conversation_text = self._format_transcription_for_analysis(transcription)
        
        # Create the analysis prompt
        prompt = f"""
        Analyze this customer service conversation transcript for quality and compliance issues.
        
        CONVERSATION TRANSCRIPT:
        {conversation_text}
        
        TOTAL DURATION: {transcription.total_duration} seconds
        
        ANALYSIS REQUIREMENTS:
        
        1. PAUSE ANALYSIS:
        - Identify ALL pauses longer than 60 seconds (1 minute) (make sure they are not shorter ones)
        - For each pause, determine if the customer was properly informed
        - Proper announcement includes phrases like "please wait", "one moment", "let me check", "hold on", etc.
        - Mark as compliance violation if pause > 60 seconds without announcement
        - Include context before and after each pause
        
        2. RESOLUTION ANALYSIS:
        - Identify if the customer's problem was resolved
        - Look for phrases indicating unresolved issues:
          * "still not working"
          * "problem remains"
          * "didn't help"
          * "still have the issue"
          * "need more help"
          * "will call back"
          * "not satisfied"
        - Note any explicit statements about resolution status
        
        3. POLITENESS ANALYSIS:
        - Identify ALL politeness elements (greeting, farewell, thanks, apologies, courtesy phrases)
        - Note who said them (agent or customer) and when
        - Evaluate appropriateness of each element
        - Check for presence of:
          * Proper greeting at start
          * Proper farewell at end
          * Thanks expressions
          * Apologies when appropriate
        
        4. SATISFACTION SIGNALS:
        - Detect customer satisfaction signals throughout conversation
        - Look for key phrases indicating satisfaction/dissatisfaction:
          * Positive: "thank you", "great", "perfect", "solved", "works now"
          * Negative: "frustrated", "angry", "not working", "terrible", "bad service"
        - Assess final satisfaction level at conversation end
        
        5. EMOTIONAL TONE EVALUATION:
        - Identify customer's emotional tone (angry, frustrated, neutral, satisfied, happy)
        - Evaluate agent's tone (empathetic, professional, neutral, cold, inappropriate)
        - Assess appropriateness of agent's tone relative to customer's emotional state
        - Score agent on:
          * Empathy (0-100)
          * Politeness (0-100)
          * Respect (0-100)
        - Note any tone mismatches where agent's response was inappropriate
        
        6. CONVERSATION STRUCTURE ANALYSIS:
        - Identify conversation stages present in the conversation:
          * GREETING: Initial contact, introduction, welcome
          * PROBLEM_IDENTIFICATION: Customer states issue/reason for contact
          * PROBLEM_ANALYSIS: Agent investigates, asks clarifying questions
          * SOLUTION_PRESENTATION: Agent provides solution, explains steps
          * CLOSURE: Farewell, summary, next steps
        - For each stage found:
          * Mark start and end timestamps
          * Assess completeness (complete/partial/missing)
          * Note quality (0-100)
          * Identify deviations from standard
        - Expected flow: greeting → problem_identification → problem_analysis → solution_presentation → closure
        - Note any missing stages or incorrect order
        - Identify deviations such as:
          * Missing greeting or farewell
          * Jumping to solution without analysis
          * No clear problem identification
          * Abrupt ending without closure
          * Stages out of order
        
        7. REVIEW REQUIREMENTS:
        - Mark for review if:
          * Customer explicitly states problem unresolved
          * Multiple long pauses without announcement
          * Customer expresses frustration or dissatisfaction
          * Agent unable to provide solution
          * Significant tone mismatches detected
        
        Provide a detailed, structured analysis following the schema.
        Be specific about timestamps and exact phrases used.
        """
        
        try:
            # Generate analysis using Gemini with structured output
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ConversationAnalysisResult,
                    "temperature": 0.1,  # Low temperature for consistent analysis
                }
            )
            
            # Parse the response
            if response and response.text:
                analysis_data = json.loads(response.text)
                
                # Add metadata
                analysis_data['session_id'] = session_id
                analysis_data['analysis_timestamp'] = datetime.now().isoformat()
                analysis_data['total_conversation_duration'] = transcription.total_duration
                
                # Create the result object
                return ConversationAnalysisResult(**analysis_data)
            
        except Exception as e:
            print(f"Error during analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
        return None
    
    def _format_transcription_for_analysis(self, transcription: TranscriptionResponse) -> str:
        """
        Format transcription for analysis, including pause markers
        
        Args:
            transcription: The transcription to format
        
        Returns:
            Formatted text with timestamps and pause indicators
        """
        lines = []
        prev_end = 0
        
        for segment in transcription.transcription:
            # Check for pause between segments
            if prev_end > 0 and segment.timestamp_start - prev_end > 2:
                pause_duration = segment.timestamp_start - prev_end
                lines.append(f"[PAUSE: {pause_duration:.1f} seconds from {prev_end:.1f}s to {segment.timestamp_start:.1f}s]")
            
            # Add the segment
            if segment.speaker_label != "silence":
                lines.append(f"[{segment.timestamp_start:.1f}s - {segment.timestamp_end:.1f}s] {segment.speaker_label.upper()}: {segment.text}")
            else:
                # Mark silence segments
                silence_duration = segment.timestamp_end - segment.timestamp_start
                if silence_duration > 2:  # Only show significant silences
                    lines.append(f"[SILENCE: {silence_duration:.1f} seconds from {segment.timestamp_start:.1f}s to {segment.timestamp_end:.1f}s]")
            
            prev_end = segment.timestamp_end
        
        return "\n".join(lines)
    
    def get_analysis_summary(self, analysis: ConversationAnalysisResult) -> dict:
        """
        Get a summary of the analysis for quick viewing
        
        Args:
            analysis: The analysis result
        
        Returns:
            Dictionary with summary information
        """
        return {
            "requires_review": analysis.requires_review,
            "review_priority": analysis.review_priority,
            "compliance_violations": analysis.compliance_violations,
            "resolution_status": analysis.resolution_status,
            "unresolved_count": len(analysis.unresolved_issues),
            "long_pauses_count": len(analysis.long_pauses),
            "pause_compliance_score": analysis.pause_compliance_score
        }