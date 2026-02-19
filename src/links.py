#!/usr/bin/env python3
"""
Bidirectional Memory Links
Typed relationships between memories, Zettelkasten-style.

Inspired by A-MEM's Zettelkasten linking approach.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Set
from dataclasses import dataclass, asdict, field
from enum import Enum

# Import existing modules
from reinforcement import get_tracker

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
LINKS_FILE = PROJECT_ROOT / ".links.json"


class LinkType(Enum):
    """Types of relationships between memories."""
    ELABORATES = "elaborates"    # Adds detail to target
    CONTRADICTS = "contradicts"  # Conflicts with target
    SUPERSEDES = "supersedes"    # Replaces target (newer info)
    RELATES_TO = "relates_to"    # General connection
    CAUSED_BY = "caused_by"      # Target caused this
    LEADS_TO = "leads_to"        # This leads to target
    
    def __str__(self):
        return self.value
    
    @property
    def inverse(self) -> 'LinkType':
        """Get the inverse relationship type."""
        inverses = {
            LinkType.ELABORATES: LinkType.RELATES_TO,  # X elaborates Y → Y relates_to X
            LinkType.CONTRADICTS: LinkType.CONTRADICTS,  # Symmetric
            LinkType.SUPERSEDES: LinkType.RELATES_TO,  # X supersedes Y → Y relates_to X (old)
            LinkType.RELATES_TO: LinkType.RELATES_TO,  # Symmetric
            LinkType.CAUSED_BY: LinkType.LEADS_TO,  # X caused_by Y → Y leads_to X
            LinkType.LEADS_TO: LinkType.CAUSED_BY,  # X leads_to Y → Y caused_by X
        }
        return inverses.get(self, LinkType.RELATES_TO)


@dataclass
class Link:
    """A single link between memories."""
    source_id: str
    target_id: str
    link_type: str
    note: str = ""
    created: str = ""
    
    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat()


@dataclass 
class MemoryLinks:
    """All links for a single memory."""
    memory_id: str
    outbound: List[Dict] = field(default_factory=list)  # Links from this memory
    inbound: List[Dict] = field(default_factory=list)   # Links to this memory


class LinkManager:
    """Manages links between memories."""
    
    def __init__(self, links_file: Path = LINKS_FILE):
        self.links_file = links_file
        self.data: Dict[str, MemoryLinks] = {}
        self._load()
    
    def _load(self):
        """Load link data from file."""
        if self.links_file.exists():
            try:
                raw = json.loads(self.links_file.read_text())
                for mem_id, entry in raw.items():
                    self.data[mem_id] = MemoryLinks(
                        memory_id=mem_id,
                        outbound=entry.get('outbound', []),
                        inbound=entry.get('inbound', [])
                    )
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load links data: {e}")
                self.data = {}
    
    def _save(self):
        """Save link data to file."""
        raw = {}
        for mem_id, entry in self.data.items():
            raw[mem_id] = {
                'memory_id': entry.memory_id,
                'outbound': entry.outbound,
                'inbound': entry.inbound
            }
        self.links_file.write_text(json.dumps(raw, indent=2))
    
    def get(self, memory_id: str) -> MemoryLinks:
        """Get links for a memory, creating if needed."""
        if memory_id not in self.data:
            self.data[memory_id] = MemoryLinks(memory_id=memory_id)
        return self.data[memory_id]
    
    def add_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType,
        note: str = "",
        bidirectional: bool = True
    ) -> Dict:
        """
        Add a link from source to target.
        
        If bidirectional=True, also adds inverse link from target to source.
        """
        # Validate link type
        if isinstance(link_type, str):
            link_type = LinkType(link_type)
        
        # Create link
        link = Link(
            source_id=source_id,
            target_id=target_id,
            link_type=link_type.value,
            note=note
        )
        
        # Add to source's outbound
        source_links = self.get(source_id)
        # Check for duplicate
        existing = [l for l in source_links.outbound 
                   if l['target_id'] == target_id and l['link_type'] == link_type.value]
        if not existing:
            source_links.outbound.append(asdict(link))
        
        # Add to target's inbound
        target_links = self.get(target_id)
        inbound_link = {
            'source_id': source_id,
            'link_type': link_type.value,
            'note': note,
            'created': link.created
        }
        existing = [l for l in target_links.inbound
                   if l['source_id'] == source_id and l['link_type'] == link_type.value]
        if not existing:
            target_links.inbound.append(inbound_link)
        
        # Update reinforcement tracking (for salience boost)
        get_tracker().add_link(source_id, target_id)
        
        # Add bidirectional link
        if bidirectional:
            inverse_type = link_type.inverse
            inverse_link = Link(
                source_id=target_id,
                target_id=source_id,
                link_type=inverse_type.value,
                note=f"[inverse] {note}" if note else "[inverse link]"
            )
            
            # Add to target's outbound (now source)
            existing = [l for l in target_links.outbound
                       if l['target_id'] == source_id and l['link_type'] == inverse_type.value]
            if not existing:
                target_links.outbound.append(asdict(inverse_link))
            
            # Add to source's inbound (now target)
            inbound_inverse = {
                'source_id': target_id,
                'link_type': inverse_type.value,
                'note': inverse_link.note,
                'created': inverse_link.created
            }
            existing = [l for l in source_links.inbound
                       if l['source_id'] == target_id and l['link_type'] == inverse_type.value]
            if not existing:
                source_links.inbound.append(inbound_inverse)
            
            get_tracker().add_link(target_id, source_id)
        
        self._save()
        
        return {
            'source': source_id,
            'target': target_id,
            'type': link_type.value,
            'bidirectional': bidirectional
        }
    
    def remove_link(self, source_id: str, target_id: str, link_type: str = None) -> bool:
        """Remove a link (and its inverse if bidirectional)."""
        source_links = self.get(source_id)
        target_links = self.get(target_id)
        
        removed = False
        
        # Remove from source outbound
        original_len = len(source_links.outbound)
        source_links.outbound = [
            l for l in source_links.outbound
            if not (l['target_id'] == target_id and 
                   (link_type is None or l['link_type'] == link_type))
        ]
        if len(source_links.outbound) < original_len:
            removed = True
        
        # Remove from target inbound
        target_links.inbound = [
            l for l in target_links.inbound
            if not (l['source_id'] == source_id and
                   (link_type is None or l['link_type'] == link_type))
        ]
        
        # Also remove inverse links
        target_links.outbound = [
            l for l in target_links.outbound
            if not (l['target_id'] == source_id)
        ]
        source_links.inbound = [
            l for l in source_links.inbound
            if not (l['source_id'] == target_id)
        ]
        
        if removed:
            self._save()
        
        return removed
    
    def get_related(self, memory_id: str, link_type: str = None) -> List[Dict]:
        """Get all memories related to this one."""
        links = self.get(memory_id)
        related = []
        
        for link in links.outbound:
            if link_type is None or link['link_type'] == link_type:
                related.append({
                    'id': link['target_id'],
                    'direction': 'outbound',
                    'type': link['link_type'],
                    'note': link.get('note', '')
                })
        
        for link in links.inbound:
            if link_type is None or link['link_type'] == link_type:
                related.append({
                    'id': link['source_id'],
                    'direction': 'inbound',
                    'type': link['link_type'],
                    'note': link.get('note', '')
                })
        
        return related
    
    def find_path(self, from_id: str, to_id: str, max_depth: int = 3) -> Optional[List[str]]:
        """Find shortest path between two memories via links."""
        if from_id == to_id:
            return [from_id]
        
        visited: Set[str] = set()
        queue: List[List[str]] = [[from_id]]
        
        while queue:
            path = queue.pop(0)
            current = path[-1]
            
            if len(path) > max_depth:
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            links = self.get(current)
            neighbors = set()
            
            for link in links.outbound:
                neighbors.add(link['target_id'])
            for link in links.inbound:
                neighbors.add(link['source_id'])
            
            for neighbor in neighbors:
                if neighbor == to_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    queue.append(path + [neighbor])
        
        return None  # No path found
    
    def get_link_graph(self) -> Dict:
        """Get summary of all links as a graph."""
        nodes = set()
        edges = []
        
        for mem_id, links in self.data.items():
            nodes.add(mem_id)
            for link in links.outbound:
                nodes.add(link['target_id'])
                edges.append({
                    'source': mem_id,
                    'target': link['target_id'],
                    'type': link['link_type']
                })
        
        return {
            'nodes': list(nodes),
            'edges': edges,
            'node_count': len(nodes),
            'edge_count': len(edges)
        }
    
    def suggest_links(self, memory_id: str) -> List[Dict]:
        """
        Suggest potential links based on shared frames/tags.
        Returns memories that might be related but aren't linked yet.
        """
        # This would ideally use the memory content, but for now
        # we'll use the reinforcement tracker's data
        suggestions = []
        current_links = self.get(memory_id)
        linked_ids = set()
        
        for link in current_links.outbound:
            linked_ids.add(link['target_id'])
        for link in current_links.inbound:
            linked_ids.add(link['source_id'])
        
        # Check all other memories
        for other_id in self.data.keys():
            if other_id != memory_id and other_id not in linked_ids:
                # Simple heuristic: if they share any links, they might be related
                other_links = self.get(other_id)
                shared = set()
                
                for link in other_links.outbound:
                    if link['target_id'] in linked_ids:
                        shared.add(link['target_id'])
                for link in other_links.inbound:
                    if link['source_id'] in linked_ids:
                        shared.add(link['source_id'])
                
                if shared:
                    suggestions.append({
                        'id': other_id,
                        'shared_connections': list(shared),
                        'reason': f"Shares {len(shared)} connection(s)"
                    })
        
        return suggestions


# Global manager instance
_manager: Optional[LinkManager] = None


def get_link_manager() -> LinkManager:
    """Get the global link manager instance."""
    global _manager
    if _manager is None:
        _manager = LinkManager()
    return _manager


# Convenience functions
def link(source: str, target: str, link_type: str, note: str = "") -> Dict:
    return get_link_manager().add_link(source, target, LinkType(link_type), note)

def unlink(source: str, target: str, link_type: str = None) -> bool:
    return get_link_manager().remove_link(source, target, link_type)

def related(memory_id: str, link_type: str = None) -> List[Dict]:
    return get_link_manager().get_related(memory_id, link_type)

def path(from_id: str, to_id: str) -> Optional[List[str]]:
    return get_link_manager().find_path(from_id, to_id)


def format_link_type(link_type: str) -> str:
    """Get formatted display for link type."""
    icons = {
        'elaborates': '📝',
        'contradicts': '⚔️',
        'supersedes': '🔄',
        'relates_to': '🔗',
        'caused_by': '⬅️',
        'leads_to': '➡️'
    }
    return f"{icons.get(link_type, '?')} {link_type}"


if __name__ == '__main__':
    import sys
    
    manager = get_link_manager()
    
    if len(sys.argv) < 2:
        print("Usage: links.py [graph|show <id>|link <src> <tgt> <type>|unlink <src> <tgt>|path <from> <to>|suggest <id>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'graph':
        graph = manager.get_link_graph()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║  MEMORY LINK GRAPH                                           ║")
        print(f"║  Nodes: {graph['node_count']}  |  Edges: {graph['edge_count']}                              ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        
        if graph['edges']:
            print("║  LINKS:")
            for edge in graph['edges'][:20]:
                icon = format_link_type(edge['type']).split()[0]
                src = edge['source'][:20]
                tgt = edge['target'][:20]
                print(f"║    {src} {icon} {tgt}")
            if len(graph['edges']) > 20:
                print(f"║    ... and {len(graph['edges']) - 20} more")
        else:
            print("║  (no links yet)")
        
        print("╚══════════════════════════════════════════════════════════════╝")
    
    elif cmd == 'show' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        links = manager.get(mem_id)
        
        print("╔══════════════════════════════════════════════════════════════╗")
        print(f"║  LINKS: {mem_id[:50]}")
        print("╠══════════════════════════════════════════════════════════════╣")
        
        if links.outbound:
            print("║  OUTBOUND:")
            for link in links.outbound:
                print(f"║    {format_link_type(link['link_type'])} → {link['target_id']}")
                if link.get('note'):
                    print(f"║      Note: {link['note'][:50]}")
        else:
            print("║  OUTBOUND: (none)")
        
        if links.inbound:
            print("║  INBOUND:")
            for link in links.inbound:
                print(f"║    {format_link_type(link['link_type'])} ← {link['source_id']}")
                if link.get('note'):
                    print(f"║      Note: {link['note'][:50]}")
        else:
            print("║  INBOUND: (none)")
        
        print("╚══════════════════════════════════════════════════════════════╝")
    
    elif cmd == 'link' and len(sys.argv) >= 5:
        src = sys.argv[2]
        tgt = sys.argv[3]
        link_type = sys.argv[4]
        note = ' '.join(sys.argv[5:]) if len(sys.argv) > 5 else ""
        
        try:
            result = manager.add_link(src, tgt, LinkType(link_type), note)
            print(f"✓ Linked: {src} --[{link_type}]--> {tgt}")
        except ValueError:
            print(f"Unknown link type: {link_type}")
            print(f"Valid types: {', '.join(t.value for t in LinkType)}")
            sys.exit(1)
    
    elif cmd == 'unlink' and len(sys.argv) >= 4:
        src = sys.argv[2]
        tgt = sys.argv[3]
        link_type = sys.argv[4] if len(sys.argv) > 4 else None
        
        if manager.remove_link(src, tgt, link_type):
            print(f"✓ Unlinked: {src} -- {tgt}")
        else:
            print("No link found")
    
    elif cmd == 'path' and len(sys.argv) >= 4:
        from_id = sys.argv[2]
        to_id = sys.argv[3]
        
        path = manager.find_path(from_id, to_id)
        if path:
            print(f"Path found ({len(path)} steps):")
            print(" → ".join(path))
        else:
            print("No path found")
    
    elif cmd == 'suggest' and len(sys.argv) > 2:
        mem_id = sys.argv[2]
        suggestions = manager.suggest_links(mem_id)
        
        if suggestions:
            print(f"Suggested links for {mem_id}:")
            for s in suggestions[:10]:
                print(f"  → {s['id']}: {s['reason']}")
        else:
            print("No suggestions (need more linked memories)")
    
    else:
        print("Unknown command or missing arguments")
        sys.exit(1)
