#!/usr/bin/env python3
"""
Multi-Perspective Frames for Gist Memory
Same memory viewed through different frames yields different gists.

Inspired by HawkinsDB's Thousand Brains Theory / cortical columns.

Example: A debugging session memory viewed through:
- code_craft frame: "A* heuristic was wrong"  
- collaborative_exploration frame: "Good session, gblfxt spotted the bug"
- game_development frame: "LLMoblings pathfinding needs more work"
"""

import json
import yaml
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict, field

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
PERSPECTIVES_FILE = PROJECT_ROOT / ".perspectives.json"

# Import frames for validation
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@dataclass
class Perspective:
    """A single perspective on a memory."""
    frame: str           # Which frame this perspective is from
    gist: str            # The gist from this frame's viewpoint
    salience: float      # How relevant this memory is to this frame (0-1)
    keywords: List[str] = field(default_factory=list)  # Frame-specific keywords
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MemoryPerspectives:
    """All perspectives for a single memory."""
    memory_id: str
    perspectives: Dict[str, Dict] = field(default_factory=dict)  # frame -> Perspective
    primary_frame: str = ""  # The dominant perspective
    generated_at: str = ""
    
    def add(self, perspective: Perspective):
        self.perspectives[perspective.frame] = perspective.to_dict()
        # Update primary if this has higher salience
        if not self.primary_frame or perspective.salience > self.perspectives.get(self.primary_frame, {}).get('salience', 0):
            self.primary_frame = perspective.frame
    
    def get(self, frame: str) -> Optional[Dict]:
        return self.perspectives.get(frame)
    
    def get_top(self, n: int = 3) -> List[Dict]:
        """Get top N perspectives by salience."""
        sorted_persp = sorted(
            self.perspectives.values(),
            key=lambda p: p.get('salience', 0),
            reverse=True
        )
        return sorted_persp[:n]


