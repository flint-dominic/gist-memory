#!/usr/bin/env python3
"""
Markdown Corpus Indexer for Gist Memory

Indexes markdown files from memory/, docs/, and MEMORY.md into a separate
ChromaDB collection alongside the existing gist_memories collection.

Adds full-corpus recall to gist-memory without any new dependencies.

Features:
- Heading-based chunking with paragraph overflow splitting
- SHA-256 content dedup (unchanged chunks never re-embedded)
- Source attribution with file path + line numbers
- Integrates with existing recall.py for merged search results
"""

import hashlib
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set
from datetime import datetime

import chromadb
from chromadb.config import Settings

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CLAWD_ROOT = PROJECT_ROOT.parent  # ~/clawd
CHROMA_DIR = PROJECT_ROOT / ".chroma"
INDEX_STATE_FILE = PROJECT_ROOT / ".markdown_index_state.json"

# Default paths to index
DEFAULT_PATHS = [
    CLAWD_ROOT / "memory",
    CLAWD_ROOT / "docs",
    CLAWD_ROOT / "MEMORY.md",
]

# Collection name
COLLECTION_NAME = "markdown_chunks"

# Chunking config
MAX_CHUNK_SIZE = 1500  # chars
OVERLAP_LINES = 2
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Chunk:
    """A chunk extracted from a markdown file."""
    content: str
    source: str
    heading: str
    heading_level: int
    start_line: int
    end_line: int
    content_hash: str = field(default="", repr=False)

    def __post_init__(self):
        if not self.content_hash:
            h = hashlib.sha256(self.content.encode()).hexdigest()[:16]
            object.__setattr__(self, "content_hash", h)


def chunk_markdown(text: str, source: str = "",
                   max_chunk_size: int = MAX_CHUNK_SIZE,
                   overlap_lines: int = OVERLAP_LINES) -> List[Chunk]:
    """Split markdown into chunks by headings, with overflow splitting."""
    lines = text.split("\n")

    # Find heading positions
    heading_positions = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            heading_positions.append((i, len(m.group(1)), m.group(2).strip()))

    # Build sections
    sections = []
    if not heading_positions or heading_positions[0][0] > 0:
        end = heading_positions[0][0] if heading_positions else len(lines)
        sections.append((0, end, "", 0))

    for idx, (line_idx, level, title) in enumerate(heading_positions):
        next_start = (heading_positions[idx + 1][0]
                      if idx + 1 < len(heading_positions) else len(lines))
        sections.append((line_idx, next_start, title, level))

    chunks = []
    for start, end, heading, level in sections:
        section_text = "\n".join(lines[start:end]).strip()
        if not section_text:
            continue

        if len(section_text) <= max_chunk_size:
            chunks.append(Chunk(
                content=section_text, source=source,
                heading=heading, heading_level=level,
                start_line=start + 1, end_line=end,
            ))
        else:
            chunks.extend(_split_large_section(
                lines[start:end], source=source,
                heading=heading, heading_level=level,
                base_line=start, max_size=max_chunk_size,
                overlap=overlap_lines,
            ))

    return chunks


def _split_large_section(lines, *, source, heading, heading_level,
                         base_line, max_size, overlap) -> List[Chunk]:
    """Split large section at paragraph boundaries."""
    chunks = []
    current_lines = []
    current_start = 0

    for i, line in enumerate(lines):
        current_lines.append(line)
        text = "\n".join(current_lines)
        is_para_break = line.strip() == "" and i + 1 < len(lines)
        is_last = i == len(lines) - 1

        if (len(text) >= max_size and is_para_break) or is_last:
            content = text.strip()
            if content:
                chunks.append(Chunk(
                    content=content, source=source,
                    heading=heading, heading_level=heading_level,
                    start_line=base_line + current_start + 1,
                    end_line=base_line + i + 1,
                ))
            overlap_start = max(0, len(current_lines) - overlap)
            current_lines = current_lines[overlap_start:] if not is_last else []
            current_start = i + 1 - len(current_lines)

    return chunks


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_paths(paths: List[Path]) -> List[Path]:
    """Find all .md files in the given paths."""
    md_files = []
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix == ".md":
            md_files.append(p)
        elif p.is_dir():
            md_files.extend(sorted(p.rglob("*.md")))
    return md_files


