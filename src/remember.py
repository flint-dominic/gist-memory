#!/usr/bin/env python3
"""
Gist Memory - Remember Command
Quick encoding of current context into a memory entry.
"""

import os
import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from encode import encode_text
from retrieval import get_client, get_collection, index_memories

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def get_next_number() -> str:
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


def remember(
    content: str,
    title: str = "auto",
    entry_type: str = "conversation",
    session_type: str = "telegram",
    model: str = "llama3:8b",
    auto_index: bool = True
) -> Path:
    """
    Remember content by encoding and saving it.
    
    Returns path to created memory file.
    """
    number = get_next_number()
    slug = title.lower().replace(' ', '-')[:20] if title != "auto" else "memory"
    filename = f"{number}-{slug}.yaml"
    filepath = EXAMPLES_DIR / filename
    
    print(f"Encoding memory {number}...", file=sys.stderr)
    
    entry = encode_text(
        content,
        model=model,
        entry_type=entry_type,
        session_type=session_type,
        number=number
    )
    
    if not entry:
        print("Error: Encoding failed", file=sys.stderr)
        return None
    
    # Fix the ID to use our number
    if 'id' in entry:
        entry['id'] = f"mem-{number}-{slug}"
    
    # Write to file
    yaml_output = yaml.dump(entry, default_flow_style=False, sort_keys=False, allow_unicode=True)
    filepath.write_text(yaml_output)
    print(f"Saved to {filepath}", file=sys.stderr)
    
    # Auto-index
    if auto_index:
        print("Indexing...", file=sys.stderr)
        client = get_client()
        collection = get_collection(client)
        index_memories(collection, force=False)
    
    return filepath


def main():
    parser = argparse.ArgumentParser(description='Remember - Quick Memory Encoding')
    parser.add_argument('content', nargs='?', help='Content to remember (or - for stdin)')
    parser.add_argument('-t', '--title', default='auto', help='Short title for memory')
    parser.add_argument('--type', default='conversation',
                       help='Memory type (conversation, debugging, planning, reflection)')
    parser.add_argument('--session', default='telegram', help='Session type')
    parser.add_argument('-m', '--model', default='llama3:8b', help='Ollama model')
    parser.add_argument('--no-index', action='store_true', help='Skip auto-indexing')
    
    args = parser.parse_args()
    
    # Read content
    if args.content == '-' or args.content is None:
        content = sys.stdin.read()
    else:
        content = args.content
    
    if not content.strip():
        print("Error: No content to remember", file=sys.stderr)
        sys.exit(1)
    
    filepath = remember(
        content,
        title=args.title,
        entry_type=args.type,
        session_type=args.session,
        model=args.model,
        auto_index=not args.no_index
    )
    
    if filepath:
        print(f"\n✓ Remembered as {filepath.name}")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