class PerspectiveManager:
    """Manages perspectives for all memories."""
    
    def __init__(self, perspectives_file: Path = PERSPECTIVES_FILE):
        self.perspectives_file = perspectives_file
        self.data: Dict[str, MemoryPerspectives] = {}
        self._load()
    
    def _load(self):
        """Load perspectives from file."""
        if self.perspectives_file.exists():
            try:
                raw = json.loads(self.perspectives_file.read_text())
                for mem_id, entry in raw.items():
                    self.data[mem_id] = MemoryPerspectives(
                        memory_id=mem_id,
                        perspectives=entry.get('perspectives', {}),
                        primary_frame=entry.get('primary_frame', ''),
                        generated_at=entry.get('generated_at', '')
                    )
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load perspectives: {e}")
                self.data = {}
    
    def _save(self):
        """Save perspectives to file."""
        raw = {}
        for mem_id, entry in self.data.items():
            raw[mem_id] = {
                'memory_id': entry.memory_id,
                'perspectives': entry.perspectives,
                'primary_frame': entry.primary_frame,
                'generated_at': entry.generated_at
            }
        self.perspectives_file.write_text(json.dumps(raw, indent=2))
    
    def get(self, memory_id: str) -> MemoryPerspectives:
        """Get perspectives for a memory."""
        if memory_id not in self.data:
            self.data[memory_id] = MemoryPerspectives(memory_id=memory_id)
        return self.data[memory_id]
    
    def add_perspective(
        self,
        memory_id: str,
        frame: str,
        gist: str,
        salience: float,
        keywords: List[str] = None
    ) -> Dict:
        """Add a perspective to a memory."""
        persp = Perspective(
            frame=frame,
            gist=gist,
            salience=salience,
            keywords=keywords or []
        )
        
        mem_persp = self.get(memory_id)
        mem_persp.add(persp)
        mem_persp.generated_at = datetime.now().isoformat()
        self._save()
        
        return persp.to_dict()
    
    def get_for_context(self, memory_id: str, context_frames: List[str]) -> Optional[Dict]:
        """
        Get the most relevant perspective for a given context.
        
        Args:
            memory_id: The memory to get perspective for
            context_frames: Frames active in the current context
        
        Returns:
            The perspective dict that best matches context, or None
        """
        mem_persp = self.get(memory_id)
        
        if not mem_persp.perspectives:
            return None
        
        # Score each perspective by context match
        best_score = -1
        best_persp = None
        
        for frame, persp in mem_persp.perspectives.items():
            score = persp.get('salience', 0)
            # Boost if frame matches context
            if frame in context_frames:
                score += 0.3
            
            if score > best_score:
                best_score = score
                best_persp = persp
        
        return best_persp
    
    def generate_perspectives(
        self,
        memory_id: str,
        memory_content: Dict,
        model: str = "llama3:8b"
    ) -> List[Dict]:
        """
        Generate perspectives for a memory using LLM.
        
        Args:
            memory_id: ID of the memory
            memory_content: Full memory dict (from YAML)
            model: Ollama model to use
        
        Returns:
            List of generated perspectives
        """
        import subprocess
        import json
        
        # Get the memory's frames
        frames = memory_content.get('gist', {}).get('frames', [])
        summary = memory_content.get('summary', '')
        verbatim = memory_content.get('verbatim', {}).get('stored', {})
        
        if not frames:
            return []
        
        # Build context for LLM
        verbatim_str = "\n".join(f"- {k}: {v}" for k, v in list(verbatim.items())[:10])
        
        prompt = f"""Analyze this memory from multiple perspectives.

MEMORY SUMMARY:
{summary}

KEY DETAILS:
{verbatim_str}

ACTIVE FRAMES: {', '.join(frames[:5])}

For each of the top 3 most relevant frames, provide:
1. A 1-2 sentence gist from that frame's viewpoint
2. A salience score (0.0-1.0) for how relevant this memory is to that frame
3. 2-3 keywords specific to that perspective

Output as JSON array:
[
  {{"frame": "frame_name", "gist": "...", "salience": 0.X, "keywords": ["...", "..."]}},
  ...
]

Only output the JSON array, no other text."""

        try:
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout.strip()
            
            # Try to parse JSON from output
            # Find JSON array in output
            start = output.find('[')
            end = output.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = output[start:end]
                perspectives = json.loads(json_str)
                
                # Add each perspective
                for p in perspectives:
                    if all(k in p for k in ['frame', 'gist', 'salience']):
                        self.add_perspective(
                            memory_id,
                            p['frame'],
                            p['gist'],
                            float(p['salience']),
                            p.get('keywords', [])
                        )
                
                return perspectives
            
        except Exception as e:
            print(f"Error generating perspectives: {e}", file=sys.stderr)
        
        return []
    
    def batch_generate(self, model: str = "llama3:8b", force: bool = False) -> int:
        """Generate perspectives for all memories that don't have them."""
        count = 0
        
        for yaml_file in EXAMPLES_DIR.glob("*.yaml"):
            try:
                content = yaml.safe_load(yaml_file.read_text())
                mem_id = content.get('id')
                
                if not mem_id:
                    continue
                
                # Skip if already has perspectives (unless force)
                existing = self.get(mem_id)
                if existing.perspectives and not force:
                    continue
                
                print(f"Generating perspectives for {mem_id}...", file=sys.stderr)
                result = self.generate_perspectives(mem_id, content, model)
                
                if result:
                    count += 1
                    print(f"  ✓ {len(result)} perspectives", file=sys.stderr)
                
            except Exception as e:
                print(f"  Error: {e}", file=sys.stderr)
        
        return count


# Global manager instance
_manager: Optional[PerspectiveManager] = None


def get_manager() -> PerspectiveManager:
    """Get the global perspective manager."""
    global _manager
    if _manager is None:
        _manager = PerspectiveManager()
    return _manager


# Convenience functions
def add_perspective(memory_id: str, frame: str, gist: str, salience: float, keywords: List[str] = None):
    return get_manager().add_perspective(memory_id, frame, gist, salience, keywords)

def get_perspectives(memory_id: str) -> MemoryPerspectives:
    return get_manager().get(memory_id)

def get_for_context(memory_id: str, context_frames: List[str]) -> Optional[Dict]:
    return get_manager().get_for_context(memory_id, context_frames)

def generate(memory_id: str, content: Dict, model: str = "llama3:8b"):
    return get_manager().generate_perspectives(memory_id, content, model)


