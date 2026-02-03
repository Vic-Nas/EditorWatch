"""
All metric functions expect compact event data:
    { base_time: int, events: [[delta_ms, type, filename, char_count], ...] }
Type codes: 'i' = insert, 'd' = delete, 's' = save
Absolute timestamp = base_time + delta_ms
"""

import numpy as np
from .messages import render as render_message


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def incremental_score(event_data):
    """
    Incremental development score (0-10).
    Based on what percentage of characters came from large pastes (>100 chars).
    0-3 = SUSPICIOUS | 4-6 = WARNING | 7-10 = GOOD
    """
    events = event_data.get('events', [])
    inserts = [e for e in events if e[1] == 'i']
    if not inserts:
        return 0.0

    total_chars = sum(e[3] for e in inserts)
    if total_chars == 0:
        return 0.0

    large_paste_chars = sum(e[3] for e in inserts if e[3] > 100)
    score = (1.0 - large_paste_chars / total_chars) * 10
    return round(score, 1)


def typing_variance(event_data):
    """
    Variance in typing speed (0-10).
    Low variance = robotic/pasted. High variance = natural human typing.
    0-3 = SUSPICIOUS | 4-6 = WARNING | 7-10 = GOOD
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])
    inserts = [e for e in events if e[1] == 'i' and e[3] > 0]

    if len(inserts) < 2:
        return 0.0

    # Time intervals between consecutive inserts (absolute ms)
    intervals = []
    for i in range(1, len(inserts)):
        diff = (base_time + inserts[i][0]) - (base_time + inserts[i - 1][0])
        if diff > 0:
            intervals.append(diff)

    if len(intervals) < 2:
        return 0.0

    mean = np.mean(intervals)
    if mean == 0:
        return 0.0

    cv = np.std(intervals) / mean  # coefficient of variation
    raw_score = min(cv / 2.0, 1.0)
    return round(raw_score * 10, 1)


def error_correction_ratio(event_data):
    """
    Ratio of deletions to insertions (0-10).
    No mistakes at all = suspicious (perfect code first try).
    0-3 = SUSPICIOUS | 4-6 = WARNING | 7-10 = GOOD
    """
    events = event_data.get('events', [])
    insert_count = sum(1 for e in events if e[1] == 'i')
    delete_count = sum(1 for e in events if e[1] == 'd')

    if insert_count == 0:
        return 0.0

    ratio = delete_count / insert_count
    return round(min(ratio / 0.3, 1.0) * 10, 1)


def paste_burst_detection(event_data):
    """
    Count rapid large insertions (>100 chars within 2s of each other).
    Higher count = more suspicious.
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])

    bursts = 0
    last_time = 0

    for e in events:
        if e[1] == 'i' and e[3] > 100:
            abs_time = base_time + e[0]
            if abs_time - last_time < 2000:
                bursts += 1
            last_time = abs_time

    return bursts


def code_velocity_analysis(event_data):
    """
    Typing speed in 30-second windows (0-10 score).
    0-3 = SUSPICIOUS (>200 cpm, likely pasting)
    4-6 = WARNING (100-200 cpm)
    7-10 = GOOD (40-80 cpm, normal human)

    Returns: dict with velocity metrics and score
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])

    if len(events) < 2:
        return {'average_cpm': 0, 'max_cpm': 0, 'score': 0, 'suspicious_bursts': []}

    inserts = [e for e in events if e[1] == 'i']
    if not inserts:
        return {'average_cpm': 0, 'max_cpm': 0, 'score': 0, 'suspicious_bursts': []}

    window_size = 30 * 1000  # 30 seconds in ms
    start_time = base_time + events[0][0]
    end_time = base_time + events[-1][0]

    velocities = []
    suspicious_bursts = []

    current_time = start_time
    while current_time < end_time:
        window_end = current_time + window_size
        window_chars = sum(
            e[3] for e in inserts
            if current_time <= (base_time + e[0]) < window_end
        )

        if window_chars:
            cpm = window_chars * 2  # 30-sec window → per-minute
            velocities.append(cpm)
            if cpm > 200:
                suspicious_bursts.append({
                    'time_offset': (current_time - start_time) / 1000 / 60,
                    'cpm': cpm,
                    'chars': window_chars
                })

        current_time += window_size

    avg_cpm = round(sum(velocities) / len(velocities), 1) if velocities else 0
    max_cpm = round(max(velocities), 1) if velocities else 0

    # Score curve: ≤80 → 10, 80-150 → 10→5, 150-200 → 5→1, >200 → 0
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
    Work-session score (0-10). A gap >5 min between events = new session.
    1 session → 0 | 2 → 3 | 3 → 6 | 4 → 8 | 5+ → 10
    """
    events = event_data.get('events', [])
    if not events:
        return 0.0

    # Count sessions by gaps
    sessions = 1
    last_delta = events[0][0]
    for e in events[1:]:
        if (e[0] - last_delta) / 1000 / 60 > 5:
            sessions += 1
        last_delta = e[0]

    return {1: 0.0, 2: 3.0, 3: 6.0, 4: 8.0}.get(sessions, 10.0)


