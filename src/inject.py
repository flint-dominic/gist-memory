#!/usr/bin/env python3
"""
Gist Memory Context Injection
Generates a GIST_CONTEXT.md file for OpenClaw to include in system prompts.

Usage:
    python inject.py              # Generate context file
    python inject.py --watch      # Regenerate every 5 minutes
    python inject.py --cron       # Regenerate and exit (for cron)
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from session import get_identity_memories, bootstrap
from reinforcement import get_tracker

# Paths
WORKSPACE = Path.home() / "clawd"
CONTEXT_FILE = WORKSPACE / "GIST_CONTEXT.md"


def generate_context_file():
    """Generate GIST_CONTEXT.md with current memory state."""
    
    identity = get_identity_memories()
    tracker = get_tracker()
    stats = tracker.all_stats()
    
    lines = [
        "# GIST_CONTEXT.md",
        "",
        "*Auto-generated gist memory context. Updated: " + datetime.now().strftime("%Y-%m-%d %H:%M") + "*",
        "",
        "## Identity Memories (Core Self)",
        "",
    ]
    
    # Add identity memories
    for m in identity[:5]:
        immune = "🔒" if m['decay_immune'] else ""
        lines.append(f"### {m['id']} {immune}")
        lines.append(f"*Salience: {m['salience']:.2f} | Frames: {', '.join(m['frames'][:3])}*")
        lines.append("")
        # Truncate summary
        summary = m['summary'].strip()[:300]
        if len(m['summary']) > 300:
            summary += "..."
        lines.append(summary)
        lines.append("")
    
    # Add quick stats
    lines.extend([
        "---",
        "",
        "## Memory Stats",
        "",
        f"- **Total memories:** {stats.get('total_memories', 0)}",
        f"- **Total accesses:** {stats.get('total_accesses', 0)}",
        f"- **Locked (decay-immune):** {stats.get('decay_immune_count', 0)}",
        "",
        "## Context Recovery",
        "",
        "If context was lost after compaction, run:",
        "```bash",
        "cd ~/clawd && source .venv/bin/activate && gist recall 'your topic'",
        "```",
        "",
        "Or for full bootstrap:",
        "```bash",
        "gist bootstrap",
        "```",
        "",
    ])
    
    content = "\n".join(lines)
    CONTEXT_FILE.write_text(content)
    return content


def watch_mode(interval_seconds: int = 300):
    """Regenerate context file periodically."""
    print(f"Watching gist memory, regenerating every {interval_seconds}s...")
    while True:
        try:
            generate_context_file()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Regenerated GIST_CONTEXT.md")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description='Gist Memory Context Injection')
    parser.add_argument('--watch', action='store_true', help='Watch mode (regenerate every 5 min)')
    parser.add_argument('--cron', action='store_true', help='Generate once and exit')
    parser.add_argument('--interval', type=int, default=300, help='Watch interval in seconds')
    args = parser.parse_args()
    
    if args.watch:
        watch_mode(args.interval)
    else:
        content = generate_context_file()
        if not args.cron:
            print(content)
        else:
            print(f"Generated {CONTEXT_FILE}")


if __name__ == '__main__':
    main()
