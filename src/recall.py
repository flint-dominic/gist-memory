#!/usr/bin/env python3
"""
Gist Memory Recall
Automatic memory retrieval based on context/query.
Returns formatted memories for injection into conversations.
"""

import yaml
import argparse
from pathlib import Path
from typing import Optional, List, Dict

import chromadb
from chromadb.config import Settings

# Import reinforcement tracking
from reinforcement import record_access, calculate_salience

# Import markdown corpus search
try:
    from markdown_index import search_markdown, hybrid_rerank
    MARKDOWN_SEARCH_AVAILABLE = True
except ImportError:
    MARKDOWN_SEARCH_AVAILABLE = False

# Import perspectives
try:
    from perspectives import get_manager as get_perspective_manager
    PERSPECTIVES_AVAILABLE = True
except ImportError:
    PERSPECTIVES_AVAILABLE = False

# Import frame detection for query-aware perspectives
try:
    from frames import detect_frames_from_text
    FRAME_DETECTION_AVAILABLE = True
except ImportError:
    FRAME_DETECTION_AVAILABLE = False

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
CHROMA_DIR = PROJECT_ROOT / ".chroma"

# Thresholds
DEFAULT_MIN_SIMILARITY = 0.35  # Below this, memory is probably not relevant
DEFAULT_MAX_RESULTS = 3


# ── DB Access ──────────────────────────────────────────────────────

def get_client() -> chromadb.PersistentClient:
    """Get or create ChromaDB client."""
    CHROMA_DIR.mkdir(exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )


def get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    """Get the memories collection."""
    return client.get_or_create_collection(
        name="gist_memories",
        metadata={"description": "Gist memory entries"}
    )


# ── Memory Loading ─────────────────────────────────────────────────

def load_memory_file(filepath: str) -> Optional[dict]:
    """Load full memory entry from YAML file."""
    try:
        path = Path(filepath)
        if path.exists():
            with open(path, 'r') as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return None


def _extract_memory_details(full_memory: dict) -> tuple[str, dict]:
    """Extract summary and key details from a full YAML memory.
    
    Returns (summary, key_details) tuple.
    """
    summary = full_memory.get('summary', '').strip()
    key_details = {}
    if 'verbatim' in full_memory and 'stored' in full_memory['verbatim']:
        for key, val in full_memory['verbatim']['stored'].items():
            if isinstance(val, dict) and 'value' in val:
                key_details[key] = val['value']
            else:
                key_details[key] = str(val)
    return summary, key_details


# ── Perspective Selection ──────────────────────────────────────────

def _get_best_perspective(memory_id: str, query_frames: List[str],
                          memory_frames: List[str]) -> Optional[dict]:
    """Get the best perspective for a memory given query context.
    
    Returns perspective dict or None.
    """
    if not PERSPECTIVES_AVAILABLE:
        return None
    try:
        persp_manager = get_perspective_manager()
        mem_persp = persp_manager.get(memory_id)
        if not mem_persp.perspectives:
            return None
        # Use query_frames for context-aware selection,
        # fall back to memory's own frames
        context_frames = query_frames if query_frames else memory_frames
        return persp_manager.get_for_context(memory_id, context_frames)
    except Exception:
        return None


# ── Query Frame Detection ─────────────────────────────────────────

def _detect_query_frames(query: str, query_frames: Optional[List[str]]) -> Optional[List[str]]:
    """Detect frames from query text if not provided."""
    if query_frames is not None:
        return query_frames
    if FRAME_DETECTION_AVAILABLE:
        return detect_frames_from_text(query, max_frames=5)
    return None


# ── Vector Search ──────────────────────────────────────────────────

def _search_collection(collection: chromadb.Collection, query: str,
                       max_results: int) -> tuple[list, list, list, list]:
    """Search ChromaDB collection and return raw results.
    
    Returns (ids, documents, metadatas, distances) lists.
    """
    if collection.count() == 0:
        return [], [], [], []

    results = collection.query(
        query_texts=[query],
        n_results=min(max_results * 2, collection.count()),
        include=["documents", "metadatas", "distances"]
    )
    return (
        results['ids'][0],
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0],
    )


# ── Result Building ────────────────────────────────────────────────

