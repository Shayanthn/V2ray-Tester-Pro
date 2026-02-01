"""
Source Rotator - Rotating source management for continuous testing
Ensures all sources are tested in rotation, not repeatedly from start
"""
import os
import json
from typing import List, Dict, Optional
from datetime import datetime
import logging


class SourceRotator:
    """Manages rotating through sources to ensure even coverage."""
    
    def __init__(self, all_sources: List[str], batch_size: int = 10, logger: Optional[logging.Logger] = None):
        """
        Initialize source rotator.
        
        Args:
            all_sources: Complete list of all available sources
            batch_size: How many sources to test per run
            logger: Logger instance
        """
        self.all_sources = all_sources
        self.batch_size = batch_size
        self.logger = logger or logging.getLogger(__name__)
        self.state_file = "source_rotation_state.json"
        self.load_state()
    
    def load_state(self):
        """Load rotation state from file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                self.logger.info(f"Loaded rotation state: position {self.state.get('current_position', 0)}")
            except Exception as e:
                self.logger.error(f"Failed to load rotation state: {e}")
                self.state = self._empty_state()
        else:
            self.state = self._empty_state()
    
    def save_state(self):
        """Save rotation state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            self.logger.info(f"Saved rotation state: position {self.state['current_position']}")
        except Exception as e:
            self.logger.error(f"Failed to save rotation state: {e}")
    
    def _empty_state(self) -> Dict:
        """Create empty state."""
        return {
            'current_position': 0,
            'total_sources': len(self.all_sources),
            'batch_size': self.batch_size,
            'rotation_count': 0,
            'last_rotation_time': None,
            'sources_tested_this_rotation': 0
        }
    
    def get_next_batch(self) -> List[str]:
        """
        Get next batch of sources to test.
        
        Returns:
            List of source URLs for this run
        """
        total = len(self.all_sources)
        current_pos = self.state['current_position']
        
        # Calculate end position
        end_pos = min(current_pos + self.batch_size, total)
        
        # Get batch
        batch = self.all_sources[current_pos:end_pos]
        
        # Update position
        new_position = end_pos
        sources_tested = end_pos - current_pos
        
        # Check if we've completed a full rotation
        if new_position >= total:
            self.logger.info(f"✅ Completed full rotation #{self.state['rotation_count'] + 1}")
            new_position = 0  # Reset to start
            self.state['rotation_count'] += 1
            self.state['last_rotation_time'] = datetime.now().isoformat()
            self.state['sources_tested_this_rotation'] = 0
        
        # Update state
        self.state['current_position'] = new_position
        self.state['sources_tested_this_rotation'] += sources_tested
        self.state['total_sources'] = total
        self.state['batch_size'] = self.batch_size
        
        self.save_state()
        
        # Log progress
        progress = (self.state['sources_tested_this_rotation'] / total) * 100 if total > 0 else 0
        self.logger.info(
            f"📍 Rotation progress: {self.state['sources_tested_this_rotation']}/{total} "
            f"({progress:.1f}%) | Batch: {len(batch)} sources | "
            f"Next position: {new_position}/{total}"
        )
        
        return batch
    
    def get_stats(self) -> Dict:
        """Get rotation statistics."""
        total = len(self.all_sources)
        current_pos = self.state['current_position']
        tested = self.state['sources_tested_this_rotation']
        
        return {
            'total_sources': total,
            'current_position': current_pos,
            'sources_tested_this_rotation': tested,
            'sources_remaining_this_rotation': total - tested,
            'rotation_count': self.state['rotation_count'],
            'progress_percentage': (tested / total * 100) if total > 0 else 0,
            'batch_size': self.batch_size,
            'last_rotation_completed': self.state.get('last_rotation_time')
        }
    
    def reset(self):
        """Reset rotation to beginning."""
        self.state = self._empty_state()
        self.save_state()
        self.logger.info("🔄 Rotation reset to beginning")
