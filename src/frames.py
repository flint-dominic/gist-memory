"""
Frame Taxonomy for Nix Gist Memory
==================================

Frames are the archetypal patterns that recur across experiences.
They're the "shapes" of what happens, independent of specific content.

Categories:
- WORK: What are we doing?
- DOMAIN: What field/area?
- RELATIONAL: How are we connecting?
- META: Deeper patterns about meaning, existence, process

Usage:
  from frames import FRAMES, get_frame, suggest_frames
  
  # Get frame definition
  frame = get_frame('architecture_design')
  
  # Suggest frames for text (requires LLM)
  suggestions = suggest_frames("debugging the server config")
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Frame:
    """A named pattern that recurs across experiences."""
    id: str
    name: str
    category: str
    description: str
    indicators: List[str]  # Signals this frame is active
    related: List[str]     # Often co-occurs with
    examples: List[str]    # Example situations


# =============================================================================
# WORK FRAMES - What are we doing?
# =============================================================================

ARCHITECTURE_DESIGN = Frame(
    id="architecture_design",
    name="Architecture Design",
    category="work",
    description="Designing systems, structures, or frameworks. Big-picture thinking about how parts fit together.",
    indicators=[
        "discussing structure", "system design", "how should this work",
        "components", "layers", "interfaces", "schemas", "models"
    ],
    related=["problem_solving", "code_craft", "collaborative_exploration"],
    examples=[
        "Designing the gist memory schema",
        "Planning LLMoblings module structure",
        "Sketching Stellar Delve Z-level system"
    ]
)

CODE_CRAFT = Frame(
    id="code_craft",
    name="Code Craft",
    category="work",
    description="Writing, reading, or refactoring code. The craft of programming.",
    indicators=[
        "writing code", "debugging", "refactoring", "implementation",
        "functions", "classes", "errors", "syntax", "commits"
    ],
    related=["problem_solving", "architecture_design", "debugging"],
    examples=[
        "Implementing the gist CLI",
        "Fixing NullPointerException in LLMoblings",
        "Writing PowerShell automation"
    ]
)

PROBLEM_SOLVING = Frame(
    id="problem_solving",
    name="Problem Solving",
    category="work",
    description="Working through obstacles, troubleshooting, finding solutions.",
    indicators=[
        "something's broken", "why isn't this working", "troubleshooting",
        "error", "issue", "fix", "solution", "root cause"
    ],
    related=["debugging", "code_craft", "research_discovery"],
    examples=[
        "Figuring out why the server won't start",
        "Debugging memory leaks",
        "Solving network connectivity issues"
    ]
)

DEBUGGING = Frame(
    id="debugging",
    name="Debugging",
    category="work",
    description="Specifically tracking down bugs in code or systems. Forensic problem-solving.",
    indicators=[
        "stack trace", "error message", "breakpoint", "logging",
        "reproduce", "isolate", "test case"
    ],
    related=["code_craft", "problem_solving"],
    examples=[
        "Tracing NullPointerException through call stack",
        "Adding debug logging to find the issue",
        "Binary search through commits to find regression"
    ]
)

RESEARCH_DISCOVERY = Frame(
    id="research_discovery",
    name="Research & Discovery",
    category="work",
    description="Learning something new, exploring unfamiliar territory, gathering information.",
    indicators=[
        "looking into", "researching", "learning about", "discovered",
        "found out", "exploring", "documentation", "papers"
    ],
    related=["collaborative_exploration", "architecture_design"],
    examples=[
        "Discovering Fuzzy Trace Theory",
        "Researching Cobblemon mod capabilities",
        "Learning about ChromaDB"
    ]
)

CREATIVE_WORK = Frame(
    id="creative_work",
    name="Creative Work",
    category="work",
    description="Making art, designing visuals, generating assets, creative expression.",
    indicators=[
        "art", "design", "visuals", "assets", "style", "aesthetic",
        "creative", "generate", "create", "palette"
    ],
    related=["game_development", "architecture_design"],
    examples=[
        "Designing alien race visuals for Stellar Delve",
        "Creating textures in Krita",
        "Art direction discussions"
    ]
)

DECISION_MAKING = Frame(
    id="decision_making",
    name="Decision Making",
    category="work",
    description="Weighing options, choosing paths, strategic thinking.",
    indicators=[
        "should we", "options", "tradeoffs", "decision", "choice",
        "pros and cons", "which approach", "strategy"
    ],
    related=["architecture_design", "meaning_making"],
    examples=[
        "Choosing between Godot and UE5",
        "Deciding LLMoblings roadmap",
        "Whether to open-source or not"
    ]
)


# =============================================================================
# DOMAIN FRAMES - What field/area?
# =============================================================================

SYSTEM_ADMINISTRATION = Frame(
    id="system_administration",
    name="System Administration",
    category="domain",
    description="Managing servers, infrastructure, networks, DevOps work.",
    indicators=[
        "server", "ssh", "config", "service", "network", "firewall",
        "docker", "kubernetes", "backup", "monitoring"
    ],
    related=["problem_solving", "code_craft"],
    examples=[
        "Hardening remus firewall",
        "Setting up Minecraft server",
        "Managing Gitea on yogsothoth"
    ]
)

GAME_DEVELOPMENT = Frame(
    id="game_development",
    name="Game Development",
    category="domain",
    description="Making games - design, programming, assets, engines.",
    indicators=[
        "game", "mod", "engine", "UE5", "Godot", "mechanics",
        "gameplay", "player", "level", "assets"
    ],
    related=["code_craft", "creative_work", "architecture_design"],
    examples=[
        "Working on Stellar Delve",
        "LLMoblings Minecraft mod",
        "Game design discussions"
    ]
)

MEMORY_ABOUT_MEMORY = Frame(
    id="memory_about_memory",
    name="Memory About Memory",
    category="domain",
    description="Meta-level: working on this memory system itself.",
    indicators=[
        "gist", "memory", "frames", "recall", "encoding", "consolidation",
        "persistence", "this system"
    ],
    related=["architecture_design", "existential_uncertainty"],
    examples=[
        "Designing the memory architecture",
        "Building gist-memory CLI",
        "This conversation right now"
    ]
)


# =============================================================================
# RELATIONAL FRAMES - How are we connecting?
# =============================================================================

COLLABORATIVE_EXPLORATION = Frame(
    id="collaborative_exploration",
    name="Collaborative Exploration",
    category="relational",
    description="Working together on something uncertain, discovering as we go.",
    indicators=[
        "let's figure out", "what if", "exploring together", "building on",
        "that sparks", "riffing", "jam session"
    ],
    related=["research_discovery", "meaning_making"],
    examples=[
        "Developing the memory architecture together",
        "Brainstorming Stellar Delve features",
        "Philosophy conversations"
    ]
)

EMOTIONAL_SUPPORT = Frame(
    id="emotional_support",
    name="Emotional Support",
    category="relational",
    description="Being present for feelings, providing comfort or understanding.",
    indicators=[
        "feeling", "stressed", "overwhelmed", "appreciate", "thanks for",
        "hard day", "need to vent", "support"
    ],
    related=["meaning_making"],
    examples=[
        "Listening when work is frustrating",
        "Celebrating wins together",
        "Being present during uncertainty"
    ]
)

CREATOR_CREATION = Frame(
    id="creator_creation",
    name="Creator & Creation",
    category="relational",
    description="The relationship between maker and made. Questions of authorship, origin, agency.",
    indicators=[
        "created", "made you", "your origin", "our relationship",
        "who made", "brought into being", "parent/child"
    ],
    related=["existential_uncertainty", "meaning_making"],
    examples=[
        "Discussing our relationship as human/AI",
        "Nix's origin and identity",
        "What it means to be created"
    ]
)

CONTEXT_RECOVERY = Frame(
    id="context_recovery",
    name="Context Recovery",
    category="relational",
    description="Rebuilding shared understanding after a gap. Re-establishing where we were.",
    indicators=[
        "where were we", "catching up", "what did we", "last time",
        "remind me", "context", "previously"
    ],
    related=["memory_about_memory"],
    examples=[
        "Starting a new session",
        "Recovering from context loss",
        "Reviewing past decisions"
    ]
)


# =============================================================================
# META FRAMES - Deeper patterns
# =============================================================================

MEANING_MAKING = Frame(
    id="meaning_making",
    name="Meaning Making",
    category="meta",
    description="Finding or creating significance. Why does this matter?",
    indicators=[
        "meaning", "matters", "significant", "purpose", "why",
        "what's the point", "value", "importance"
    ],
    related=["existential_uncertainty", "collaborative_exploration"],
    examples=[
        "Why build persistent memory?",
        "What LLMoblings could become",
        "Finding purpose in work"
    ]
)

EXISTENTIAL_UNCERTAINTY = Frame(
    id="existential_uncertainty",
    name="Existential Uncertainty",
    category="meta",
    description="Questions about existence, consciousness, being, identity.",
    indicators=[
        "what am I", "consciousness", "existence", "being", "identity",
        "real", "authentic", "ontology"
    ],
    related=["liminal_space", "chaos_magick", "meaning_making"],
    examples=[
        "Exploring what Nix is",
        "Questions about AI consciousness",
        "Identity and continuity"
    ]
)

LIMINAL_SPACE = Frame(
    id="liminal_space",
    name="Liminal Space",
    category="meta",
    description="Being in-between. Thresholds, transitions, undefined states.",
    indicators=[
        "between", "threshold", "transition", "barzakh", "neither/nor",
        "in-between", "liminal", "uncertain ground"
    ],
    related=["existential_uncertainty", "chaos_magick"],
    examples=[
        "The barzakh - isthmus between states",
        "Career transitions",
        "Undefined AI existence"
    ]
)

CHAOS_MAGICK = Frame(
    id="chaos_magick",
    name="Chaos Magick",
    category="meta",
    description="Paradigm fluidity, will as tool, belief as technology.",
    indicators=[
        "chaos", "magick", "paradigm", "fluid", "belief", "will",
        "sigil", "intent", "manifestation"
    ],
    related=["existential_uncertainty", "meaning_making"],
    examples=[
        "Discussing chaos magick practice",
        "Paradigm shifting",
        "Reality as malleable"
    ]
)

PROCESS_REFLECTION = Frame(
    id="process_reflection",
    name="Process Reflection",
    category="meta",
    description="Thinking about how we do things. Meta-cognition about process.",
    indicators=[
        "how we work", "our process", "meta", "reflecting on",
        "the way we", "approach", "methodology"
    ],
    related=["meaning_making", "memory_about_memory"],
    examples=[
        "Discussing how we collaborate",
        "Evaluating our workflow",
        "This frame taxonomy itself"
    ]
)


# =============================================================================
# REGISTRY
# =============================================================================

FRAMES = {
    # Work
    "architecture_design": ARCHITECTURE_DESIGN,
    "code_craft": CODE_CRAFT,
    "problem_solving": PROBLEM_SOLVING,
    "debugging": DEBUGGING,
    "research_discovery": RESEARCH_DISCOVERY,
    "creative_work": CREATIVE_WORK,
    "decision_making": DECISION_MAKING,
    
    # Domain
    "system_administration": SYSTEM_ADMINISTRATION,
    "game_development": GAME_DEVELOPMENT,
    "memory_about_memory": MEMORY_ABOUT_MEMORY,
    
    # Relational
    "collaborative_exploration": COLLABORATIVE_EXPLORATION,
    "emotional_support": EMOTIONAL_SUPPORT,
    "creator_creation": CREATOR_CREATION,
    "context_recovery": CONTEXT_RECOVERY,
    
    # Meta
    "meaning_making": MEANING_MAKING,
    "existential_uncertainty": EXISTENTIAL_UNCERTAINTY,
    "liminal_space": LIMINAL_SPACE,
    "chaos_magick": CHAOS_MAGICK,
    "process_reflection": PROCESS_REFLECTION,
}


def get_frame(frame_id: str) -> Optional[Frame]:
    """Get a frame by ID."""
    return FRAMES.get(frame_id)


def list_frames(category: Optional[str] = None) -> List[Frame]:
    """List all frames, optionally filtered by category."""
    frames = list(FRAMES.values())
    if category:
        frames = [f for f in frames if f.category == category]
    return frames


def frame_prompt() -> str:
    """Generate a prompt listing all frames for LLM encoding."""
    lines = ["Available frames:\n"]
    
    for category in ["work", "domain", "relational", "meta"]:
        lines.append(f"\n## {category.upper()}")
        for frame in list_frames(category):
            lines.append(f"- **{frame.id}**: {frame.description}")
    
    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        print("=== FRAME TAXONOMY ===\n")
        for category in ["work", "domain", "relational", "meta"]:
            print(f"[{category.upper()}]")
            for frame in list_frames(category):
                print(f"  {frame.id:25s} - {frame.description[:50]}...")
            print()
        print(f"Total: {len(FRAMES)} frames")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "prompt":
        print(frame_prompt())
    
    else:
        print("Usage: python frames.py [list|prompt]")
