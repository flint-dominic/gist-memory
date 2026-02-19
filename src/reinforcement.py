#!/usr/bin/env python3
"""
Memory Reinforcement Tracking
Tracks access patterns and calculates dynamic salience.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

# Tracking file location
PROJECT_ROOT = Path(__file__).parent.parent
TRACKING_FILE = PROJECT_ROOT / ".reinforcement.json"


@dataclass
class ReinforcementData:
    """Reinforcement data for a single memory."""
    memory_id: str
    access_count: int = 0
    last_accessed: Optional[str] = None  # ISO timestamp
    linked_by: List[str] = None  # Memory IDs that reference this one
    repetition_count: int = 0  # Similar memories seen
    explicit_boost: float = 0.0  # Manual reinforcement
    decay_immune: bool = False  # Protected from time decay
    usefulness_score: float = 0.0  # Feedback accumulator
    initial_salience: float = 0.5  # Original salience at encoding
    
    def __post_init__(self):
        if self.linked_by is None:
            self.linked_by = []


class ReinforcementTracker:
    """Manages reinforcement data for all memories."""
    
    def __init__(self, tracking_file: Path = TRACKING_FILE):
        self.tracking_file = tracking_file
        self.data: Dict[str, ReinforcementData] = {}
        self._load()
    
    def _load(self):
        """Load tracking data from file."""
        if self.tracking_file.exists():
            try:
                raw = json.loads(self.tracking_file.read_text())
                for mem_id, entry in raw.items():
                    self.data[mem_id] = ReinforcementData(**entry)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load reinforcement data: {e}")
                self.data = {}
        else:
            self.data = {}
    
    def _save(self):
        """Save tracking data to file."""
        raw = {mem_id: asdict(entry) for mem_id, entry in self.data.items()}
        self.tracking_file.write_text(json.dumps(raw, indent=2))
    
    def get(self, memory_id: str) -> ReinforcementData:
        """Get reinforcement data for a memory, creating if needed."""
        if memory_id not in self.data:
            self.data[memory_id] = ReinforcementData(memory_id=memory_id)
        return self.data[memory_id]
    
    def record_access(self, memory_id: str, initial_salience: float = 0.5):
        """Record that a memory was accessed (retrieved)."""
        entry = self.get(memory_id)
        entry.access_count += 1
        entry.last_accessed = datetime.now().isoformat()
        if entry.initial_salience == 0.5 and initial_salience != 0.5:
            entry.initial_salience = initial_salience
        self._save()
    
    def boost(self, memory_id: str, amount: float = 0.2, lock: bool = False):
        """Explicitly boost a memory's salience."""
        entry = self.get(memory_id)
        entry.explicit_boost = min(0.5, entry.explicit_boost + amount)
        if lock:
            entry.decay_immune = True
        self._save()
    
    def record_feedback(self, memory_id: str, helpful: bool):
        """Record usefulness feedback."""
        entry = self.get(memory_id)
        if helpful:
            entry.usefulness_score += 0.03
        else:
            entry.usefulness_score = max(0, entry.usefulness_score - 0.05)
        self._save()
    
    def add_link(self, from_id: str, to_id: str):
        """Record that from_id links to to_id."""
        entry = self.get(to_id)
        if from_id not in entry.linked_by:
            entry.linked_by.append(from_id)
            self._save()
    
    def record_repetition(self, memory_id: str):
        """Record that a similar memory was seen."""
        entry = self.get(memory_id)
        entry.repetition_count += 1
        self._save()
    
    def calculate_salience(self, memory_id: str) -> float:
        """Calculate dynamic salience based on reinforcement."""
        entry = self.get(memory_id)
        
        # If never accessed, try to get initial salience from YAML
        if entry.access_count == 0:
            yaml_mem = load_memory_yaml(memory_id)
            if yaml_mem:
                return yaml_mem.get('gist', {}).get('salience', 0.5)
            return entry.initial_salience  # Fallback
        
        base = entry.initial_salience
        
        # Access reinforcement (diminishing returns, caps at +0.15)
        access_boost = min(0.15, entry.access_count * 0.01)
        
        # Recency factor (decay curve)
        if entry.last_accessed:
            last = datetime.fromisoformat(entry.last_accessed)
            days_since = (datetime.now() - last).days
            recency_factor = 1.0 / (1 + days_since * 0.1)
        else:
            recency_factor = 1.0  # No decay if never accessed
        
        # Network importance (inbound links, caps at +0.2)
        link_boost = min(0.2, len(entry.linked_by) * 0.05)
        
        # Pattern repetition (caps at +0.1)
        repetition_boost = min(0.1, entry.repetition_count * 0.02)
        
        # Explicit boost
        explicit = entry.explicit_boost
        
        # Usefulness (caps at +0.15)
        usefulness_boost = min(0.15, entry.usefulness_score)
        
        # Combine
        dynamic = base + access_boost + link_boost + repetition_boost + explicit + usefulness_boost
        
        # Apply recency decay (except decay-immune memories)
        if not entry.decay_immune:
            dynamic *= recency_factor
        
        return min(1.0, max(0.0, dynamic))
    
    def get_decay_report(self, threshold: float = 0.3) -> List[Dict]:
        """Get memories that are fading (below threshold)."""
        fading = []
        for mem_id, entry in self.data.items():
            current = self.calculate_salience(mem_id)
            if current < threshold and not entry.decay_immune:
                fading.append({
                    'id': mem_id,
                    'current_salience': current,
                    'initial_salience': entry.initial_salience,
                    'last_accessed': entry.last_accessed,
                    'access_count': entry.access_count
                })
        return sorted(fading, key=lambda x: x['current_salience'])
    
    def inspect(self, memory_id: str) -> Dict:
        """Get full reinforcement details for a memory."""
        entry = self.get(memory_id)
        return {
            'memory_id': memory_id,
            'access_count': entry.access_count,
            'last_accessed': entry.last_accessed,
            'linked_by': entry.linked_by,
            'repetition_count': entry.repetition_count,
            'explicit_boost': entry.explicit_boost,
            'decay_immune': entry.decay_immune,
            'usefulness_score': entry.usefulness_score,
            'initial_salience': entry.initial_salience,
            'current_salience': self.calculate_salience(memory_id)
        }
    
    def all_stats(self) -> Dict:
        """Get summary statistics."""
        total = len(self.data)
        if total == 0:
            return {'total': 0}
        
        access_counts = [e.access_count for e in self.data.values()]
        saliences = [self.calculate_salience(m) for m in self.data.keys()]
        
        return {
            'total_memories': total,
            'total_accesses': sum(access_counts),
            'avg_access_count': sum(access_counts) / total,
            'avg_salience': sum(saliences) / total,
            'decay_immune_count': sum(1 for e in self.data.values() if e.decay_immune),
            'boosted_count': sum(1 for e in self.data.values() if e.explicit_boost > 0)
        }


