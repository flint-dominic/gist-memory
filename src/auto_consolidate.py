#!/usr/bin/env python3
"""
Auto-Consolidation
Finds highly similar memory pairs and merges them using LLM.
"""

import sys
import yaml
import argparse
from pathlib import Path
from typing import Optional, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from consolidate import find_similar_pairs, EXAMPLES_DIR, get_collection
from reinforcement import get_tracker, load_memory_yaml

# Try ollama for LLM merging
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

PROJECT_ROOT = Path(__file__).parent.parent

MERGE_PROMPT = """You are merging two similar memories into one consolidated memory.

## Base Memory (higher salience — keep this as the foundation):
{base_summary}

## Secondary Memory (lower salience — extract unique details):
{secondary_summary}

## Task
Produce a merged summary that:
1. Keeps the base memory's core content intact
2. Adds any unique details/facts from the secondary memory that aren't in the base
3. Is concise but comprehensive (3-7 sentences)
4. Does NOT duplicate information

Output ONLY the merged summary text, nothing else."""


def load_memory_from_yaml(memory_id: str) -> Optional[Dict]:
    """Load full memory dict from YAML file. Returns (content, filepath) or None."""
    for f in EXAMPLES_DIR.glob("*.yaml"):
        try:
            content = yaml.safe_load(f.read_text())
            if content and content.get('id') == memory_id:
                return {'content': content, 'filepath': f}
        except:
            continue
    return None


def merge_summaries_llm(base_summary: str, secondary_summary: str, model: str = "llama3:8b") -> Optional[str]:
    """Use LLM to merge two memory summaries."""
    if not HAS_OLLAMA:
        # Fallback: simple concatenation
        return f"{base_summary.strip()}\n\nAdditional context: {secondary_summary.strip()}"

    prompt = MERGE_PROMPT.format(
        base_summary=base_summary,
        secondary_summary=secondary_summary,
    )

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0.3, "num_predict": 500},
        )
        return response['response'].strip()
    except Exception as e:
        print(f"  LLM merge failed ({e}), using concatenation fallback", file=sys.stderr)
        return f"{base_summary.strip()}\n\nAdditional context: {secondary_summary.strip()}"


