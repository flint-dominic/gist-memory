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
from encode import encode_text
from retrieval import get_client, get_collection, index_memories
from perspectives import get_manager as get_perspective_manager

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


DAILY_MEMORY_DIR = PROJECT_ROOT.parent / "memory"


def _todays_themes(max_themes: int = 8) -> List[str]:
    """Extract themes from today's daily memory file (if any)."""
    if not DAILY_MEMORY_DIR.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    candidates = sorted(DAILY_MEMORY_DIR.glob(f"{today}*.md"))
    if not candidates:
        # Fall back to most recent daily file within last 3 days
        candidates = sorted(DAILY_MEMORY_DIR.glob("2*.md"))[-1:]
    if not candidates:
        return []
    try:
        text = candidates[-1].read_text()[:2000]
    except Exception:
        return []
    # Reuse context.py's theme extraction
    from context import extract_themes
    return extract_themes(text, max_themes=max_themes)


def _recent_memories_by_mtime(limit: int = 3) -> List[Dict]:
    """Return most-recently-modified memory YAMLs as recall-shaped dicts."""
    files = sorted(EXAMPLES_DIR.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    tracker = get_tracker()
    for f in files[:limit]:
        try:
            mem = yaml.safe_load(f.read_text())
            if not mem:
                continue
            mem_id = mem.get('id', f.stem)
            out.append({
                'id': mem_id,
                'similarity': 1.0,  # local source, no vector distance
                'frames': mem.get('gist', {}).get('frames', []),
                'salience': tracker.calculate_salience(mem_id),
                'initial_salience': mem.get('gist', {}).get('salience', 0.5),
                'summary': mem.get('summary', ''),
                'key_details': {},
                'perspective': None,
            })
        except Exception:
            continue
    return out


def session_start(
    participant: str = "gblfxt",
    channel: str = "unknown",
    inject_context: bool = True
) -> str:
    """
    Called at session start. Returns context to inject.

    Strategy: avoid generic global queries (which always return the same
    handful of memories). Instead, surface (a) the most recently created
    memories and (b) anything matching themes from today's daily memory file.
    """
    log = load_session_log()

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

    all_memories: List[Dict] = []
    seen_ids = set()

    # 1. Recently encoded memories — the model probably wants to know
    #    what was just learned, not what's been seen 100 times.
    for m in _recent_memories_by_mtime(limit=3):
        if m['id'] not in seen_ids:
            all_memories.append(m)
            seen_ids.add(m['id'])

    # 2. Memories matching themes from today's (or most recent) daily file.
    themes = _todays_themes(max_themes=8)
    if themes:
        query = ' '.join(themes)
        for m in recall(query, max_results=3, min_similarity=0.35):
            if m['id'] not in seen_ids:
                all_memories.append(m)
                seen_ids.add(m['id'])

    top_memories = all_memories[:5]

    session_entry["memories_loaded"] = [m['id'] for m in top_memories]
    session_entry["bootstrap_themes"] = themes
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


def get_next_memory_number() -> str:
    """Get next memory number based on existing files."""
    existing = list(EXAMPLES_DIR.glob("*.yaml"))
    numbers = []
    for f in existing:
        try:
            num = int(f.stem.split('-')[0])
            numbers.append(num)
        except (ValueError, IndexError):
            pass
    
    next_num = max(numbers) + 1 if numbers else 1
    return f"{next_num:03d}"


def auto_encode(
    content: str,
    title: Optional[str] = None,
    session_type: str = "conversation",
    participant: str = "gblfxt",
    model: str = "llama3:8b",
    generate_perspectives: bool = True,
    min_length: int = 100
) -> Dict:
    """
    Fully automatic memory encoding from session content.
    
    1. Validates content is worth encoding
    2. Encodes via LLM to extract frames, gist, verbatim
    3. Saves memory file
    4. Indexes in vector store
    5. Generates perspectives
    
    Args:
        content: Session transcript or summary to encode
        title: Optional title (auto-generated if not provided)
        session_type: Type of session (conversation, debugging, planning, etc)
        participant: Who was involved
        model: Ollama model to use
        generate_perspectives: Whether to auto-generate perspectives
        min_length: Minimum content length to encode
    
    Returns:
        Dict with success status, memory_id, and details
    """
    result = {
        "success": False,
        "memory_id": None,
        "filepath": None,
        "perspectives": 0,
        "message": ""
    }
    
    # Validate content
    if len(content.strip()) < min_length:
        result["message"] = f"Content too short ({len(content)} chars, min {min_length})"
        return result
    
    # Generate title if needed
    if not title:
        # Try to extract title from content
        lines = content.strip().split('\n')
        first_line = lines[0][:50].strip()
        # Clean up for filename
        title = "-".join(first_line.lower().split()[:4])
        title = "".join(c for c in title if c.isalnum() or c == '-')[:30]
        if not title:
            title = f"session-{datetime.now().strftime('%H%M')}"
    
    number = get_next_memory_number()
    memory_id = f"mem-{number}-{title}"
    filename = f"{number}-{title}.yaml"
    filepath = EXAMPLES_DIR / filename
    
    print(f"🧠 Auto-encoding as {memory_id}...", file=sys.stderr)
    
    # Encode via LLM
    try:
        entry = encode_text(
            content,
            model=model,
            entry_type=session_type,
            session_type="telegram",  # Default
            number=number
        )
        
        if not entry:
            result["message"] = "Encoding failed - no entry returned"
            return result
        
        # Fix ID to use our generated one
        entry['id'] = memory_id
        
        # Add metadata
        if 'metadata' not in entry:
            entry['metadata'] = {}
        entry['metadata']['participant'] = participant
        entry['metadata']['auto_encoded'] = True
        entry['metadata']['encoded_at'] = datetime.now().isoformat()
        
    except Exception as e:
        result["message"] = f"Encoding error: {e}"
        return result
    
    # Save to file
    try:
        yaml_output = yaml.dump(entry, default_flow_style=False, sort_keys=False, allow_unicode=True)
        filepath.write_text(yaml_output)
        print(f"  ✓ Saved to {filepath.name}", file=sys.stderr)
    except Exception as e:
        result["message"] = f"Save error: {e}"
        return result
    
    # Index in vector store
    try:
        client = get_client()
        collection = get_collection(client)
        index_memories(collection, force=False)
        print("  ✓ Indexed", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠ Index warning: {e}", file=sys.stderr)
    
    # Generate perspectives
    if generate_perspectives:
        try:
            # Quick perspective generation from detected frames
            frames = entry.get('gist', {}).get('frames', [])
            summary = entry.get('summary', '')
            
            if frames and summary:
                persp_manager = get_perspective_manager()
                
                # Add perspective for top 2-3 frames
                for i, frame in enumerate(frames[:3]):
                    salience = 0.9 - (i * 0.1)  # Decreasing salience
                    
                    # Generate frame-specific gist
                    # For now, use summary with frame context
                    # Could enhance with LLM later
                    persp_manager.add_perspective(
                        memory_id,
                        frame,
                        summary[:150] + "...",
                        salience,
                        []
                    )
                
                result["perspectives"] = min(3, len(frames))
                print(f"  ✓ Generated {result['perspectives']} perspectives", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠ Perspective warning: {e}", file=sys.stderr)
    
    result["success"] = True
    result["memory_id"] = memory_id
    result["filepath"] = str(filepath)
    result["message"] = f"Successfully encoded {memory_id}"
    
    return result


def encode_session_transcript(
    transcript_path: Optional[str] = None,
    content: Optional[str] = None,
    **kwargs
) -> Dict:
    """
    Encode a session transcript from file or string.
    
    Wrapper around auto_encode for convenience.
    """
    if transcript_path:
        path = Path(transcript_path)
        if not path.exists():
            return {"success": False, "message": f"File not found: {transcript_path}"}
        content = path.read_text()
    
    if not content:
        return {"success": False, "message": "No content provided"}
    
    return auto_encode(content, **kwargs)


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
        print("Usage: session.py [start|end|bootstrap|identity|auto-encode]")
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
    
    elif cmd == 'auto-encode':
        import argparse
        parser = argparse.ArgumentParser(description='Auto-encode session content')
        parser.add_argument('content', nargs='?', help='Content to encode (or - for stdin)')
        parser.add_argument('-t', '--title', help='Memory title')
        parser.add_argument('-f', '--file', help='Read content from file')
        parser.add_argument('--type', default='conversation', help='Session type')
        parser.add_argument('-m', '--model', default='llama3:8b', help='Ollama model')
        parser.add_argument('--no-perspectives', action='store_true', help='Skip perspective generation')
        
        # Parse remaining args
        args = parser.parse_args(sys.argv[2:])
        
        # Get content
        if args.file:
            content = Path(args.file).read_text()
        elif args.content == '-' or (args.content is None and not sys.stdin.isatty()):
            content = sys.stdin.read()
        elif args.content:
            content = args.content
        else:
            print("Error: No content provided. Use -f <file>, provide text, or pipe via stdin.")
            sys.exit(1)
        
        # Run auto-encode
        result = auto_encode(
            content,
            title=args.title,
            session_type=args.type,
            model=args.model,
            generate_perspectives=not args.no_perspectives
        )
        
        if result['success']:
            print(f"\n✅ {result['message']}")
            print(f"   Memory: {result['memory_id']}")
            print(f"   Perspectives: {result['perspectives']}")
        else:
            print(f"\n❌ {result['message']}")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