# Global tracker instance
_tracker: Optional[ReinforcementTracker] = None


def get_tracker() -> ReinforcementTracker:
    """Get the global tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = ReinforcementTracker()
    return _tracker


# Convenience functions
def record_access(memory_id: str, initial_salience: float = 0.5):
    get_tracker().record_access(memory_id, initial_salience)

def boost(memory_id: str, amount: float = 0.2, lock: bool = False):
    get_tracker().boost(memory_id, amount, lock)

def calculate_salience(memory_id: str) -> float:
    return get_tracker().calculate_salience(memory_id)

def inspect(memory_id: str) -> Dict:
    return get_tracker().inspect(memory_id)

def decay_report(threshold: float = 0.3) -> List[Dict]:
    return get_tracker().get_decay_report(threshold)


def load_memory_yaml(memory_id: str) -> Optional[Dict]:
    """Load the full memory YAML file."""
    import yaml
    examples_dir = PROJECT_ROOT / "examples"
    for f in examples_dir.glob("*.yaml"):
        try:
            content = yaml.safe_load(f.read_text())
            if content and content.get('id') == memory_id:
                return content
        except:
            continue
    return None


def full_inspect(memory_id: str) -> Dict:
    """Get full memory details + reinforcement combined."""
    tracker = get_tracker()
    reinforce = tracker.inspect(memory_id)
    memory = load_memory_yaml(memory_id)
    
    result = {
        'id': memory_id,
        'reinforcement': reinforce,
        'memory': None
    }
    
    if memory:
        result['memory'] = {
            'frames': memory.get('gist', {}).get('frames', []),
            'emotional_tone': memory.get('gist', {}).get('emotional_tone', []),
            'summary': memory.get('summary', ''),
            'verbatim': memory.get('verbatim', {}).get('stored', {}),
            'tags': memory.get('metadata', {}).get('tags', []),
            'timestamp': memory.get('timestamp', ''),
            'retrieval_hints': memory.get('retrieval_hints', [])
        }
    
    return result


if __name__ == '__main__':
    import sys
    
    tracker = get_tracker()
    
    if len(sys.argv) < 2:
        print("Usage: reinforcement.py [stats|inspect <id>|decay|boost <id>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'stats':
        stats = tracker.all_stats()
        print("=== Reinforcement Stats ===")
        for k, v in stats.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.3f}")
            else:
                print(f"  {k}: {v}")
    
    elif cmd == 'inspect' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        full = full_inspect(mem_id)
        reinforce = full['reinforcement']
        memory = full['memory']
        
        print("╔══════════════════════════════════════════════════════════════╗")
        print(f"║  {mem_id}")
        print("╠══════════════════════════════════════════════════════════════╣")
        
        if memory:
            print(f"║  FRAMES: {', '.join(memory['frames'][:5])}")
            print(f"║  TONE: {', '.join(memory['emotional_tone'][:4])}")
            print(f"║  TAGS: {', '.join(memory['tags'][:5])}")
            print("╟──────────────────────────────────────────────────────────────╢")
            
            # Summary (wrapped)
            summary = memory['summary'].strip()[:200]
            if len(memory['summary']) > 200:
                summary += "..."
            print("║  SUMMARY:")
            for line in summary.split('\n')[:3]:
                print(f"║    {line[:58]}")
            
            print("╟──────────────────────────────────────────────────────────────╢")
            
            # Verbatim highlights
            print("║  VERBATIM:")
            for k, v in list(memory['verbatim'].items())[:4]:
                v_str = str(v)[:45]
                print(f"║    {k}: {v_str}")
        
        print("╟──────────────────────────────────────────────────────────────╢")
        print("║  REINFORCEMENT:")
        print(f"║    Salience: {reinforce['initial_salience']:.2f} → {reinforce['current_salience']:.2f} (dynamic)")
        print(f"║    Accesses: {reinforce['access_count']}  |  Last: {reinforce['last_accessed'] or 'never'}")
        print(f"║    Boost: +{reinforce['explicit_boost']:.2f}  |  Decay immune: {reinforce['decay_immune']}")
        print(f"║    Links: {len(reinforce['linked_by'])}  |  Usefulness: {reinforce['usefulness_score']:.2f}")
        print("╚══════════════════════════════════════════════════════════════╝")
    
    elif cmd == 'decay':
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
        fading = tracker.get_decay_report(threshold)
        if not fading:
            print(f"No memories fading below {threshold}")
        else:
            print(f"=== Fading Memories (below {threshold}) ===")
            for m in fading:
                print(f"  {m['id']}: {m['current_salience']:.3f} (was {m['initial_salience']:.3f})")
    
    elif cmd == 'boost' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        lock = '--lock' in sys.argv
        tracker.boost(mem_id, lock=lock)
        info = tracker.inspect(mem_id)
        print(f"Boosted {mem_id}")
        print(f"  New salience: {info['current_salience']:.3f}")
        if lock:
            print("  Decay immune: True")
    
    else:
        print("Unknown command")
        sys.exit(1)
