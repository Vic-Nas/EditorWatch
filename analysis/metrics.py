import numpy as np
from datetime import datetime


def incremental_score(events):
    """
    Calculate incremental development score (0-10 scale).
    Low score = sudden large insertions (suspicious)
    High score = gradual development (normal)
    
    Returns: 0.0 to 10.0
    """
    if not events:
        return 0.0
    
    insert_events = [e for e in events if e['type'] == 'insert']
    if not insert_events:
        return 0.0
    
    # Count large insertions (>100 chars at once)
    large_inserts = sum(1 for e in insert_events if e['char_count'] > 100)
    
    # Calculate score (inverse of large insert ratio)
    raw_score = 1.0 - (large_inserts / len(insert_events))
    
    # Convert to 0-10 scale
    return round(raw_score * 10, 1)


def typing_variance(events):
    """
    Calculate variance in typing speed (0-10 scale).
    Low variance = robotic/pasted (suspicious)
    High variance = natural human typing (normal)
    
    Returns: 0.0 to 10.0
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
    
    # Normalize to 0-10 range
    raw_score = min(cv / 2.0, 1.0)
    return round(raw_score * 10, 1)


def error_correction_ratio(events):
    """
    Calculate ratio of deletions to insertions (0-10 scale).
    Low ratio = no mistakes/corrections (suspicious)
    High ratio = natural trial and error (normal)
    
    Returns: 0.0 to 10.0
    """
    if not events:
        return 0.0
    
    insert_count = sum(1 for e in events if e['type'] == 'insert')
    delete_count = sum(1 for e in events if e['type'] == 'delete')
    
    if insert_count == 0:
        return 0.0
    
    ratio = delete_count / insert_count
    
    # Normalize (typical ratio is 0.1-0.3, cap at 0.5)
    raw_score = min(ratio / 0.5, 1.0)
    return round(raw_score * 10, 1)


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


def code_velocity_analysis(events):
    """
    Analyze typing speed patterns - humans type at 40-80 chars/minute when coding.
    Sustained speeds > 200 chars/min indicate pasting.
    
    Returns: dict with velocity metrics
    """
    if len(events) < 2:
        return {'average_cpm': 0, 'max_cpm': 0, 'suspicious_bursts': []}
    
    insert_events = [e for e in events if e['type'] == 'insert']
    if not insert_events:
        return {'average_cpm': 0, 'max_cpm': 0, 'suspicious_bursts': []}
    
    # Calculate chars per minute for 30-second windows
    window_size = 30 * 1000  # 30 seconds
    start_time = events[0]['timestamp']
    end_time = events[-1]['timestamp']
    
    velocities = []
    suspicious_bursts = []
    
    current_time = start_time
    while current_time < end_time:
        window_end = current_time + window_size
        window_events = [e for e in insert_events 
                        if current_time <= e['timestamp'] < window_end]
        
        if window_events:
            chars = sum(e['char_count'] for e in window_events)
            cpm = chars * 2  # Convert 30-sec to per-minute
            velocities.append(cpm)
            
            # Flag if sustained > 200 chars/min
            if cpm > 200:
                suspicious_bursts.append({
                    'time_offset': (current_time - start_time) / 1000 / 60,
                    'cpm': cpm,
                    'chars': chars
                })
        
        current_time += window_size
    
    return {
        'average_cpm': round(sum(velocities) / len(velocities), 1) if velocities else 0,
        'max_cpm': round(max(velocities), 1) if velocities else 0,
        'suspicious_bursts': suspicious_bursts
    }


def session_consistency_score(events):
    """
    Analyze consistency of work sessions (0-10 scale).
    AI-generated code tends to appear in one or two sessions.
    Human work shows 3+ sessions with consistent patterns.
    
    Returns: 0.0 to 10.0
    """
    if not events:
        return 0.0
    
    # Group events into sessions (5+ min gap = new session)
    sessions = []
    current_session = []
    last_time = events[0]['timestamp']
    
    for event in events:
        gap = (event['timestamp'] - last_time) / 1000 / 60
        if gap > 5 and current_session:
            sessions.append(current_session)
            current_session = []
        current_session.append(event)
        last_time = event['timestamp']
    
    if current_session:
        sessions.append(current_session)
    
    # Analyze session patterns
    if len(sessions) < 2:
        return 0.0
    
    # Calculate session durations and char counts
    session_stats = []
    for session in sessions:
        duration = (session[-1]['timestamp'] - session[0]['timestamp']) / 1000 / 60
        chars = sum(e['char_count'] for e in session if e['type'] == 'insert')
        session_stats.append({'duration': duration, 'chars': chars})
    
    # More sessions = more authentic
    session_score = min(len(sessions) / 5.0, 1.0)
    
    # Consistent session sizes = more authentic
    if len(session_stats) > 1:
        char_counts = [s['chars'] for s in session_stats if s['chars'] > 0]
        if char_counts:
            variance = np.var(char_counts) / (np.mean(char_counts) + 1)
            consistency_score = min(variance / 2.0, 1.0)
        else:
            consistency_score = 0.0
    else:
        consistency_score = 0.0
    
    raw_score = (session_score + consistency_score) / 2
    return round(raw_score * 10, 1)


def file_level_analysis(events):
    """
    Analyze patterns per file to identify which files might be problematic.
    
    Returns: dict mapping filename to risk assessment
    """
    files = {}
    
    for event in events:
        filename = event.get('file', 'unknown').split('/')[-1]
        if filename not in files:
            files[filename] = {
                'inserts': [],
                'deletes': [],
                'saves': 0,
                'total_chars': 0
            }
        
        if event['type'] == 'insert':
            files[filename]['inserts'].append(event)
            files[filename]['total_chars'] += event['char_count']
        elif event['type'] == 'delete':
            files[filename]['deletes'].append(event)
        elif event['type'] == 'save':
            files[filename]['saves'] += 1
    
    # Analyze each file
    file_risks = {}
    for filename, data in files.items():
        inserts = data['inserts']
        if not inserts:
            continue
        
        # Check for large paste bursts in this file
        large_pastes = [e for e in inserts if e['char_count'] > 100]
        paste_ratio = len(large_pastes) / len(inserts) if inserts else 0
        
        # Check edit/delete ratio
        edit_ratio = len(data['deletes']) / len(inserts) if inserts else 0
        
        # Determine risk level
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
        
        # Check if file appeared suddenly (all code in < 2 minutes)
        if len(inserts) > 0:
            duration = (inserts[-1]['timestamp'] - inserts[0]['timestamp']) / 1000 / 60
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


def generate_detailed_flags(metrics, events, work_patterns):
    """
    Generate top 3 most important flags only (simplified).
    
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
            'message': f'{paste_percentage:.0f}% of code pasted in blocks rather than typed gradually'
        })
    
    if active_time < 10 and total_chars > 500:
        potential_flags.append({
            'priority': 10,
            'severity': 'high',
            'category': 'Time Analysis',
            'message': f'Entire submission completed in {active_time:.1f} minutes'
        })
    
    if velocity.get('average_cpm', 0) > 150:
        potential_flags.append({
            'priority': 10,
            'severity': 'high',
            'category': 'Typing Speed',
            'message': f'{velocity["average_cpm"]:.0f} chars/min typing speed (human: 40-80 chars/min)'
        })
    
    # File-specific critical issues (priority 9)
    high_risk_files = [f for f, data in file_risks.items() if data['risk'] == 'high']
    if high_risk_files:
        for f in high_risk_files[:1]:  # Only first file
            potential_flags.append({
                'priority': 9,
                'severity': 'high',
                'category': 'File Analysis',
                'message': f'{f}: {"; ".join(file_risks[f]["issues"])}'
            })
    
    # WARNING FLAGS (priority 5)
    if metrics['incremental_score'] < 4.0:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Development Pattern',
            'message': f'Code appeared in chunks (score: {metrics["incremental_score"]}/10)'
        })
    
    if metrics['typing_variance'] < 3.0:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Typing Behavior',
            'message': f'Robotic typing patterns (variance: {metrics["typing_variance"]}/10)'
        })
    
    if metrics['error_correction_ratio'] < 2.0 and total_chars > 200:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Error Correction',
            'message': f'Almost no corrections (score: {metrics["error_correction_ratio"]}/10)'
        })
    
    if metrics.get('session_consistency', 0) < 3.0:
        potential_flags.append({
            'priority': 5,
            'severity': 'medium',
            'category': 'Work Sessions',
            'message': f'Very few work sessions (score: {metrics.get("session_consistency", 0)}/10)'
        })
    
    # Sort by priority and take top 3
    potential_flags.sort(key=lambda x: x['priority'], reverse=True)
    flags = potential_flags[:3]
    
    # Remove priority field before returning
    for flag in flags:
        flag.pop('priority', None)
    
    # If no flags, add positive indicator
    if not flags:
        flags.append({
            'severity': 'none',
            'category': 'Assessment',
            'message': 'No suspicious patterns detected - work appears authentic'
        })
    
    return flags


