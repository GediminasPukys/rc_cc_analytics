"""
JSON parser for Gemini response to ComprehensiveCallAnalysis
Handles field name mapping and data transformation
"""

from typing import Dict, Any, List
from models import (
    ComprehensiveCallAnalysis,
    Language, EmotionalTone, ConversationStage,
    SatisfactionLevel, ProblemStatus, ConversationCategory,
    TranscriptionSegment, Transcription, Translation,
    EmotionalAnalysis, ConversationStructure,
    SatisfactionAnalysis, PolitenessAnalysis,
    ResolutionAnalysis, PauseAnalysis,
    ConversationSummary, ConversationCategorization,
    ToneMismatch, ResolutionAttempt
)


def safe_get(data: Dict, *keys, default=None):
    """Safely get nested dict values"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
    return data if data is not None else default


def parse_gemini_response(data, session_id: str, processing_duration_ms: int) -> ComprehensiveCallAnalysis:
    """
    Parse Gemini JSON response into ComprehensiveCallAnalysis
    Handles missing fields and type conversions
    """
    from datetime import datetime
    
    # Handle list response (take first item if it's a list)
    if isinstance(data, list):
        if len(data) > 0:
            data = data[0]
        else:
            data = {}
    
    # Ensure we have a dict
    if not isinstance(data, dict):
        data = {}
    
    # Parse transcription
    transcription_data = data.get('transcription', {})
    segments = []
    for seg in transcription_data.get('segments', []):
        try:
            segments.append(TranscriptionSegment(
                speaker=seg.get('speaker', 'agent'),
                text=seg.get('text', ''),
                start_time=float(seg.get('start_time', seg.get('timestamp_start', 0))),
                end_time=float(seg.get('end_time', seg.get('timestamp_end', 0))),
                confidence=float(seg.get('confidence', 0.9)),
                original_language=Language(transcription_data.get('original_language', 'unknown'))
            ))
        except:
            continue  # Skip invalid segments
    
    transcription = Transcription(
        original_language=Language(transcription_data.get('original_language', 'unknown')),
        segments=segments[:100],  # Limit segments
        full_text=transcription_data.get('full_text', ''),
        total_duration_seconds=float(transcription_data.get('total_duration_seconds', 0)),
        transcription_confidence=float(transcription_data.get('transcription_confidence', 0.9)),
        word_count=int(transcription_data.get('word_count', 0))
    )
    
    # Parse translation
    translation_data = data.get('translation', {})
    translated_segments = []
    for seg in translation_data.get('translated_segments', []):
        try:
            translated_segments.append(TranscriptionSegment(
                speaker=seg.get('speaker', 'agent'),
                text=seg.get('text', ''),
                start_time=float(seg.get('start_time', seg.get('timestamp_start', 0))),
                end_time=float(seg.get('end_time', seg.get('timestamp_end', 0))),
                confidence=0.95,
                original_language=Language(transcription_data.get('original_language', 'unknown'))
            ))
        except:
            continue
    
    translation = Translation(
        target_language="lt",
        translated_segments=translated_segments[:100],
        full_translated_text=translation_data.get('full_translated_text', ''),
        translation_notes=translation_data.get('translation_notes')
    )
    
    # Parse emotional analysis
    emotional_data = data.get('emotional_analysis', {})
    emotion_progression = []
    for prog in emotional_data.get('customer_emotion_progression', []):
        try:
            emotion_progression.append({
                'timestamp': float(prog.get('timestamp', 0)),
                'speaker': 'customer',
                'emotion': prog.get('emotion', 'neutral'),
                'intensity': float(prog.get('intensity', prog.get('confidence', 0.5))),
                'trigger_phrase': prog.get('trigger_phrase', prog.get('trigger'))
            })
        except:
            continue
    
    tone_mismatches = []
    for mismatch in emotional_data.get('tone_mismatches', []):
        try:
            tone_mismatches.append(ToneMismatch(
                timestamp=float(mismatch.get('timestamp', 0)),
                customer_tone=mismatch.get('customer_tone', 'neutral'),
                agent_tone=mismatch.get('agent_tone', 'neutral'),
                mismatch_severity=mismatch.get('mismatch_severity', 'medium'),
                recommendation=mismatch.get('recommendation', '')
            ))
        except:
            continue
    
    emotional_analysis = EmotionalAnalysis(
        customer_overall_emotion=EmotionalTone(emotional_data.get('customer_overall_emotion', 'neutral')),
        customer_emotion_progression=emotion_progression,
        customer_emotion_summary=emotional_data.get('customer_emotion_summary', ''),
        agent_overall_tone=EmotionalTone(emotional_data.get('agent_overall_tone', 'neutral')),
        agent_empathy_score=float(emotional_data.get('agent_empathy_score', 50)),
        agent_politeness_score=float(emotional_data.get('agent_politeness_score', 50)),
        agent_respect_score=float(emotional_data.get('agent_respect_score', 50)),
        tone_appropriateness_score=float(emotional_data.get('tone_appropriateness_score', 50)),
        tone_mismatches=tone_mismatches,
        recommendations=emotional_data.get('recommendations', [])
    )
    
    # Parse structure analysis
    structure_data = data.get('structure_analysis', {})
    detected_stages = []
    for stage in structure_data.get('detected_stages', []):
        try:
            detected_stages.append({
                'stage': stage.get('stage', 'greeting'),
                'present': stage.get('present', True),
                'start_time': float(stage.get('start_time', stage.get('timestamp_start', 0))),
                'end_time': float(stage.get('end_time', stage.get('timestamp_end', 0))),
                'quality_score': float(stage.get('quality_score', 75)),
                'deviations': stage.get('deviations', [])
            })
        except:
            continue
    
    structure_analysis = ConversationStructure(
        detected_stages=detected_stages,
        expected_stages=structure_data.get('expected_stages', []),
        missing_stages=structure_data.get('missing_stages', []),
        out_of_order_stages=structure_data.get('out_of_order_stages', []),
        structure_compliance_score=float(structure_data.get('structure_compliance_score', 50)),
        major_deviations=structure_data.get('major_deviations', []),
        structure_summary=structure_data.get('structure_summary', '')
    )
    
    # Parse satisfaction analysis
    satisfaction_data = data.get('satisfaction_analysis', {})
    satisfaction_indicators = []
    for ind in satisfaction_data.get('satisfaction_indicators', []):
        try:
            satisfaction_indicators.append({
                'timestamp': float(ind.get('timestamp', 0)),
                'indicator_type': ind.get('indicator_type', 'phrase'),
                'content': ind.get('content', ind.get('indicator', '')),
                'impact': ind.get('impact', ind.get('sentiment', 'neutral')),
                'confidence': float(ind.get('confidence', ind.get('weight', 0.5)))
            })
        except:
            continue
    
    satisfaction_analysis = SatisfactionAnalysis(
        overall_satisfaction=SatisfactionLevel(satisfaction_data.get('overall_satisfaction', 'neutral')),
        satisfaction_score=float(satisfaction_data.get('satisfaction_score', 50)),
        satisfaction_indicators=satisfaction_indicators,
        positive_signals=satisfaction_data.get('positive_signals', []),
        negative_signals=satisfaction_data.get('negative_signals', []),
        satisfaction_trend=satisfaction_data.get('satisfaction_trend', 'stable'),
        end_call_satisfaction=SatisfactionLevel(satisfaction_data.get('end_call_satisfaction', 'neutral')),
        requires_follow_up=bool(satisfaction_data.get('requires_follow_up', False)),
        follow_up_reason=satisfaction_data.get('follow_up_reason')
    )
    
    # Parse politeness analysis
    politeness_data = data.get('politeness_analysis', {})
    detected_elements = []
    for elem in politeness_data.get('detected_elements', []):
        try:
            # Map element types
            elem_type = elem.get('element_type', 'greeting')
            if elem_type == 'courtesy':
                elem_type = 'courtesy_phrase'
            
            detected_elements.append({
                'element_type': elem_type,
                'speaker': elem.get('speaker', 'agent') if elem.get('speaker') != 'system' else 'agent',
                'timestamp': float(elem.get('timestamp', 0)),
                'text': elem.get('text', ''),
                'culturally_appropriate': bool(elem.get('culturally_appropriate', True))
            })
        except:
            continue
    
    politeness_analysis = PolitenessAnalysis(
        detected_elements=detected_elements,
        agent_greeting_present=bool(politeness_data.get('agent_greeting_present', False)),
        agent_farewell_present=bool(politeness_data.get('agent_farewell_present', False)),
        agent_thanks_present=bool(politeness_data.get('agent_thanks_present', False)),
        agent_apologies_count=int(politeness_data.get('agent_apologies_count', 0)),
        customer_greeting_present=bool(politeness_data.get('customer_greeting_present', False)),
        customer_farewell_present=bool(politeness_data.get('customer_farewell_present', False)),
        customer_thanks_present=bool(politeness_data.get('customer_thanks_present', False)),
        politeness_score=float(politeness_data.get('politeness_score', 50)),
        missing_required_elements=politeness_data.get('missing_required_elements', []),
        cultural_appropriateness_score=float(politeness_data.get('cultural_appropriateness_score', 50)),
        recommendations=politeness_data.get('recommendations', [])
    )
    
    # Parse resolution analysis
    resolution_data = data.get('resolution_analysis', {})
    resolution_attempts = []
    for attempt in resolution_data.get('resolution_attempts', []):
        try:
            resolution_attempts.append(ResolutionAttempt(
                timestamp=str(attempt.get('timestamp', '0')),
                action=attempt.get('action', ''),
                success=str(attempt.get('success', 'false'))
            ))
        except:
            continue
    
    resolution_analysis = ResolutionAnalysis(
        problem_statement=resolution_data.get('problem_statement') or 'Not identified',
        problem_category=ConversationCategory(resolution_data.get('problem_category', 'other')),
        resolution_status=ProblemStatus(resolution_data.get('resolution_status', 'pending')),
        resolution_confidence=float(resolution_data.get('resolution_confidence', 0.5)),
        unresolved_indicators=resolution_data.get('unresolved_indicators', []),
        resolution_attempts=resolution_attempts,
        customer_confirmation_of_resolution=bool(resolution_data.get('customer_confirmation_of_resolution', False)),
        requires_escalation=bool(resolution_data.get('requires_escalation', False)),
        escalation_reason=resolution_data.get('escalation_reason'),
        recommended_next_steps=resolution_data.get('recommended_next_steps', []),
        supervisor_review_required=bool(resolution_data.get('supervisor_review_required', False)),
        review_priority=resolution_data.get('review_priority', 'medium')
    )
    
    # Parse pause analysis
    pause_data = data.get('pause_analysis', {})
    long_pauses = []
    for pause in pause_data.get('long_pauses', []):
        try:
            long_pauses.append({
                'timestamp_start': float(pause.get('timestamp_start', 0)),
                'timestamp_end': float(pause.get('timestamp_end', 0)),
                'duration': float(pause.get('duration', 0)),
                'announced': bool(pause.get('announced', False)),
                'announcement': pause.get('announcement', ''),
                'reason': pause.get('reason', '')
            })
        except:
            continue
    
    pause_analysis = PauseAnalysis(
        total_pauses=int(pause_data.get('total_pauses', 0)),
        long_pauses=long_pauses,
        total_pause_duration=float(pause_data.get('total_pause_duration', 0)),
        average_pause_duration=float(pause_data.get('average_pause_duration', 0)),
        longest_pause_duration=float(pause_data.get('longest_pause_duration', 0)),
        unannounced_long_pauses=int(pause_data.get('unannounced_long_pauses', 0)),
        compliance_score=float(pause_data.get('compliance_score', 100)),
        pause_handling_issues=pause_data.get('pause_handling_issues', []),
        recommendations=pause_data.get('recommendations', [])
    )
    
    # Parse summary
    summary_data = data.get('summary', {})
    summary = ConversationSummary(
        summary_lt=summary_data.get('summary_lt', ''),
        key_points_lt=summary_data.get('key_points_lt', []),
        customer_request=summary_data.get('customer_request') or 'Not identified',
        actions_taken=summary_data.get('actions_taken', []),
        outcome=summary_data.get('outcome', ''),
        follow_up_required=bool(summary_data.get('follow_up_required', False)),
        follow_up_actions=summary_data.get('follow_up_actions', []),
        agent_performance_notes=summary_data.get('agent_performance_notes', ''),
        improvement_suggestions=summary_data.get('improvement_suggestions', [])
    )
    
    # Parse categorization
    categorization_data = data.get('categorization', {})
    categorization = ConversationCategorization(
        primary_category=ConversationCategory(categorization_data.get('primary_category', 'other')),
        secondary_categories=categorization_data.get('secondary_categories', []),
        tags=categorization_data.get('tags', []),
        customer_type=categorization_data.get('customer_type', 'unknown'),
        service_mentioned=categorization_data.get('service_mentioned', []),
        urgency_level=categorization_data.get('urgency_level', 'normal'),
        searchable_keywords=categorization_data.get('searchable_keywords', []),
        auto_generated_labels=categorization_data.get('auto_generated_labels', [])
    )
    
    # Create the comprehensive analysis
    return ComprehensiveCallAnalysis(
        session_id=session_id,
        analysis_timestamp=datetime.now(),
        processing_duration_ms=processing_duration_ms,
        transcription=transcription,
        translation=translation,
        emotional_analysis=emotional_analysis,
        structure_analysis=structure_analysis,
        satisfaction_analysis=satisfaction_analysis,
        politeness_analysis=politeness_analysis,
        resolution_analysis=resolution_analysis,
        pause_analysis=pause_analysis,
        summary=summary,
        categorization=categorization,
        overall_quality_score=float(data.get('overall_quality_score', 50)),
        requires_immediate_review=bool(data.get('requires_immediate_review', False)),
        critical_issues=data.get('critical_issues', []),
        top_recommendations=data.get('top_recommendations', [])
    )