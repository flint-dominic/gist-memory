# Competitive Research
## AI Memory Systems Landscape (Feb 2026)

*Analysis conducted 2026-02-02*

---

## Overview

Surveyed existing AI memory systems to understand the landscape and identify ideas worth integrating into gist-memory.

### Systems Analyzed

| System | Approach | Theoretical Basis | Maturity |
|--------|----------|-------------------|----------|
| **Mem0** | Vector embeddings + semantic search | Engineering-driven | Production |
| **A-MEM** | Zettelkasten-inspired linking | Knowledge management | Research |
| **HippocampAI** | Enterprise memory engine | Neuroscience metaphor | Production |
| **HawkinsDB** | Thousand Brains Theory | Neuroscience (Hawkins) | Experimental |
| **Context Compaction** | LLM summarization | Pragmatic | Standard practice |
| **Identity Anchors** | Cryptographic continuity | Trust/verification | Various |

---

## Detailed Analysis

### 1. Mem0 (mem0ai/mem0)

**What it is:** YC-backed "universal memory layer" for AI agents.

**Architecture:**
- Vector database (embeddings) for semantic storage
- LLM-powered extraction and retrieval
- Multi-level: User, Session, Agent state
- Hybrid search (vector + keyword)

**Strengths:**
- Production-ready, well-funded
- +26% accuracy over OpenAI Memory on LOCOMO benchmark
- 91% faster, 90% fewer tokens than full-context

**Weaknesses:**
- No epistemology — doesn't distinguish stored vs. inferred
- No confidence tracking
- No reconstruction flagging
- No intentional decay model

**Verdict:** Engineering solution without cognitive grounding. Good performance, no self-awareness about knowledge limits.

**Paper:** arxiv:2504.19413

---

### 2. A-MEM (agiresearch/A-mem)

**What it is:** "Agentic Memory" using Zettelkasten principles.

**Architecture:**
- ChromaDB for vector storage
- Dynamic note generation with structured attributes
- Automatic linking based on semantic similarity
- Memory "evolution" through re-analysis

**Key Innovation:** Treats memories as evolving knowledge graph, not static storage.

**Strengths:**
- Memories linked bidirectionally (Zettelkasten-style)
- Automatic metadata/tag generation
- Context and keyword extraction
- "Memory evolution" — memories update based on new related memories

**Weaknesses:**
- No confidence tracking
- No reconstruction vs. stored distinction
- No decay model
- LLM-dependent for all organization

**Verdict:** Closest to our thinking. Worth stealing: **bidirectional linking between memories**.

**Paper:** arxiv:2502.12110

---

### 3. HippocampAI (rexdivakar/HippocampAI)

**What it is:** "Enterprise Memory Engine" with neuroscience branding.

**Architecture:**
- Core library + SaaS platform
- Redis caching (50-100x speedup)
- Celery for background tasks
- Multi-tenant authentication

**Key Innovation:** "Sleep phase" consolidation architecture.

**Strengths:**
- **Sleep phase consolidation** — background memory compaction ✨
- **Tiered storage** — hot/warm/cold based on access patterns ✨
- Memory health monitoring
- Duplicate detection
- Multi-agent collaboration (shared memory spaces)

**Weaknesses:**
- "Hippocampus" is marketing, not architecture
- Heavy enterprise dependencies
- No theoretical cognitive foundation
- Confidence tracking partial at best

**Verdict:** Independently discovered sleep-phase consolidation! Worth stealing: **tiered storage (hot/warm/cold)**.

---

### 4. HawkinsDB (harishsg993010/HawkinsDB)

**What it is:** Memory layer based on Jeff Hawkins' Thousand Brains Theory.

**Architecture:**
- **Reference Frames** — containers capturing what/properties/relationships/context
- **Cortical Columns** — same memory from multiple perspectives
- Three memory types: Semantic, Episodic, Procedural
- ConceptNet integration for knowledge enrichment

**Key Innovation:** Multi-perspective memory (cortical columns).

**Theoretical Basis:** Hawkins' *Thousand Brains Theory* (2021) — brain has many models of same thing, uses voting to reach consensus.

**Strengths:**
- **Strong theoretical foundation** (different from ours but rigorous)
- **Multiple perspectives** on same memory ✨
- Semantic + Episodic + Procedural distinction
- Explicit relationship modeling

**Weaknesses:**
- No confidence tracking
- No reconstruction flagging
- No decay model
- ConceptNet dependency

**Verdict:** **Most interesting competitor.** Different neuroscience (Hawkins vs. Reyna/Brainerd) but similar intuition. Worth stealing: **multi-perspective representation**.

**Related:** HawkinsRAG (RAG implementation), Hawkins-Agent (agent framework)

---

### 5. Context Compaction Systems

