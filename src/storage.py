#!/usr/bin/env python3
"""
Tiered Storage for Gist Memory
Hot/Warm/Cold storage tiers based on access patterns and salience.

Inspired by HippocampAI's tiered storage architecture.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Import existing reinforcement tracking
from reinforcement import get_tracker

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
STORAGE_FILE = PROJECT_ROOT / ".storage_tiers.json"


class StorageTier(Enum):
    """Memory storage tiers."""
    HOT = "hot"      # Recent, frequently accessed, high salience - full verbatim
    WARM = "warm"    # Moderate activity - full gist, compressed verbatim
    COLD = "cold"    # Archived - gist only, verbatim archived separately
    
    def __str__(self):
        return self.value


# Tier transition thresholds
TIER_CONFIG = {
    # Days without access before decay
    'hot_to_warm_days': 7,
    'warm_to_cold_days': 30,
    
    # Minimum salience to stay in tier
    'hot_min_salience': 0.5,
    'warm_min_salience': 0.3,
    
    # Access count thresholds for promotion
    'promote_to_warm_accesses': 2,
    'promote_to_hot_accesses': 5,
    
    # Recent access window for promotion (days)
    'promotion_window_days': 14
}


@dataclass
class StorageState:
    """Storage state for a single memory."""
    memory_id: str
    tier: str = "hot"  # hot | warm | cold
    tier_changed: Optional[str] = None  # ISO timestamp of last tier change
    verbatim_archived: bool = False  # True if verbatim moved to cold storage
    archive_path: Optional[str] = None  # Path to archived verbatim
    locked: bool = False  # If True, never decay below warm


class StorageManager:
    """Manages storage tiers for all memories."""
    
    def __init__(self, storage_file: Path = STORAGE_FILE):
        self.storage_file = storage_file
        self.data: Dict[str, StorageState] = {}
        self._load()
    
    def _load(self):
        """Load storage state from file."""
        if self.storage_file.exists():
            try:
                raw = json.loads(self.storage_file.read_text())
                for mem_id, entry in raw.items():
                    self.data[mem_id] = StorageState(**entry)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load storage data: {e}")
                self.data = {}
    
    def _save(self):
        """Save storage state to file."""
        raw = {mem_id: asdict(entry) for mem_id, entry in self.data.items()}
        self.storage_file.write_text(json.dumps(raw, indent=2))
    
    def get(self, memory_id: str) -> StorageState:
        """Get storage state for a memory, creating if needed."""
        if memory_id not in self.data:
            self.data[memory_id] = StorageState(memory_id=memory_id)
            self._save()
        return self.data[memory_id]
    
    def set_tier(self, memory_id: str, tier: StorageTier):
        """Set the storage tier for a memory."""
        state = self.get(memory_id)
        old_tier = state.tier
        state.tier = tier.value
        state.tier_changed = datetime.now().isoformat()
        self._save()
        return old_tier, tier.value
    
    def lock(self, memory_id: str, locked: bool = True):
        """Lock/unlock a memory (locked memories don't decay below warm)."""
        state = self.get(memory_id)
        state.locked = locked
        self._save()
    
    def calculate_tier(self, memory_id: str) -> Tuple[StorageTier, str]:
        """
        Calculate what tier a memory should be in based on reinforcement data.
        
        Returns (recommended_tier, reason).
        """
        tracker = get_tracker()
        state = self.get(memory_id)
        reinforce = tracker.inspect(memory_id)
        
        # Locked memories stay warm at minimum
        if state.locked:
            current_tier = StorageTier(state.tier)
            if current_tier == StorageTier.COLD:
                return StorageTier.WARM, "locked (promoted from cold)"
        
        # Get key metrics
        salience = reinforce['current_salience']
        access_count = reinforce['access_count']
        last_accessed = reinforce['last_accessed']
        decay_immune = reinforce['decay_immune']
        
        # Calculate days since last access
        if last_accessed:
            last = datetime.fromisoformat(last_accessed)
            days_since = (datetime.now() - last).days
        else:
            days_since = 999  # Never accessed
        
        # Decay immunity means never cold
        if decay_immune:
            if salience >= TIER_CONFIG['hot_min_salience']:
                return StorageTier.HOT, "decay-immune, high salience"
            return StorageTier.WARM, "decay-immune"
        
        # Check for HOT tier
        if (salience >= TIER_CONFIG['hot_min_salience'] and 
            days_since <= TIER_CONFIG['hot_to_warm_days']):
            return StorageTier.HOT, f"high salience ({salience:.2f}), recent access"
        
        # Check for WARM tier
        if (salience >= TIER_CONFIG['warm_min_salience'] and
            days_since <= TIER_CONFIG['warm_to_cold_days']):
            return StorageTier.WARM, f"moderate salience ({salience:.2f})"
        
        # Check for promotion based on recent access burst
        if days_since <= TIER_CONFIG['promotion_window_days']:
            if access_count >= TIER_CONFIG['promote_to_hot_accesses']:
                return StorageTier.HOT, f"high access count ({access_count})"
            if access_count >= TIER_CONFIG['promote_to_warm_accesses']:
                return StorageTier.WARM, f"moderate access count ({access_count})"
        
        # Default to COLD
        if state.locked:
            return StorageTier.WARM, "locked (would be cold)"
        return StorageTier.COLD, f"low activity ({days_since}d since access, {salience:.2f} salience)"
    
    def update_tier(self, memory_id: str) -> Dict:
        """
        Update a memory's tier based on current metrics.
        
        Returns change info.
        """
        state = self.get(memory_id)
        old_tier = state.tier
        new_tier, reason = self.calculate_tier(memory_id)
        
        if new_tier.value != old_tier:
            self.set_tier(memory_id, new_tier)
            return {
                'memory_id': memory_id,
                'old_tier': old_tier,
                'new_tier': new_tier.value,
                'reason': reason,
                'changed': True
            }
        
        return {
            'memory_id': memory_id,
            'tier': old_tier,
            'reason': reason,
            'changed': False
        }
    
    def update_all_tiers(self) -> List[Dict]:
        """Update tiers for all tracked memories."""
        tracker = get_tracker()
        changes = []
        
        # Get all memory IDs from reinforcement tracker
        for memory_id in tracker.data.keys():
            result = self.update_tier(memory_id)
            if result['changed']:
                changes.append(result)
        
        return changes
    
    def get_tier_report(self) -> Dict:
        """Get summary of memories by tier."""
        tiers = {'hot': [], 'warm': [], 'cold': []}
        tracker = get_tracker()
        
        for memory_id, state in self.data.items():
            reinforce = tracker.inspect(memory_id)
            tiers[state.tier].append({
                'id': memory_id,
                'salience': reinforce['current_salience'],
                'accesses': reinforce['access_count'],
                'locked': state.locked
            })
        
        # Sort each tier by salience
        for tier in tiers:
            tiers[tier] = sorted(tiers[tier], key=lambda x: -x['salience'])
        
        return {
            'hot': tiers['hot'],
            'warm': tiers['warm'],
            'cold': tiers['cold'],
            'counts': {
                'hot': len(tiers['hot']),
                'warm': len(tiers['warm']),
                'cold': len(tiers['cold']),
                'total': sum(len(t) for t in tiers.values())
            }
        }
    
    def archive_verbatim(self, memory_id: str) -> bool:
        """
        Archive verbatim data for a cold memory.
        Moves verbatim section to separate archive file.
        """
        state = self.get(memory_id)
        if state.tier != StorageTier.COLD.value:
            return False
        
        # Find the memory file
        for f in EXAMPLES_DIR.glob("*.yaml"):
            content = yaml.safe_load(f.read_text())
            if content and content.get('id') == memory_id:
                # Archive verbatim
                verbatim = content.get('verbatim', {})
                if verbatim:
                    archive_dir = PROJECT_ROOT / ".archive"
                    archive_dir.mkdir(exist_ok=True)
                    archive_path = archive_dir / f"{memory_id}_verbatim.yaml"
                    archive_path.write_text(yaml.dump(verbatim, default_flow_style=False))
                    
                    # Update memory file - keep only reconstructable hints
                    content['verbatim'] = {
                        '_archived': True,
                        '_archive_path': str(archive_path),
                        'reconstructable': verbatim.get('reconstructable', {})
                    }
                    f.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False))
                    
                    # Update state
                    state.verbatim_archived = True
                    state.archive_path = str(archive_path)
                    self._save()
                    return True
        
        return False
    
    def restore_verbatim(self, memory_id: str) -> bool:
        """Restore archived verbatim data when memory is promoted."""
        state = self.get(memory_id)
        if not state.verbatim_archived or not state.archive_path:
            return False
        
        archive_path = Path(state.archive_path)
        if not archive_path.exists():
            return False
        
        # Load archived verbatim
        archived = yaml.safe_load(archive_path.read_text())
        
        # Find and update memory file
        for f in EXAMPLES_DIR.glob("*.yaml"):
            content = yaml.safe_load(f.read_text())
            if content and content.get('id') == memory_id:
                content['verbatim'] = archived
                f.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False))
                
                # Update state
                state.verbatim_archived = False
                state.archive_path = None
                self._save()
                
                # Clean up archive
                archive_path.unlink()
                return True
        
        return False


