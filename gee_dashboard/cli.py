"""
Enhanced GEE Task Dashboard with Advanced Analytics
@author: Mateus H. Fulan
@date: 2026-08-27
"""

import ee
import time
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.align import Align
from datetime import datetime
from collections import defaultdict
import shutil

ee.Authenticate()
ee.Initialize()

console = Console()

GREEN = "#00ff41"
DARK_GREEN = "#00cc33"
PURPLE = "#9b30ff"
DARK_PURPLE = "#6a0dad"
NEON_PURPLE = "#cc44ff"
ACCENT = "#00ff66"

def calculate_task_duration(task):
    if hasattr(task, 'start_timestamp_ms') and hasattr(task, 'end_timestamp_ms'):
        if task.start_timestamp_ms and task.end_timestamp_ms:
            return (task.end_timestamp_ms - task.start_timestamp_ms) / 1000
    return None

def get_task_age(task):
    if hasattr(task, 'creation_timestamp_ms') and task.creation_timestamp_ms:
        age_ms = datetime.now().timestamp() * 1000 - task.creation_timestamp_ms
        return age_ms / (1000 * 60)
    return None

def analyze_failures(tasks_dict):
    failed_tasks = tasks_dict.get('FAILED', [])
    if not failed_tasks:
        return None, None
    
    error_types = defaultdict(int)
    for task in failed_tasks:
        if hasattr(task, 'error_message'):
            error_msg = task.error_message or 'Unknown error'
            if 'timeout' in error_msg.lower():
                error_types['Timeout'] += 1
            elif 'memory' in error_msg.lower():
                error_types['Memory'] += 1
            elif 'permission' in error_msg.lower():
                error_types['Permission'] += 1
            elif 'image' in error_msg.lower():
                error_types['Image Error'] += 1
            else:
                error_types['Other'] += 1
    
    return error_types

def categorize_by_type(tasks_dict):
    task_types = defaultdict(int)
    for state, tasks in tasks_dict.items():
        for task in tasks:
            if hasattr(task, 'description'):
                desc = task.description or ''
                if 'export' in desc.lower():
                    task_types['Export'] += 1
                elif 'compute' in desc.lower():
                    task_types['Compute'] += 1
                elif 'download' in desc.lower():
                    task_types['Download'] += 1
                elif 'ingest' in desc.lower():
                    task_types['Ingest'] += 1
                else:
                    task_types['Other'] += 1
    return task_types

def retrieve_tasks_details():
    tasks = ee.batch.Task.list()
    
    task_categories = {
        'READY': [], 'RUNNING': [], 'COMPLETED': [],
        'FAILED': [], 'CANCELLED': [], 'CANCEL_REQUESTED': [],
        'UNKNOWN': []
    }
    
    for task in tasks:
        state = task.state
        if state in task_categories:
            task_categories[state].append(task)
        else:
            task_categories['UNKNOWN'].append(task)
    
    return task_categories

def create_progress_bar(percentage, width):
    filled = int(width * percentage / 100)
    empty = width - filled
    
    if percentage >= 80:
        color = GREEN
    elif percentage >= 50:
        color = ACCENT
    else:
        color = NEON_PURPLE
    
    bar = "█" * filled + "░" * empty
    return f"[{color}]{bar}[/{color}]"

def create_progress_display(tasks_dict, width):
    completed = len(tasks_dict.get('COMPLETED', []))
    total = sum(len(tasks) for tasks in tasks_dict.values())
    
    if total == 0:
        progress_pct = 0
    else:
        progress_pct = (completed / total) * 100
    
    bar_width = max(10, width - 10)
    
    progress_display = Table(title="", box=None, padding=(0, 1))
    progress_display.add_column(style=f"bold {NEON_PURPLE}", justify="center")
    
    bar = create_progress_bar(progress_pct, bar_width)
    progress_display.add_row(f"{bar} {progress_pct:.1f}%")
    
    return Panel(
        progress_display,
        title=f"[bold {NEON_PURPLE}]Tasks Progress (Ready/Completed)[/bold {NEON_PURPLE}]",
        border_style=PURPLE
    )

