"""
Simplified LLM export - lightweight structured data only
"""

import json


def export_for_llm_analysis(submission, analysis, event_data, file_risks):
    """
    Export minimal, structured data for LLM analysis.
    ~50 lines of JSON instead of 500+
    
    Returns: dict with lightweight structured data
    """
    # Handle both compact and legacy formats
    if isinstance(event_data, dict):
        events = event_data.get('events', [])
        base_time = event_data.get('base_time', 0)
        is_compact = events and isinstance(events[0], list)
    else:
        events = event_data
        base_time = 0
        is_compact = False
    
    # Calculate basic stats
    if is_compact:
        inserts = [e for e in events if e[1] == 'i']
        deletes = [e for e in events if e[1] == 'd']
        total_chars_added = sum(e[3] for e in inserts)
        total_chars_deleted = sum(e[3] for e in deletes)
        
        if events:
            duration_minutes = (events[-1][0]) / 1000 / 60  # Last delta in minutes
        else:
            duration_minutes = 0
    else:
        inserts = [e for e in events if e.get('type') == 'insert']
        deletes = [e for e in events if e.get('type') == 'delete']
        total_chars_added = sum(e.get('char_count', 0) for e in inserts)
        total_chars_deleted = sum(e.get('char_count', 0) for e in deletes)
        
        if events:
            duration_minutes = (events[-1].get('timestamp', 0) - events[0].get('timestamp', 0)) / 1000 / 60
        else:
            duration_minutes = 0
    
    # Parse flags
    flags = json.loads(analysis.flags) if analysis.flags else []
    top_flags = [f['message'] for f in flags[:3]]
    
    return {
        "student": submission.email,
        "assignment": submission.assignment_id,
        "submitted": submission.submitted_at.isoformat(),
        
        "stats": {
            "duration_min": round(duration_minutes, 1),
            "chars_added": total_chars_added,
            "chars_deleted": total_chars_deleted,
            "files_count": len(file_risks)
        },
        
        "scores": {
            "overall": analysis.overall_score,
            "incremental": analysis.incremental_score,
            "typing": analysis.typing_variance,
            "corrections": analysis.error_correction_ratio,
            "sessions": analysis.session_consistency if hasattr(analysis, 'session_consistency') else 0
        },
        
        "top_issues": top_flags,
        
        "files": {
            filename: {
                "risk": data['risk'],
                "chars": data['total_chars'],
                "pastes": data['paste_count']
            }
            for filename, data in file_risks.items()
        }
    }


def generate_llm_prompt(submission, analysis, event_data, file_risks):
    """
    Generate minimal prompt for LLM analysis.
    ~20 lines instead of 100+
    
    Returns: string prompt
    """
    data = export_for_llm_analysis(submission, analysis, event_data, file_risks)
    
    # Determine verdict
    overall = data['scores']['overall']
    if overall < 4:
        verdict = "SUSPICIOUS"
    elif overall < 7:
        verdict = "WARNING"
    else:
        verdict = "LIKELY AUTHENTIC"
    
    prompt = f"""Academic Integrity Analysis

Student: {data['student']}
Assignment: {data['assignment']}
Verdict: {verdict}

Stats:
- Duration: {data['stats']['duration_min']} minutes
- Characters: {data['stats']['chars_added']:,} added, {data['stats']['chars_deleted']:,} deleted
- Files: {data['stats']['files_count']}

Scores (0-10, lower = more suspicious):
- Overall: {data['scores']['overall']}/10
- Incremental Development: {data['scores']['incremental']}/10
- Typing Variance: {data['scores']['typing']}/10
- Error Corrections: {data['scores']['corrections']}/10
- Work Sessions: {data['scores']['sessions']}/10

Top Issues:
"""
    
    for i, issue in enumerate(data['top_issues'], 1):
        prompt += f"{i}. {issue}\n"
    
    prompt += f"\nHigh-Risk Files:\n"
    high_risk = [f for f, d in data['files'].items() if d['risk'] == 'high']
    if high_risk:
        for f in high_risk:
            file_data = data['files'][f]
            prompt += f"- {f}: {file_data['chars']} chars, {file_data['pastes']} pastes\n"
    else:
        prompt += "None\n"
    
    return prompt


def export_to_json(submission, analysis, event_data, file_risks, filepath):
    """Export data to JSON file with format documentation"""
    data = export_for_llm_analysis(submission, analysis, event_data, file_risks)
    
    # Add format explanation for compact events
    if isinstance(event_data, dict) and 'base_time' in event_data:
        data['_format'] = {
            'description': 'Events use compact format for efficiency',
            'structure': '[delta_ms, type, filename, char_count]',
            'types': 'i=insert, d=delete, s=save',
            'timing': 'absolute_timestamp = base_time + delta_ms',
            'example': '[367, "i", "main.py", 25] means: insert 25 chars at base_time+367ms in main.py'
        }
        data['base_time'] = event_data.get('base_time', 0)
        data['events'] = event_data.get('events', [])
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath