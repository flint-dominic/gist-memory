#!/usr/bin/env python3
"""
Gist Memory Auto-Encoder
Converts conversations/text into memory entries using LLM analysis.
"""

import os
import sys
import json
import yaml
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

# Try to import ollama, fall back gracefully
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
FRAMES_DOC = PROJECT_ROOT / "docs" / "FRAMES.md"

# Default model
DEFAULT_MODEL = "llama3:8b"

# Load frame taxonomy for the prompt
def load_frames() -> str:
    """Load the frame taxonomy for context."""
    if FRAMES_DOC.exists():
        return FRAMES_DOC.read_text()
    return ""

ENCODE_PROMPT = """You are encoding a conversation into a gist memory entry.

## Frame Taxonomy (choose from these)
{frames}

## Task
Analyze the following content and produce a memory entry in YAML format.

Guidelines:
- frames: Pick 3-7 relevant frames from the taxonomy
- emotional_tone: List 3-6 emotional qualities present
- salience: 0.0-1.0, how important/memorable is this? (0.9+ for foundational, 0.5 for routine)
- verbatim.stored: Key specific facts/quotes/details worth preserving (5-10 items)
- verbatim.reconstructable: Things that could be inferred but weren't explicitly stored
- summary: 3-5 sentence summary capturing the gist
- retrieval_hints: 5-10 search queries that should find this memory

## Content to Encode
{content}

## Output Format
Produce ONLY valid YAML, no markdown code blocks, starting with `id:`. Use this structure:

id: mem-{number}-shortslug
timestamp: {timestamp}
type: {type}

gist:
  frames:
    - frame_name
  emotional_tone:
    - tone
  salience: 0.X
  confidence: 0.X
  source: encoded

verbatim:
  stored:
    key_name:
      value: "the specific detail"
      context: "why it matters"
      confidence: 0.X
  reconstructable:
    item_name:
      hint: "what could be inferred"
      reconstruction_confidence: 0.X
      FLAGGED: true

metadata:
  participant: name
  session_key: unknown
  session_type: {session_type}
  duration_estimate: "X hours"
  related_entries: []
  tags:
    - tag

summary: |
  Multi-line summary here.

retrieval_hints:
  - "search query"
"""


def generate_id(content: str, prefix: str = "auto") -> str:
    """Generate a unique ID based on content hash."""
    hash_short = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"mem-{prefix}-{hash_short}"


def encode_with_ollama(
    content: str,
    model: str = DEFAULT_MODEL,
    entry_type: str = "conversation",
    session_type: str = "unknown",
    number: str = "XXX"
) -> Optional[str]:
    """Use Ollama to encode content into a memory entry."""
    if not HAS_OLLAMA:
        print("Error: ollama package not installed", file=sys.stderr)
        return None
    
    frames = load_frames()
    timestamp = datetime.now().isoformat()
    
    prompt = ENCODE_PROMPT.replace('{frames}', frames)
    prompt = prompt.replace('{content}', content[:8000])
    prompt = prompt.replace('{timestamp}', timestamp)
    prompt = prompt.replace('{type}', entry_type)
    prompt = prompt.replace('{session_type}', session_type)
    prompt = prompt.replace('{number}', number)
    
    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                "temperature": 0.3,  # Lower for more consistent output
                "num_predict": 2000,
            }
        )
        return response['response']
    except Exception as e:
        print(f"Ollama error: {e}", file=sys.stderr)
        return None


def clean_yaml_output(raw: str) -> str:
    """Clean up LLM output to valid YAML."""
    # Remove markdown code blocks if present
    if "```yaml" in raw:
        raw = raw.split("```yaml")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    
    # Find where YAML starts (id: line)
    lines = raw.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('id:'):
            start_idx = i
            break
    
    return '\n'.join(lines[start_idx:]).strip()


def validate_and_fix(yaml_str: str, content: str) -> dict:
    """Validate YAML and fix common issues."""
    try:
        entry = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        print(f"YAML parse error: {e}", file=sys.stderr)
        return None
    
    # Ensure required fields
    if 'id' not in entry:
        entry['id'] = generate_id(content)
    
    if 'gist' not in entry:
        entry['gist'] = {}
    
    if 'frames' not in entry.get('gist', {}):
        entry['gist']['frames'] = ['collaborative_exploration']
    
    if 'salience' not in entry.get('gist', {}):
        entry['gist']['salience'] = 0.5
    
    if 'source' not in entry.get('gist', {}):
        entry['gist']['source'] = 'encoded'
    
    if 'summary' not in entry:
        entry['summary'] = "Auto-encoded memory entry."
    
    if 'retrieval_hints' not in entry:
        entry['retrieval_hints'] = []
    
    return entry


def encode_file(filepath: Path, **kwargs) -> Optional[dict]:
    """Encode a file's contents into a memory entry."""
    content = filepath.read_text()
    return encode_text(content, **kwargs)


def encode_text(content: str, model: str = DEFAULT_MODEL, **kwargs) -> Optional[dict]:
    """Encode text content into a memory entry."""
    print(f"Encoding with {model}...", file=sys.stderr)
    
    raw_output = encode_with_ollama(content, model=model, **kwargs)
    if not raw_output:
        return None
    
    cleaned = clean_yaml_output(raw_output)
    entry = validate_and_fix(cleaned, content)
    
    return entry


def main():
    parser = argparse.ArgumentParser(description='Gist Memory Auto-Encoder')
    parser.add_argument('input', nargs='?', help='File to encode (or - for stdin)')
    parser.add_argument('-m', '--model', default=DEFAULT_MODEL,
                       help=f'Ollama model to use (default: {DEFAULT_MODEL})')
    parser.add_argument('-t', '--type', default='conversation',
                       help='Memory type (conversation, debugging, planning, reflection, setup)')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('-n', '--number', default='XXX',
                       help='Entry number for ID (e.g., 008)')
    parser.add_argument('--session-type', default='unknown',
                       help='Session type (webchat, telegram, etc.)')
    
    args = parser.parse_args()
    
    if not HAS_OLLAMA:
        print("Error: Please install ollama: pip install ollama", file=sys.stderr)
        sys.exit(1)
    
    # Read input
    if args.input == '-' or args.input is None:
        content = sys.stdin.read()
    else:
        filepath = Path(args.input)
        if not filepath.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        content = filepath.read_text()
    
    if not content.strip():
        print("Error: No content to encode", file=sys.stderr)
        sys.exit(1)
    
    # Encode
    entry = encode_text(
        content,
        model=args.model,
        entry_type=args.type,
        session_type=args.session_type,
        number=args.number
    )
    
    if not entry:
        print("Error: Encoding failed", file=sys.stderr)
        sys.exit(1)
    
    # Output
    yaml_output = yaml.dump(entry, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    if args.output:
        Path(args.output).write_text(yaml_output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(yaml_output)


if __name__ == '__main__':
    main()
