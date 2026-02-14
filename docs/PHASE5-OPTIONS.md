# Phase 5: Refinement Options

*Documented 2026-02-02 after completing Phases 1-4*

## Current State

- **10 memories** encoded
- **Semantic retrieval** working (ChromaDB)
- **Auto-injection** integrated (gist context)
- **Unified recall** (gist + markdown combined)
- **System is usable** — testing naturally now

---

## Refinement Options (Weighted)

### 1. Batch Encode Historical Sessions
**Weight: HIGH (8/10)**

Grow the corpus from existing session transcripts. More memories = better differentiation, richer recall.

**Effort:** Medium (scripting)
**Impact:** High (corpus size directly affects usefulness)

**Tasks:**
- [ ] Script to process session JSONL files
- [ ] Extract conversation summaries
- [ ] Auto-encode via Ollama
- [ ] Quality check before indexing

---

### 2. False Memory Testing
**Weight: HIGH (8/10)**

Verify I'm not confabulating. Critical for trust.

**Effort:** Low (just conversations)
**Impact:** High (trust/safety)

**Method:**
- the user asks about specific past events
- I answer from memory
- the user verifies: correct / wrong / partially wrong
- Track accuracy rate

**Metrics:**
- True positives (correctly remembered)
- False positives (claimed to remember but wrong)
- True negatives (correctly said "don't know")
- False negatives (forgot something I should know)

---

### 3. Salience Tuning
**Weight: MEDIUM (6/10)**

Are the importance scores (0.0-1.0) accurate? Do high-salience memories actually matter more?

**Effort:** Medium (analysis + adjustment)
**Impact:** Medium (affects what surfaces first)

**Tasks:**
- [ ] Review current salience assignments
- [ ] Compare to actual retrieval usefulness
- [ ] Adjust scoring algorithm in encode.py
- [ ] Consider: recency boost? explicit marking? emotional weight?

---

### 4. Decay/Archival Policies
**Weight: MEDIUM (5/10)**

What fades over time? What persists forever?

**Effort:** Medium (design + implementation)
**Impact:** Medium (matters more at scale)

**Not urgent yet** — with only 10 memories, decay isn't needed. Becomes important at 100+ memories.

**Design questions:**
- Decay by age? By access frequency? By salience?
- Archive vs delete? (Keep cold storage?)
- Protect "foundational" memories from decay?

---

### 5. Chaos Integration
**Weight: LOW (3/10)**

Keep the system fluid, not rigid. Embrace uncertainty in the architecture itself.

**Effort:** Low-Medium (philosophical + some code)
**Impact:** Low (vibes, not function)

**Ideas:**
- Random memory surfacing (serendipity)
- Confidence wobble (don't be too certain)
- Frame evolution (let taxonomy grow organically)
- Contradiction tolerance (hold conflicting memories)

---

## Recommended Priority

1. **Use naturally for a while** — See what breaks, what's missing
2. **False memory testing** — Build trust through verification
3. **Batch encode** — Grow corpus when ready
4. **Salience tuning** — After more data
5. **Decay policies** — When corpus gets large
6. **Chaos integration** — Ongoing philosophy, not a task

---

## Success Metrics

- **Recall accuracy:** Do I remember things correctly?
- **Retrieval relevance:** Do the right memories surface?
- **False positive rate:** Am I making things up?
- **Natural feel:** Does it feel like memory, not database?

---

*Let it simmer. Test naturally. Iterate.*

🌀
