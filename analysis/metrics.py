import numpy as np
from datetime import datetime


def incremental_score(events):
    """
    Calculate incremental development score.
    Low score = sudden large insertions (suspicious)
    High score = gradual development (normal)
    
    Returns: 0.0 to 1.0
    """
    if not events:
        return 0.0
    
    insert_events = [e for e in events if e['type'] == 'insert']
    if not insert_events:
        return 0.0
    
    # Count large insertions (>100 chars at once)
    large_inserts = sum(1 for e in insert_events if e['char_count'] > 100)
    
    # Calculate score (inverse of large insert ratio)
    score = 1.0 - (large_inserts / len(insert_events))
    return round(score, 3)


def typing_variance(events):
    """
    Calculate variance in typing speed.
    Low variance = robotic/pasted (suspicious)
    High variance = natural human typing (normal)
    
    Returns: 0.0 to 1.0
    """
    if len(events) < 2:
        return 0.0
    
    insert_events = [e for e in events if e['type'] == 'insert' and e['char_count'] > 0]
    if len(insert_events) < 2:
        return 0.0
    
    # Calculate time intervals between insertions
    intervals = []
    for i in range(1, len(insert_events)):
        time_diff = insert_events[i]['timestamp'] - insert_events[i-1]['timestamp']
        if time_diff > 0:
            intervals.append(time_diff)
    
    if not intervals:
        return 0.0
    
    # Calculate coefficient of variation (normalized variance)
    variance = np.var(intervals)
    mean = np.mean(intervals)
    
    if mean == 0:
        return 0.0
    
    cv = np.sqrt(variance) / mean
    
    # Normalize to 0-1 range (cap at 1.0)
    score = min(cv / 2.0, 1.0)
    return round(score, 3)


def error_correction_ratio(events):
    """
    Calculate ratio of deletions to insertions.
    Low ratio = no mistakes/corrections (suspicious)
    High ratio = natural trial and error (normal)
    
    Returns: 0.0 to 1.0
    """
    if not events:
        return 0.0
    
    insert_count = sum(1 for e in events if e['type'] == 'insert')
    delete_count = sum(1 for e in events if e['type'] == 'delete')
    
    if insert_count == 0:
        return 0.0
    
    ratio = delete_count / insert_count
    
    # Normalize (typical ratio is 0.1-0.3, cap at 0.5)
    score = min(ratio / 0.5, 1.0)
    return round(score, 3)


def paste_burst_detection(events):
    """
    Detect rapid large insertions (paste bursts).
    High count = likely copied code (suspicious)
    
    Returns: integer count
    """
    if not events:
        return 0
    
    bursts = 0
    last_time = 0
    
    for e in events:
        if e['type'] == 'insert' and e['char_count'] > 100:
            # If less than 2 seconds since last large insert
            if e['timestamp'] - last_time < 2000:
                bursts += 1
            last_time = e['timestamp']
    
    return bursts


def analyze_work_patterns(events):
    """
    Analyze detailed work patterns for human-readable insights.
    
    Returns: dict with detailed analysis
    """
    if not events:
        return {}
    
    insert_events = [e for e in events if e['type'] == 'insert']
    delete_events = [e for e in events if e['type'] == 'delete']
    
    total_chars_inserted = sum(e['char_count'] for e in insert_events)
    total_chars_deleted = sum(e['char_count'] for e in delete_events)
    
    # Time analysis
    start_time = events[0]['timestamp']
    end_time = events[-1]['timestamp']
    total_duration_minutes = (end_time - start_time) / 1000 / 60
    
    # Break detection (gaps > 10 minutes)
    breaks = []
    for i in range(1, len(events)):
        gap = (events[i]['timestamp'] - events[i-1]['timestamp']) / 1000 / 60
        if gap > 10:
            breaks.append(gap)
    
    # Active coding time (excluding breaks)
    active_time = total_duration_minutes - sum(breaks)
    
    # Paste analysis
    large_pastes = [e for e in insert_events if e['char_count'] > 100]
    large_paste_chars = sum(e['char_count'] for e in large_pastes)
    paste_percentage = (large_paste_chars / total_chars_inserted * 100) if total_chars_inserted > 0 else 0
    
    # File activity
    files = {}
    for e in events:
        file = e.get('file', 'unknown')
        if file not in files:
            files[file] = {'inserts': 0, 'deletes': 0, 'chars': 0}
        if e['type'] == 'insert':
            files[file]['inserts'] += 1
            files[file]['chars'] += e['char_count']
        elif e['type'] == 'delete':
            files[file]['deletes'] += 1
    
    return {
        'total_duration_minutes': round(total_duration_minutes, 1),
        'active_coding_minutes': round(active_time, 1),
        'breaks_count': len(breaks),
        'longest_break_minutes': round(max(breaks), 1) if breaks else 0,
        'total_chars_inserted': total_chars_inserted,
        'total_chars_deleted': total_chars_deleted,
        'paste_percentage': round(paste_percentage, 1),
        'large_pastes_count': len(large_pastes),
        'files_edited': len(files),
        'file_details': files
    }


