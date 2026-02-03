import numpy as np
from datetime import datetime

# Message rendering helper (centralized templates)
from .messages import render as render_message


def _normalize_events(event_data):
    """
    Helper to extract events array and metadata from either compact or legacy format.
    Returns: (events_list, base_time, is_compact)
    """
    if isinstance(event_data, dict):
        events = event_data.get('events', [])
        base_time = event_data.get('base_time', 0)
        is_legacy = event_data.get('_legacy', False)
        
        if events and isinstance(events[0], list):
            # Compact format
            return events, base_time, True
        else:
            # Legacy dict format stored in new structure
            return events, base_time, False
    else:
        # Direct list (legacy)
        return event_data, 0, False


def _get_timestamp(event, base_time, is_compact):
    """Get absolute timestamp from event"""
    if is_compact:
        return base_time + event[0]  # delta + base
    return event.get('timestamp', 0)


def _get_type(event, is_compact):
    """Get event type"""
    if is_compact:
        type_map = {'i': 'insert', 'd': 'delete', 's': 'save'}
        return type_map.get(event[1], 'insert')
    return event.get('type', 'insert')


def _get_char_count(event, is_compact):
    """Get character count"""
    if is_compact:
        return event[3] if len(event) > 3 else 0
    return event.get('char_count', 0)


def incremental_score(event_data):
    """
    Calculate incremental development score (0-10 scale).
    0-3 = SUSPICIOUS (sudden large insertions)
    4-6 = WARNING (mix of gradual and chunks)
    7-10 = GOOD (gradual development)
    
    Returns: 0.0 to 10.0
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if not events:
        return 0.0
    
    insert_events = [e for e in events if _get_type(e, is_compact) == 'insert']
    if not insert_events:
        return 0.0
    
    # Calculate PERCENTAGE OF CHARACTERS from large pastes
    total_chars = sum(_get_char_count(e, is_compact) for e in insert_events)
    if total_chars == 0:
        return 0.0
    
    large_paste_chars = sum(_get_char_count(e, is_compact) for e in insert_events 
                           if _get_char_count(e, is_compact) > 100)
    
    large_ratio = large_paste_chars / total_chars
    score = (1.0 - large_ratio) * 10
    
    return round(score, 1)


def typing_variance(event_data):
    """
    Calculate variance in typing speed (0-10 scale).
    0-3 = SUSPICIOUS (robotic/pasted, too consistent)
    4-6 = WARNING (somewhat consistent)
    7-10 = GOOD (natural human variance)
    
    Returns: 0.0 to 10.0
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if len(events) < 2:
        return 0.0
    
    insert_events = [e for e in events if _get_type(e, is_compact) == 'insert' 
                    and _get_char_count(e, is_compact) > 0]
    if len(insert_events) < 2:
        return 0.0
    
    # Calculate time intervals between insertions
    intervals = []
    for i in range(1, len(insert_events)):
        time_diff = (_get_timestamp(insert_events[i], base_time, is_compact) - 
                    _get_timestamp(insert_events[i-1], base_time, is_compact))
        if time_diff > 0:
            intervals.append(time_diff)
    
    if not intervals or len(intervals) < 2:
        return 0.0
    
    variance = np.var(intervals)
    mean = np.mean(intervals)
    
    if mean == 0 or variance == 0:
        return 0.0
    
    cv = np.sqrt(variance) / mean
    raw_score = min(cv / 2.0, 1.0)
    return round(raw_score * 10, 1)


def error_correction_ratio(event_data):
    """
    Calculate ratio of deletions to insertions (0-10 scale).
    0-3 = SUSPICIOUS (no mistakes, code perfect first time)
    4-6 = WARNING (few corrections)
    7-10 = GOOD (natural trial and error)
    
    Returns: 0.0 to 10.0
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if not events:
        return 0.0
    
    insert_count = sum(1 for e in events if _get_type(e, is_compact) == 'insert')
    delete_count = sum(1 for e in events if _get_type(e, is_compact) == 'delete')
    
    if insert_count == 0:
        return 0.0
    
    ratio = delete_count / insert_count
    raw_score = min(ratio / 0.3, 1.0)
    return round(raw_score * 10, 1)


def paste_burst_detection(event_data):
    """
    Detect rapid large insertions (paste bursts).
    Returns count - higher = worse (more suspicious)
    
    Returns: integer count
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if not events:
        return 0
    
    bursts = 0
    last_time = 0
    
    for e in events:
        if _get_type(e, is_compact) == 'insert' and _get_char_count(e, is_compact) > 100:
            timestamp = _get_timestamp(e, base_time, is_compact)
            if timestamp - last_time < 2000:
                bursts += 1
            last_time = timestamp
    
    return bursts