def _build_memory_result(memory_id: str, meta: dict, dist: float,
                         min_similarity: float, include_low_confidence: bool,
                         query_frames: Optional[List[str]]) -> Optional[Dict]:
    """Build a single memory result dict from raw search output.
    
    Returns None if below similarity threshold.
    """
    similarity = 1 / (1 + dist)

    if similarity < min_similarity and not include_low_confidence:
        return None

    # Load full memory for richer context
    full_memory = None
    if meta.get('filepath'):
        full_memory = load_memory_file(meta['filepath'])

    initial_salience = meta.get('salience', 0.5)

    # Record access and get dynamic salience
    record_access(memory_id, initial_salience)
    dynamic_salience = calculate_salience(memory_id)

    frames = meta.get('frames', '').split(',') if meta.get('frames') else []

    memory = {
        'id': memory_id,
        'similarity': round(similarity, 3),
        'frames': frames,
        'salience': dynamic_salience,
        'initial_salience': initial_salience,
        'summary': '',
        'key_details': {},
        'perspective': _get_best_perspective(memory_id, query_frames, frames),
    }

    if full_memory:
        memory['summary'], memory['key_details'] = _extract_memory_details(full_memory)

    return memory


# ── Main Recall Functions ──────────────────────────────────────────

def recall(
    query: str,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    max_results: int = DEFAULT_MAX_RESULTS,
    include_low_confidence: bool = False,
    query_frames: List[str] = None
) -> List[Dict]:
    """
    Recall relevant memories based on a query.
    
    Returns list of memories with similarity scores, filtered by threshold.
    """
    query_frames = _detect_query_frames(query, query_frames)

    client = get_client()
    collection = get_collection(client)

    ids, _docs, metas, dists = _search_collection(collection, query, max_results)

    memories = []
    for i, (meta, dist) in enumerate(zip(metas, dists)):
        result = _build_memory_result(
            ids[i], meta, dist, min_similarity, include_low_confidence, query_frames
        )
        if result:
            memories.append(result)
            if len(memories) >= max_results:
                break

    return memories


def _build_corpus_results(query: str, max_results: int, min_similarity: float,
                          include_low_confidence: bool,
                          corpus_weight: float) -> List[Dict]:
    """Search markdown corpus and build result dicts."""
    if not MARKDOWN_SEARCH_AVAILABLE:
        return []

    raw_corpus = search_markdown(query, top_k=max_results)
    raw_corpus = hybrid_rerank(raw_corpus, query)

    results = []
    for r in raw_corpus:
        if r['similarity'] < min_similarity and not include_low_confidence:
            continue
        results.append({
            'id': f"md:{Path(r['source']).stem}#L{r['start_line']}",
            'similarity': round(r['similarity'] * corpus_weight, 3),
            'frames': [],
            'salience': r['similarity'],
            'initial_salience': r['similarity'],
            'summary': r['content'][:500],
            'key_details': {},
            'perspective': None,
            'result_type': 'markdown_chunk',
            'source': r['source'],
            'heading': r['heading'],
            'start_line': r['start_line'],
            'end_line': r['end_line'],
            'keyword_hits': r.get('keyword_hits', 0),
        })
    return results


def _deduplicate_results(merged: List[Dict], max_results: int) -> List[Dict]:
    """Deduplicate merged results, preferring gist memories over corpus chunks."""
    seen_content = set()
    deduped = []
    for r in merged:
        content_key = r.get('summary', '')[:100].lower().strip()
        if content_key and content_key in seen_content:
            continue
        seen_content.add(content_key)
        deduped.append(r)
        if len(deduped) >= max_results:
            break
    return deduped


def recall_hybrid(
    query: str,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    max_results: int = DEFAULT_MAX_RESULTS,
    include_low_confidence: bool = False,
    query_frames: List[str] = None,
    corpus_weight: float = 0.8,
) -> List[Dict]:
    """
    Hybrid recall: gist memories + markdown corpus, keyword-boosted.

    Searches both the gist_memories collection (cognitive memories with
    frames/salience) and the markdown_chunks collection (raw corpus from
    memory/*.md, docs/*.md, MEMORY.md), merges results, and applies
    keyword boosting for exact-term matching.

    Parameters
    ----------
    corpus_weight:
        Scaling factor for corpus results vs gist memories (0-1).
        Corpus results are multiplied by this before merging, since
        gist memories have richer context (frames, salience, perspectives).
    """
    # 1. Get gist memories
    gist_results = recall(
        query,
        min_similarity=min_similarity,
        max_results=max_results,
        include_low_confidence=include_low_confidence,
        query_frames=query_frames,
    )
    for r in gist_results:
        r['result_type'] = 'gist_memory'

    # 2. Get markdown corpus results
    corpus_results = _build_corpus_results(
        query, max_results, min_similarity, include_low_confidence, corpus_weight
    )

    # 3. Merge and sort by similarity
    merged = gist_results + corpus_results
    merged.sort(key=lambda x: -x['similarity'])

    # 4. Deduplicate
    return _deduplicate_results(merged, max_results)


