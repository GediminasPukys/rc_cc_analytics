"""
Pydantic models for conversation analysis
Focus on pause detection and unresolved issues
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class PauseAnnouncementStatus(str, Enum):
    PROPERLY_ANNOUNCED = "properly_announced"
    NOT_ANNOUNCED = "not_announced"
    UNCLEAR = "unclear"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNCLEAR = "unclear"
    PARTIAL = "partial"


class ConversationPause(BaseModel):
    """Represents a pause in the conversation"""
    timestamp_start: float = Field(description="Start time of the pause in seconds")
    timestamp_end: float = Field(description="End time of the pause in seconds")
    duration_seconds: float = Field(description="Duration of pause in seconds")
    announcement_status: str = Field(
        description="Whether the customer was properly informed about the pause: properly_announced, not_announced, or unclear"
    )
    announcement_text: Optional[str] = Field(
        default=None,
        description="What was said to announce the pause, if anything"
    )
    context_before: str = Field(
        description="What was said immediately before the pause"
    )
    context_after: str = Field(
        description="What was said immediately after the pause"
    )
    compliance_issue: bool = Field(
        description="True if this pause violates compliance (>1 min without announcement)"
    )
    recommendation: Optional[str] = Field(
        default=None,
        description="Recommendation for handling similar pauses"
    )


class PolitenessElement(BaseModel):
    """Represents a politeness element in conversation"""
    element_type: str = Field(
        description="Type of politeness element: greeting, farewell, thanks, apology, courtesy_phrase"
    )
    speaker: str = Field(
        description="Who said it: agent or customer"
    )
    timestamp: float = Field(
        description="When it was said in seconds"
    )
    text: str = Field(
        description="Exact text of the politeness element"
    )
    appropriateness: str = Field(
        description="How appropriate it was: excellent, good, adequate, poor, missing"
    )


class SatisfactionSignal(BaseModel):
    """Customer satisfaction signal detected"""
    timestamp: float = Field(
        description="When the signal was detected"
    )
    signal_type: str = Field(
        description="Type of signal: positive, negative, neutral"
    )
    phrase: str = Field(
        description="Exact phrase indicating satisfaction level"
    )
    confidence: float = Field(
        description="Confidence level 0-100"
    )


class EmotionalToneEvaluation(BaseModel):
    """Evaluation of emotional tones in conversation"""
    customer_tone: str = Field(
        description="Customer's emotional tone: angry, frustrated, neutral, satisfied, happy"
    )
    agent_tone: str = Field(
        description="Agent's emotional tone: empathetic, professional, neutral, cold, inappropriate"
    )
    tone_appropriateness: str = Field(
        description="How appropriate agent's tone was: excellent, good, adequate, poor, very_poor"
    )
    empathy_score: float = Field(
        description="Agent empathy score 0-100"
    )
    politeness_score: float = Field(
        description="Agent politeness score 0-100"
    )
    respect_score: float = Field(
        description="Agent respect score 0-100"
    )
    tone_mismatches: List[str] = Field(
        default_factory=list,
        description="List of moments where agent's tone was inappropriate"
    )


class UnresolvedIssue(BaseModel):
    """Represents an unresolved customer issue"""
    timestamp: float = Field(description="When the issue was expressed")
    customer_statement: str = Field(
        description="Exact customer statement indicating unresolved issue, it should be presented in Lithuanian language"
    )
    issue_description: str = Field(
        description="Brief description of the unresolved issue, it should be presented in Lithuanian language"
    )
    agent_response: Optional[str] = Field(
        default=None,
        description="How the agent responded to the unresolved issue, it should be presented in Lithuanian language"
    )
    severity: str = Field(
        description="Severity level: low, medium, high, critical"
    )
    requires_followup: bool = Field(
        description="Whether this requires immediate follow-up"
    )


class ConversationStage(BaseModel):
    """Represents a stage in the conversation structure"""
    stage_type: str = Field(
        description="Type of stage: greeting, problem_identification, problem_analysis, solution_presentation, closure, other"
    )
    start_time: float = Field(
        description="Start timestamp of the stage in seconds"
    )
    end_time: float = Field(
        description="End timestamp of the stage in seconds"
    )
    text_snippet: str = Field(
        description="Representative text from this stage"
    )
    speaker: str = Field(
        description="Primary speaker in this stage: agent, customer, both"
    )
    completeness: str = Field(
        description="How complete this stage is: complete, partial, missing, unclear"
    )
    quality_score: float = Field(
        description="Quality score for this stage 0-100"
    )
    deviations: List[str] = Field(
        default_factory=list,
        description="List of deviations from standard for this stage"
    )


class ConversationStructureAnalysis(BaseModel):
    """Analysis of conversation structure and flow"""
    stages_identified: List[ConversationStage] = Field(
        default_factory=list,
        description="List of conversation stages identified"
    )
    expected_flow: List[str] = Field(
        default_factory=list,
        description="Expected conversation flow: greeting -> problem_identification -> problem_analysis -> solution_presentation -> closure"
    )
    actual_flow: List[str] = Field(
        default_factory=list,
        description="Actual conversation flow detected"
    )
    flow_deviations: List[str] = Field(
        default_factory=list,
        description="Deviations from expected flow"
    )
    missing_stages: List[str] = Field(
        default_factory=list,
        description="Expected stages that are missing"
    )
    structure_score: float = Field(
        description="Overall conversation structure score 0-100"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improving conversation structure"
    )


class ConversationAnalysisResult(BaseModel):
    """Complete analysis result for a conversation"""
    
    # Pause Analysis
    total_pauses: int = Field(description="Total number of pauses detected longer then 60 seconds")
    long_pauses: List[ConversationPause] = Field(
        default_factory=list,
        description="List of pauses longer than 1 minute (60 seconds)"
    )
    compliance_violations: int = Field(
        description="Number of pauses that violate compliance (longer than 1 minute (60 seconds))"
    )
    pause_compliance_score: float = Field(
        description="Score from 0-100 for pause handling compliance"
    )
    
    # Resolution Analysis
    resolution_status: str = Field(
        description="Overall resolution status: resolved, unresolved, unclear, or partial. It should be presented in Lithuanian language."
    )
    unresolved_issues: List[UnresolvedIssue] = Field(
        default_factory=list,
        description="List of unresolved customer issues"
    )
    customer_satisfaction_indicators: List[str] = Field(
        default_factory=list,
        description="Phrases indicating satisfaction or dissatisfaction"
    )
    requires_review: bool = Field(
        description="Whether this conversation requires additional review"
    )
    review_priority: str = Field(
        description="Priority for review: low, medium, high, urgent"
    )
    review_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons why review is needed"
    )
    
    # Politeness Analysis
    politeness_elements: List[PolitenessElement] = Field(
        default_factory=list,
        description="List of politeness elements found in conversation"
    )
    has_greeting: bool = Field(
        description="Whether conversation has proper greeting"
    )
    has_farewell: bool = Field(
        description="Whether conversation has proper farewell"
    )
    has_thanks: bool = Field(
        description="Whether thanks were expressed"
    )
    politeness_score: float = Field(
        description="Overall politeness score 0-100"
    )
    
    # Satisfaction Analysis
    satisfaction_signals: List[SatisfactionSignal] = Field(
        default_factory=list,
        description="Customer satisfaction signals detected"
    )
    final_satisfaction: str = Field(
        description="Final customer satisfaction level: very_satisfied, satisfied, neutral, dissatisfied, very_dissatisfied"
    )
    
    # Emotional Tone Analysis
    tone_evaluation: EmotionalToneEvaluation = Field(
        description="Evaluation of emotional tones in conversation"
    )
    
    # Conversation Structure Analysis
    structure_analysis: ConversationStructureAnalysis = Field(
        description="Analysis of conversation structure and flow"
    )
    
    # Summary
    analysis_summary: str = Field(
        description="Brief summary of the analysis findings, it should be presented in Lithuanian language"
    )
    key_findings: List[str] = Field(
        default_factory=list,
        description="Key findings from the analysis, it should be presented in Lithuanian language"
    )
    
    # Metadata
    session_id: str = Field(description="Session ID analyzed")
    analysis_timestamp: str = Field(description="When analysis was performed")
    total_conversation_duration: float = Field(
        description="Total duration of conversation in seconds"
    )