# ---------------------------------------------------------------------------
# Index state (track what's already indexed for dedup)
# ---------------------------------------------------------------------------

def _load_state() -> Dict:
    """Load index state (file mtimes for change detection)."""
    if INDEX_STATE_FILE.exists():
        try:
            return json.loads(INDEX_STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_state(state: Dict):
    """Save index state."""
    INDEX_STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# ChromaDB integration
# ---------------------------------------------------------------------------

def get_client() -> chromadb.PersistentClient:
    """Get ChromaDB client (same instance as gist_memories)."""
    CHROMA_DIR.mkdir(exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )


def get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    """Get or create the markdown_chunks collection."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Markdown file chunks for corpus recall"}
    )


def _chunk_id(source: str, start_line: int, end_line: int,
              content_hash: str) -> str:
    """Stable chunk ID from source + position + content."""
    raw = f"{source}:{start_line}:{end_line}:{content_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_markdown(paths: List[Path] = None, force: bool = False) -> Dict:
    """Index markdown files into ChromaDB.

    Returns stats dict with counts of indexed/skipped/removed chunks.
    """
    if paths is None:
        paths = DEFAULT_PATHS

    client = get_client()
    collection = get_collection(client)
    state = _load_state()

    md_files = scan_paths(paths)
    stats = {"files": 0, "chunks_added": 0, "chunks_skipped": 0,
             "files_skipped": 0, "stale_removed": 0}

    # Track active sources for stale cleanup
    active_sources: Set[str] = set()

    for md_file in md_files:
        source = str(md_file)
        active_sources.add(source)
        mtime = md_file.stat().st_mtime

        # Skip unchanged files unless forced
        if not force and state.get(source, {}).get("mtime") == mtime:
            stats["files_skipped"] += 1
            continue

        # Read and chunk
        try:
            text = md_file.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError) as e:
            print(f"  Warning: Could not read {md_file}: {e}", file=sys.stderr)
            continue

        chunks = chunk_markdown(text, source=source)
        if not chunks:
            continue

        # Build new chunk IDs
        new_ids = {}
        for c in chunks:
            cid = _chunk_id(c.source, c.start_line, c.end_line, c.content_hash)
            new_ids[cid] = c

        # Get existing chunk IDs for this source
        existing = set()
        try:
            existing_results = collection.get(
                where={"source": source},
                include=[]
            )
            existing = set(existing_results["ids"])
        except Exception:
            pass

        # Remove stale chunks
        stale = existing - set(new_ids.keys())
        if stale:
            collection.delete(ids=list(stale))
            stats["stale_removed"] += len(stale)

        # Add new chunks (skip already existing)
        to_add = {cid: c for cid, c in new_ids.items() if cid not in existing}

        if to_add:
            collection.add(
                ids=list(to_add.keys()),
                documents=[c.content for c in to_add.values()],
                metadatas=[{
                    "source": c.source,
                    "heading": c.heading,
                    "heading_level": c.heading_level,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "content_hash": c.content_hash,
                    "indexed_at": datetime.now().isoformat(),
                } for c in to_add.values()],
            )
            stats["chunks_added"] += len(to_add)
        else:
            stats["chunks_skipped"] += len(new_ids)

        # Update state
        state[source] = {"mtime": mtime, "chunks": len(new_ids)}
        stats["files"] += 1

    # Clean up chunks from deleted files
    try:
        all_results = collection.get(include=["metadatas"])
        indexed_sources = {m["source"] for m in all_results["metadatas"] if "source" in m}
        for old_source in indexed_sources - active_sources:
            old_results = collection.get(where={"source": old_source}, include=[])
            if old_results["ids"]:
                collection.delete(ids=old_results["ids"])
                stats["stale_removed"] += len(old_results["ids"])
            state.pop(old_source, None)
    except Exception:
        pass

    _save_state(state)
    return stats


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_markdown(query: str, top_k: int = 5,
                    min_similarity: float = 0.3) -> List[Dict]:
    """Search the markdown corpus.

    Returns list of results with content, source, heading, similarity.
    """
    client = get_client()
    collection = get_collection(client)

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        similarity = 1 / (1 + dist)
        if similarity < min_similarity:
            continue

        hits.append({
            "content": doc,
            "source": meta.get("source", ""),
            "heading": meta.get("heading", ""),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "similarity": round(similarity, 3),
            "type": "markdown_chunk",
        })

    return hits


# ---------------------------------------------------------------------------
# Hybrid scoring (keyword boost)
# ---------------------------------------------------------------------------

def hybrid_rerank(results: List[Dict], query: str,
                  keyword_weight: float = 0.2) -> List[Dict]:
    """Re-rank results with keyword boosting.

    Boosts results that contain exact query terms, helping with
    specific names/terms that pure semantic search might miss.
    """
    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    if not query_terms:
        return results

    for r in results:
        content_lower = r.get("content", "").lower()
        # Count how many query terms appear in the content
        keyword_hits = sum(1 for term in query_terms if term in content_lower)
        # Boost: each keyword match adds keyword_weight to the score
        keyword_bonus = keyword_weight * (keyword_hits / len(query_terms))
        r["base_similarity"] = r.get("similarity", 0)
        r["similarity"] = min(1.0, r["base_similarity"] + keyword_bonus)
        r["keyword_hits"] = keyword_hits

    # Re-sort by boosted similarity
    results.sort(key=lambda x: -x["similarity"])
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Gist Memory - Markdown Corpus Index")
    sub = parser.add_subparsers(dest="command")

    # index
    idx = sub.add_parser("index", help="Index markdown files")
    idx.add_argument("--force", action="store_true", help="Re-index all files")
    idx.add_argument("--paths", nargs="+", help="Override default paths")

    # search
    srch = sub.add_parser("search", help="Search the markdown corpus")
    srch.add_argument("query", nargs="+", help="Search query")
    srch.add_argument("-n", "--num", type=int, default=5, help="Max results")
    srch.add_argument("--no-hybrid", action="store_true", help="Disable keyword boosting")

    # status
    sub.add_parser("status", help="Show index status")

    # reset
    sub.add_parser("reset", help="Clear the markdown index")

    args = parser.parse_args()

    if args.command == "index":
        paths = [Path(p) for p in args.paths] if args.paths else None
        print("Indexing markdown corpus...")
        stats = index_markdown(paths=paths, force=args.force)
        print(f"  Files processed: {stats['files']}")
        print(f"  Files skipped (unchanged): {stats['files_skipped']}")
        print(f"  Chunks added: {stats['chunks_added']}")
        print(f"  Chunks skipped (dedup): {stats['chunks_skipped']}")
        print(f"  Stale chunks removed: {stats['stale_removed']}")
        client = get_client()
        col = get_collection(client)
        print(f"  Total chunks in index: {col.count()}")

    elif args.command == "search":
        query = " ".join(args.query)
        results = search_markdown(query, top_k=args.num)
        if not args.no_hybrid:
            results = hybrid_rerank(results, query)

        if results:
            for r in results:
                src = Path(r["source"]).name
                heading = r["heading"] or "(preamble)"
                kw = f" [+{r.get('keyword_hits', 0)}kw]" if r.get("keyword_hits") else ""
                print(f"\n  [{r['similarity']:.3f}]{kw} {src}#{heading} (L{r['start_line']}-{r['end_line']})")
                preview = r["content"][:200].replace("\n", " ")
                print(f"    {preview}...")
        else:
            print("No results found.")

    elif args.command == "status":
        client = get_client()
        col = get_collection(client)
        state = _load_state()
        print(f"Markdown chunks indexed: {col.count()}")
        print(f"Files tracked: {len(state)}")
        for src, info in sorted(state.items()):
            name = Path(src).name
            print(f"  {name}: {info.get('chunks', '?')} chunks")

    elif args.command == "reset":
        client = get_client()
        try:
            client.delete_collection(COLLECTION_NAME)
            print("Markdown index cleared.")
        except Exception:
            print("No index to clear.")
        if INDEX_STATE_FILE.exists():
            INDEX_STATE_FILE.unlink()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