def code_velocity_analysis(event_data):
    """
    Analyze typing speed - creates a 0-10 score where:
    0-3 = SUSPICIOUS (>200 chars/min sustained = pasting)
    4-6 = WARNING (100-200 chars/min = fast but possible)
    7-10 = GOOD (40-80 chars/min = normal human coding)
    
    Returns: dict with velocity metrics and score
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if len(events) < 2:
        return {'average_cpm': 0, 'max_cpm': 0, 'score': 0, 'suspicious_bursts': []}
    
    insert_events = [e for e in events if _get_type(e, is_compact) == 'insert']
    if not insert_events:
        return {'average_cpm': 0, 'max_cpm': 0, 'score': 0, 'suspicious_bursts': []}
    
    # Calculate chars per minute for 30-second windows
    window_size = 30 * 1000  # 30 seconds
    start_time = _get_timestamp(events[0], base_time, is_compact)
    end_time = _get_timestamp(events[-1], base_time, is_compact)
    
    velocities = []
    suspicious_bursts = []
    
    current_time = start_time
    while current_time < end_time:
        window_end = current_time + window_size
        window_events = [e for e in insert_events 
                        if current_time <= _get_timestamp(e, base_time, is_compact) < window_end]
        
        if window_events:
            chars = sum(_get_char_count(e, is_compact) for e in window_events)
            cpm = chars * 2  # Convert 30-sec to per-minute
            velocities.append(cpm)
            
            if cpm > 200:
                suspicious_bursts.append({
                    'time_offset': (current_time - start_time) / 1000 / 60,
                    'cpm': cpm,
                    'chars': chars
                })
        
        current_time += window_size
    
    avg_cpm = round(sum(velocities) / len(velocities), 1) if velocities else 0
    max_cpm = round(max(velocities), 1) if velocities else 0
    
    if avg_cpm <= 80:
        score = 10.0
    elif avg_cpm <= 150:
        score = 10.0 - ((avg_cpm - 80) / 70) * 5
    elif avg_cpm <= 200:
        score = 5.0 - ((avg_cpm - 150) / 50) * 4
    else:
        score = 0.0
    
    return {
        'average_cpm': avg_cpm,
        'max_cpm': max_cpm,
        'score': round(score, 1),
        'suspicious_bursts': suspicious_bursts
    }


def session_consistency_score(event_data):
    """
    Analyze work sessions (0-10 scale).
    0-3 = SUSPICIOUS (1-2 sessions, AI-generated pattern)
    4-6 = WARNING (2-3 sessions, could be rushed work)
    7-10 = GOOD (3+ sessions, authentic work pattern)
    
    Returns: 0.0 to 10.0
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if not events:
        return 0.0
    
    # Group events into sessions (5+ min gap = new session)
    sessions = []
    current_session = []
    last_time = _get_timestamp(events[0], base_time, is_compact)
    
    for event in events:
        timestamp = _get_timestamp(event, base_time, is_compact)
        gap = (timestamp - last_time) / 1000 / 60
        if gap > 5 and current_session:
            sessions.append(current_session)
            current_session = []
        current_session.append(event)
        last_time = timestamp
    
    if current_session:
        sessions.append(current_session)
    
    num_sessions = len(sessions)
    
    if num_sessions == 1:
        score = 0.0
    elif num_sessions == 2:
        score = 3.0
    elif num_sessions == 3:
        score = 6.0
    elif num_sessions == 4:
        score = 8.0
    else:
        score = 10.0
    
    return score


