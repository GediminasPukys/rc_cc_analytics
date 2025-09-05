"""
Gemini 2.5 Pro service for comprehensive call analysis
Handles audio transcription and all analysis requirements using Pydantic structured outputs
"""

import os
import time
import json
from typing import Optional
from datetime import datetime
import google.generativeai as genai
from pydantic import ValidationError
import streamlit as st

from json_parser import parse_gemini_response
from models import (
    ComprehensiveCallAnalysis,
    Language,
    EmotionalTone,
    ConversationStage,
    SatisfactionLevel,
    ProblemStatus,
    ConversationCategory,
    TranscriptionSegment,
    Transcription,
    Translation,
    EmotionalAnalysis,
    ConversationStructure,
    SatisfactionAnalysis,
    PolitenessAnalysis,
    ResolutionAnalysis,
    PauseAnalysis,
    ConversationSummary,
    ConversationCategorization
)



class GeminiCallAnalyzer:
    """
    Comprehensive call analyzer using Gemini 2.5 Pro with Pydantic structured outputs
    Implements all requirements R_13 through R_19 plus categorization
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini client with API key from Streamlit secrets"""
        # Try to get API key from Streamlit secrets first, then fall back to parameter
        try:
            self.api_key = api_key or st.secrets.get("gcs", {}).get("GEMINI_API_KEY")
        except:
            # If st.secrets not available (e.g., when running outside Streamlit)
            self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Please add it to .streamlit/secrets.toml or provide it as an argument.")
        
        genai.configure(api_key=self.api_key)
        
        # Use the latest Gemini model that supports structured outputs
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    def analyze_audio(self, audio_path: str, session_id: str) -> ComprehensiveCallAnalysis:
        """
        Perform complete analysis of audio file using Pydantic structured output
        
        Args:
            audio_path: Path to audio file
            session_id: Session identifier
            
        Returns:
            ComprehensiveCallAnalysis with all structured outputs
        """
        start_time = time.time()
        
        # Upload audio file
        audio_file = genai.upload_file(audio_path)
        
        # Create comprehensive prompt focusing on requirements, not structure
        prompt = self._create_analysis_prompt()
        
        # Configure generation with JSON mode (schema too complex for Gemini)
        generation_config = genai.GenerationConfig(
            temperature=0.3,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="application/json"
            # NOTE: ComprehensiveCallAnalysis schema is too complex for Gemini
            # Using JSON mode without schema constraint
        )
        
        try:
            # Generate analysis with structured output
            response = self.model.generate_content(
                [audio_file, prompt],
                generation_config=generation_config
            )
            
            # Parse JSON response
            analysis_data = json.loads(response.text)
            
            # Use the parser to create ComprehensiveCallAnalysis
            analysis = parse_gemini_response(
                analysis_data, 
                session_id,
                int((time.time() - start_time) * 1000)
            )
            
            return analysis
            
        except ValidationError as e:
            print(f"Validation error: {e}")
            import traceback
            traceback.print_exc()
            return self._create_partial_analysis({}, session_id, start_time)
        except Exception as e:
            print(f"Error during analysis: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return self._create_partial_analysis({}, session_id, start_time)
    
    def _create_analysis_prompt(self) -> str:
        """Create comprehensive analysis prompt for Gemini"""
        return """
        Analyze this customer service call recording and provide a comprehensive structured analysis.
        
        REQUIRED TASKS:
        
        1. TRANSCRIPTION:
        - Transcribe the entire conversation in the original language
        - Identify speakers (customer/agent/system)
        - Include timestamps for each segment
        - Detect the original language (Lithuanian/English/Russian/Polish)
        
        2. TRANSLATION:
        - Translate the entire conversation to Lithuanian
        - Preserve speaker identification and timestamps
        - Note any idioms or context that doesn't translate well
        
        3. EMOTIONAL ANALYSIS (R_13):
        - Evaluate customer's emotional tone throughout the call
        - Track emotional progression with timestamps
        - Assess agent's empathy, politeness, and respect (0-100 scores)
        - Identify tone mismatches where agent response was inappropriate
        - Provide specific recommendations for improvement
        
        4. CONVERSATION STRUCTURE (R_14):
        - Classify conversation stages: greeting, problem identification, information gathering, solution presentation, problem resolution, closure, farewell
        - Mark which stages are present/missing
        - Note any deviations from standard structure
        - Calculate structure compliance score (0-100)
        
        5. SATISFACTION ANALYSIS (R_15):
        - Detect customer satisfaction level (very_satisfied/satisfied/neutral/dissatisfied/very_dissatisfied)
        - Identify satisfaction indicators (phrases, sentiment, tone)
        - Track satisfaction trend (improving/stable/declining)
        - Determine if follow-up is required
        
        6. POLITENESS ANALYSIS (R_16):
        - Identify politeness elements: greeting, farewell, thanks, apologies, please, courtesy phrases
        - Check for required elements from both customer and agent
        - Assess cultural appropriateness for Lithuanian context
        - Calculate politeness score (0-100)
        
        7. RESOLUTION ANALYSIS (R_17):
        - Identify the customer's problem/question
        - Determine resolution status (resolved/partially_resolved/unresolved/escalated/pending)
        - Detect phrases indicating unresolved issues
        - Determine if supervisor review is required
        - Set review priority (high/medium/low)
        
        8. PAUSE ANALYSIS (R_18):
        - Detect all pauses longer than 60 seconds
        - Identify if pauses were announced ("please wait", "let me check")
        - Calculate pause compliance score
        - List recommendations for pause handling
        
        9. CONVERSATION SUMMARY (R_19):
        - Provide comprehensive summary in Lithuanian
        - List key discussion points in Lithuanian
        - Describe customer request, actions taken, and outcome
        - Note required follow-up actions
        - Include agent performance notes and improvement suggestions
        
        10. CATEGORIZATION:
        - Assign primary category: general_info/application_inquiry/technical_support/billing_issue/complaint/service_request/cancellation/other
        - Add searchable tags and keywords
        - Determine customer type (new/existing/vip/problematic/unknown)
        - Set urgency level (urgent/normal/low)
        
        IMPORTANT INSTRUCTIONS:
        - Be very precise with timestamps
        - Use Lithuanian cultural context for politeness assessment
        - Consider Lithuanian language nuances in satisfaction detection
        - Flag any critical issues that need immediate attention
        - Provide actionable recommendations
        - Calculate all scores on 0-100 scale where applicable
        - Ensure all boolean fields are true/false
        - Include confidence scores where relevant (0.0-1.0)
        """
    
    def _create_partial_analysis(self, data: dict, session_id: str, start_time: float) -> ComprehensiveCallAnalysis:
        """Create analysis with partial data when full parsing fails"""
        # Provide defaults for all required fields
        return ComprehensiveCallAnalysis(
            session_id=session_id,
            analysis_timestamp=datetime.now(),
            processing_duration_ms=int((time.time() - start_time) * 1000),
            
            transcription=Transcription(
                original_language=Language.UNKNOWN,
                segments=[],
                full_text=data.get('transcription', {}).get('full_text', 'Analysis failed'),
                total_duration_seconds=0,
                transcription_confidence=0.5,
                word_count=0
            ),
            
            translation=Translation(
                target_language="lt",
                translated_segments=[],
                full_translated_text=data.get('translation', {}).get('full_translated_text', 'Analizė nepavyko'),
                translation_notes=None
            ),
            
            emotional_analysis=EmotionalAnalysis(
                customer_overall_emotion=EmotionalTone.NEUTRAL,
                customer_emotion_progression=[],
                customer_emotion_summary="Analysis failed",
                agent_overall_tone=EmotionalTone.NEUTRAL,
                agent_empathy_score=50,
                agent_politeness_score=50,
                agent_respect_score=50,
                tone_appropriateness_score=50,
                tone_mismatches=[],
                recommendations=[]
            ),
            
            structure_analysis=ConversationStructure(
                detected_stages=[],
                expected_stages=[],
                missing_stages=[],
                out_of_order_stages=[],
                structure_compliance_score=50,
                major_deviations=[],
                structure_summary="Analysis incomplete"
            ),
            
            satisfaction_analysis=SatisfactionAnalysis(
                overall_satisfaction=SatisfactionLevel.NEUTRAL,
                satisfaction_score=50,
                satisfaction_indicators=[],
                positive_signals=[],
                negative_signals=[],
                satisfaction_trend="stable",
                end_call_satisfaction=SatisfactionLevel.NEUTRAL,
                requires_follow_up=False,
                follow_up_reason=None
            ),
            
            politeness_analysis=PolitenessAnalysis(
                detected_elements=[],
                agent_greeting_present=False,
                agent_farewell_present=False,
                agent_thanks_present=False,
                agent_apologies_count=0,
                customer_greeting_present=False,
                customer_farewell_present=False,
                customer_thanks_present=False,
                politeness_score=50,
                missing_required_elements=[],
                cultural_appropriateness_score=50,
                recommendations=[]
            ),
            
            resolution_analysis=ResolutionAnalysis(
                problem_statement="Unknown",
                problem_category=ConversationCategory.OTHER,
                resolution_status=ProblemStatus.PENDING,
                resolution_confidence=0.5,
                unresolved_indicators=[],
                resolution_attempts=[],
                customer_confirmation_of_resolution=False,
                requires_escalation=False,
                escalation_reason=None,
                recommended_next_steps=[],
                supervisor_review_required=True,
                review_priority="medium"
            ),
            
            pause_analysis=PauseAnalysis(
                total_pauses=0,
                long_pauses=[],
                total_pause_duration=0,
                average_pause_duration=0,
                longest_pause_duration=0,
                unannounced_long_pauses=0,
                compliance_score=50,
                pause_handling_issues=[],
                recommendations=[]
            ),
            
            summary=ConversationSummary(
                summary_lt="Analizė nepilna",
                key_points_lt=["Analizės klaida"],
                customer_request="Unknown",
                actions_taken=[],
                outcome="Analysis incomplete",
                follow_up_required=True,
                follow_up_actions=["Review recording manually"],
                agent_performance_notes="Analysis failed",
                improvement_suggestions=[]
            ),
            
            categorization=ConversationCategorization(
                primary_category=ConversationCategory.OTHER,
                secondary_categories=[],
                tags=[],
                customer_type="unknown",
                service_mentioned=[],
                urgency_level="normal",
                searchable_keywords=[],
                auto_generated_labels=[]
            ),
            
            overall_quality_score=0,
            requires_immediate_review=True,
            critical_issues=["Analysis failed - manual review required"],
            top_recommendations=["Manually review this recording"]
        )


# Singleton instance
_analyzer = None

def get_gemini_analyzer() -> GeminiCallAnalyzer:
    """Get or create Gemini analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = GeminiCallAnalyzer()
    return _analyzer