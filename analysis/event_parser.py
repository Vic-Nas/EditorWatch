from datetime import datetime, timedelta


def get_event_summary(event_data):
    """
    Get a brief summary of events for display.
    Handles both compact and legacy formats.
    
    Returns: dict with summary statistics
    """
    # Normalize event data
    if isinstance(event_data, dict):
        events = event_data.get('events', [])
        base_time = event_data.get('base_time', 0)
        is_compact = events and isinstance(events[0], list)
    else:
        events = event_data
        base_time = 0
        is_compact = False
    
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
    
    # Extract data based on format
    if is_compact:
        # Compact format: [delta_ms, type, filename, char_count]
        inserts = [e for e in events if e[1] == 'i']
        deletes = [e for e in events if e[1] == 'd']
        
        start_time = base_time
        end_time = base_time + events[-1][0]  # base + last delta
        duration_minutes = (end_time - start_time) / 1000 / 60
        
        # Count activity periods (gaps > 5 min = new period)
        periods = 1
        last_time = start_time
        for event in events:
            event_time = base_time + event[0]
            if (event_time - last_time) / 1000 / 60 > 5:
                periods += 1
            last_time = event_time
        
        files = set(e[2] for e in events if len(e) > 2 and e[2])
        chars_added = sum(e[3] for e in inserts)
        chars_removed = sum(e[3] for e in deletes)
        
    else:
        # Legacy format: dict with 'type', 'timestamp', etc.
        inserts = [e for e in events if e.get('type') == 'insert']
        deletes = [e for e in events if e.get('type') == 'delete']
        
        start_time = events[0].get('timestamp', 0)
        end_time = events[-1].get('timestamp', 0)
        duration_minutes = (end_time - start_time) / 1000 / 60
        
        # Count activity periods
        periods = 1
        last_time = start_time
        for event in events:
            event_time = event.get('timestamp', 0)
            if (event_time - last_time) / 1000 / 60 > 5:
                periods += 1
            last_time = event_time
        
        files = set(e.get('file', 'unknown').split('/')[-1] for e in events if e.get('file'))
        chars_added = sum(e.get('char_count', 0) for e in inserts)
        chars_removed = sum(e.get('char_count', 0) for e in deletes)
    
    return {
        'total_events': len(events),
        'duration': f"{duration_minutes:.1f} minutes",
        'files': sorted(f for f in files if f),
        'activity_periods': periods,
        'insert_events': len(inserts),
        'delete_events': len(deletes),
        'chars_added': chars_added,
        'chars_removed': chars_removed
    }