def file_level_analysis(event_data):
    """
    Analyze patterns per file to identify which files might be problematic.
    
    Returns: dict mapping filename to risk assessment
    """
    events, base_time, is_compact = _normalize_events(event_data)
    files = {}
    
    for event in events:
        # Get filename
        if is_compact:
            filename = event[2] if len(event) > 2 else 'unknown'
        else:
            filename = event.get('file', 'unknown').split('/')[-1]
        
        if filename not in files:
            files[filename] = {
                'inserts': [],
                'deletes': [],
                'saves': 0,
                'total_chars': 0
            }
        
        event_type = _get_type(event, is_compact)
        
        if event_type == 'insert':
            files[filename]['inserts'].append(event)
            files[filename]['total_chars'] += _get_char_count(event, is_compact)
        elif event_type == 'delete':
            files[filename]['deletes'].append(event)
        elif event_type == 'save':
            files[filename]['saves'] += 1
    
    # Analyze each file
    file_risks = {}
    for filename, data in files.items():
        inserts = data['inserts']
        if not inserts:
            continue
        
        large_pastes = [e for e in inserts if _get_char_count(e, is_compact) > 100]
        paste_ratio = len(large_pastes) / len(inserts) if inserts else 0
        edit_ratio = len(data['deletes']) / len(inserts) if inserts else 0
        
        risk = 'low'
        issues = []
        
        if paste_ratio > 0.5:
            risk = 'high'
            issues.append(f'{len(large_pastes)} large pastes ({paste_ratio*100:.0f}%)')
        elif paste_ratio > 0.3:
            risk = 'medium'
            issues.append(f'{len(large_pastes)} large pastes')
        
        if edit_ratio < 0.05 and len(inserts) > 10:
            if risk == 'medium':
                risk = 'high'
            elif risk == 'low':
                risk = 'medium'
            issues.append(f'very few edits ({edit_ratio*100:.1f}%)')
        
        if len(inserts) > 0:
            duration = (_get_timestamp(inserts[-1], base_time, is_compact) - 
                       _get_timestamp(inserts[0], base_time, is_compact)) / 1000 / 60
            if duration < 2 and data['total_chars'] > 200:
                risk = 'high'
                issues.append(f'entire file in {duration:.1f} minutes')
        
        file_risks[filename] = {
            'risk': risk,
            'issues': issues,
            'total_chars': data['total_chars'],
            'paste_count': len(large_pastes),
            'edit_ratio': round(edit_ratio, 3),
            'insert_count': len(inserts),
            'delete_count': len(data['deletes'])
        }
    
    return file_risks


def generate_detailed_flags(metrics, event_data, work_patterns):
    """
    Generate top 3 most important flags only.
    
    Returns: list of flag objects with severity and detailed message
    """
    flags = []
    
    total_chars = work_patterns.get('total_chars_inserted', 0)
    paste_percentage = work_patterns.get('paste_percentage', 0)
    active_time = work_patterns.get('active_coding_minutes', 0)
    
    velocity = metrics.get('velocity', {})
    file_risks = metrics.get('file_risks', {})
    
    # Collect all potential flags with priority scores
    potential_flags = []
    
    # CRITICAL FLAGS (priority 10)
    if paste_percentage > 70 and total_chars > 500:
        potential_flags.append({
            'priority': 10,
            'severity': 'high',
            'category': 'Code Origin',
            'message': render_message('paste_percentage', paste_percentage=paste_percentage)
        })

    if active_time < 10 and total_chars > 500:
        potential_flags.append({
            'priority': 10,
            'severity': 'high',
            'category': 'Time Analysis',
            'message': render_message('completed_quickly', active_time=active_time)
        })

    if velocity.get('average_cpm', 0) > 150:
        potential_flags.append({
            'priority': 10,
            'severity': 'high',
            'category': 'Typing Speed',
            'message': render_message('high_typing_speed', average_cpm=velocity.get('average_cpm', 0))
        })
    
    # File-specific critical issues (priority 9)
    high_risk_files = [f for f, data in file_risks.items() if data['risk'] == 'high']
    if high_risk_files:
        for f in high_risk_files[:1]:
            issues = '; '.join(file_risks[f].get('issues', []))
            potential_flags.append({
                'priority': 9,
                'severity': 'high',
                'category': 'File Analysis',
                'message': render_message('file_risks', file=f, issues=issues)
            })
    
    # WARNING FLAGS (priority 5)
    if metrics['incremental_score'] < 4.0:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Development Pattern',
            'message': render_message('chunks_appeared', incremental_score=metrics['incremental_score'])
        })
    
    if metrics['typing_variance'] < 3.0:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Typing Behavior',
            'message': render_message('robotic_typing', typing_variance=metrics['typing_variance'])
        })
    
    if metrics['error_correction_ratio'] < 2.0 and total_chars > 200:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Error Correction',
            'message': render_message('few_corrections', error_correction_ratio=metrics['error_correction_ratio'])
        })
    
    if metrics.get('session_consistency', 0) < 4.0:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Work Sessions',
            'message': render_message('few_sessions', session_consistency=metrics.get('session_consistency', 0))
        })
    
    # Sort by priority and take top 3
    potential_flags.sort(key=lambda x: x['priority'], reverse=True)
    flags = potential_flags[:3]
    
    # Remove priority field before returning
    for flag in flags:
        flag.pop('priority', None)
    
    if not flags:
        flags.append({
            'severity': 'none',
            'category': 'Assessment',
            'message': render_message('no_suspicious')
        })
    
    return flags


