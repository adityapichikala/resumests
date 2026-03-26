"""
ATS Visuals — Generates a modern radar/spider chart for 5-dimension ATS scores.
"""

import io
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from typing import Dict


def generate_radar_chart(scores_dict: Dict[str, int]) -> io.BytesIO:
    """
    Generate a professional radar/spider chart for ATS dimension scores.

    Args:
        scores_dict: Dict with keys 'keyword', 'skills', 'experience', 'achievement', 'formatting'
                     and int values 0-100.

    Returns:
        io.BytesIO buffer containing the PNG image.
    """
    # Dimension labels and values
    labels = ['Keyword\nMatch', 'Skills\nMatch', 'Experience', 'Achievement', 'Formatting']
    keys = ['keyword', 'skills', 'experience', 'achievement', 'formatting']
    values = [scores_dict.get(k, 0) for k in keys]

    # Close the polygon
    N = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    # Figure setup — dark theme
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('#0f0f1a')
    ax.set_facecolor('#0f0f1a')

    # Grid lines
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'],
                        fontsize=8, color='#555577', fontweight='bold')
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=11, color='#c8c8e0', fontweight='bold',
                        ha='center')

    # Style the grid
    ax.spines['polar'].set_color('#2a2a4a')
    ax.spines['polar'].set_linewidth(1.5)
    ax.tick_params(axis='y', colors='#555577')
    ax.tick_params(axis='x', pad=15)

    for spine in ax.spines.values():
        spine.set_color('#2a2a4a')

    ax.yaxis.grid(True, color='#2a2a4a', linewidth=0.8, linestyle='--', alpha=0.6)
    ax.xaxis.grid(True, color='#2a2a4a', linewidth=0.8, alpha=0.6)

    # Reference rings at 50 (threshold) and 80 (strong)
    threshold_vals = [50] * (N + 1)
    strong_vals = [80] * (N + 1)
    ax.plot(angles_closed, threshold_vals, color='#ff6b6b', linewidth=1, linestyle=':', alpha=0.4, label='Min Pass (50)')
    ax.plot(angles_closed, strong_vals, color='#51cf66', linewidth=1, linestyle=':', alpha=0.4, label='Strong (80)')

    # Main data fill
    gradient_color = '#6366f1'  # Indigo
    ax.fill(angles_closed, values_closed, color=gradient_color, alpha=0.15)
    ax.plot(angles_closed, values_closed, color=gradient_color, linewidth=2.5, linestyle='-')

    # Data point markers with adaptive coloring
    for i, (angle, val) in enumerate(zip(angles, values)):
        if val >= 80:
            color = '#51cf66'  # Green
        elif val >= 60:
            color = '#ffd43b'  # Yellow
        elif val >= 40:
            color = '#ff922b'  # Orange
        else:
            color = '#ff6b6b'  # Red

        ax.plot(angle, val, 'o', markersize=10, color=color,
                markeredgecolor='white', markeredgewidth=2, zorder=5)
        # Score label
        ax.annotate(f'{val}', xy=(angle, val), fontsize=10, fontweight='bold',
                    color='white', ha='center', va='bottom',
                    xytext=(0, 12), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.85, edgecolor='none'))

    # Title
    overall = sum(values) / len(values)
    fig.suptitle('ATS Performance Breakdown', fontsize=18, fontweight='bold',
                 color='#e0e0ff', y=0.98)

    # Legend
    ax.legend(loc='lower right', bbox_to_anchor=(1.25, -0.05),
              fontsize=9, facecolor='#1a1a2e', edgecolor='#2a2a4a',
              labelcolor='#aaaacc')

    plt.tight_layout(pad=2.0)

    # Save to buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='#0f0f1a', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf
