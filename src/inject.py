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
from session import get_identity_memories
from reinforcement import get_tracker

# Paths
WORKSPACE = Path.home() / "clawd"
CONTEXT_FILE = WORKSPACE / "GIST_CONTEXT.md"
MEMORY_FILE = WORKSPACE / "MEMORY.md"
GIST_MARKER_START = "\n<!-- GIST_CONTEXT_START -->\n"
GIST_MARKER_END = "\n<!-- GIST_CONTEXT_END -->\n"


def generate_gist_section() -> str:
    """Generate the gist memory section content."""
    identity = get_identity_memories()
    tracker = get_tracker()
    stats = tracker.all_stats()
    
    lines = [
        "## Gist Memory (Auto-Injected)",
        "",
        f"*Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {stats.get('total_memories', 0)} memories, {stats.get('decay_immune_count', 0)} locked*",
        "",
        "### Identity Memories",
        "",
    ]
    
    # Add identity memories
    for m in identity[:5]:
        immune = "🔒" if m['decay_immune'] else ""
        lines.append(f"**{m['id']}** {immune} (sal: {m['salience']:.2f})")
        summary = m['summary'].strip()[:150]
        if len(m['summary']) > 150:
            summary += "..."
        lines.append(f"> {summary}")
        lines.append("")
    
    # Add recovery instructions
    lines.extend([
        "### Context Recovery",
        "If context was lost, run: `gist recall 'your topic'`",
        "",
    ])
    
    return "\n".join(lines)


def inject_into_memory_md():
    """Inject gist context into MEMORY.md."""
    if not MEMORY_FILE.exists():
        return False
    
    content = MEMORY_FILE.read_text()
    gist_section = generate_gist_section()
    
    # Remove old gist section if present
    if GIST_MARKER_START in content:
        before = content.split(GIST_MARKER_START)[0]
        after_marker = content.split(GIST_MARKER_START)[1]
        if GIST_MARKER_END in after_marker:
            after = after_marker.split(GIST_MARKER_END)[1]
        else:
            after = ""
        content = before + after
    
    # Add new gist section at the end
    new_content = content.rstrip() + "\n\n" + GIST_MARKER_START + gist_section + GIST_MARKER_END
    
    MEMORY_FILE.write_text(new_content)
    return True


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
    parser.add_argument('--memory-md', action='store_true', help='Inject into MEMORY.md instead')
    args = parser.parse_args()
    
    if args.watch:
        watch_mode(args.interval)
    elif args.memory_md:
        if inject_into_memory_md():
            print(f"Injected gist context into {MEMORY_FILE}")
        else:
            print("Could not inject (MEMORY.md not found)")
    else:
        content = generate_context_file()
        if inject_into_memory_md():
            pass  # Also inject into MEMORY.md
        if not args.cron:
            print(content)
        else:
            print(f"Generated {CONTEXT_FILE}")


if __name__ == '__main__':
    main()
