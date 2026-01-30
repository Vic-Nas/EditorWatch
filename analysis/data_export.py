"""
Data export module for EditorWatch
Generates clean, structured data suitable for LLM analysis (e.g., Ollama, Claude, etc.)
"""

import json
from datetime import datetime


def export_for_llm_analysis(submission, analysis, events, file_risks):
    """
    Export comprehensive, clean data in a format optimized for LLM analysis.
    
    Returns: dict with structured, human-readable data
    """
    
    # Parse events into human-readable format
    event_summary = _summarize_events(events)
    
    # Create session breakdown
    sessions = _create_session_breakdown(events)
    
    # File-by-file analysis
    file_analysis = _create_file_analysis(events, file_risks)
    
    # Timeline of significant events
    timeline = _create_timeline_narrative(events)
    
    # Metrics interpretation
    metrics_interpretation = _interpret_metrics(analysis)
    
    return {
        "metadata": {
            "student_email": submission.email,
            "assignment_id": submission.assignment_id,
            "submission_time": submission.submitted_at.isoformat(),
            "analysis_version": "2.0"
        },
        
        "summary": {
            "total_events": len(events),
            "total_characters_written": sum(e['char_count'] for e in events if e['type'] == 'insert'),
            "total_characters_deleted": sum(e['char_count'] for e in events if e['type'] == 'delete'),
            "coding_duration_minutes": round((events[-1]['timestamp'] - events[0]['timestamp']) / 1000 / 60, 1) if events else 0,
            "number_of_files": len(set(e.get('file', '') for e in events)),
            "event_summary": event_summary
        },
        
        "work_sessions": sessions,
        
        "file_by_file_analysis": file_analysis,
        
        "timeline_narrative": timeline,
        
        "metrics": {
            "raw_scores": {
                "incremental_score": analysis.incremental_score,
                "typing_variance": analysis.typing_variance,
                "error_correction_ratio": analysis.error_correction_ratio,
                "paste_burst_count": analysis.paste_burst_count
            },
            "interpretation": metrics_interpretation
        },
        
        "flags": json.loads(analysis.flags) if analysis.flags else [],
        
        "raw_events": _clean_events_for_export(events)
    }


def _summarize_events(events):
    """Create high-level event summary"""
    event_types = {}
    for e in events:
        event_type = e['type']
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    return {
        "insert_events": event_types.get('insert', 0),
        "delete_events": event_types.get('delete', 0),
        "save_events": event_types.get('save', 0),
        "large_paste_events": sum(1 for e in events if e['type'] == 'insert' and e['char_count'] > 100)
    }


def _create_session_breakdown(events):
    """Break down work into distinct sessions"""
    if not events:
        return []
    
    sessions = []
    current_session = []
    last_time = events[0]['timestamp']
    
    for event in events:
        gap_minutes = (event['timestamp'] - last_time) / 1000 / 60
        
        # 5+ minute gap = new session
        if gap_minutes > 5 and current_session:
            sessions.append(_summarize_session(current_session))
            current_session = []
        
        current_session.append(event)
        last_time = event['timestamp']
    
    if current_session:
        sessions.append(_summarize_session(current_session))
    
    return sessions


def _summarize_session(session_events):
    """Summarize a single work session"""
    if not session_events:
        return None
    
    start_time = session_events[0]['timestamp']
    end_time = session_events[-1]['timestamp']
    duration_minutes = (end_time - start_time) / 1000 / 60
    
    inserts = [e for e in session_events if e['type'] == 'insert']
    deletes = [e for e in session_events if e['type'] == 'delete']
    
    chars_added = sum(e['char_count'] for e in inserts)
    chars_removed = sum(e['char_count'] for e in deletes)
    
    files = list(set(e.get('file', 'unknown').split('/')[-1] for e in session_events))
    
    large_pastes = [e for e in inserts if e['char_count'] > 100]
    
    return {
        "duration_minutes": round(duration_minutes, 1),
        "event_count": len(session_events),
        "characters_added": chars_added,
        "characters_removed": chars_removed,
        "files_worked_on": files,
        "large_paste_count": len(large_pastes),
        "average_chars_per_insert": round(chars_added / len(inserts), 1) if inserts else 0,
        "summary": f"{len(session_events)} events, {chars_added} chars added, {len(files)} file(s)"
    }


