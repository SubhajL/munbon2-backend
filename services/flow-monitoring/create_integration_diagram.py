#!/usr/bin/env python3
"""
Create visual diagram of service integration architecture
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np

# Create figure
fig, ax = plt.subplots(1, 1, figsize=(16, 12))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# Color scheme
colors = {
    'external': '#FFE5B4',  # Peach
    'core': '#B4E5FF',      # Light Blue
    'data': '#B4FFB4',      # Light Green
    'flow': '#FFB4B4'       # Light Red
}

# Service positions
services = {
    'SCADA': (1, 8.5),
    'Sensors': (1, 7),
    'Mobile': (1, 5.5),
    'Farmers': (1, 4),
    
    'Flow Monitor': (4, 7),
    'Gravity Opt': (4, 5),
    'Field Ops': (4, 3),
    'SCADA Int': (4, 9),
    
    'InfluxDB': (7, 8),
    'TimescaleDB': (7, 6.5),
    'Redis': (7, 5),
    'PostgreSQL': (7, 3.5)
}

# Draw boxes
def draw_box(ax, pos, text, color, width=1.5, height=0.8):
    box = FancyBboxPatch(
        (pos[0] - width/2, pos[1] - height/2),
        width, height,
        boxstyle="round,pad=0.1",
        facecolor=color,
        edgecolor='black',
        linewidth=2
    )
    ax.add_patch(box)
    ax.text(pos[0], pos[1], text, ha='center', va='center', fontsize=10, weight='bold')

# Draw external systems
for service in ['SCADA', 'Sensors', 'Mobile', 'Farmers']:
    draw_box(ax, services[service], service, colors['external'])

# Draw core services
draw_box(ax, services['Flow Monitor'], 'Flow Monitoring\nService\n(Port 3011)', colors['flow'], width=1.8, height=1.2)
draw_box(ax, services['Gravity Opt'], 'Gravity\nOptimization\n(Port 3010)', colors['core'])
draw_box(ax, services['Field Ops'], 'Scheduled\nField Ops\n(Port 3031)', colors['core'])
draw_box(ax, services['SCADA Int'], 'SCADA\nIntegration\n(Port 3015)', colors['core'])

# Draw data stores
for db in ['InfluxDB', 'TimescaleDB', 'Redis', 'PostgreSQL']:
    draw_box(ax, services[db], db, colors['data'])

# Draw connections with labels
def draw_arrow(ax, start, end, label, color='blue', style='->'):
    arrow = ConnectionPatch(
        start, end, "data", "data",
        arrowstyle=style,
        shrinkA=40, shrinkB=40,
        mutation_scale=20,
        fc=color,
        ec=color,
        linewidth=2
    )
    ax.add_artist(arrow)
    
    # Add label
    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2
    angle = np.arctan2(end[1] - start[1], end[0] - start[0]) * 180 / np.pi
    
    ax.text(mid_x, mid_y, label, ha='center', va='bottom', 
            fontsize=8, rotation=angle if abs(angle) < 90 else angle + 180,
            bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))

# External to services connections
draw_arrow(ax, services['Sensors'], services['Flow Monitor'], 'Raw Data', 'green')
draw_arrow(ax, services['SCADA'], services['SCADA Int'], 'OPC UA', 'purple')
draw_arrow(ax, services['Farmers'], services['Field Ops'], 'Requests', 'orange')
draw_arrow(ax, services['Mobile'], services['Field Ops'], 'Updates', 'orange', '<->')

# Service interactions
draw_arrow(ax, services['Flow Monitor'], services['Gravity Opt'], 'Current State', 'blue')
draw_arrow(ax, services['Gravity Opt'], services['Flow Monitor'], 'Optimal Settings', 'red')
draw_arrow(ax, services['Flow Monitor'], services['Field Ops'], 'Flow Data', 'blue')
draw_arrow(ax, services['Field Ops'], services['Flow Monitor'], 'Manual Gates', 'orange')
draw_arrow(ax, services['SCADA Int'], services['Flow Monitor'], 'Gate Status', 'purple')
draw_arrow(ax, services['Flow Monitor'], services['SCADA Int'], 'Commands', 'red')

# Data store connections
draw_arrow(ax, services['Flow Monitor'], services['InfluxDB'], 'Real-time', 'green')
draw_arrow(ax, services['Flow Monitor'], services['TimescaleDB'], 'Aggregated', 'green')
draw_arrow(ax, services['Flow Monitor'], services['Redis'], 'Cache', 'green')

# Title and sections
ax.text(1, 9.5, 'External Systems', fontsize=14, weight='bold', ha='center')
ax.text(4, 9.8, 'Core Services', fontsize=14, weight='bold', ha='center')
ax.text(7, 9.5, 'Data Stores', fontsize=14, weight='bold', ha='center')

# Add main title
ax.text(5, 9.8, 'Munbon Irrigation Service Integration Architecture', 
        fontsize=18, weight='bold', ha='center',
        bbox=dict(boxstyle="round,pad=0.5", facecolor='lightgray'))

# Add legend
legend_items = [
    ('Data Flow', 'blue'),
    ('Control Commands', 'red'),
    ('Sensor/Hardware', 'green'),
    ('SCADA Protocol', 'purple'),
    ('Field Operations', 'orange')
]

y_pos = 2
for label, color in legend_items:
    ax.plot([8.5, 9], [y_pos, y_pos], color=color, linewidth=3)
    ax.text(9.1, y_pos, label, va='center', fontsize=10)
    y_pos -= 0.3

ax.text(8.5, 2.5, 'Connection Types:', fontsize=12, weight='bold')

plt.tight_layout()
plt.savefig('integration_architecture_diagram.png', dpi=300, bbox_inches='tight')
plt.savefig('integration_architecture_diagram.pdf', bbox_inches='tight')
print("Integration architecture diagram saved as PNG and PDF")

# Create a second diagram showing data flow timing
fig2, ax2 = plt.subplots(1, 1, figsize=(14, 10))
ax2.set_xlim(0, 10)
ax2.set_ylim(0, 10)
ax2.axis('off')

# Draw timeline for real-time control loop
ax2.text(5, 9.5, 'Real-Time Control Loop (Automated Gates)', 
         fontsize=16, weight='bold', ha='center')

# Timeline positions
timeline_y = 8
steps = [
    (1, 'Sensors\nRead'),
    (2.5, 'Flow Monitor\nCalculate'),
    (4, 'Gravity Opt\nOptimize'),
    (5.5, 'Flow Monitor\nCommand'),
    (7, 'SCADA\nExecute'),
    (8.5, 'Gate\nMoves')
]

# Draw timeline
ax2.arrow(0.5, timeline_y, 9, 0, head_width=0.2, head_length=0.2, fc='black', ec='black')

for x, label in steps:
    ax2.plot(x, timeline_y, 'bo', markersize=12)
    ax2.text(x, timeline_y - 0.5, label, ha='center', va='top', fontsize=10)
    ax2.text(x, timeline_y + 0.3, f'{int((x-1)*100)}ms', ha='center', va='bottom', fontsize=8)

# Draw weekly planning loop
ax2.text(5, 6, 'Weekly Planning Loop (Manual Gates)', 
         fontsize=16, weight='bold', ha='center')

weekly_y = 4.5
weekly_steps = [
    (1, 'Monday\nPlanning', 'Mon 6:00'),
    (3, 'Work Orders\nGenerated', 'Mon 8:00'),
    (5, 'Field Teams\nExecute', 'Mon-Fri'),
    (7, 'Status\nUpdates', 'Real-time'),
    (9, 'State\nReconciled', 'Continuous')
]

# Draw weekly timeline
ax2.arrow(0.5, weekly_y, 9, 0, head_width=0.2, head_length=0.2, fc='gray', ec='gray')

for x, label, time in weekly_steps:
    ax2.plot(x, weekly_y, 'go', markersize=12)
    ax2.text(x, weekly_y - 0.5, label, ha='center', va='top', fontsize=10)
    ax2.text(x, weekly_y + 0.3, time, ha='center', va='bottom', fontsize=8, style='italic')

# Draw mode transition flow
ax2.text(5, 2.5, 'Mode Transition Flow', fontsize=16, weight='bold', ha='center')

transition_y = 1
ax2.text(1, transition_y, 'Auto Mode', ha='center', bbox=dict(boxstyle="round", facecolor='lightgreen'))
ax2.text(3, transition_y, 'Failure\nDetected', ha='center', bbox=dict(boxstyle="round", facecolor='yellow'))
ax2.text(5, transition_y, 'State\nPreserved', ha='center', bbox=dict(boxstyle="round", facecolor='lightblue'))
ax2.text(7, transition_y, 'Manual\nMode', ha='center', bbox=dict(boxstyle="round", facecolor='orange'))
ax2.text(9, transition_y, 'Recovery', ha='center', bbox=dict(boxstyle="round", facecolor='lightgreen'))

# Draw arrows between states
for i in range(4):
    ax2.arrow(1.5 + i*2, transition_y, 1, 0, head_width=0.1, head_length=0.1, fc='red', ec='red')

plt.tight_layout()
plt.savefig('service_timing_diagram.png', dpi=300, bbox_inches='tight')
plt.savefig('service_timing_diagram.pdf', bbox_inches='tight')
print("Service timing diagram saved as PNG and PDF")

# Create a third diagram showing data structures
fig3, ax3 = plt.subplots(1, 1, figsize=(14, 10))
ax3.set_xlim(0, 10)
ax3.set_ylim(0, 10)
ax3.axis('off')

ax3.text(5, 9.5, 'Key Data Structures Between Services', 
         fontsize=16, weight='bold', ha='center')

# Draw data structure boxes
structures = [
    {
        'pos': (2, 7),
        'title': 'Hydraulic State',
        'content': '• Water Levels\n• Gate Flows\n• Gate Positions\n• System Efficiency',
        'color': colors['flow']
    },
    {
        'pos': (5, 7),
        'title': 'Optimization Target',
        'content': '• Zone Flows\n• Gate Suggestions\n• Constraints\n• Priority Zones',
        'color': colors['core']
    },
    {
        'pos': (8, 7),
        'title': 'Work Order',
        'content': '• Gate ID\n• Target Opening\n• Schedule Time\n• Team Assignment',
        'color': colors['core']
    },
    {
        'pos': (2, 4),
        'title': 'Gate Registry',
        'content': '• Control Mode\n• SCADA Tags\n• Calibration\n• Equipment Status',
        'color': colors['data']
    },
    {
        'pos': (5, 4),
        'title': 'Mode Transition',
        'content': '• Current Mode\n• Trigger Event\n• Preserved State\n• Recovery Plan',
        'color': colors['flow']
    },
    {
        'pos': (8, 4),
        'title': 'Performance Metrics',
        'content': '• Response Time\n• Flow Accuracy\n• Gate Reliability\n• Water Losses',
        'color': colors['data']
    }
]

for struct in structures:
    # Draw box
    box = FancyBboxPatch(
        (struct['pos'][0] - 1.3, struct['pos'][1] - 1.2),
        2.6, 2.4,
        boxstyle="round,pad=0.1",
        facecolor=struct['color'],
        edgecolor='black',
        linewidth=2
    )
    ax3.add_patch(box)
    
    # Add title
    ax3.text(struct['pos'][0], struct['pos'][1] + 0.8, struct['title'], 
             ha='center', va='center', fontsize=12, weight='bold')
    
    # Add content
    ax3.text(struct['pos'][0], struct['pos'][1] - 0.2, struct['content'], 
             ha='center', va='center', fontsize=10)

# Draw relationships
draw_arrow(ax3, (3.3, 7), (3.7, 7), '', 'blue', '<->')
draw_arrow(ax3, (6.3, 7), (6.7, 7), '', 'orange', '->')
draw_arrow(ax3, (2, 5.2), (5, 5.2), 'Triggers', 'red')
draw_arrow(ax3, (5, 2.8), (8, 2.8), 'Monitors', 'green')

plt.tight_layout()
plt.savefig('data_structures_diagram.png', dpi=300, bbox_inches='tight')
plt.savefig('data_structures_diagram.pdf', bbox_inches='tight')
print("Data structures diagram saved as PNG and PDF")

print("\nAll diagrams created successfully!")