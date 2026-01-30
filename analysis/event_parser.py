from datetime import datetime, timedelta


def get_event_summary(events):
    """
    Get a brief summary of events for display.
    
    Returns: dict with summary statistics
    """
    if not events:
        return {
            'total_events': 0,
            'duration': '0 minutes',
            'files': [],
            'activity_periods': 0,
            'insert_events': 0,
            'delete_events': 0,
            'chars_added': 0,
            'chars_removed': 0
        }
    
    inserts = [e for e in events if e['type'] == 'insert']
    deletes = [e for e in events if e['type'] == 'delete']
    
    start_time = events[0]['timestamp']
    end_time = events[-1]['timestamp']
    duration_minutes = (end_time - start_time) / 1000 / 60
    
    # Count activity periods (gaps > 5 min = new period)
    periods = 1
    last_time = start_time
    for event in events:
        if (event['timestamp'] - last_time) / 1000 / 60 > 5:
            periods += 1
        last_time = event['timestamp']
    
    files = set(e.get('file', 'unknown').split('/')[-1] for e in events)
    
    return {
        'total_events': len(events),
        'duration': f"{duration_minutes:.1f} minutes",
        'files': list(files),
        'activity_periods': periods,
        'insert_events': len(inserts),
        'delete_events': len(deletes),
        'chars_added': sum(e['char_count'] for e in inserts),
        'chars_removed': sum(e['char_count'] for e in deletes)
    }