#!/usr/bin/env python3
"""
Conversation-Aware Salience Boosting
Extracts themes from conversation text and boosts related memories.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

from context import extract_themes
from recall import get_client, get_collection
from reinforcement import get_tracker


def find_related_memories(text: str, max_results: int = 5, min_similarity: float = 0.35) -> List[Dict]:
    """Find memories related to conversation text via theme extraction + ChromaDB search."""
    themes = extract_themes(text, max_themes=8)
    if not themes:
        return []

    query = ' '.join(themes)
    client = get_client()
    collection = get_collection(client)

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(max_results, collection.count()),
        include=["metadatas", "distances"]
    )

    memories = []
    for i, (mem_id, dist) in enumerate(zip(results['ids'][0], results['distances'][0])):
        similarity = 1 / (1 + dist)
        if similarity >= min_similarity:
            memories.append({
                'id': mem_id,
                'similarity': round(similarity, 3),
                'salience': results['metadatas'][0][i].get('salience', 0.5),
            })
    return memories


def inject_conversation_boost(text: str, amount: float = 0.1, min_similarity: float = 0.35) -> List[Dict]:
    """
    Main entry point: extract themes from conversation text,
    find related memories, and boost their salience.

    Returns list of boosted memories with details.
    """
    tracker = get_tracker()
    related = find_related_memories(text, min_similarity=min_similarity)
    boosted = []

    for mem in related:
        mem_id = mem['id']
        # Record access (topic came up)
        tracker.record_access(mem_id)
        # Apply conversation boost
        tracker.conversation_boost(mem_id, amount=amount)
        new_salience = tracker.calculate_salience(mem_id)
        boosted.append({
            'id': mem_id,
            'similarity': mem['similarity'],
            'old_salience': mem['salience'],
            'new_salience': round(new_salience, 3),
        })

    return boosted


def main():
    parser = argparse.ArgumentParser(description='Conversation-Aware Salience Boosting')
    parser.add_argument('text', nargs='+', help='Conversation text to extract themes from')
    parser.add_argument('-a', '--amount', type=float, default=0.1,
                        help='Boost amount per memory (default: 0.1, caps at 0.3)')
    parser.add_argument('-t', '--threshold', type=float, default=0.35,
                        help='Min similarity threshold (default: 0.35)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()
    text = ' '.join(args.text)

    themes = extract_themes(text, max_themes=8)
    print(f"Extracted themes: {', '.join(themes)}")
    print()

    boosted = inject_conversation_boost(text, amount=args.amount, min_similarity=args.threshold)

    if args.json:
        import json
        print(json.dumps(boosted, indent=2))
    elif boosted:
        print(f"Boosted {len(boosted)} memories:")
        for m in boosted:
            print(f"  {m['id']}: {m['old_salience']:.2f} → {m['new_salience']:.3f} (sim: {m['similarity']})")
    else:
        print("No related memories found.")


if __name__ == '__main__':
    main()
