#!/usr/bin/env python3
"""
Unified Statistics Manager for Email Reports
This module handles statistics collection and email reporting for both pipelines.
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

class StatisticsManager:
    """Manages statistics collection and reporting for both pipelines."""
    
    def __init__(self):
        self.stats_dir = Path('/app/shared/stats')
        self.stats_dir.mkdir(exist_ok=True)
        
        # Statistics file paths
        self.viajeros_stats_file = self.stats_dir / 'viajeros_latest_stats.json'
        self.si_stats_file = self.stats_dir / 'si_latest_stats.json'
        self.combined_stats_file = self.stats_dir / 'combined_latest_stats.json'
        
    def save_pipeline_stats(self, pipeline_type: str, stats: Dict) -> bool:
        """Save statistics for a specific pipeline run."""
        try:
            # Add metadata
            stats_with_meta = {
                'pipeline_type': pipeline_type,
                'run_timestamp': datetime.now().isoformat(),
                'run_date': datetime.now().strftime('%Y-%m-%d'),
                'run_time': datetime.now().strftime('%H:%M:%S'),
                **stats
            }
            
            # Save to pipeline-specific file
            if pipeline_type == 'viajeros':
                stats_file = self.viajeros_stats_file
            elif pipeline_type == 'si':
                stats_file = self.si_stats_file
            else:
                logger.error(f"Unknown pipeline type: {pipeline_type}")
                return False
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_with_meta, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📊 Saved {pipeline_type} statistics: {stats.get('successful', 0)} successful, {stats.get('failed', 0)} failed")
            
            # Update combined stats
            self._update_combined_stats()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving {pipeline_type} statistics: {e}")
            return False
    
    def _update_combined_stats(self):
        """Update combined statistics from both pipelines."""
        try:
            combined_stats = {
                'run_timestamp': datetime.now().isoformat(),
                'run_date': datetime.now().strftime('%Y-%m-%d'),
                'run_time': datetime.now().strftime('%H:%M:%S'),
                'pipelines': {}
            }
            
            # Load Viajeros stats
            if self.viajeros_stats_file.exists():
                with open(self.viajeros_stats_file, 'r', encoding='utf-8') as f:
                    viajeros_data = json.load(f)
                combined_stats['pipelines']['viajeros'] = viajeros_data
            
            # Load SI stats
            if self.si_stats_file.exists():
                with open(self.si_stats_file, 'r', encoding='utf-8') as f:
                    si_data = json.load(f)
                combined_stats['pipelines']['si'] = si_data
            
            # Calculate totals
            total_successful = 0
            total_failed = 0
            total_processed = 0
            
            for pipeline_data in combined_stats['pipelines'].values():
                total_successful += pipeline_data.get('successful', 0)
                total_failed += pipeline_data.get('failed', 0)
                total_processed += pipeline_data.get('total_processed', 0)
            
            combined_stats['totals'] = {
                'successful': total_successful,
                'failed': total_failed,
                'total_processed': total_processed,
                'success_rate': (total_successful / total_processed * 100) if total_processed > 0 else 0.0
            }
            
            # Save combined stats
            with open(self.combined_stats_file, 'w', encoding='utf-8') as f:
                json.dump(combined_stats, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📊 Updated combined statistics: {total_successful} successful, {total_failed} failed")
            
        except Exception as e:
            logger.error(f"❌ Error updating combined statistics: {e}")
    
    def get_pipeline_stats(self, pipeline_type: str) -> Optional[Dict]:
        """Get latest statistics for a specific pipeline."""
        try:
            if pipeline_type == 'viajeros':
                stats_file = self.viajeros_stats_file
            elif pipeline_type == 'si':
                stats_file = self.si_stats_file
            else:
                logger.error(f"Unknown pipeline type: {pipeline_type}")
                return None
            
            if not stats_file.exists():
                logger.warning(f"No statistics file found for {pipeline_type}")
                return None
            
            with open(stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"❌ Error reading {pipeline_type} statistics: {e}")
            return None
    
    def get_combined_stats(self) -> Optional[Dict]:
        """Get combined statistics for both pipelines."""
        try:
            if not self.combined_stats_file.exists():
                logger.warning("No combined statistics file found")
                return None
            
            with open(self.combined_stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"❌ Error reading combined statistics: {e}")
            return None
    
    def clear_stats(self, pipeline_type: str = None):
        """Clear statistics files."""
        try:
            if pipeline_type is None:
                # Clear all stats
                for stats_file in [self.viajeros_stats_file, self.si_stats_file, self.combined_stats_file]:
                    if stats_file.exists():
                        stats_file.unlink()
                logger.info("📊 Cleared all statistics files")
            else:
                # Clear specific pipeline stats
                if pipeline_type == 'viajeros':
                    stats_file = self.viajeros_stats_file
                elif pipeline_type == 'si':
                    stats_file = self.si_stats_file
                else:
                    logger.error(f"Unknown pipeline type: {pipeline_type}")
                    return
                
                if stats_file.exists():
                    stats_file.unlink()
                logger.info(f"📊 Cleared {pipeline_type} statistics")
                
                # Update combined stats
                self._update_combined_stats()
                
        except Exception as e:
            logger.error(f"❌ Error clearing statistics: {e}")

# Global instance
stats_manager = StatisticsManager()

def save_pipeline_execution_stats(pipeline_type: str, execution_results: Dict) -> bool:
    """Save execution statistics for a pipeline run."""
    return stats_manager.save_pipeline_stats(pipeline_type, execution_results)

def get_pipeline_execution_stats(pipeline_type: str) -> Optional[Dict]:
    """Get latest execution statistics for a pipeline."""
    return stats_manager.get_pipeline_stats(pipeline_type)

def get_combined_execution_stats() -> Optional[Dict]:
    """Get combined execution statistics."""
    return stats_manager.get_combined_stats()

def clear_execution_stats(pipeline_type: str = None):
    """Clear execution statistics."""
    stats_manager.clear_stats(pipeline_type)
