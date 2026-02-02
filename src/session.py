#!/usr/bin/env python3
"""
Session Integration for Gist Memory
Handles automatic context loading and session encoding.
"""

import sys
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent))
from reinforcement import get_tracker
from recall import recall, format_for_context

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SESSION_LOG = PROJECT_ROOT / ".session-log.json"


def load_session_log() -> Dict:
    """Load session history."""
    if SESSION_LOG.exists():
        try:
            return json.loads(SESSION_LOG.read_text())
        except:
            pass
    return {"sessions": [], "last_context": None}


def save_session_log(log: Dict):
    """Save session history."""
    SESSION_LOG.write_text(json.dumps(log, indent=2, default=str))


def session_start(
    participant: str = "gblfxt",
    channel: str = "unknown",
    inject_context: bool = True
) -> str:
    """
    Called at session start. Returns context to inject.
    
    1. Logs session start
    2. Recalls relevant memories based on participant/recent activity
    3. Returns formatted context for injection
    """
    log = load_session_log()
    
    # Log this session
    session_entry = {
        "started": datetime.now().isoformat(),
        "participant": participant,
        "channel": channel,
        "memories_loaded": []
    }
    
    if not inject_context:
        log["sessions"].append(session_entry)
        save_session_log(log)
        return ""
    
    # Build context query from recent activity
    queries = [
        f"conversations with {participant}",
        "recent work and projects",
        "important context"
    ]
    
    # Get recent memories
    all_memories = []
    seen_ids = set()
    
    for q in queries:
        memories = recall(q, max_results=3, min_similarity=0.3)
        for m in memories:
            if m['id'] not in seen_ids:
                all_memories.append(m)
                seen_ids.add(m['id'])
    
    # Sort by salience
    all_memories.sort(key=lambda x: -x['salience'])
    top_memories = all_memories[:5]
    
    session_entry["memories_loaded"] = [m['id'] for m in top_memories]
    log["sessions"].append(session_entry)
    log["last_context"] = datetime.now().isoformat()
    save_session_log(log)
    
    if not top_memories:
        return "No relevant memories found for context."
    
    return format_for_context(top_memories, verbose=False)


def session_end_prompt(summary: str = "") -> Dict:
    """
    Called at session end. Returns encoding prompt/suggestion.
    
    Analyzes what might be worth remembering from this session.
    """
    log = load_session_log()
    
    result = {
        "should_encode": True,
        "suggested_title": "",
        "suggested_frames": [],
        "prompt": ""
    }
    
    # Check last session
    if log["sessions"]:
        last = log["sessions"][-1]
        started = datetime.fromisoformat(last["started"])
        duration = datetime.now() - started
        
        if duration.total_seconds() < 300:  # Less than 5 minutes
            result["should_encode"] = False
            result["prompt"] = "Session too short to encode."
            return result
    
    # Generate encoding prompt
    result["prompt"] = f"""Session ending. Consider encoding if:
- Significant decisions were made
- New information was learned
- Important work was completed
- Meaningful conversation occurred

Quick encode: gist remember "summary of session" -t "short-title"

Summary provided: {summary if summary else "(none)"}
"""
    
    return result


def quick_remember(
    content: str,
    title: Optional[str] = None,
    auto_title: bool = True
) -> Dict:
    """
    Quick memory encoding with minimal friction.
    """
    import subprocess
    
    cmd = ["python", str(PROJECT_ROOT / "src" / "remember.py"), content]
    
    if title:
        cmd.extend(["-t", title])
    elif auto_title:
        # Generate title from first few words
        words = content.split()[:4]
        title = "-".join(w.lower() for w in words)
        cmd.extend(["-t", title])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr
    }


def get_identity_memories() -> List[Dict]:
    """
    Get core identity memories (L3 equivalent - highest salience, decay-immune).
    These should always be available.
    """
    tracker = get_tracker()
    identity = []
    
    for f in EXAMPLES_DIR.glob("*.yaml"):
        try:
            mem = yaml.safe_load(f.read_text())
            mem_id = mem.get('id', f.stem)
            data = tracker.get(mem_id)
            salience = tracker.calculate_salience(mem_id)
            
            # Identity memories: high salience OR decay immune
            if salience >= 0.9 or data.decay_immune:
                identity.append({
                    'id': mem_id,
                    'salience': salience,
                    'decay_immune': data.decay_immune,
                    'summary': mem.get('summary', '')[:200],
                    'frames': mem.get('gist', {}).get('frames', [])
                })
        except:
            continue
    
    return sorted(identity, key=lambda x: -x['salience'])


def bootstrap() -> str:
    """
    Full bootstrap for session start.
    Returns formatted context including identity + recent memories.
    """
    lines = ["# 🌀 Gist Memory Bootstrap\n"]
    
    # Identity memories (always load)
    identity = get_identity_memories()
    if identity:
        lines.append("## Core Memories (Identity)")
        for m in identity[:3]:
            immune = "🔒" if m['decay_immune'] else ""
            lines.append(f"- **{m['id']}** {immune} ({m['salience']:.2f})")
            lines.append(f"  {m['summary'][:150]}...")
        lines.append("")
    
    # Recent context
    lines.append("## Recent Context")
    context = session_start(inject_context=True)
    if context and context != "No relevant memories found for context.":
        lines.append(context)
    else:
        lines.append("(No specific recent context)")
    
    # Stats
    tracker = get_tracker()
    stats = tracker.all_stats()
    lines.append(f"\n*{stats.get('total_memories', 0)} memories indexed, {stats.get('decay_immune_count', 0)} locked*")
    
    return "\n".join(lines)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: session.py [start|end|bootstrap|identity]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'start':
        participant = sys.argv[2] if len(sys.argv) > 2 else "gblfxt"
        channel = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        print(session_start(participant, channel))
    
    elif cmd == 'end':
        summary = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        result = session_end_prompt(summary)
        print(result['prompt'])
    
    elif cmd == 'bootstrap':
        print(bootstrap())
    
    elif cmd == 'identity':
        identity = get_identity_memories()
        print("=== Identity Memories ===")
        for m in identity:
            immune = "🔒" if m['decay_immune'] else "  "
            print(f"{immune} {m['salience']:.2f}  {m['id']}")
            print(f"      Frames: {', '.join(m['frames'][:3])}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