def generate_detailed_flags(metrics, events, work_patterns):
    """
    Generate comprehensive, human-readable flags based on all analysis.
    
    Returns: list of flag objects with severity and detailed message
    """
    flags = []
    
    total_chars = work_patterns.get('total_chars_inserted', 0)
    paste_percentage = work_patterns.get('paste_percentage', 0)
    active_time = work_patterns.get('active_coding_minutes', 0)
    
    # CRITICAL FLAGS (High severity)
    if paste_percentage > 70 and total_chars > 500:
        flags.append({
            'severity': 'high',
            'category': 'Code Origin',
            'message': f'{paste_percentage:.0f}% of code ({work_patterns["large_pastes_count"]} large pastes) appeared in blocks rather than being typed gradually. This strongly suggests copied content.'
        })
    
    if metrics['paste_burst_count'] > 5:
        flags.append({
            'severity': 'high',
            'category': 'Paste Detection',
            'message': f'{metrics["paste_burst_count"]} paste burst events detected - multiple large code blocks inserted within seconds of each other.'
        })
    
    if active_time < 10 and total_chars > 500:
        flags.append({
            'severity': 'high',
            'category': 'Time Analysis',
            'message': f'Entire submission completed in {active_time:.1f} minutes with {total_chars} characters. This is suspiciously fast for genuine development.'
        })
    
    # WARNING FLAGS (Medium severity)
    if metrics['incremental_score'] < 0.4:
        flags.append({
            'severity': 'medium',
            'category': 'Development Pattern',
            'message': f'Code development shows sudden large insertions (score: {metrics["incremental_score"]:.2f}/1.0) rather than gradual, iterative work.'
        })
    
    if metrics['typing_variance'] < 0.15:
        flags.append({
            'severity': 'medium',
            'category': 'Typing Behavior',
            'message': f'Typing patterns are unusually consistent (variance: {metrics["typing_variance"]:.2f}/1.0), suggesting automated insertion rather than manual coding.'
        })
    
    if metrics['error_correction_ratio'] < 0.05 and total_chars > 200:
        flags.append({
            'severity': 'medium',
            'category': 'Error Correction',
            'message': f'Almost no deletions or corrections detected ({work_patterns["total_chars_deleted"]} chars deleted vs {total_chars} inserted). Real coding involves trial and error.'
        })
    
    # INFORMATIONAL FLAGS (Low severity)
    if work_patterns.get('breaks_count', 0) == 0 and active_time > 60:
        flags.append({
            'severity': 'low',
            'category': 'Work Pattern',
            'message': f'No breaks detected during {active_time:.0f} minutes of coding. Consider if this is realistic for this student.'
        })
    
    if paste_percentage > 30 and paste_percentage <= 70:
        flags.append({
            'severity': 'low',
            'category': 'Code Origin',
            'message': f'{paste_percentage:.0f}% of code came from large insertions. Some copying may be legitimate (e.g., templates, boilerplate).'
        })
    
    # POSITIVE INDICATORS (None severity)
    if not flags:
        positive_indicators = []
        
        if metrics['incremental_score'] > 0.7:
            positive_indicators.append('gradual code development')
        if metrics['typing_variance'] > 0.3:
            positive_indicators.append('natural typing patterns')
        if metrics['error_correction_ratio'] > 0.15:
            positive_indicators.append('appropriate trial and error')
        if work_patterns.get('breaks_count', 0) > 0:
            positive_indicators.append(f'{work_patterns["breaks_count"]} work breaks')
        
        flags.append({
            'severity': 'none',
            'category': 'Assessment',
            'message': f'No suspicious patterns detected. Positive indicators: {", ".join(positive_indicators)}. Work appears authentic.'
        })
    
    return flags


def calculate_all_metrics(events):
    """Calculate all metrics and generate comprehensive analysis"""
    metrics = {
        'incremental_score': incremental_score(events),
        'typing_variance': typing_variance(events),
        'error_correction_ratio': error_correction_ratio(events),
        'paste_burst_count': paste_burst_detection(events)
    }
    
    # Get detailed work pattern analysis
    work_patterns = analyze_work_patterns(events)
    
    # Generate detailed flags
    flags = generate_detailed_flags(metrics, events, work_patterns)
    
    return {
        **metrics,
        'work_patterns': work_patterns,
        'flags': flags
    }