def file_level_analysis(event_data):
    """
    Per-file risk assessment based on paste ratio, edit ratio, and creation speed.
    Returns: dict mapping filename → risk data
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])

    # Group events by file
    files = {}
    for e in events:
        filename = e[2] if len(e) > 2 else 'unknown'
        if filename not in files:
            files[filename] = {'inserts': [], 'deletes': [], 'saves': 0, 'total_chars': 0}

        if e[1] == 'i':
            files[filename]['inserts'].append(e)
            files[filename]['total_chars'] += e[3]
        elif e[1] == 'd':
            files[filename]['deletes'].append(e)
        elif e[1] == 's':
            files[filename]['saves'] += 1

    # Score each file
    file_risks = {}
    for filename, data in files.items():
        inserts = data['inserts']
        if not inserts:
            continue

        large_pastes = [e for e in inserts if e[3] > 100]
        paste_ratio = len(large_pastes) / len(inserts)
        edit_ratio = len(data['deletes']) / len(inserts)

        risk = 'low'
        issues = []

        if paste_ratio > 0.5:
            risk = 'high'
            issues.append(f'{len(large_pastes)} large pastes ({paste_ratio * 100:.0f}%)')
        elif paste_ratio > 0.3:
            risk = 'medium'
            issues.append(f'{len(large_pastes)} large pastes')

        if edit_ratio < 0.05 and len(inserts) > 10:
            if risk == 'medium':
                risk = 'high'
            elif risk == 'low':
                risk = 'medium'
            issues.append(f'very few edits ({edit_ratio * 100:.1f}%)')

        # Check if entire file appeared too fast
        duration = (inserts[-1][0] - inserts[0][0]) / 1000 / 60  # deltas are relative, diff is fine
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


# ---------------------------------------------------------------------------
# Work-pattern summary (used by flag generation)
# ---------------------------------------------------------------------------

def analyze_work_patterns(event_data):
    """
    High-level work-pattern stats for flag generation.
    Returns: dict with duration, paste %, active time, etc.
    """
    events = event_data.get('events', [])
    if not events:
        return {}

    inserts = [e for e in events if e[1] == 'i']
    deletes = [e for e in events if e[1] == 'd']

    total_chars_inserted = sum(e[3] for e in inserts)
    total_chars_deleted = sum(e[3] for e in deletes)

    total_duration_minutes = events[-1][0] / 1000 / 60  # last delta

    # Breaks: gaps > 10 min between consecutive events
    breaks = []
    for i in range(1, len(events)):
        gap = (events[i][0] - events[i - 1][0]) / 1000 / 60
        if gap > 10:
            breaks.append(gap)

    active_time = total_duration_minutes - sum(breaks)

    # Paste percentage by character volume
    large_paste_chars = sum(e[3] for e in inserts if e[3] > 100)
    paste_percentage = (large_paste_chars / total_chars_inserted * 100) if total_chars_inserted > 0 else 0

    return {
        'total_duration_minutes': round(total_duration_minutes, 1),
        'active_coding_minutes': round(active_time, 1),
        'breaks_count': len(breaks),
        'total_chars_inserted': total_chars_inserted,
        'total_chars_deleted': total_chars_deleted,
        'paste_percentage': round(paste_percentage, 1),
        'large_pastes_count': sum(1 for e in inserts if e[3] > 100)
    }


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

def generate_detailed_flags(metrics, event_data, work_patterns):
    """
    Generate top 3 most important flags, sorted by priority.
    Returns: list of flag dicts with severity, category, message
    """
    total_chars = work_patterns.get('total_chars_inserted', 0)
    paste_percentage = work_patterns.get('paste_percentage', 0)
    active_time = work_patterns.get('active_coding_minutes', 0)
    velocity = metrics.get('velocity', {})
    file_risks = metrics.get('file_risks', {})

    potential_flags = []

    # --- Critical (priority 10) ---
    if paste_percentage > 70 and total_chars > 500:
        potential_flags.append({
            'priority': 10, 'severity': 'high', 'category': 'Code Origin',
            'message': render_message('paste_percentage', paste_percentage=paste_percentage)
        })

    if active_time < 10 and total_chars > 500:
        potential_flags.append({
            'priority': 10, 'severity': 'high', 'category': 'Time Analysis',
            'message': render_message('completed_quickly', active_time=active_time)
        })

    if velocity.get('average_cpm', 0) > 150:
        potential_flags.append({
            'priority': 10, 'severity': 'high', 'category': 'Typing Speed',
            'message': render_message('high_typing_speed', average_cpm=velocity.get('average_cpm', 0))
        })

    # --- File-level critical (priority 9) ---
    high_risk_files = [f for f, d in file_risks.items() if d['risk'] == 'high']
    if high_risk_files:
        f = high_risk_files[0]
        potential_flags.append({
            'priority': 9, 'severity': 'high', 'category': 'File Analysis',
            'message': render_message('file_risks', file=f, issues='; '.join(file_risks[f].get('issues', [])))
        })

    # --- Warnings (priority 5) ---
    if metrics['incremental_score'] < 4.0:
        potential_flags.append({
            'priority': 5, 'severity': 'medium', 'category': 'Development Pattern',
            'message': render_message('chunks_appeared', incremental_score=metrics['incremental_score'])
        })

    if metrics['typing_variance'] < 3.0:
        potential_flags.append({
            'priority': 5, 'severity': 'medium', 'category': 'Typing Behavior',
            'message': render_message('robotic_typing', typing_variance=metrics['typing_variance'])
        })

    if metrics['error_correction_ratio'] < 2.0 and total_chars > 200:
        potential_flags.append({
            'priority': 5, 'severity': 'medium', 'category': 'Error Correction',
            'message': render_message('few_corrections', error_correction_ratio=metrics['error_correction_ratio'])
        })

    if metrics.get('session_consistency', 0) < 4.0:
        potential_flags.append({
            'priority': 5, 'severity': 'medium', 'category': 'Work Sessions',
            'message': render_message('few_sessions', session_consistency=metrics.get('session_consistency', 0))
        })

    # Top 3 by priority
    potential_flags.sort(key=lambda x: x['priority'], reverse=True)
    flags = potential_flags[:3]
    for f in flags:
        f.pop('priority', None)

    if not flags:
        flags.append({
            'severity': 'none', 'category': 'Assessment',
            'message': render_message('no_suspicious')
        })

    return flags


# ---------------------------------------------------------------------------
# Overall score
# ---------------------------------------------------------------------------

def calculate_overall_score(metrics):
    """
    Weighted authenticity score (0-10) with hard penalties for obvious cheating.
    """
    score = (
        metrics['incremental_score'] * 0.25 +
        metrics['typing_variance'] * 0.20 +
        metrics['error_correction_ratio'] * 0.20 +
        metrics.get('session_consistency', 0) * 0.20 +
        metrics['velocity'].get('score', 0) * 0.15
    )

    # Hard cap if any single critical metric is very low
    if (metrics['incremental_score'] <= 2 or
            metrics['typing_variance'] <= 2 or
            metrics['velocity'].get('score', 10) <= 2):
        score = min(score, 3.0)

    # Extremely fast typing → near-zero
    if metrics['velocity'].get('average_cpm', 0) > 500:
        score = min(score, 1.0)

    # Paste bursts
    if metrics['paste_burst_count'] > 5:
        score *= 0.3
    elif metrics['paste_burst_count'] > 2:
        score *= 0.6

    # Single session penalty
    if metrics.get('session_consistency', 0) <= 1:
        score *= 0.7

    return round(max(score, 0.0), 1)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def calculate_all_metrics(event_data):
    """Calculate all metrics and return comprehensive analysis dict."""
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