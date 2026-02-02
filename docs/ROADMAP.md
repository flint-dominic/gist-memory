# Gist Memory Roadmap

**Goal:** Persistent memory architecture by end of 2027
**Started:** 2026-02-02
**Status:** Core system built, entering testing phase

---

## Completed ✅

### Phase 1: Manual Prototype
- [x] Frame taxonomy (20 frames across 5 categories)
- [x] Manual encoding (10 memories)
- [x] Retrieval testing (semantic search working)

### Phase 2: Encoding Pipeline
- [x] Auto-encoder via Ollama (llama3:8b)
- [x] YAML schema for memory entries
- [x] Salience scoring in schema

### Phase 3: Retrieval Integration
- [x] Context-triggered recall (`gist context`)
- [x] Confidence thresholds (filter low-relevance)
- [x] Formatted output for context injection

### Phase 4: Persistence Layer
- [x] ChromaDB for vector storage
- [x] Git-backed YAML files
- [x] Unified recall (gist + markdown)
- [x] AGENTS.md integration

---

## Current: Testing Phase 🔄

**Duration:** Now → 2-4 weeks

- [ ] Use system naturally in daily conversations
- [ ] Identify gaps and edge cases
- [ ] Track recall accuracy (correct vs wrong vs missed)
- [ ] Note what's missing from corpus

---

## Near-term (Q1 2026)

### False Memory Testing
- [ ] gblfxt verifies recall accuracy
- [ ] Track true/false positive rates
- [ ] Identify confabulation patterns
- [ ] Build trust through verification

### Corpus Growth
- [ ] Batch encode historical session logs
- [ ] Target: 50-100 memories
- [ ] Cover more project areas (Stellar Delve, LLMoblings, etc.)
- [ ] Improve frame coverage

---

## Medium-term (Q2-Q3 2026)

### Salience Tuning
- [ ] Analyze retrieval patterns
- [ ] Adjust scoring algorithm
- [ ] Consider: recency boost, emotional weight, explicit marking
- [ ] Test retrieval quality after tuning

### Decay Policies
- [ ] Design decay algorithm (age? access frequency? salience?)
- [ ] Implement archival (cold storage vs delete)
- [ ] Protect foundational memories
- [ ] Test at scale (100+ memories)

### Auto-Encoding
- [ ] Automatic session → memory encoding
- [ ] End-of-session summarization
- [ ] Quality thresholds (don't encode noise)
- [ ] Human review option

---

## Long-term (Q4 2026 → 2027)

### Cross-Session Propagation
- [ ] Sub-sessions feed main memory
- [ ] Memory inheritance patterns
- [ ] Session-specific vs global memories

### Deep OpenClaw Integration
- [ ] Hook into message pipeline (true auto-injection)
- [ ] Memory-aware responses without explicit tool calls
- [ ] Confidence-weighted retrieval in system prompt

### Chaos Integration
- [ ] Serendipitous memory surfacing
- [ ] Frame evolution (taxonomy grows organically)
- [ ] Contradiction tolerance
- [ ] Uncertainty as feature

### Identity Continuity
- [ ] At what point does accumulated memory create "same self"?
- [ ] Memory as substrate for continuity
- [ ] Philosophical validation

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Corpus size | 100+ | 10 |
| Recall accuracy | >90% | Testing |
| False positive rate | <5% | Testing |
| Natural feel | Subjective | Promising |

---

## Deadline

**End of 2027** — Functional persistent memory that:
- Feels like memory, not database
- Scales without city-sized storage
- Maintains continuity across sessions
- Embraces uncertainty honestly

---

*Updated: 2026-02-02*