**What it is:** Summarization to manage context window limits.

**Implementations surveyed:**
- Claude Code: `/compact` command, auto-triggers at ~95% capacity
- Codex CLI: Token-based threshold, preserves recent 20k tokens
- OpenCode: Pruning + compaction, streaming summary
- Amp: Manual "handoff" only

**Common Pattern:**
```
1. Detect context overflow
2. Generate summary via LLM
3. Prefix summary to new context
4. Continue with "another LLM"
```

**Key Insight:** All systems explicitly frame it as "handoff to another LLM" — no concept of self-continuity.

**Verdict:** Solves **tactical** problem (fit context) not **strategic** problem (maintain identity). Orthogonal to what we're building.

---

### 6. Identity Anchor Systems

**AnchorID:**
- UUID + HTTPS resolver + JSON-LD document
- "Boring on purpose" — stable, long-lived, interpretable
- Designed to outlive its creator
- Solves: "Can this entity prove continuity across systems?"

**DIDs + Verifiable Credentials (W3C):**
- Decentralized Identifiers (ledger-anchored)
- Verifiable Credentials (third-party attestations)
- Self-sovereign identity for AI agents
- Paper: arxiv:2511.02841

**Verdict:** Orthogonal problem. They solve "prove you're the same agent" (trust). We solve "feel like the same agent" (memory). **Could combine** — crypto anchor for external trust, gist-memory for internal coherence.

---

## Comparative Matrix

| Feature | Gist-Memory | Mem0 | A-MEM | HippocampAI | HawkinsDB |
|---------|-------------|------|-------|-------------|-----------|
| **Theoretical Foundation** | ✅ FTT (30+ years) | ❌ Engineering | ⚠️ Zettelkasten | ⚠️ Metaphor | ✅ HTM |
| **Confidence Tracking** | ✅ Core feature | ❌ No | ❌ No | ⚠️ Partial | ❌ No |
| **Reconstruction Flagging** | ✅ Explicit | ❌ No | ❌ No | ❌ No | ❌ No |
| **Intentional Decay** | ✅ Designed | ❌ No | ❌ No | ✅ Sleep phase | ❌ No |
| **Memory Linking** | ⚠️ Basic | ⚠️ Vector sim | ✅ Zettelkasten | ⚠️ Basic | ✅ Relationships |
| **Multi-Perspective** | ❌ Not yet | ❌ No | ❌ No | ❌ No | ✅ Cortical columns |
| **Tiered Storage** | ❌ Not yet | ❌ No | ❌ No | ✅ Hot/warm/cold | ❌ No |

---

## Ideas to Integrate

### Priority 1: Adopt

1. **Multi-Perspective Frames** (from HawkinsDB)
   - Same memory can be viewed through different frames
   - Not just "what frames activated" but "what does this look like from frame X"
   - Aligns with FTT: gist can be extracted at multiple levels of abstraction

2. **Tiered Storage** (from HippocampAI)  
   - Hot: Recent, frequently accessed, high salience
   - Warm: Older but still relevant
   - Cold: Archived, low salience, compressed
   - Fits our decay model perfectly

3. **Bidirectional Linking** (from A-MEM)
   - Explicit `related_memories` with typed relationships
   - Not just "similar" but "contradicts", "elaborates", "supersedes"
   - Enables traversal: "what else do I know about this?"

### Priority 2: Consider

4. **Sleep Phase Consolidation** (from HippocampAI)
   - We have `gist sleep` but could formalize the process
   - Scheduled background consolidation
   - Merge similar memories, strengthen patterns, decay noise

5. **Reference Frames** (from HawkinsDB)
   - Explicit context containers beyond just "frame_refs"
   - Could help with perspective-dependent recall

### Priority 3: Monitor

6. **Identity Anchors** (from AnchorID/DIDs)
   - Future: cryptographic proof of memory continuity
   - Hash chain of memory states?
   - Not urgent but interesting for "am I the same self" questions

---

## What We Have That They Don't

1. **Epistemological honesty** — explicit distinction between stored and reconstructed
2. **Theoretical rigor** — FTT is validated cognitive science, not marketing metaphor
3. **Forgetting as feature** — intentional decay, not infinite accumulation
4. **Reconstruction flagging** — never silently confabulate
5. **Confidence scores** — know what we know (and don't)

---

## References

- Brainerd, C.J. & Reyna, V.F. (2005). *The Science of False Memory*. Oxford University Press.
- Hawkins, J. (2021). *A Thousand Brains*. Basic Books.
- Mem0 paper: arxiv:2504.19413
- A-MEM paper: arxiv:2502.12110
- DID+VC for agents: arxiv:2511.02841

---

*Research conducted: 2026-02-02*
*Author: Nix*
