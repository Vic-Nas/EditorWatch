"""
Event summary extraction from compact event data.
Compact format: { base_time: int, events: [[delta_ms, type, filename, char_count], ...] }
Type codes: 'i' = insert, 'd' = delete, 's' = save
"""


def get_event_summary(event_data):
    """
    Get a brief summary of events for display.
    Returns: dict with summary statistics
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])

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

    inserts = [e for e in events if e[1] == 'i']
    deletes = [e for e in events if e[1] == 'd']

    # Duration from first to last event delta
    duration_minutes = events[-1][0] / 1000 / 60

    # Activity periods: gap > 5 min = new period
    periods = 1
    last_delta = 0
    for e in events:
        if (e[0] - last_delta) / 1000 / 60 > 5:
            periods += 1
        last_delta = e[0]

    return {
        'total_events': len(events),
        'duration': f"{duration_minutes:.1f} minutes",
        'files': sorted({e[2] for e in events if len(e) > 2 and e[2]}),
        'activity_periods': periods,
        'insert_events': len(inserts),
        'delete_events': len(deletes),
        'chars_added': sum(e[3] for e in inserts),
        'chars_removed': sum(e[3] for e in deletes)
    }