"""
Centralized message templates for teacher-facing flags.
Each entry contains:
- template: a format string (f-string style placeholders using .format keys)
- severity: 'high'|'medium'|'low'|'none'
- category: short category name
- example_context: example keys required to render the template

Keeping templates here makes them easier to maintain and translate.
"""

MESSAGES = {
    'paste_percentage': {
        'template': "{paste_percentage:.0f}% of code pasted in blocks rather than typed gradually",
        'severity': 'high',
        'category': 'Code Origin',
        'example_context': {'paste_percentage': 82}
    },
    'completed_quickly': {
        'template': "Entire submission completed in {active_time:.1f} minutes",
        'severity': 'high',
        'category': 'Time Analysis',
        'example_context': {'active_time': 3.5}
    },
    'high_typing_speed': {
        'template': "{average_cpm:.0f} chars/min typing speed (human: 40-80 chars/min)",
        'severity': 'high',
        'category': 'Typing Speed',
        'example_context': {'average_cpm': 420}
    },
    'file_risks': {
        'template': "{file}: {issues}",
        'severity': 'high',
        'category': 'File Analysis',
        'example_context': {'file': 'main.py', 'issues': 'sudden creation; large pastes'}
    },
    'chunks_appeared': {
        'template': "Code appeared in chunks (score: {incremental_score}/10)",
        'severity': 'medium',
        'category': 'Development Pattern',
        'example_context': {'incremental_score': 2.0}
    },
    'robotic_typing': {
        'template': "Robotic typing patterns (variance: {typing_variance}/10)",
        'severity': 'medium',
        'category': 'Typing Behavior',
        'example_context': {'typing_variance': 1.5}
    },
    'few_corrections': {
        'template': "Almost no corrections (score: {error_correction_ratio}/10)",
        'severity': 'medium',
        'category': 'Error Correction',
        'example_context': {'error_correction_ratio': 1.2}
    },
    'few_sessions': {
        'template': "Very few work sessions (score: {session_consistency}/10)",
        'severity': 'medium',
        'category': 'Work Sessions',
        'example_context': {'session_consistency': 1.0}
    },
    'no_suspicious': {
        'template': "No suspicious patterns detected - work appears authentic",
        'severity': 'none',
        'category': 'Assessment',
        'example_context': {}
    },
    'large_pastes_count_ratio': {
        'template': "{count} large pastes ({ratio:.0f}%)",
        'severity': 'high',
        'category': 'File Analysis',
        'example_context': {'count': 3, 'ratio': 52}
    },
    'very_few_edits': {
        'template': "very few edits ({edit_ratio:.1f}%)",
        'severity': 'medium',
        'category': 'File Analysis',
        'example_context': {'edit_ratio': 2.3}
    },
    'entire_file_quick': {
        'template': "entire file in {duration:.1f} minutes",
        'severity': 'high',
        'category': 'File Analysis',
        'example_context': {'duration': 1.2}
    }
}


def render(key, **context):
    """Render the template for `key` with provided context.
    Falls back to a safe message if required keys are missing.
    """
    entry = MESSAGES.get(key)
    if not entry:
        return f'Unknown flag: {key}'
    tpl = entry['template']
    try:
        return tpl.format(**context)
    except Exception:
        # Provide a safe fallback that includes available context values
        available = ', '.join(f"{k}={v!r}" for k, v in context.items())
        return f"{tpl} ({available})"
