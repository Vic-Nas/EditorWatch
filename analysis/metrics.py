import numpy as np


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


def calculate_all_metrics(events):
    """Calculate all metrics at once"""
    return {
        'incremental_score': incremental_score(events),
        'typing_variance': typing_variance(events),
        'error_correction_ratio': error_correction_ratio(events),
        'paste_burst_count': paste_burst_detection(events)
    }
