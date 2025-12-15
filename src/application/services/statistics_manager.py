"""
Statistics manager for build history and performance tracking.
"""

import json
import os
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import io

from src.domain.interfaces.base import ILogger
from src.domain.models.configuration import BuildConfiguration
from src.domain.exceptions import FileSystemError

# Optional matplotlib import
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class StatisticsManager:
    """Manages build statistics and history tracking."""
    
    def __init__(self, config: BuildConfiguration, logger: ILogger):
        self.config = config
        self.logger = logger
        self.history_file = Path(config.history_file)
        
        # Ensure history file directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
    
    def save_build_time(self, key: str, duration: float) -> None:
        """Record build time for statistics."""
        try:
            # Load existing history
            history = self._load_history()
            
            # Add new entry
            if key not in history:
                history[key] = []
            
            history[key].append(duration)
            
            # Keep only recent entries
            history[key] = history[key][-self.config.max_history_entries:]
            
            # Save updated history
            self._save_history(history)
            
            self.logger.info(f"Build time recorded: {key} = {duration:.1f}s")
            
        except Exception as e:
            self.logger.error(f"Failed to save build time: {e}")
            raise FileSystemError(f"Failed to save build time: {e}")
    
    def get_estimated_time(self, key: str) -> str:
        """Get estimated build time for a key."""
        try:
            history = self._load_history()
            
            if key not in history or not history[key]:
                return "❓"
            
            times = history[key]
            average_time = sum(times) / len(times)
            
            return self._format_duration(average_time)
            
        except Exception as e:
            self.logger.warning(f"Failed to get estimated time: {e}")
            return "❓"
    
    def get_build_statistics(self) -> Dict[str, any]:
        """Get comprehensive build statistics."""
        try:
            history = self._load_history()
            
            if not history:
                return {'message': '📊 暂无历史数据'}
            
            stats = {}
            
            for key, times in history.items():
                if not times:
                    continue
                
                stats[key] = {
                    'count': len(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'latest': times[-1],
                    'trend': self._calculate_trend(times)
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get build statistics: {e}")
            return {'error': str(e)}
    
    def generate_statistics_report(self) -> Union[str, Tuple[str, str]]:
        """Generate statistics report, with optional chart."""
        try:
            history = self._load_history()
            
            if not history:
                return "📊 暂无历史数据"
            
            if not HAS_MATPLOTLIB:
                # Text-only report
                return self._generate_text_report(history)
            else:
                # Generate chart and return both text and image path
                text_report = self._generate_text_report(history)
                chart_path = self._generate_chart(history)
                return text_report, chart_path
                
        except Exception as e:
            self.logger.error(f"Failed to generate statistics report: {e}")
            return f"❌ 统计报告生成失败: {e}"
    
    def clear_statistics(self, key: Optional[str] = None) -> Dict[str, any]:
        """Clear statistics for a specific key or all keys."""
        try:
            history = self._load_history()
            
            if key:
                if key in history:
                    del history[key]
                    self._save_history(history)
                    return {'status': 'success', 'message': f'已清除 {key} 的统计数据'}
                else:
                    return {'status': 'not_found', 'message': f'未找到 {key} 的统计数据'}
            else:
                # Clear all
                self._save_history({})
                return {'status': 'success', 'message': '已清除所有统计数据'}
                
        except Exception as e:
            self.logger.error(f"Failed to clear statistics: {e}")
            return {'status': 'error', 'message': f'清除失败: {e}'}
    
    def _load_history(self) -> Dict[str, List[float]]:
        """Load build history from file."""
        if not self.history_file.exists():
            return {}
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to load history file: {e}")
            return {}
    
    def _save_history(self, history: Dict[str, List[float]]) -> None:
        """Save build history to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4)
        except IOError as e:
            self.logger.error(f"Failed to save history file: {e}")
            raise FileSystemError(f"Failed to save history: {e}")
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        else:
            return f"{minutes}m {secs}s"
    
    def _calculate_trend(self, times: List[float]) -> str:
        """Calculate trend for build times."""
        if len(times) < 2:
            return "stable"
        
        # Compare recent half with older half
        mid_point = len(times) // 2
        older_avg = sum(times[:mid_point]) / mid_point
        recent_avg = sum(times[mid_point:]) / (len(times) - mid_point)
        
        change_percent = ((recent_avg - older_avg) / older_avg) * 100
        
        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        else:
            return "stable"
    
    def _generate_text_report(self, history: Dict[str, List[float]]) -> str:
        """Generate text-based statistics report."""
        report_lines = ["📊 **打包耗时统计**\n"]
        
        for key, times in history.items():
            if not times:
                continue
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            trend = self._calculate_trend(times)
            
            trend_emoji = {
                'increasing': '📈',
                'decreasing': '📉',
                'stable': '➡️'
            }.get(trend, '➡️')
            
            report_lines.append(
                f"- **{key}**: 平均 {self._format_duration(avg_time)} "
                f"(最快 {self._format_duration(min_time)}, "
                f"最慢 {self._format_duration(max_time)}) "
                f"{trend_emoji} 最近{len(times)}次"
            )
        
        return "\n".join(report_lines)
    
    def _generate_chart(self, history: Dict[str, List[float]]) -> str:
        """Generate statistics chart and return image path."""
        try:
            plt.figure(figsize=(12, 8))
            
            # Plot trends for each build type
            for key, times in history.items():
                if len(times) > 1:  # Need at least 2 points for a line
                    plt.plot(range(len(times)), times, marker='o', label=key, linewidth=2)
            
            plt.title("Build Time Trends", fontsize=16, fontweight='bold')
            plt.xlabel("Build Number (Recent Builds)", fontsize=12)
            plt.ylabel("Duration (seconds)", fontsize=12)
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save chart
            chart_path = self.history_file.parent / "build_stats_chart.png"
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Statistics chart generated: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            self.logger.error(f"Failed to generate chart: {e}")
            raise FileSystemError(f"Failed to generate chart: {e}")
    
    def export_statistics(self, export_path: str) -> Dict[str, any]:
        """Export statistics to external file."""
        try:
            history = self._load_history()
            stats = self.get_build_statistics()
            
            export_data = {
                'export_timestamp': str(Path().cwd()),
                'raw_history': history,
                'statistics': stats,
                'summary': {
                    'total_builds': sum(len(times) for times in history.values()),
                    'build_types': len(history),
                    'average_duration': sum(
                        sum(times) / len(times) for times in history.values() if times
                    ) / len([times for times in history.values() if times]) if history else 0
                }
            }
            
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            
            return {
                'status': 'success',
                'message': f'统计数据已导出到: {export_file}',
                'file_path': str(export_file)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to export statistics: {e}")
            return {'status': 'error', 'message': f'导出失败: {e}'}