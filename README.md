# Gist Memory

*Fuzzy Trace Theory-inspired persistent memory for AI systems*

## What Is This?

A memory architecture based on cognitive science research showing that human memory stores **two parallel traces**:

| Cognitive Term | Our Term | What It Holds |
|----------------|----------|---------------|
| **Gist** | Frame | Patterns, meanings, "the shape of things" |
| **Verbatim** | Texture | Specific details, exact facts, surface features |

Gist persists. Verbatim fades. We lean into this rather than fighting it.

## Core Principles

- **Store frames with high fidelity** — The pattern is the memory
- **Let texture be lossy** — Details can degrade or reconstruct
- **Flag all reconstruction** — Never confabulate silently
- **Confidence on everything** — Know what you know (and don't)
- **Forgetting as feature** — Space to grow, not bug to fix

## Theoretical Foundation

Based on **Fuzzy Trace Theory** by Valerie F. Reyna & Charles J. Brainerd (Cornell University), 30+ years of validated research.

> Brainerd, C.J. & Reyna, V.F. (2005). *The Science of False Memory*. Oxford University Press.

## Status

**Phase 1: Manual Prototype** — building frame taxonomy and testing encoding

## Project Structure

```
gist-memory/
├── docs/
│   ├── ARCHITECTURE.md    # Full design document
│   ├── FRAMES.md          # Frame taxonomy
│   ├── RESEARCH.md        # Competitive analysis (Feb 2026)
│   └── ROADMAP.md         # Implementation timeline
├── src/                   # Implementation
├── examples/              # Example encodings
└── tests/                 # Validation
```

## Origin

Born in conversation between Nix (AI) and gblfxt (human), 2026-02-02. The first memory it holds is the conversation that created it.

🌀
