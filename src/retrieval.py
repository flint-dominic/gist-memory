#!/usr/bin/env python3
"""
Gist Memory Retrieval
Semantic search over encoded memories using ChromaDB
"""

import sys
import yaml
import argparse
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
CHROMA_DIR = PROJECT_ROOT / ".chroma"


def get_client() -> chromadb.PersistentClient:
    """Get or create ChromaDB client."""
    CHROMA_DIR.mkdir(exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )


def get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    """Get or create the memories collection."""
    return client.get_or_create_collection(
        name="gist_memories",
        metadata={"description": "Gist memory entries"}
    )


def build_embedding_text(entry: dict) -> str:
    """
    Build the text to embed for a memory entry.
    Combines frames, summary, retrieval hints, and key verbatim.
    """
    parts = []
    
    # Frames (weighted heavily - this is the gist)
    if 'gist' in entry and 'frames' in entry['gist']:
        frames = entry['gist']['frames']
        parts.append(f"Frames: {', '.join(frames)}")
    
    # Emotional tone
    if 'gist' in entry and 'emotional_tone' in entry['gist']:
        tones = entry['gist']['emotional_tone']
        parts.append(f"Tone: {', '.join(tones)}")
    
    # Summary (the human-readable gist)
    if 'summary' in entry:
        parts.append(f"Summary: {entry['summary']}")
    
    # Retrieval hints
    if 'retrieval_hints' in entry:
        parts.append(f"Keywords: {', '.join(entry['retrieval_hints'])}")
    
    # Key verbatim concepts (just the keys and values, not full structure)
    if 'verbatim' in entry and 'stored' in entry['verbatim']:
        verbatim_parts = []
        for key, val in entry['verbatim']['stored'].items():
            if isinstance(val, dict) and 'value' in val:
                verbatim_parts.append(f"{key}: {val['value']}")
            else:
                verbatim_parts.append(f"{key}: {val}")
        if verbatim_parts:
            parts.append(f"Details: {'; '.join(verbatim_parts)}")
    
    # Tags
    if 'metadata' in entry and entry['metadata'].get('tags'):
        tags = entry['metadata']['tags']
        if isinstance(tags, list):
            parts.append(f"Tags: {', '.join(tags)}")
    
    return "\n".join(parts)


def load_memory(filepath: Path) -> Optional[dict]:
    """Load a memory entry from YAML file."""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}", file=sys.stderr)
        return None


def index_memories(collection: chromadb.Collection, force: bool = False) -> int:
    """Index all memory files in examples directory."""
    indexed = 0
    
    for filepath in EXAMPLES_DIR.glob("*.yaml"):
        entry = load_memory(filepath)
        if not entry:
            continue
        
        entry_id = entry.get('id', filepath.stem)
        
        # Check if already indexed (unless forcing)
        if not force:
            existing = collection.get(ids=[entry_id])
            if existing['ids']:
                print(f"  Skipping {entry_id} (already indexed)")
                continue
        
        # Build embedding text
        embed_text = build_embedding_text(entry)
        
        # Store with metadata
        timestamp = entry.get('timestamp', '')
        if hasattr(timestamp, 'isoformat'):
            timestamp = timestamp.isoformat()
        
        metadata = {
            "filepath": str(filepath),
            "timestamp": str(timestamp),
            "salience": float(entry.get('gist', {}).get('salience', 0.5)),
            "type": entry.get('type', 'unknown'),
        }
        
        # Add frames as metadata for filtering
        if 'gist' in entry and 'frames' in entry['gist']:
            metadata['frames'] = ','.join(entry['gist']['frames'])
        
        collection.upsert(
            ids=[entry_id],
            documents=[embed_text],
            metadatas=[metadata]
        )
        
        print(f"  Indexed: {entry_id}")
        indexed += 1
    
    return indexed


def search(collection: chromadb.Collection, query: str, n_results: int = 5) -> list:
    """Search memories by semantic similarity."""
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    
    # Format results
    formatted = []
    for i, (doc, meta, dist) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        # Convert distance to similarity (ChromaDB uses L2 by default)
        # Lower distance = more similar
        similarity = 1 / (1 + dist)
        
        formatted.append({
            'rank': i + 1,
            'id': results['ids'][0][i],
            'similarity': similarity,
            'distance': dist,
            'filepath': meta.get('filepath', ''),
            'frames': meta.get('frames', '').split(',') if meta.get('frames') else [],
            'salience': meta.get('salience', 0),
            'document_preview': doc[:500] + '...' if len(doc) > 500 else doc
        })
    
    return formatted


def main():
    parser = argparse.ArgumentParser(description='Gist Memory Retrieval')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Index command
    index_parser = subparsers.add_parser('index', help='Index memory files')
    index_parser.add_argument('--force', '-f', action='store_true', 
                             help='Re-index existing entries')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search memories')
    search_parser.add_argument('query', nargs='+', help='Search query')
    search_parser.add_argument('-n', '--num', type=int, default=5,
                              help='Number of results')
    
    # Stats command
    subparsers.add_parser('stats', help='Show collection statistics')
    
    args = parser.parse_args()
    
    client = get_client()
    collection = get_collection(client)
    
    if args.command == 'index':
        print("Indexing memories...")
        count = index_memories(collection, force=args.force)
        print(f"Indexed {count} new entries")
        print(f"Total entries in collection: {collection.count()}")
    
    elif args.command == 'search':
        query = ' '.join(args.query)
        print(f"Searching for: {query}\n")
        
        results = search(collection, query, n_results=args.num)
        
        if not results:
            print("No results found.")
            return
        
        for r in results:
            print(f"#{r['rank']} [{r['similarity']:.3f}] {r['id']}")
            print(f"   Frames: {', '.join(r['frames'])}")
            print(f"   Salience: {r['salience']}")
            print(f"   Preview: {r['document_preview'][:200]}...")
            print()
    
    elif args.command == 'stats':
        print("Collection: gist_memories")
        print(f"Total entries: {collection.count()}")
        
        # List all entries
        all_entries = collection.get(include=['metadatas'])
        if all_entries['ids']:
            print("\nIndexed memories:")
            for id_, meta in zip(all_entries['ids'], all_entries['metadatas']):
                print(f"  - {id_} (salience: {meta.get('salience', '?')})")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
