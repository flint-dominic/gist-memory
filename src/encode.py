#!/usr/bin/env python3
"""
Gist Memory Auto-Encoder
Converts conversations/text into memory entries using LLM analysis.

Uses the formal frame taxonomy from frames.py for consistent encoding.
"""

import sys
import yaml
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Try to import ollama, fall back gracefully
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"

# Import frame taxonomy
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from frames import FRAMES, frame_prompt

# Default model
DEFAULT_MODEL = "llama3:8b"


def load_frames() -> str:
    """Load the formal frame taxonomy for the encoding prompt."""
    return frame_prompt()


def get_valid_frame_ids() -> List[str]:
    """Get list of valid frame IDs."""
    return list(FRAMES.keys())


def validate_frames(frame_list: List[str]) -> List[str]:
    """Validate and filter frame list to only valid frames."""
    valid = get_valid_frame_ids()
    validated = []
    for f in frame_list:
        f_clean = f.strip().lower().replace(' ', '_').replace('-', '_')
        if f_clean in valid:
            validated.append(f_clean)
        else:
            # Try fuzzy match
            for v in valid:
                if f_clean in v or v in f_clean:
                    validated.append(v)
                    break
    return list(set(validated)) or ['collaborative_exploration']  # Default fallback

ENCODE_PROMPT = """You are encoding a conversation into a gist memory entry.

## Frame Taxonomy (YOU MUST CHOOSE ONLY FROM THESE)
{frames}

IMPORTANT: Only use frame IDs exactly as listed above. Do not invent new frames.

## Valid Frame IDs (copy exactly):
{frame_ids}

## Task
Analyze the following content and produce a memory entry in YAML format.

Guidelines:
- frames: Pick 3-7 relevant frames ONLY from the list above (use exact IDs)
- emotional_tone: List 3-6 emotional qualities present
- salience: 0.0-1.0, how important/memorable is this? (0.9+ for foundational, 0.5 for routine)
- verbatim.stored: Key specific facts/quotes/details worth preserving (5-10 items as key:value pairs)
- verbatim.reconstructable: "none" if nothing, else what could be inferred
- summary: 3-5 sentence summary capturing the gist
- retrieval_hints: 5-10 search queries that should find this memory

## Content to Encode
{content}

## Output Format
Produce ONLY valid YAML, no markdown code blocks, starting with `id:`. Use SIMPLE key-value pairs.

id: mem-{number}-shortslug
timestamp: {timestamp}
type: {type}
gist:
  frames:
  - frame_name_here
  emotional_tone:
  - tone_here
  salience: 0.7
  confidence: 0.8
  source: encoded
verbatim:
  stored:
    detail_one: "specific fact or quote"
    detail_two: "another important detail"
    detail_three: "yet another detail"
  reconstructable: none
metadata:
  participant: gblfxt
  session_key: unknown
  session_type: {session_type}
  duration_estimate: unknown
  related_entries: []
  tags:
  - tag_here
summary: |
  Summary of what happened in 2-3 sentences.
retrieval_hints:
- search term one
- search term two
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
    frame_ids = ", ".join(get_valid_frame_ids())
    timestamp = datetime.now().isoformat()
    
    prompt = ENCODE_PROMPT.replace('{frames}', frames)
    prompt = prompt.replace('{frame_ids}', frame_ids)
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
    """Validate YAML and fix common issues, including frame validation."""
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
    
    # Validate frames against taxonomy
    raw_frames = entry.get('gist', {}).get('frames', [])
    if raw_frames:
        validated_frames = validate_frames(raw_frames)
        entry['gist']['frames'] = validated_frames
        if set(raw_frames) != set(validated_frames):
            print(f"  Frames validated: {raw_frames} → {validated_frames}", file=sys.stderr)
    else:
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