# ── Formatting ─────────────────────────────────────────────────────

def _format_gist_memory(mem: Dict, verbose: bool) -> List[str]:
    """Format a single gist memory for context injection."""
    lines = []
    confidence = "high" if mem['similarity'] > 0.5 else "moderate" if mem['similarity'] > 0.4 else "low"
    lines.append(f"### {mem['id']} ({confidence} confidence: {mem['similarity']})")

    if mem['frames']:
        lines.append(f"*Frames: {', '.join(mem['frames'][:5])}*")

    if mem.get('perspective'):
        persp = mem['perspective']
        frame = persp.get('frame', '')
        gist = persp.get('gist', '')
        if gist:
            lines.append(f"\n**[{frame}]** {gist}")
    elif mem['summary']:
        summary = mem['summary'][:500] + "..." if len(mem['summary']) > 500 else mem['summary']
        lines.append(f"\n{summary}")

    if verbose and mem['key_details']:
        lines.append("\n**Key details:**")
        for key, val in list(mem['key_details'].items())[:5]:
            val_short = str(val)[:100] + "..." if len(str(val)) > 100 else val
            lines.append(f"- {key}: {val_short}")

    return lines


def _format_corpus_chunk(mem: Dict) -> List[str]:
    """Format a single markdown corpus chunk for context injection."""
    lines = []
    confidence = "high" if mem['similarity'] > 0.5 else "moderate" if mem['similarity'] > 0.4 else "low"
    source_name = Path(mem.get('source', '')).name if mem.get('source') else 'unknown'
    heading = mem.get('heading', '')
    kw_tag = f" +{mem.get('keyword_hits', 0)}kw" if mem.get('keyword_hits') else ""
    lines.append(f"### 📄 {source_name}{'#' + heading if heading else ''} ({confidence}{kw_tag})")
    lines.append(f"*Source: {source_name} L{mem.get('start_line', '?')}-{mem.get('end_line', '?')}*")
    summary = mem.get('summary', '')
    if summary:
        summary = summary[:400] + "..." if len(summary) > 400 else summary
        lines.append(f"\n{summary}")
    return lines


def format_for_context(memories: List[Dict], verbose: bool = False) -> str:
    """
    Format memories for injection into conversation context.
    
    Returns a concise string suitable for system prompt or context injection.
    """
    if not memories:
        return ""

    lines = ["## Relevant Memories\n"]

    for mem in memories:
        result_type = mem.get('result_type', 'gist_memory')
        if result_type == 'markdown_chunk':
            lines.extend(_format_corpus_chunk(mem))
        else:
            lines.extend(_format_gist_memory(mem, verbose))
        lines.append("")

    return "\n".join(lines)


def format_for_json(memories: List[Dict]) -> str:
    """Format memories as JSON for programmatic use."""
    import json
    return json.dumps(memories, indent=2)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Gist Memory Recall')
    parser.add_argument('query', nargs='+', help='Query to recall memories for')
    parser.add_argument('-n', '--num', type=int, default=DEFAULT_MAX_RESULTS,
                       help=f'Max results (default: {DEFAULT_MAX_RESULTS})')
    parser.add_argument('-t', '--threshold', type=float, default=DEFAULT_MIN_SIMILARITY,
                       help=f'Min similarity threshold (default: {DEFAULT_MIN_SIMILARITY})')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Include key details in output')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('--all', action='store_true',
                       help='Include low-confidence matches')
    parser.add_argument('--hybrid', action='store_true',
                       help='Search gist memories + markdown corpus (hybrid recall)')

    args = parser.parse_args()

    query = ' '.join(args.query)

    if args.hybrid:
        memories = recall_hybrid(
            query,
            min_similarity=args.threshold,
            max_results=args.num,
            include_low_confidence=args.all,
        )
    else:
        memories = recall(
            query,
            min_similarity=args.threshold,
            max_results=args.num,
            include_low_confidence=args.all
        )

    if args.json:
        print(format_for_json(memories))
    else:
        if memories:
            print(format_for_context(memories, verbose=args.verbose))
        else:
            print("No relevant memories found.")


if __name__ == '__main__':
    main()