def _create_file_analysis(events, file_risks):
    """Create detailed per-file analysis"""
    file_data = {}
    
    for event in events:
        filename = event.get('file', 'unknown').split('/')[-1]
        if filename not in file_data:
            file_data[filename] = {
                'events': [],
                'chars_added': 0,
                'chars_deleted': 0,
                'save_count': 0
            }
        
        file_data[filename]['events'].append({
            'type': event['type'],
            'timestamp': event['timestamp'],
            'char_count': event.get('char_count', 0)
        })
        
        if event['type'] == 'insert':
            file_data[filename]['chars_added'] += event['char_count']
        elif event['type'] == 'delete':
            file_data[filename]['chars_deleted'] += event['char_count']
        elif event['type'] == 'save':
            file_data[filename]['save_count'] += 1
    
    # Combine with risk analysis
    result = {}
    for filename, data in file_data.items():
        risk_info = file_risks.get(filename, {})
        
        first_event = data['events'][0]['timestamp'] if data['events'] else 0
        last_event = data['events'][-1]['timestamp'] if data['events'] else 0
        development_time = (last_event - first_event) / 1000 / 60
        
        result[filename] = {
            "total_events": len(data['events']),
            "characters_added": data['chars_added'],
            "characters_deleted": data['chars_deleted'],
            "save_count": data['save_count'],
            "development_time_minutes": round(development_time, 1),
            "risk_level": risk_info.get('risk', 'unknown'),
            "risk_issues": risk_info.get('issues', []),
            "edit_ratio": risk_info.get('edit_ratio', 0),
            "paste_count": risk_info.get('paste_count', 0)
        }
    
    return result


def _create_timeline_narrative(events):
    """Create human-readable narrative of what happened when"""
    if not events:
        return []
    
    narrative = []
    start_time = events[0]['timestamp']
    
    # Group into logical chunks (every 10 minutes or significant event)
    current_time = start_time
    time_window = 10 * 60 * 1000  # 10 minutes
    
    while current_time < events[-1]['timestamp']:
        window_end = current_time + time_window
        window_events = [e for e in events if current_time <= e['timestamp'] < window_end]
        
        if window_events:
            elapsed = (current_time - start_time) / 1000 / 60
            
            inserts = [e for e in window_events if e['type'] == 'insert']
            deletes = [e for e in window_events if e['type'] == 'delete']
            
            chars_added = sum(e['char_count'] for e in inserts)
            large_pastes = [e for e in inserts if e['char_count'] > 100]
            
            files = list(set(e.get('file', '').split('/')[-1] for e in window_events))
            
            description = f"At {elapsed:.0f} minutes: "
            if large_pastes:
                description += f"{len(large_pastes)} large paste(s) ({sum(e['char_count'] for e in large_pastes)} chars), "
            description += f"{chars_added} chars added, {len(deletes)} deletions"
            if files:
                description += f" in {', '.join(files)}"
            
            narrative.append({
                "time_offset_minutes": round(elapsed, 1),
                "description": description,
                "event_count": len(window_events),
                "suspicious": len(large_pastes) > 2
            })
        
        current_time += time_window
    
    return narrative


def _interpret_metrics(analysis):
    """Provide human interpretation of metric scores"""
    interpretations = {}
    
    # Incremental score
    inc_score = analysis.incremental_score
    if inc_score > 0.7:
        interpretations['incremental_score'] = "GOOD: Code developed gradually over time"
    elif inc_score > 0.4:
        interpretations['incremental_score'] = "CONCERNING: Mix of gradual work and sudden insertions"
    else:
        interpretations['incremental_score'] = "BAD: Code appeared in large chunks, not typed gradually"
    
    # Typing variance
    var_score = analysis.typing_variance
    if var_score > 0.3:
        interpretations['typing_variance'] = "GOOD: Natural variation in typing patterns"
    elif var_score > 0.15:
        interpretations['typing_variance'] = "CONCERNING: Somewhat consistent typing (borderline)"
    else:
        interpretations['typing_variance'] = "BAD: Too consistent - suggests automated/pasted content"
    
    # Error correction ratio
    err_ratio = analysis.error_correction_ratio
    if err_ratio > 0.15:
        interpretations['error_correction_ratio'] = "GOOD: Appropriate trial and error, making corrections"
    elif err_ratio > 0.05:
        interpretations['error_correction_ratio'] = "CONCERNING: Few corrections made"
    else:
        interpretations['error_correction_ratio'] = "BAD: Almost no corrections - code appeared 'perfect' immediately"
    
    # Paste bursts
    bursts = analysis.paste_burst_count
    if bursts == 0:
        interpretations['paste_burst_count'] = "GOOD: No paste burst events detected"
    elif bursts <= 2:
        interpretations['paste_burst_count'] = "CONCERNING: Some paste bursts detected"
    else:
        interpretations['paste_burst_count'] = f"BAD: {bursts} paste burst events - multiple large code blocks pasted rapidly"
    
    return interpretations