def calculate_overall_score(metrics):
    """
    Calculate overall authenticity score (0-10).
    Applies HARD penalties for obvious cheating indicators.
    
    Returns: float 0.0-10.0
    """
    score = (
        metrics['incremental_score'] * 0.25 +
        metrics['typing_variance'] * 0.20 +
        metrics['error_correction_ratio'] * 0.20 +
        metrics.get('session_consistency', 0) * 0.20 +
        metrics['velocity'].get('score', 0) * 0.15
    )
    
    # HARD PENALTIES for obvious red flags
    if (metrics['incremental_score'] <= 2 or 
        metrics['typing_variance'] <= 2 or
        metrics['velocity'].get('score', 10) <= 2):
        score = min(score, 3.0)
    
    if metrics['velocity'].get('average_cpm', 0) > 500:
        score = min(score, 1.0)
    
    if metrics['paste_burst_count'] > 5:
        score = score * 0.3
    elif metrics['paste_burst_count'] > 2:
        score = score * 0.6
    
    if metrics.get('session_consistency', 0) <= 1:
        score = score * 0.7
    
    return round(max(score, 0.0), 1)


def analyze_work_patterns(event_data):
    """
    Analyze detailed work patterns for human-readable insights.
    
    Returns: dict with detailed analysis
    """
    events, base_time, is_compact = _normalize_events(event_data)
    
    if not events:
        return {}
    
    insert_events = [e for e in events if _get_type(e, is_compact) == 'insert']
    delete_events = [e for e in events if _get_type(e, is_compact) == 'delete']
    
    total_chars_inserted = sum(_get_char_count(e, is_compact) for e in insert_events)
    total_chars_deleted = sum(_get_char_count(e, is_compact) for e in delete_events)
    
    # Time analysis
    start_time = _get_timestamp(events[0], base_time, is_compact)
    end_time = _get_timestamp(events[-1], base_time, is_compact)
    total_duration_minutes = (end_time - start_time) / 1000 / 60
    
    # Break detection (gaps > 10 minutes)
    breaks = []
    for i in range(1, len(events)):
        gap = (_get_timestamp(events[i], base_time, is_compact) - 
               _get_timestamp(events[i-1], base_time, is_compact)) / 1000 / 60
        if gap > 10:
            breaks.append(gap)
    
    active_time = total_duration_minutes - sum(breaks)
    
    # Paste analysis
    large_pastes = [e for e in insert_events if _get_char_count(e, is_compact) > 100]
    large_paste_chars = sum(_get_char_count(e, is_compact) for e in large_pastes)
    paste_percentage = (large_paste_chars / total_chars_inserted * 100) if total_chars_inserted > 0 else 0
    
    return {
        'total_duration_minutes': round(total_duration_minutes, 1),
        'active_coding_minutes': round(active_time, 1),
        'breaks_count': len(breaks),
        'total_chars_inserted': total_chars_inserted,
        'total_chars_deleted': total_chars_deleted,
        'paste_percentage': round(paste_percentage, 1),
        'large_pastes_count': len(large_pastes)
    }


def calculate_all_metrics(event_data):
    """Calculate all metrics and generate comprehensive analysis"""
    velocity_data = code_velocity_analysis(event_data)
    
    metrics = {
        'incremental_score': incremental_score(event_data),
        'typing_variance': typing_variance(event_data),
        'error_correction_ratio': error_correction_ratio(event_data),
        'paste_burst_count': paste_burst_detection(event_data),
        'session_consistency': session_consistency_score(event_data),
        'velocity': velocity_data,
        'velocity_score': velocity_data.get('score', 0),
        'file_risks': file_level_analysis(event_data)
    }
    
    work_patterns = analyze_work_patterns(event_data)
    metrics['overall_score'] = calculate_overall_score(metrics)
    flags = generate_detailed_flags(metrics, event_data, work_patterns)
    
    return {
        **metrics,
        'work_patterns': work_patterns,
        'flags': flags
    }