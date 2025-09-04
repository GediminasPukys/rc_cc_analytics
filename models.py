"""
Pydantic models for structured Gemini API outputs
Detailed schemas for call analysis requirements
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Literal
from datetime import datetime
from enum import Enum


# Enums for structured categories
class Language(str, Enum):
    LITHUANIAN = "lt"
    ENGLISH = "en"
    RUSSIAN = "ru"
    POLISH = "pl"
    UNKNOWN = "unknown"


class EmotionalTone(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    SATISFIED = "satisfied"
    CONFUSED = "confused"


class ConversationStage(str, Enum):
    GREETING = "greeting"
    PROBLEM_IDENTIFICATION = "problem_identification"
    INFORMATION_GATHERING = "information_gathering"
    SOLUTION_PRESENTATION = "solution_presentation"
    PROBLEM_RESOLUTION = "problem_resolution"
    CLOSURE = "closure"
    FAREWELL = "farewell"


class SatisfactionLevel(str, Enum):
    VERY_SATISFIED = "very_satisfied"
    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    DISSATISFIED = "dissatisfied"
    VERY_DISSATISFIED = "very_dissatisfied"


class ProblemStatus(str, Enum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    UNRESOLVED = "unresolved"
    ESCALATED = "escalated"
    PENDING = "pending"


class ConversationCategory(str, Enum):
    GENERAL_INFO = "general_info"
    APPLICATION_INQUIRY = "application_inquiry"
    TECHNICAL_SUPPORT = "technical_support"
    BILLING_ISSUE = "billing_issue"
    COMPLAINT = "complaint"
    SERVICE_REQUEST = "service_request"
    CANCELLATION = "cancellation"
    OTHER = "other"


# Detailed models for each requirement

class TranscriptionSegment(BaseModel):
    """Individual segment of transcription"""
    speaker: Literal["customer", "agent", "system"]
    text: str
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    confidence: float = Field(description="Transcription confidence between 0.0 and 1.0")
    original_language: Language


class Transcription(BaseModel):
    """R_Base: Complete transcription in original language"""
    original_language: Language
    segments: List[TranscriptionSegment]
    full_text: str = Field(description="Complete transcription as single text")
    total_duration_seconds: float
    transcription_confidence: float = Field(description="Overall transcription confidence between 0.0 and 1.0")
    word_count: int
    
    @validator('word_count', always=True)
    def calculate_word_count(cls, v, values):
        if 'full_text' in values:
            return len(values['full_text'].split())
        return v


class Translation(BaseModel):
    """R_Translation: Lithuanian translation of the conversation"""
    target_language: str = Field(description="Target language for translation (always 'lt')")
    translated_segments: List[TranscriptionSegment]
    full_translated_text: str
    translation_notes: Optional[str] = Field(
        description="Notes about idioms, context, or untranslatable elements"
    )


class ToneMismatch(BaseModel):
    """Tone mismatch instance"""
    timestamp: float
    customer_tone: str
    agent_tone: str
    mismatch_severity: Literal["low", "medium", "high"]
    recommendation: str


class ResolutionAttempt(BaseModel):
    """Single resolution attempt by agent"""
    timestamp: str
    action: str
    success: str


class EmotionalAnalysis(BaseModel):
    """R_13: Emotional Tone Assessment"""
    
    class EmotionalMoment(BaseModel):
        timestamp: float
        speaker: Literal["customer", "agent"]
        emotion: EmotionalTone
        intensity: float = Field(description="Emotional intensity between 0.0 and 1.0")
        trigger_phrase: Optional[str]
    
    customer_overall_emotion: EmotionalTone
    customer_emotion_progression: List[EmotionalMoment]
    customer_emotion_summary: str
    
    agent_overall_tone: EmotionalTone
    agent_empathy_score: float = Field(description="Empathy level 0-100")
    agent_politeness_score: float = Field(description="Politeness level 0-100")
    agent_respect_score: float = Field(description="Respect level 0-100")
    
    tone_appropriateness_score: float = Field(description="Tone appropriateness score 0-100")
    tone_mismatches: List[ToneMismatch] = Field(
        description="Moments where agent tone was inappropriate"
    )
    recommendations: List[str] = Field(
        description="Specific recommendations for tone improvement"
    )


class ConversationStructure(BaseModel):
    """R_14: Conversation Structure Classification"""
    
    class StageOccurrence(BaseModel):
        stage: ConversationStage
        present: bool
        start_time: Optional[float]
        end_time: Optional[float]
        quality_score: float = Field(description="Stage quality score 0-100")
        deviations: List[str] = Field(description="Deviations from standard")
    
    detected_stages: List[StageOccurrence]
    expected_stages: List[ConversationStage]
    missing_stages: List[ConversationStage]
    out_of_order_stages: List[ConversationStage]
    structure_compliance_score: float = Field(description="Structure compliance score 0-100")
    major_deviations: List[str]
    structure_summary: str


class SatisfactionAnalysis(BaseModel):
    """R_15: Customer Satisfaction Detection"""
    
    class SatisfactionIndicator(BaseModel):
        timestamp: float
        indicator_type: Literal["phrase", "sentiment", "tone"]
        content: str
        impact: Literal["positive", "negative", "neutral"]
        confidence: float = Field(description="Indicator confidence between 0.0 and 1.0")
    
    overall_satisfaction: SatisfactionLevel
    satisfaction_score: float = Field(description="Customer satisfaction score 0-100")
    satisfaction_indicators: List[SatisfactionIndicator]
    
    positive_signals: List[str] = Field(description="Positive satisfaction phrases detected")
    negative_signals: List[str] = Field(description="Negative satisfaction phrases detected")
    
    satisfaction_trend: Literal["improving", "stable", "declining"]
    end_call_satisfaction: SatisfactionLevel
    requires_follow_up: bool
    follow_up_reason: Optional[str]


class PolitenessAnalysis(BaseModel):
    """R_16: Politeness Elements Analysis"""
    
    class PolitenessElement(BaseModel):
        element_type: Literal["greeting", "farewell", "thanks", "apology", "please", "courtesy_phrase"]
        text: str
        speaker: Literal["customer", "agent"]
        timestamp: float
        culturally_appropriate: bool = Field(
            description="Whether the element is appropriate for Lithuanian culture"
        )
    
    detected_elements: List[PolitenessElement]
    
    agent_greeting_present: bool
    agent_farewell_present: bool
    agent_thanks_present: bool
    agent_apologies_count: int
    
    customer_greeting_present: bool
    customer_farewell_present: bool
    customer_thanks_present: bool
    
    politeness_score: float = Field(description="Overall politeness score 0-100")
    missing_required_elements: List[str]
    cultural_appropriateness_score: float = Field(description="Cultural appropriateness score 0-100")
    recommendations: List[str]


class ResolutionAnalysis(BaseModel):
    """R_17: Unresolved Problem Detection"""
    
    problem_statement: str = Field(description="Customer's main problem/question")
    problem_category: ConversationCategory
    
    resolution_status: ProblemStatus
    resolution_confidence: float = Field(description="Resolution confidence between 0.0 and 1.0")
    
    unresolved_indicators: List[str] = Field(
        description="Phrases indicating problem not resolved"
    )
    resolution_attempts: List[ResolutionAttempt] = Field(
        description="Agent's attempts to resolve the issue"
    )
    
    customer_confirmation_of_resolution: bool
    requires_escalation: bool
    escalation_reason: Optional[str]
    recommended_next_steps: List[str]
    
    supervisor_review_required: bool
    review_priority: Literal["high", "medium", "low"]


class PauseAnalysis(BaseModel):
    """R_18: Long Pause Detection"""
    
    class Pause(BaseModel):
        start_time: float
        end_time: float
        duration_seconds: float
        announced: bool
        announcement_text: Optional[str]
        reason_given: Optional[str]
        customer_response: Optional[str]
    
    total_pauses: int
    long_pauses: List[Pause] = Field(
        description="Pauses longer than 60 seconds"
    )
    
    total_pause_duration: float
    average_pause_duration: float
    longest_pause_duration: float
    
    unannounced_long_pauses: int
    compliance_score: float = Field(description="Pause compliance score 0-100")
    
    pause_handling_issues: List[str]
    recommendations: List[str]


class ConversationSummary(BaseModel):
    """R_19: Post-Call Summary in Lithuanian"""
    
    summary_lt: str = Field(description="Comprehensive summary in Lithuanian")
    key_points_lt: List[str] = Field(description="Main discussion points in Lithuanian")
    
    customer_request: str = Field(description="What the customer wanted")
    actions_taken: List[str] = Field(description="What was done during the call")
    outcome: str = Field(description="Final result of the conversation")
    
    follow_up_required: bool
    follow_up_actions: List[str] = Field(description="Required follow-up actions")
    
    agent_performance_notes: str
    improvement_suggestions: List[str]


class ConversationCategorization(BaseModel):
    """Categorization for search and filtering"""
    
    primary_category: ConversationCategory
    secondary_categories: List[ConversationCategory]
    
    tags: List[str] = Field(
        description="Searchable tags extracted from conversation"
    )
    
    customer_type: Literal["new", "existing", "vip", "problematic", "unknown"]
    
    service_mentioned: List[str] = Field(
        description="Services or products mentioned"
    )
    
    urgency_level: Literal["urgent", "normal", "low"]
    
    searchable_keywords: List[str]
    auto_generated_labels: List[str]


class ComprehensiveCallAnalysis(BaseModel):
    """Complete analysis output from Gemini 2.5 Pro"""
    
    # Basic information
    session_id: str
    analysis_timestamp: datetime = Field(description="Timestamp when analysis was performed")
    processing_duration_ms: int
    
    # Core outputs
    transcription: Transcription
    translation: Translation
    
    # Analysis outputs (R_13 to R_19)
    emotional_analysis: EmotionalAnalysis
    structure_analysis: ConversationStructure
    satisfaction_analysis: SatisfactionAnalysis
    politeness_analysis: PolitenessAnalysis
    resolution_analysis: ResolutionAnalysis
    pause_analysis: PauseAnalysis
    summary: ConversationSummary
    
    # Categorization and search
    categorization: ConversationCategorization
    
    # Overall metrics
    overall_quality_score: float = Field(
        description="Weighted average of all quality metrics (0-100)"
    )
    
    # Flags for immediate attention
    requires_immediate_review: bool
    critical_issues: List[str]
    
    # Recommendations
    top_recommendations: List[str] = Field(
        description="Top 3-5 actionable recommendations"
    )
    
    @validator('overall_quality_score', always=True)
    def calculate_overall_score(cls, v, values):
        """Calculate weighted average of all scores"""
        if all(k in values for k in ['emotional_analysis', 'structure_analysis', 
                                     'satisfaction_analysis', 'politeness_analysis']):
            scores = [
                values['emotional_analysis'].tone_appropriateness_score * 0.25,
                values['structure_analysis'].structure_compliance_score * 0.20,
                values['satisfaction_analysis'].satisfaction_score * 0.30,
                values['politeness_analysis'].politeness_score * 0.25
            ]
            return sum(scores)
        return v or 0.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }