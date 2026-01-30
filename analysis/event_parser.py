from datetime import datetime, timedelta


def parse_events_to_timeline(events):
    """
    Parse raw events into human-readable timeline entries.
    
    Returns: list of timeline entries with formatted messages
    """
    if not events:
        return []
    
    timeline = []
    start_time = events[0]['timestamp']
    
    # Group nearby events together
    current_session = []
    last_timestamp = start_time
    
    for event in events:
        time_gap = (event['timestamp'] - last_timestamp) / 1000 / 60  # minutes
        
        # If gap > 5 minutes, treat as new session
        if time_gap > 5 and current_session:
            timeline.append(_summarize_session(current_session, start_time))
            current_session = []
        
        current_session.append(event)
        last_timestamp = event['timestamp']
    
    # Add final session
    if current_session:
        timeline.append(_summarize_session(current_session, start_time))
    
    return timeline


def _summarize_session(session, start_time):
    """Summarize a session of events into a readable entry"""
    if not session:
        return None
    
    first_event = session[0]
    last_event = session[-1]
    
    # Calculate elapsed time from start
    elapsed_minutes = (first_event['timestamp'] - start_time) / 1000 / 60
    duration_minutes = (last_event['timestamp'] - first_event['timestamp']) / 1000 / 60
    
    # Count event types
    inserts = [e for e in session if e['type'] == 'insert']
    deletes = [e for e in session if e['type'] == 'delete']
    saves = [e for e in session if e['type'] == 'save']
    
    # Calculate characters
    chars_added = sum(e['char_count'] for e in inserts)
    chars_removed = sum(e['char_count'] for e in deletes)
    
    # Get affected files
    files = set(e.get('file', 'unknown').split('/')[-1] for e in session)
    
    # Detect large pastes
    large_pastes = [e for e in inserts if e['char_count'] > 100]
    
    # Build message
    if len(session) == 1:
        event = session[0]
        if event['type'] == 'save':
            message = f"Saved {event.get('file', 'file').split('/')[-1]}"
        elif event['type'] == 'insert':
            if event['char_count'] > 100:
                message = f"⚠️ Large insert: {event['char_count']} characters"
            else:
                message = f"Typed {event['char_count']} characters"
        else:
            message = f"Deleted {event['char_count']} characters"
    else:
        parts = []
        
        if inserts:
            if large_pastes:
                parts.append(f"⚠️ {len(large_pastes)} large paste(s), {chars_added - sum(e['char_count'] for e in large_pastes)} chars typed")
            else:
                parts.append(f"{chars_added} chars added")
        
        if deletes:
            parts.append(f"{chars_removed} chars removed")
        
        if saves:
            parts.append(f"{len(saves)} save(s)")
        
        message = ", ".join(parts)
        
        if len(files) > 1:
            message += f" across {len(files)} files"
        else:
            message += f" in {list(files)[0]}"
    
    return {
        'time_elapsed': f"{elapsed_minutes:.0f}m" if elapsed_minutes > 0 else "Start",
        'duration': f"{duration_minutes:.1f}m" if duration_minutes > 0.1 else "instant",
        'message': message,
        'event_count': len(session),
        'suspicious': len(large_pastes) > 0,
        'files': list(files)
    }


def format_timeline_for_display(timeline):
    """
    Format timeline entries as HTML for display.
    
    Returns: HTML string
    """
    if not timeline:
        return "<p>No activity recorded</p>"
    
    html = ['<div class="timeline">']
    
    for entry in timeline:
        css_class = 'timeline-entry suspicious' if entry.get('suspicious') else 'timeline-entry'
        
        html.append(f'''
        <div class="{css_class}">
            <div class="timeline-time">
                <strong>{entry['time_elapsed']}</strong>
                <span class="duration">({entry['duration']})</span>
            </div>
            <div class="timeline-message">{entry['message']}</div>
            <div class="timeline-meta">{entry['event_count']} events</div>
        </div>
        ''')
    
    html.append('</div>')
    
    return '\n'.join(html)


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
            'activity_periods': 0
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