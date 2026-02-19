#!/usr/bin/env python3
"""
Gist Memory Context Injection
Automatically extract themes from input and inject relevant memories.
"""

import sys
import re
import json
import argparse
from pathlib import Path
from typing import List, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from recall import recall, format_for_context

# Stopwords to filter out
STOPWORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
    'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
    'because', 'until', 'while', 'this', 'that', 'these', 'those', 'what',
    'which', 'who', 'whom', 'its', 'it', 'i', 'me', 'my', 'myself', 'we',
    'our', 'ours', 'you', 'your', 'yours', 'he', 'him', 'his', 'she', 'her',
    'hers', 'they', 'them', 'their', 'lets', 'let', 'get', 'got', 'go',
    'going', 'want', 'like', 'know', 'think', 'see', 'look', 'make', 'take',
    'come', 'say', 'said', 'tell', 'told', 'ask', 'asked', 'yes', 'no',
    'okay', 'ok', 'hey', 'hi', 'hello', 'thanks', 'thank', 'please', 'sorry',
    'well', 'also', 'now', 'still', 'already', 'even', 'back', 'up', 'out',
    'about', 'over', 'after', 'before', 'around', 'down', 'off', 'away'
}

# Keywords that boost memory relevance
MEMORY_TRIGGERS = {
    'remember', 'recall', 'forgot', 'forget', 'memory', 'memories',
    'discussed', 'talked', 'mentioned', 'said', 'told', 'earlier',
    'before', 'previously', 'last', 'time', 'when', 'history',
    'what was', 'what did', 'what were', 'how did', 'why did',
    'project', 'working', 'built', 'made', 'created', 'designed'
}


def extract_themes(text: str, max_themes: int = 5) -> List[str]:
    """
    Extract key themes/keywords from text.
    Simple but effective: filter stopwords, keep meaningful words.
    """
    # Normalize
    text = text.lower()
    
    # Extract words (alphanumeric + some special)
    words = re.findall(r'[a-z][a-z0-9_-]*[a-z0-9]|[a-z]', text)
    
    # Filter stopwords and short words
    meaningful = [w for w in words if w not in STOPWORDS and len(w) > 2]
    
    # Count frequency
    freq = {}
    for w in meaningful:
        freq[w] = freq.get(w, 0) + 1
    
    # Sort by frequency, take top N
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    themes = [w for w, _ in sorted_words[:max_themes]]
    
    return themes


def should_recall(text: str) -> bool:
    """
    Determine if this message warrants memory recall.
    Not every message needs it - save resources.
    """
    text_lower = text.lower()
    
    # Check for memory trigger words
    for trigger in MEMORY_TRIGGERS:
        if trigger in text_lower:
            return True
    
    # Check message length - very short messages probably don't need recall
    if len(text.split()) < 4:
        return False
    
    # Check for question patterns
    if any(text_lower.startswith(q) for q in ['what', 'how', 'why', 'when', 'where', 'who', 'did', 'do', 'can', 'could']):
        return True
    
    # Check for project/topic names (customize these)
    project_names = ['stellar', 'delve', 'llmoblings', 'voidborne', 'railways', 
                     'gist', 'memory', 'barzakh', 'minecraft', 'remus', 'mercy']
    for name in project_names:
        if name in text_lower:
            return True
    
    # Default: recall for medium-length messages
    return len(text.split()) > 8


def inject_context(
    message: str,
    min_similarity: float = 0.38,
    max_memories: int = 2,
    force: bool = False
) -> Optional[str]:
    """
    Process a message and return context to inject (if any).
    
    Returns formatted memory context or None if no relevant memories.
    """
    # Check if recall is warranted
    if not force and not should_recall(message):
        return None
    
    # Extract themes
    themes = extract_themes(message)
    if not themes:
        return None
    
    # Build query from themes
    query = ' '.join(themes)
    
    # Recall memories
    memories = recall(
        query,
        min_similarity=min_similarity,
        max_results=max_memories
    )
    
    if not memories:
        return None
    
    # Format for injection
    context = format_for_context(memories, verbose=False)
    
    return context


def main():
    parser = argparse.ArgumentParser(description='Gist Memory Context Injection')
    parser.add_argument('message', nargs='*', help='Message to process')
    parser.add_argument('-t', '--threshold', type=float, default=0.38,
                       help='Min similarity threshold')
    parser.add_argument('-n', '--num', type=int, default=2,
                       help='Max memories to inject')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Force recall even for short messages')
    parser.add_argument('--themes', action='store_true',
                       help='Just show extracted themes')
    parser.add_argument('--check', action='store_true',
                       help='Just check if recall would trigger')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    
    args = parser.parse_args()
    
    # Read message
    if args.message:
        message = ' '.join(args.message)
    else:
        message = sys.stdin.read().strip()
    
    if not message:
        print("No message provided", file=sys.stderr)
        sys.exit(1)
    
    # Theme extraction only
    if args.themes:
        themes = extract_themes(message)
        print(f"Themes: {', '.join(themes)}")
        return
    
    # Check only
    if args.check:
        will_recall = should_recall(message)
        print(f"Would recall: {will_recall}")
        if will_recall:
            themes = extract_themes(message)
            print(f"Themes: {', '.join(themes)}")
        return
    
    # Full context injection
    context = inject_context(
        message,
        min_similarity=args.threshold,
        max_memories=args.num,
        force=args.force
    )
    
    if args.json:
        result = {
            'has_context': context is not None,
            'themes': extract_themes(message),
            'context': context
        }
        print(json.dumps(result, indent=2))
    else:
        if context:
            print(context)
        else:
            print("(no relevant memories)")


if __name__ == '__main__':
    main()
