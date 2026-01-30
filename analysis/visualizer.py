import plotly.graph_objects as go
from datetime import datetime


def create_timeline(events):
    """
    Create interactive timeline visualization showing when code was written.
    
    Returns: HTML string
    """
    if not events:
        return "<p>No events to visualize</p>"
    
    # Convert timestamps to datetime
    start_time = min(e['timestamp'] for e in events)
    
    # Group events by type
    event_types = {}
    for event in events:
        event_type = event['type']
        if event_type not in event_types:
            event_types[event_type] = []
        
        # Convert to minutes since start
        time_offset = (event['timestamp'] - start_time) / 1000 / 60
        event_types[event_type].append({
            'time': time_offset,
            'char_count': event.get('char_count', 0),
            'file': event.get('file', '').split('/')[-1]
        })
    
    # Create figure
    fig = go.Figure()
    
    colors = {
        'insert': '#2ecc71',
        'delete': '#e74c3c',
        'save': '#3498db'
    }
    
    for event_type, data in event_types.items():
        if not data:
            continue
        
        times = [d['time'] for d in data]
        char_counts = [d['char_count'] for d in data]
        files = [d['file'] for d in data]
        
        # Size markers by character count (for insert/delete)
        if event_type in ['insert', 'delete']:
            sizes = [min(max(c / 10, 5), 20) for c in char_counts]
        else:
            sizes = [10] * len(times)
        
        hover_text = [
            f"{event_type.title()}<br>{c} chars<br>{f}<br>{t:.1f} min"
            for t, c, f in zip(times, char_counts, files)
        ]
        
        fig.add_trace(go.Scatter(
            x=times,
            y=[1] * len(times),
            mode='markers',
            name=event_type.title(),
            marker=dict(
                size=sizes,
                color=colors.get(event_type, '#95a5a6')
            ),
            hovertext=hover_text,
            hoverinfo='text'
        ))
    
    # Update layout
    fig.update_layout(
        title='Coding Timeline',
        xaxis_title='Time (minutes since start)',
        yaxis_visible=False,
        height=400,
        hovermode='closest',
        showlegend=True
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_activity_heatmap(events):
    """
    Create heatmap of coding activity over time.
    
    Returns: HTML string
    """
    if not events:
        return ""
    
    # Group events into 5-minute bins
    start_time = min(e['timestamp'] for e in events)
    end_time = max(e['timestamp'] for e in events)
    
    bin_size = 5 * 60 * 1000  # 5 minutes in milliseconds
    bins = {}
    
    for event in events:
        bin_index = int((event['timestamp'] - start_time) / bin_size)
        if bin_index not in bins:
            bins[bin_index] = 0
        bins[bin_index] += 1
    
    # Create bar chart
    bin_labels = [f"{i*5}-{(i+1)*5} min" for i in sorted(bins.keys())]
    counts = [bins[i] for i in sorted(bins.keys())]
    
    fig = go.Figure(data=[
        go.Bar(x=bin_labels, y=counts, marker_color='#3498db')
    ])
    
    fig.update_layout(
        title='Activity Distribution (5-minute intervals)',
        xaxis_title='Time Period',
        yaxis_title='Number of Events',
        height=300
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')