def merge_pair(base_id: str, secondary_id: str, execute: bool = False, model: str = "llama3:8b") -> Dict:
    """
    Merge two memories: keep base, absorb secondary.

    Returns info dict. Only modifies files if execute=True.
    """
    tracker = get_tracker()

    base_data = load_memory_from_yaml(base_id)
    secondary_data = load_memory_from_yaml(secondary_id)

    result = {
        'base': base_id,
        'secondary': secondary_id,
        'executed': False,
        'error': None,
    }

    if not base_data or not secondary_data:
        result['error'] = 'Could not load one or both memories from YAML'
        return result

    base_content = base_data['content']
    sec_content = secondary_data['content']
    base_summary = base_content.get('summary', '')
    sec_summary = sec_content.get('summary', '')

    if not execute:
        result['base_summary'] = base_summary[:200]
        result['secondary_summary'] = sec_summary[:200]
        return result

    # Merge summaries
    merged_summary = merge_summaries_llm(base_summary, sec_summary, model=model)
    if not merged_summary:
        result['error'] = 'Merge failed'
        return result

    # Update base memory YAML
    base_content['summary'] = merged_summary

    # Merge tags (handle YAML `null` → None by coercing to [])
    base_tags = set((base_content.get('metadata') or {}).get('tags') or [])
    sec_tags = set((sec_content.get('metadata') or {}).get('tags') or [])
    if 'metadata' not in base_content or base_content['metadata'] is None:
        base_content['metadata'] = {}
    base_content['metadata']['tags'] = sorted(base_tags | sec_tags)

    # Merge retrieval hints
    base_hints = set(base_content.get('retrieval_hints') or [])
    sec_hints = set(sec_content.get('retrieval_hints') or [])
    base_content['retrieval_hints'] = sorted(base_hints | sec_hints)

    # Merge frames
    base_frames = set((base_content.get('gist') or {}).get('frames') or [])
    sec_frames = set((sec_content.get('gist') or {}).get('frames') or [])
    if 'gist' not in base_content or base_content['gist'] is None:
        base_content['gist'] = {}
    base_content['gist']['frames'] = sorted(base_frames | sec_frames)

    # Write updated base
    base_data['filepath'].write_text(
        yaml.dump(base_content, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )

    # Merge reinforcement data
    base_r = tracker.get(base_id)
    sec_r = tracker.get(secondary_id)
    base_r.access_count += sec_r.access_count
    base_r.explicit_boost = max(base_r.explicit_boost, sec_r.explicit_boost)
    base_r.usefulness_score = max(base_r.usefulness_score, sec_r.usefulness_score)
    if hasattr(sec_r, 'conversation_boost_score'):
        base_r.conversation_boost_score = max(
            getattr(base_r, 'conversation_boost_score', 0.0),
            sec_r.conversation_boost_score
        )
    # Merge linked_by
    for link in sec_r.linked_by:
        if link not in base_r.linked_by:
            base_r.linked_by.append(link)
    tracker._save()

    # Remove secondary from ChromaDB
    try:
        collection = get_collection()
        collection.delete(ids=[secondary_id])
    except Exception as e:
        print(f"  Warning: Could not remove {secondary_id} from ChromaDB: {e}", file=sys.stderr)

    # Delete secondary YAML
    secondary_data['filepath'].unlink()

    # Remove secondary from reinforcement tracking
    if secondary_id in tracker.data:
        del tracker.data[secondary_id]
        tracker._save()

    result['executed'] = True
    result['merged_summary'] = merged_summary[:200]
    return result


def auto_consolidate(threshold: float = 0.75, execute: bool = False, model: str = "llama3:8b") -> List[Dict]:
    """
    Find and merge highly similar memory pairs.

    Args:
        threshold: Similarity threshold for merging (default 0.75)
        execute: If False, dry-run only
        model: Ollama model for LLM merging
    """
    tracker = get_tracker()
    pairs = find_similar_pairs(threshold)

    if not pairs:
        return []

    results = []
    merged_ids = set()  # Track already-merged to avoid double-merging

    for id1, id2, similarity in pairs:
        if id1 in merged_ids or id2 in merged_ids:
            continue

        # Higher salience = base
        sal1 = tracker.calculate_salience(id1)
        sal2 = tracker.calculate_salience(id2)

        if sal1 >= sal2:
            base_id, secondary_id = id1, id2
        else:
            base_id, secondary_id = id2, id1

        result = merge_pair(base_id, secondary_id, execute=execute, model=model)
        result['similarity'] = round(similarity, 3)
        results.append(result)

        if execute and not result.get('error'):
            merged_ids.add(secondary_id)

    return results


def main():
    parser = argparse.ArgumentParser(description='Auto-Consolidation of Similar Memories')
    parser.add_argument('--execute', action='store_true',
                        help='Actually perform merges (default: dry run)')
    parser.add_argument('--threshold', type=float, default=0.75,
                        help='Similarity threshold (default: 0.75)')
    parser.add_argument('--model', default='llama3:8b',
                        help='Ollama model for merging (default: llama3:8b)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"=== Auto-Consolidation ({mode}) ===")
    print(f"Threshold: {args.threshold}")
    print()

    results = auto_consolidate(
        threshold=args.threshold,
        execute=args.execute,
        model=args.model,
    )

    if args.json:
        import json
        print(json.dumps(results, indent=2))
    elif results:
        for r in results:
            status = "✓ MERGED" if r.get('executed') else "⚠ ERROR" if r.get('error') else "→ would merge"
            print(f"  {status}: {r['base']} ← {r['secondary']} (sim: {r.get('similarity', '?')})")
            if r.get('error'):
                print(f"    Error: {r['error']}")
            if r.get('base_summary'):
                print(f"    Base: {r['base_summary'][:80]}...")
                print(f"    Secondary: {r['secondary_summary'][:80]}...")
        print(f"\nTotal: {len(results)} pair(s)")
    else:
        print("No similar pairs found above threshold.")


if __name__ == '__main__':
    main()
