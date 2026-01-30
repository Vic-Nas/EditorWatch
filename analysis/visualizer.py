import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime


def create_velocity_chart(events):
    """
    Create clear velocity/speed chart showing typing speed over time.
    Color-coded: Green = normal human speed, Yellow = fast, Red = suspiciously fast
    
    Returns: HTML string
    """
    if not events:
        return ""
    
    insert_events = [e for e in events if e['type'] == 'insert']
    if not insert_events:
        return ""
    
    # Calculate chars per minute for 30-second windows
    window_size = 30 * 1000  # 30 seconds
    start_time = events[0]['timestamp']
    end_time = events[-1]['timestamp']
    
    times = []
    speeds = []
    colors = []
    
    current_time = start_time
    while current_time < end_time:
        window_end = current_time + window_size
        window_events = [e for e in insert_events 
                        if current_time <= e['timestamp'] < window_end]
        
        if window_events:
            chars = sum(e['char_count'] for e in window_events)
            cpm = chars * 2  # Convert 30-sec to per-minute
            time_minutes = (current_time - start_time) / 1000 / 60
            
            times.append(time_minutes)
            speeds.append(cpm)
            
            # Color code based on speed
            if cpm > 200:
                colors.append('red')
            elif cpm > 100:
                colors.append('orange')
            else:
                colors.append('green')
        
        current_time += window_size
    
    fig = go.Figure()
    
    # Add reference zones
    fig.add_hrect(y0=0, y1=80, fillcolor="green", opacity=0.1, 
                  annotation_text="Normal Human Speed", annotation_position="top left")
    fig.add_hrect(y0=80, y1=150, fillcolor="yellow", opacity=0.1,
                  annotation_text="Fast", annotation_position="top left")
    fig.add_hrect(y0=150, y1=500, fillcolor="red", opacity=0.1,
                  annotation_text="SUSPICIOUSLY FAST (likely pasting)", annotation_position="top left")
    
    # Add speed line
    fig.add_trace(go.Scatter(
        x=times,
        y=speeds,
        mode='lines+markers',
        name='Typing Speed',
        line=dict(color='blue', width=2),
        marker=dict(size=8, color=colors),
        hovertemplate='<b>Time: %{x:.1f} min</b><br>Speed: %{y:.0f} chars/min<extra></extra>'
    ))
    
    fig.update_layout(
        title='<b>Typing Speed Over Time</b><br><sub>Human coders: 40-80 chars/min | Pasting: >200 chars/min</sub>',
        xaxis_title='Time (minutes since start)',
        yaxis_title='Characters per Minute',
        height=400,
        hovermode='closest',
        showlegend=False
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_activity_overview(events, file_risks):
    """
    Create multi-panel overview dashboard with key insights.
    
    Returns: HTML string
    """
    if not events:
        return ""
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Event Types', 'Activity Over Time', 'File Risk Levels', 'Insert vs Delete Balance'),
        specs=[[{'type': 'pie'}, {'type': 'bar'}],
               [{'type': 'bar'}, {'type': 'bar'}]]
    )
    
    # 1. Event types pie chart
    event_counts = {}
    for e in events:
        event_type = e['type']
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    fig.add_trace(go.Pie(
        labels=list(event_counts.keys()),
        values=list(event_counts.values()),
        marker=dict(colors=['#2ecc71', '#e74c3c', '#3498db']),
        hovertemplate='<b>%{label}</b><br>%{value} events<br>%{percent}<extra></extra>'
    ), row=1, col=1)
    
    # 2. Activity over time (5-minute bins)
    start_time = min(e['timestamp'] for e in events)
    bin_size = 5 * 60 * 1000
    bins = {}
    
    for event in events:
        bin_index = int((event['timestamp'] - start_time) / bin_size)
        bins[bin_index] = bins.get(bin_index, 0) + 1
    
    bin_labels = [f"{i*5}" for i in sorted(bins.keys())]
    counts = [bins[i] for i in sorted(bins.keys())]
    
    fig.add_trace(go.Bar(
        x=bin_labels,
        y=counts,
        marker_color='#3498db',
        hovertemplate='<b>Minutes %{x}-' + str(int(bin_labels[-1]) + 5) + '</b><br>%{y} events<extra></extra>'
    ), row=1, col=2)
    
    # 3. File risk levels
    if file_risks:
        risk_counts = {'high': 0, 'medium': 0, 'low': 0}
        for data in file_risks.values():
            risk_counts[data['risk']] = risk_counts.get(data['risk'], 0) + 1
        
        fig.add_trace(go.Bar(
            x=['High Risk', 'Medium Risk', 'Low Risk'],
            y=[risk_counts['high'], risk_counts['medium'], risk_counts['low']],
            marker_color=['#e74c3c', '#f39c12', '#2ecc71'],
            hovertemplate='<b>%{x}</b><br>%{y} files<extra></extra>'
        ), row=2, col=1)
    
    # 4. Insert vs Delete balance
    inserts = [e['char_count'] for e in events if e['type'] == 'insert']
    deletes = [e['char_count'] for e in events if e['type'] == 'delete']
    
    fig.add_trace(go.Bar(
        x=['Characters Added', 'Characters Deleted'],
        y=[sum(inserts), sum(deletes)],
        marker_color=['#2ecc71', '#e74c3c'],
        text=[f'{sum(inserts):,}', f'{sum(deletes):,}'],
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>%{y:,} chars<extra></extra>'
    ), row=2, col=2)
    
    fig.update_layout(
        height=700,
        showlegend=False,
        title_text="<b>Activity Overview</b>"
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


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
        title='<b>Coding Timeline</b><br><sub>Larger bubbles = more characters changed</sub>',
        xaxis_title='Time (minutes since start)',
        yaxis_visible=False,
        height=400,
        hovermode='closest',
        showlegend=True
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_file_risk_table(file_risks):
    """
    Create HTML table showing file-level risk analysis.
    
    Returns: HTML string
    """
    if not file_risks:
        return "<p>No files analyzed</p>"
    
    # Sort by risk level
    risk_order = {'high': 0, 'medium': 1, 'low': 2}
    sorted_files = sorted(file_risks.items(), 
                         key=lambda x: (risk_order[x[1]['risk']], x[0]))
    
    html = ['<table style="width: 100%; border-collapse: collapse; margin-top: 20px;">']
    html.append('''
        <tr style="background: #f8f9fa; font-weight: bold;">
            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">File</th>
            <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Risk</th>
            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Issues</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Total Chars</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Edit Ratio</th>
        </tr>
    ''')
    
    risk_colors = {
        'high': '#ffebee',
        'medium': '#fff3e0',
        'low': '#e8f5e9'
    }
    
    risk_badges = {
        'high': '🔴 HIGH',
        'medium': '🟡 MEDIUM',
        'low': '🟢 LOW'
    }
    
    for filename, data in sorted_files:
        bg_color = risk_colors[data['risk']]
        html.append(f'''
            <tr style="background: {bg_color};">
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>{filename}</strong></td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">{risk_badges[data['risk']]}</td>
                <td style="padding: 12px; border: 1px solid #ddd;">{"; ".join(data['issues']) if data['issues'] else "No issues"}</td>
                <td style="padding: 12px; text-align: right; border: 1px solid #ddd;">{data['total_chars']:,}</td>
                <td style="padding: 12px; text-align: right; border: 1px solid #ddd;">{data['edit_ratio']:.2%}</td>
            </tr>
        ''')
    
    html.append('</table>')
    return '\n'.join(html)


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
        go.Bar(
            x=bin_labels, 
            y=counts, 
            marker_color='#3498db',
            hovertemplate='<b>%{x}</b><br>%{y} events<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title='<b>Activity Distribution</b><br><sub>Events per 5-minute interval</sub>',
        xaxis_title='Time Period',
        yaxis_title='Number of Events',
        height=300
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')