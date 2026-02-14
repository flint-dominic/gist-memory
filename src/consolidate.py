#!/usr/bin/env python3
"""
Memory Consolidation
Analyzes memories for clustering and suggests consolidation.
"""

import sys
import yaml
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict

import chromadb
from chromadb.config import Settings

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
CHROMA_DIR = PROJECT_ROOT / ".chroma"

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from reinforcement import get_tracker, load_memory_yaml


def get_collection():
    """Get ChromaDB collection."""
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )
    return client.get_or_create_collection("gist_memories")


def find_similar_pairs(threshold: float = 0.7) -> List[Tuple[str, str, float]]:
    """Find pairs of memories that are similar enough to potentially consolidate."""
    collection = get_collection()
    all_memories = collection.get(include=['embeddings', 'metadatas'])
    
    pairs = []
    ids = all_memories['ids']
    embeddings = all_memories['embeddings']
    
    if embeddings is None or len(embeddings) == 0:
        return []
    
    # Compare each pair
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            # Cosine similarity
            e1, e2 = embeddings[i], embeddings[j]
            dot = sum(a * b for a, b in zip(e1, e2))
            norm1 = sum(a * a for a in e1) ** 0.5
            norm2 = sum(a * a for a in e2) ** 0.5
            similarity = dot / (norm1 * norm2) if norm1 and norm2 else 0
            
            if similarity >= threshold:
                pairs.append((ids[i], ids[j], similarity))
    
    return sorted(pairs, key=lambda x: -x[2])


def find_frame_clusters() -> Dict[str, List[str]]:
    """Find memories that share frames."""
    clusters = defaultdict(list)
    
    for f in EXAMPLES_DIR.glob("*.yaml"):
        try:
            mem = yaml.safe_load(f.read_text())
            mem_id = mem.get('id', f.stem)
            frames = mem.get('gist', {}).get('frames', [])
            
            # Add to cluster for each frame
            for frame in frames:
                clusters[frame].append(mem_id)
        except:
            continue
    
    # Only return clusters with 3+ memories
    return {k: v for k, v in clusters.items() if len(v) >= 3}


def find_time_clusters(window_days: int = 7) -> List[List[str]]:
    """Find memories that were created close together in time."""
    memories = []
    
    for f in EXAMPLES_DIR.glob("*.yaml"):
        try:
            mem = yaml.safe_load(f.read_text())
            mem_id = mem.get('id', f.stem)
            timestamp = mem.get('timestamp', '')
            
            if isinstance(timestamp, str):
                # Parse various formats
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        dt = datetime.strptime(timestamp[:19], fmt[:len(timestamp[:19])+2])
                        memories.append((mem_id, dt))
                        break
                    except:
                        continue
        except:
            continue
    
    if not memories:
        return []
    
    # Sort by time
    memories.sort(key=lambda x: x[1])
    
    # Find clusters within window
    clusters = []
    current_cluster = [memories[0]]
    
    for i in range(1, len(memories)):
        if (memories[i][1] - current_cluster[-1][1]).days <= window_days:
            current_cluster.append(memories[i])
        else:
            if len(current_cluster) >= 3:
                clusters.append([m[0] for m in current_cluster])
            current_cluster = [memories[i]]
    
    if len(current_cluster) >= 3:
        clusters.append([m[0] for m in current_cluster])
    
    return clusters


def consolidation_report() -> Dict:
    """Generate a full consolidation analysis report."""
    tracker = get_tracker()
    
    report = {
        'similar_pairs': find_similar_pairs(0.75),
        'frame_clusters': find_frame_clusters(),
        'time_clusters': find_time_clusters(7),
        'low_salience': [],
        'candidates': []
    }
    
    # Find low-salience memories (consolidation candidates)
    for f in EXAMPLES_DIR.glob("*.yaml"):
        try:
            mem = yaml.safe_load(f.read_text())
            mem_id = mem.get('id', f.stem)
            salience = tracker.calculate_salience(mem_id)
            
            if salience < 0.5:
                report['low_salience'].append({
                    'id': mem_id,
                    'salience': salience,
                    'frames': mem.get('gist', {}).get('frames', [])[:3]
                })
        except:
            continue
    
    # Identify consolidation candidates (low salience + in a cluster)
    low_sal_ids = {m['id'] for m in report['low_salience']}
    
    for frame, members in report['frame_clusters'].items():
        in_cluster = [m for m in members if m in low_sal_ids]
        if len(in_cluster) >= 2:
            report['candidates'].append({
                'reason': f'Low-salience memories sharing frame: {frame}',
                'memories': in_cluster
            })
    
    return report


def print_sleep_report():
    """Print the consolidation analysis."""
    report = consolidation_report()
    
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  🌙 GIST SLEEP - Consolidation Analysis                            ║")
    print("╠════════════════════════════════════════════════════════════════════╣")
    
    # Similar pairs
    print("║  SIMILAR MEMORIES (semantic):")
    if report['similar_pairs']:
        for m1, m2, sim in report['similar_pairs'][:5]:
            print(f"║    {sim:.2f}  {m1[:20]} ↔ {m2[:20]}")
    else:
        print("║    (none found above threshold)")
    
    print("╟────────────────────────────────────────────────────────────────────╢")
    
    # Frame clusters
    print("║  FRAME CLUSTERS (3+ memories sharing frame):")
    for frame, members in list(report['frame_clusters'].items())[:5]:
        print(f"║    {frame}: {len(members)} memories")
    
    print("╟────────────────────────────────────────────────────────────────────╢")
    
    # Time clusters
    print("║  TIME CLUSTERS (within 7 days):")
    for i, cluster in enumerate(report['time_clusters'][:3]):
        print(f"║    Cluster {i+1}: {len(cluster)} memories")
    if not report['time_clusters']:
        print("║    (all memories spread out)")
    
    print("╟────────────────────────────────────────────────────────────────────╢")
    
    # Consolidation candidates
    print("║  CONSOLIDATION CANDIDATES:")
    if report['candidates']:
        for cand in report['candidates'][:5]:
            print(f"║    → {cand['reason']}")
            for m in cand['memories'][:3]:
                print(f"║        - {m}")
    else:
        print("║    ✓ No urgent consolidation needed")
    
    print("╟────────────────────────────────────────────────────────────────────╢")
    
    # Summary
    total = len(list(EXAMPLES_DIR.glob("*.yaml")))
    low = len(report['low_salience'])
    print(f"║  SUMMARY: {total} memories, {low} fading, {len(report['candidates'])} consolidation opportunities")
    print("╚════════════════════════════════════════════════════════════════════╝")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'report':
        import json
        print(json.dumps(consolidation_report(), indent=2, default=str))
    else:
        print_sleep_report()