def _clean_events_for_export(events):
    """Clean and format raw events for export"""
    cleaned = []
    start_time = events[0]['timestamp'] if events else 0
    
    for e in events:
        cleaned.append({
            "time_offset_seconds": round((e['timestamp'] - start_time) / 1000, 1),
            "type": e['type'],
            "file": e.get('file', 'unknown').split('/')[-1],
            "character_count": e.get('char_count', 0)
        })
    
    return cleaned


def export_to_json(submission, analysis, events, file_risks, filepath):
    """
    Export data to JSON file for external LLM analysis.
    
    Args:
        submission: Submission object
        analysis: AnalysisResult object
        events: List of event dicts
        file_risks: File risk analysis dict
        filepath: Path to save JSON file
    """
    data = export_for_llm_analysis(submission, analysis, events, file_risks)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath


def generate_llm_prompt(submission, analysis, events, file_risks):
    """
    Generate a prompt suitable for LLM analysis.
    Can be used with Ollama, Claude API, etc.
    
    Returns: string prompt
    """
    data = export_for_llm_analysis(submission, analysis, events, file_risks)
    
    prompt = f"""# Academic Integrity Analysis Request

## Student Submission
- Student: {data['metadata']['student_email']}
- Assignment: {data['metadata']['assignment_id']}
- Submitted: {data['metadata']['submission_time']}

## Summary Statistics
- Total coding time: {data['summary']['coding_duration_minutes']} minutes
- Total characters written: {data['summary']['total_characters_written']:,}
- Total characters deleted: {data['summary']['total_characters_deleted']:,}
- Files edited: {data['summary']['number_of_files']}
- Large paste events: {data['summary']['event_summary']['large_paste_events']}

## Automated Analysis Results

### Metrics (0.0 = suspicious, 1.0 = authentic)
- Incremental Score: {data['metrics']['raw_scores']['incremental_score']:.2f} - {data['metrics']['interpretation']['incremental_score']}
- Typing Variance: {data['metrics']['raw_scores']['typing_variance']:.2f} - {data['metrics']['interpretation']['typing_variance']}
- Error Correction: {data['metrics']['raw_scores']['error_correction_ratio']:.2f} - {data['metrics']['interpretation']['error_correction_ratio']}
- Paste Bursts: {data['metrics']['raw_scores']['paste_burst_count']} - {data['metrics']['interpretation']['paste_burst_count']}

### Automated Flags
{_format_flags_for_llm(data['flags'])}

### Work Sessions
{_format_sessions_for_llm(data['work_sessions'])}

### File Analysis
{_format_file_analysis_for_llm(data['file_by_file_analysis'])}

## Your Task
Based on this data, provide:
1. **Overall Assessment**: Is this submission likely authentic, suspicious, or clearly problematic?
2. **Key Evidence**: What are the 3 most important pieces of evidence supporting your assessment?
3. **Recommendation**: What should the instructor do? (Accept, review with student, investigate further, reject)
4. **Confidence Level**: How confident are you in this assessment? (Low/Medium/High)

Please provide a balanced analysis considering both suspicious and authentic indicators.
"""
    
    return prompt


def _format_flags_for_llm(flags):
    """Format flags for LLM prompt"""
    if not flags:
        return "No flags generated"
    
    output = []
    for flag in flags:
        severity_emoji = {
            'high': '🔴 HIGH',
            'medium': '🟡 MEDIUM',
            'low': '🔵 LOW',
            'none': '🟢 CLEAN'
        }
        output.append(f"- {severity_emoji.get(flag['severity'], flag['severity'])}: [{flag['category']}] {flag['message']}")
    
    return '\n'.join(output)


def _format_sessions_for_llm(sessions):
    """Format work sessions for LLM prompt"""
    if not sessions:
        return "No distinct work sessions detected"
    
    output = [f"Total sessions: {len(sessions)}\n"]
    for i, session in enumerate(sessions, 1):
        output.append(f"Session {i}: {session['summary']}")
        if session['large_paste_count'] > 0:
            output[-1] += f" ⚠️ {session['large_paste_count']} large paste(s)"
    
    return '\n'.join(output)


def _format_file_analysis_for_llm(file_analysis):
    """Format file analysis for LLM prompt"""
    if not file_analysis:
        return "No files analyzed"
    
    output = []
    for filename, data in file_analysis.items():
        risk_emoji = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }
        emoji = risk_emoji.get(data['risk_level'], '❓')
        
        output.append(f"{emoji} {filename}:")
        output.append(f"  - {data['characters_added']:,} chars added in {data['development_time_minutes']:.1f} minutes")
        output.append(f"  - {data['paste_count']} large pastes, {data['edit_ratio']:.1%} edit ratio")
        if data['risk_issues']:
            output.append(f"  - Issues: {'; '.join(data['risk_issues'])}")
    
    return '\n'.join(output)