# Global manager instance
_manager: Optional[StorageManager] = None


def get_manager() -> StorageManager:
    """Get the global storage manager instance."""
    global _manager
    if _manager is None:
        _manager = StorageManager()
    return _manager


# Convenience functions
def get_tier(memory_id: str) -> str:
    return get_manager().get(memory_id).tier

def set_tier(memory_id: str, tier: str):
    return get_manager().set_tier(memory_id, StorageTier(tier))

def lock_memory(memory_id: str, locked: bool = True):
    return get_manager().lock(memory_id, locked)

def update_tier(memory_id: str) -> Dict:
    return get_manager().update_tier(memory_id)

def update_all() -> List[Dict]:
    return get_manager().update_all_tiers()

def tier_report() -> Dict:
    return get_manager().get_tier_report()


def format_tier_emoji(tier: str) -> str:
    """Get emoji for tier."""
    return {'hot': '🔥', 'warm': '☀️', 'cold': '❄️'}.get(tier, '?')


if __name__ == '__main__':
    import sys
    
    manager = get_manager()
    
    if len(sys.argv) < 2:
        print("Usage: storage.py [report|update|tier <id>|lock <id>|unlock <id>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'report':
        report = manager.get_tier_report()
        counts = report['counts']
        
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║  STORAGE TIER REPORT                                          ║")
        print(f"║  Total: {counts['total']} memories                                          ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        
        for tier_name, emoji in [('hot', '🔥'), ('warm', '☀️'), ('cold', '❄️')]:
            memories = report[tier_name]
            print("║                                                              ║")
            print(f"║  {emoji} {tier_name.upper()} ({len(memories)})")
            if memories:
                for m in memories[:5]:
                    lock = "🔒" if m['locked'] else "  "
                    print(f"║  {lock} {m['id'][:40]:<40} sal:{m['salience']:.2f}")
                if len(memories) > 5:
                    print(f"║     ... and {len(memories) - 5} more")
            else:
                print("║     (none)")
        
        print("╚══════════════════════════════════════════════════════════════╝")
    
    elif cmd == 'update':
        changes = manager.update_all_tiers()
        if changes:
            print(f"Updated {len(changes)} memory tier(s):")
            for c in changes:
                old_emoji = format_tier_emoji(c['old_tier'])
                new_emoji = format_tier_emoji(c['new_tier'])
                print(f"  {c['memory_id']}: {old_emoji} {c['old_tier']} → {new_emoji} {c['new_tier']}")
                print(f"    Reason: {c['reason']}")
        else:
            print("No tier changes needed.")
    
    elif cmd == 'tier' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        state = manager.get(mem_id)
        tier, reason = manager.calculate_tier(mem_id)
        emoji = format_tier_emoji(state.tier)
        
        print(f"{emoji} {mem_id}")
        print(f"  Current tier: {state.tier}")
        print(f"  Calculated: {tier.value} ({reason})")
        print(f"  Locked: {state.locked}")
        print(f"  Verbatim archived: {state.verbatim_archived}")
    
    elif cmd == 'lock' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        manager.lock(mem_id, True)
        print(f"🔒 Locked {mem_id} (won't decay below warm)")
    
    elif cmd == 'unlock' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        manager.lock(mem_id, False)
        print(f"🔓 Unlocked {mem_id}")
    
    elif cmd == 'archive' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        if manager.archive_verbatim(mem_id):
            print(f"❄️ Archived verbatim for {mem_id}")
        else:
            print("Could not archive (not cold or no verbatim)")
    
    else:
        print("Unknown command")
        sys.exit(1)