def format_perspective(persp: Dict) -> str:
    """Format a perspective for display."""
    frame = persp.get('frame', '?')
    gist = persp.get('gist', '')
    salience = persp.get('salience', 0)
    keywords = persp.get('keywords', [])
    
    kw_str = f" [{', '.join(keywords[:3])}]" if keywords else ""
    return f"[{frame}] ({salience:.2f}){kw_str}\n  {gist}"


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Perspective Memory Frames')
    parser.add_argument('command', choices=['show', 'add', 'generate', 'batch', 'context'],
                       help='Command to run')
    parser.add_argument('memory_id', nargs='?', help='Memory ID')
    parser.add_argument('--frame', '-f', help='Frame name')
    parser.add_argument('--gist', '-g', help='Gist text')
    parser.add_argument('--salience', '-s', type=float, default=0.5, help='Salience score')
    parser.add_argument('--keywords', '-k', nargs='*', help='Keywords')
    parser.add_argument('--model', '-m', default='llama3:8b', help='Ollama model')
    parser.add_argument('--context', '-c', nargs='*', help='Context frames')
    parser.add_argument('--force', action='store_true', help='Force regenerate')
    
    args = parser.parse_args()
    manager = get_manager()
    
    if args.command == 'show':
        if not args.memory_id:
            # Show all memories with perspectives
            print("╔══════════════════════════════════════════════════════════════╗")
            print("║  MEMORY PERSPECTIVES                                         ║")
            print("╠══════════════════════════════════════════════════════════════╣")
            
            for mem_id, persp in manager.data.items():
                if persp.perspectives:
                    print(f"║  {mem_id}")
                    print(f"║    Primary: {persp.primary_frame}")
                    print(f"║    Perspectives: {len(persp.perspectives)}")
                    for frame, p in list(persp.perspectives.items())[:3]:
                        print(f"║      • [{frame}] {p.get('salience', 0):.2f}")
            
            if not manager.data:
                print("║  (no perspectives yet)")
            
            print("╚══════════════════════════════════════════════════════════════╝")
        else:
            # Show specific memory
            persp = manager.get(args.memory_id)
            
            print("╔══════════════════════════════════════════════════════════════╗")
            print(f"║  PERSPECTIVES: {args.memory_id[:45]}")
            print("╠══════════════════════════════════════════════════════════════╣")
            
            if persp.perspectives:
                print(f"║  Primary frame: {persp.primary_frame}")
                print("║")
                
                for frame, p in persp.perspectives.items():
                    gist = p.get('gist', '')[:50]
                    sal = p.get('salience', 0)
                    kw = p.get('keywords', [])
                    
                    primary = " ★" if frame == persp.primary_frame else ""
                    print(f"║  [{frame}] {sal:.2f}{primary}")
                    print(f"║    {gist}...")
                    if kw:
                        print(f"║    Keywords: {', '.join(kw[:5])}")
                    print("║")
            else:
                print("║  (no perspectives yet)")
                print("║  Run: gist perspectives generate <id>")
            
            print("╚══════════════════════════════════════════════════════════════╝")
    
    elif args.command == 'add':
        if not all([args.memory_id, args.frame, args.gist]):
            print("Error: Need --memory_id, --frame, and --gist")
            sys.exit(1)
        
        result = manager.add_perspective(
            args.memory_id,
            args.frame,
            args.gist,
            args.salience,
            args.keywords or []
        )
        print(f"✓ Added perspective [{args.frame}] to {args.memory_id}")
    
    elif args.command == 'generate':
        if not args.memory_id:
            print("Error: Need memory_id")
            sys.exit(1)
        
        # Load memory content
        for yaml_file in EXAMPLES_DIR.glob("*.yaml"):
            content = yaml.safe_load(yaml_file.read_text())
            if content.get('id') == args.memory_id:
                print(f"Generating perspectives for {args.memory_id}...")
                result = manager.generate_perspectives(args.memory_id, content, args.model)
                if result:
                    print(f"✓ Generated {len(result)} perspectives:")
                    for p in result:
                        print(f"  [{p['frame']}] {p['salience']:.2f}: {p['gist'][:50]}...")
                else:
                    print("No perspectives generated")
                break
        else:
            print(f"Memory {args.memory_id} not found")
    
    elif args.command == 'batch':
        print("Batch generating perspectives...")
        count = manager.batch_generate(model=args.model, force=args.force)
        print(f"✓ Generated perspectives for {count} memories")
    
    elif args.command == 'context':
        if not args.memory_id or not args.context:
            print("Error: Need memory_id and --context frames")
            sys.exit(1)
        
        result = manager.get_for_context(args.memory_id, args.context)
        if result:
            print(f"Best perspective for context {args.context}:")
            print(format_perspective(result))
        else:
            print("No matching perspective found")