def calculate_overall_score(metrics):
    """
    Calculate overall authenticity score (0-10).
    
    Returns: float 0.0-10.0
    """
    # Weight the metrics
    score = (
        metrics['incremental_score'] * 0.3 +
        metrics['typing_variance'] * 0.25 +
        metrics['error_correction_ratio'] * 0.25 +
        metrics.get('session_consistency', 0) * 0.2
    )
    
    # Penalize for paste bursts
    if metrics['paste_burst_count'] > 5:
        score = score * 0.5
    elif metrics['paste_burst_count'] > 2:
        score = score * 0.7
    
    return round(score, 1)


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
    
    return {
        'total_duration_minutes': round(total_duration_minutes, 1),
        'active_coding_minutes': round(active_time, 1),
        'breaks_count': len(breaks),
        'total_chars_inserted': total_chars_inserted,
        'total_chars_deleted': total_chars_deleted,
        'paste_percentage': round(paste_percentage, 1),
        'large_pastes_count': len(large_pastes)
    }


def calculate_all_metrics(events):
    """Calculate all metrics and generate comprehensive analysis"""
    # Core metrics (0-10 scale)
    metrics = {
        'incremental_score': incremental_score(events),
        'typing_variance': typing_variance(events),
        'error_correction_ratio': error_correction_ratio(events),
        'paste_burst_count': paste_burst_detection(events),
        'session_consistency': session_consistency_score(events),
        'velocity': code_velocity_analysis(events),
        'file_risks': file_level_analysis(events)
    }
    
    # Get detailed work pattern analysis
    work_patterns = analyze_work_patterns(events)
    
    # Calculate overall score
    metrics['overall_score'] = calculate_overall_score(metrics)
    
    # Generate top 3 flags only
    flags = generate_detailed_flags(metrics, events, work_patterns)
    
    return {
        **metrics,
        'work_patterns': work_patterns,
        'flags': flags
    }