def create_analytics_panel(tasks_dict):
    stats_table = Table(title=" ", box=None, padding=(0, 2))
    stats_table.add_column("Metric", style=f"bold {NEON_PURPLE}")
    stats_table.add_column("Value", justify="center")
    
    completed = len(tasks_dict.get('COMPLETED', []))
    failed = len(tasks_dict.get('FAILED', []))
    total = sum(len(tasks) for tasks in tasks_dict.values())
    
    for state, tasks in tasks_dict.items():
        if tasks:
            color = {
                'READY': GREEN,
                'RUNNING': NEON_PURPLE,
                'COMPLETED': GREEN,
                'FAILED': "#ff0044",
                'CANCELLED': PURPLE
            }.get(state, 'white')
            stats_table.add_row(f"{state.lower().capitalize()}", f"[{color}]{len(tasks)}[/{color}]")
    
    failed_count = failed
    if failed_count > 0:
        stats_table.add_row("Failed Tasks", f"[bold #ff0044]{failed_count}[/bold #ff0044]")
        
        error_types = analyze_failures(tasks_dict)
        if error_types:
            error_summary = ", ".join([f"{k}: {v}" for k, v in error_types.items()])
            stats_table.add_row("Error Types", f"[{GREEN}]{error_summary}[/{GREEN}]")
    
    durations = []
    for task in tasks_dict.get('COMPLETED', []):
        duration = calculate_task_duration(task)
        if duration:
            durations.append(duration)
    
    if durations:
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations)
        
        duration_str = f"{total_duration/3600:.1f}h" if total_duration > 3600 else f"{total_duration/60:.1f}m"
        avg_str = f"{avg_duration/60:.1f}m" if avg_duration > 60 else f"{avg_duration:.1f}s"
        
        stats_table.add_row("Total Time", duration_str)
        stats_table.add_row("Avg Duration", avg_str)
    
    task_types = categorize_by_type(tasks_dict)
    if task_types:
        types_str = ", ".join([f"{k}: {v}" for k, v in task_types.items()])
        stats_table.add_row("Task Types", f"[{GREEN}]{types_str}[/{GREEN}]")
    
    oldest_age = None
    for state, tasks in tasks_dict.items():
        if state not in ['COMPLETED', 'CANCELLED', 'FAILED']:
            for task in tasks:
                age = get_task_age(task)
                if age and (oldest_age is None or age > oldest_age):
                    oldest_age = age
    if oldest_age:
        age_str = f"{oldest_age:.0f}m" if oldest_age < 60 else f"{oldest_age/60:.1f}h"
        color = "#ff4444" if oldest_age > 60 else GREEN if oldest_age > 30 else GREEN
        stats_table.add_row("Oldest Task", f"[{color}]{age_str}[/{color}]")
    
    stats_table.add_row("Total Tasks", str(total))
    
    return Panel(
        stats_table,
        title=f"[bold {NEON_PURPLE}]Analytics Dashboard[/bold {NEON_PURPLE}]",
        border_style=PURPLE
    )

def create_dashboard(tasks_dict, console_width=None):
    if console_width is None:
        console_width = shutil.get_terminal_size().columns
    
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    layout["body"].split_row(
        Layout(name="left_panel", ratio=1),
        Layout(name="table", ratio=1)
    )
    
    layout["left_panel"].split(
        Layout(name="progress", size=4),
        Layout(name="analytics")
    )
    
    header_text = Text("GEE Tasks Dashboard", style=f"bold {GREEN}")
    header_text.append(f" - Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
    layout["header"].update(Panel(Align.center(header_text), style=DARK_PURPLE))
    
    progress_width = max(30, (console_width // 2) - 8)
    
    layout["progress"].update(create_progress_display(tasks_dict, progress_width))
    layout["analytics"].update(create_analytics_panel(tasks_dict))
    
    task_table = Table(title=" ", box=None)
    task_table.add_column("ID", style="dim", width=15)
    task_table.add_column("Description", width=25)
    task_table.add_column("State", width=12)
    task_table.add_column("Age", width=10)
    task_table.add_column("Duration", width=12)
    
    all_tasks = []
    for state, tasks in tasks_dict.items():
        for task in tasks:
            all_tasks.append((task, state))
    
    all_tasks = sorted(all_tasks, key=lambda x: 
                      x[0].creation_timestamp_ms if hasattr(x[0], 'creation_timestamp_ms') and x[0].creation_timestamp_ms else 0,
                      reverse=True)[:10]
    
    for task, state in all_tasks:
        description = task.description if hasattr(task, 'description') else 'N/A'
        task_id = task.id if hasattr(task, 'id') else 'N/A'
        
        color = {
            'READY': GREEN,
            'RUNNING': NEON_PURPLE,
            'COMPLETED': GREEN,
            'FAILED': "#ff0044",
            'CANCELLED': PURPLE,
            'CANCEL_REQUESTED': NEON_PURPLE
        }.get(state, 'white')
        
        age = get_task_age(task)
        age_str = f"{age:.0f}m" if age else 'N/A'
        age_color = '#ff4444' if (age and age > 60) else GREEN if (age and age > 30) else GREEN
        
        duration = calculate_task_duration(task)
        if duration:
            duration_str = f"{duration/60:.1f}m" if duration > 60 else f"{duration:.0f}s"
        else:
            duration_str = 'Running...' if state == 'RUNNING' else 'N/A'
        
        task_table.add_row(
            task_id[:12] + '...' if len(task_id) > 12 else task_id,
            description[:22] + '...' if len(description) > 22 else description,
            f"[{color}]{state}[/{color}]",
            f"[{age_color}]{age_str}[/{age_color}]",
            duration_str
        )
    
    layout["table"].update(Panel(
        task_table,
        title=f"[bold {NEON_PURPLE}]Recent Tasks[/bold {NEON_PURPLE}]",
        border_style=PURPLE
    ))
    
    footer_text = Text("Press Ctrl+C to exit", style="dim italic")
    failed_count = len(tasks_dict.get('FAILED', []))
    if failed_count > 0:
        footer_text.append(f" | {failed_count} failed tasks detected!", style="bold #ff4444")
    layout["footer"].update(Panel(Align.center(footer_text), style=DARK_PURPLE))
    
    return layout

def main():
    console.clear()
    
    with Live(console=console, refresh_per_second=1, screen=True) as live:
        try:
            while True:
                terminal_width = shutil.get_terminal_size().columns
                tasks_dict = retrieve_tasks_details()
                dashboard = create_dashboard(tasks_dict, terminal_width)
                live.update(dashboard)
                time.sleep(5)
                
        except KeyboardInterrupt:
            console.print(f"\n[bold {NEON_PURPLE}]Dashboard stopped by user.[/bold {NEON_PURPLE}]")

if __name__ == "__main__":
    main()
