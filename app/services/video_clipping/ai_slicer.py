"""
AI智能切片算法
使用Gemini 2.5-pro识别语义完整的段落，生成最佳切片方案
"""

from typing import List, Dict, Optional
import json
import re
import logging
import math
from .srt_parser import SRTParser
from ..gemini_client import GeminiClient
from .prompt_config import PromptConfig

logger = logging.getLogger(__name__)

class AISlicer:
    """AI智能切片器"""
    
    def __init__(self, gemini_client: GeminiClient):
        """
        初始化AI切片器
        
        Args:
            gemini_client: Gemini客户端实例
        """
        self.client = gemini_client
    
    def analyze_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        分析文本段落，使用AI优化切片方案
        
        Args:
            segments: SRT解析器生成的初始段落列表
            
        Returns:
            优化后的切片方案
        """
        optimized_segments = []
        
        for segment in segments:
            # 对每个段落进行AI分析
            analysis = self._analyze_single_segment(segment)
            
            # 合并分析结果
            enhanced_segment = {
                **segment,
                'ai_analysis': analysis,
                'quality_score': analysis.get('quality_score', 0.5),
                'topic': analysis.get('topic', ''),
                'key_points': analysis.get('key_points', []),
                'emotional_tone': analysis.get('emotional_tone', 'neutral'),
                'suggested_title': analysis.get('suggested_title', ''),
                'tags': analysis.get('tags', [])
            }
            
            optimized_segments.append(enhanced_segment)
        
        # 根据AI分析结果进一步优化切片
        return self._optimize_segments(optimized_segments)
    
    def _analyze_single_segment(self, segment: Dict, total_duration: float = None) -> Dict:
        """
        使用AI分析单个文本段落
        
        Args:
            segment: 文本段落数据
            total_duration: 视频总时长，用于计算位置
            
        Returns:
            AI分析结果
        """
        # 计算在视频中的位置（分钟）
        position_minutes = segment['start_time'] / 60.0
        
        # 使用配置文件中的提示词
        prompt = PromptConfig.CONTENT_ANALYSIS_PROMPT.format(
            text_content=segment['full_text'],
            duration=segment['duration'],
            position_minutes=position_minutes
        )
        
        try:
            full_prompt = f"{PromptConfig.SYSTEM_ROLE_PROMPT}\n\n{prompt}"
            
            response_text = self.client.generate_content(full_prompt)
            
            # 尝试提取JSON内容
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    analysis = json.loads(json_match.group())
                    # 添加计算出的综合评分
                    analysis['composite_score'] = self._calculate_composite_score(analysis)
                    return analysis
                except json.JSONDecodeError:
                    logger.warning(f"JSON解析失败，使用默认响应: {json_match.group()}")
                    return self._get_default_analysis(segment)
            else:
                try:
                    analysis = json.loads(response_text)
                    analysis['composite_score'] = self._calculate_composite_score(analysis)
                    return analysis
                except json.JSONDecodeError:
                    logger.warning(f"响应不是有效JSON，使用默认响应: {response_text}")
                    return self._get_default_analysis(segment)
                
        except Exception as e:
            logger.error(f"AI分析失败: {str(e)}")
            return self._get_default_analysis(segment)
    
    def _calculate_composite_score(self, analysis: Dict) -> float:
        """计算综合评分"""
        weights = PromptConfig.SelectionStrategy.WEIGHTS
        score = 0.0
        
        for metric, weight in weights.items():
            value = analysis.get(metric, 0.5)
            score += value * weight
        
        return min(1.0, max(0.0, score))
    
    def _get_default_analysis(self, segment: Dict) -> Dict:
        """获取默认分析结果"""
        return {
            'quality_score': 0.5,
            'topic': '未知主题',
            'key_points': ['内容待分析'],
            'emotional_tone': 'neutral',
            'suggested_title': segment['full_text'][:20] + '...',
            'tags': ['视频片段'],
            'completeness': 0.5,
            'engagement': 0.5,
            'independence': 0.5,
            'hook_potential': 0.5,
            'conclusion_strength': 0.5,
            'reason': 'AI分析失败，使用默认评分',
            'composite_score': 0.5
        }
    
    def _optimize_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        根据AI分析结果优化切片方案
        
        Args:
            segments: 包含AI分析结果的段落列表
            
        Returns:
            优化后的段落列表
        """
        optimized = []
        
        for segment in segments:
            # 根据质量评分和完整性决定是否保留
            quality = segment.get('ai_analysis', {}).get('quality_score', 0.5)
            completeness = segment.get('ai_analysis', {}).get('completeness', 0.5)
            
            # 设置保留阈值
            if quality >= 0.3 and completeness >= 0.3:
                # 调整时长限制
                if segment['duration'] < 10:
                    # 短片段：尝试与下一个片段合并
                    segment['merge_suggestion'] = True
                elif segment['duration'] > 90:
                    # 长片段：建议分割
                    segment['split_suggestion'] = True
                
                optimized.append(segment)
        
        return optimized
    
    def generate_clip_plan(self, srt_file_path: str, 
                          min_duration: float = 10.0, 
                          max_duration: float = 60.0,
                          target_count: int = 5) -> List[Dict]:
        """
        生成完整的切片计划
        
        Args:
            srt_file_path: SRT文件路径
            min_duration: 最小时长（秒）
            max_duration: 最大时长（秒）
            target_count: 目标切片数量
            
        Returns:
            切片计划列表
        """
        # 解析SRT文件
        parser = SRTParser()
        parser.parse_file(srt_file_path)
        
        # 获取基础段落
        segments = parser.get_text_segments(min_duration, max_duration)
        
        if not segments:
            logger.warning("未找到符合条件的文本段落")
            return []
        
        # 获取视频总时长
        total_duration = max(s['end_time'] for s in segments) if segments else 0
        
        # AI分析优化（传入总时长用于位置计算）
        optimized_segments = self.analyze_segments(segments, total_duration)
        
        # 过滤低质量片段
        filtered_segments = self._filter_segments(optimized_segments)
        
        # 根据配置选择最终片段
        if PromptConfig.SelectionStrategy.ENABLE_TIME_DISTRIBUTION:
            selected_segments = self._select_with_time_distribution(filtered_segments, target_count, total_duration)
        else:
            selected_segments = self._select_by_score(filtered_segments, target_count)
        
        # 按时间顺序重新排序
        final_plan = sorted(selected_segments, key=lambda x: x['start_time'])
        
        if PromptConfig.Debug.LOG_SELECTION_PROCESS:
            self._log_selection_results(final_plan, len(segments), len(filtered_segments))
        
        return final_plan
    
    def _filter_segments(self, segments: List[Dict]) -> List[Dict]:
        """根据配置过滤低质量片段"""
        config = PromptConfig.SelectionStrategy
        filtered = []
        
        for segment in segments:
            analysis = segment.get('ai_analysis', {})
            
            # 检查各项指标是否达标
            if (analysis.get('quality_score', 0) >= config.MIN_QUALITY_SCORE and
                analysis.get('completeness', 0) >= config.MIN_COMPLETENESS and
                analysis.get('independence', 0) >= config.MIN_INDEPENDENCE and
                analysis.get('engagement', 0) >= config.MIN_ENGAGEMENT):
                filtered.append(segment)
        
        logger.info(f"过滤后保留 {len(filtered)}/{len(segments)} 个高质量片段")
        return filtered
    
    def _select_with_time_distribution(self, segments: List[Dict], target_count: int, total_duration: float) -> List[Dict]:
        """使用时间分布策略选择片段"""
        config = PromptConfig.SelectionStrategy
        
        # 将视频按时间分段
        segment_duration = total_duration / config.TIME_SEGMENTS
        time_buckets = [[] for _ in range(config.TIME_SEGMENTS)]
        
        # 将片段分配到时间段
        for segment in segments:
            bucket_index = min(int(segment['start_time'] / segment_duration), config.TIME_SEGMENTS - 1)
            time_buckets[bucket_index].append(segment)
        
        # 从每个时间段选择最佳片段
        selected = []
        clips_per_segment = max(1, target_count // config.TIME_SEGMENTS)
        
        for bucket in time_buckets:
            if not bucket:
                continue
            
            # 按综合评分排序
            bucket_sorted = sorted(bucket, 
                                 key=lambda x: x.get('ai_analysis', {}).get('composite_score', 0), 
                                 reverse=True)
            
            # 选择该时间段的最佳片段
            take_count = min(config.MAX_CLIPS_PER_SEGMENT, clips_per_segment, len(bucket_sorted))
            selected.extend(bucket_sorted[:take_count])
        
        # 如果还需要更多片段，从剩余的高质量片段中选择
        if len(selected) < target_count:
            remaining_segments = [s for s in segments if s not in selected]
            remaining_sorted = sorted(remaining_segments,
                                    key=lambda x: x.get('ai_analysis', {}).get('composite_score', 0),
                                    reverse=True)
            
            needed = target_count - len(selected)
            selected.extend(remaining_sorted[:needed])
        
        # 如果选择了太多，按评分裁剪
        if len(selected) > target_count:
            selected = sorted(selected,
                            key=lambda x: x.get('ai_analysis', {}).get('composite_score', 0),
                            reverse=True)[:target_count]
        
        logger.info(f"时间分布策略选择了 {len(selected)} 个片段，分布在 {config.TIME_SEGMENTS} 个时间段")
        return selected
    
    def _select_by_score(self, segments: List[Dict], target_count: int) -> List[Dict]:
        """按评分选择片段"""
        sorted_segments = sorted(segments, 
                               key=lambda x: x.get('ai_analysis', {}).get('composite_score', 0), 
                               reverse=True)
        
        selected = sorted_segments[:target_count]
        logger.info(f"评分策略选择了 {len(selected)} 个片段")
        return selected
    
    def _log_selection_results(self, final_plan: List[Dict], total_segments: int, filtered_segments: int):
        """记录选择结果"""
        logger.info(f"=== 切片选择结果 ===")
        logger.info(f"原始片段数: {total_segments}")
        logger.info(f"过滤后片段数: {filtered_segments}")
        logger.info(f"最终选择数: {len(final_plan)}")
        
        for i, segment in enumerate(final_plan):
            analysis = segment.get('ai_analysis', {})
            start_min = segment['start_time'] / 60
            logger.info(f"片段{i+1}: {start_min:.1f}分钟, 评分={analysis.get('composite_score', 0):.2f}, 主题={analysis.get('topic', 'unknown')}")

    def analyze_segments(self, segments: List[Dict], total_duration: float = None) -> List[Dict]:
        """
        分析文本段落，使用AI优化切片方案
        
        Args:
            segments: SRT解析器生成的初始段落列表
            total_duration: 视频总时长
            
        Returns:
            优化后的切片方案
        """
        optimized_segments = []
        
        for segment in segments:
            # 对每个段落进行AI分析
            analysis = self._analyze_single_segment(segment, total_duration)
            
            # 合并分析结果
            enhanced_segment = {
                **segment,
                'ai_analysis': analysis,
                'quality_score': analysis.get('quality_score', 0.5),
                'topic': analysis.get('topic', ''),
                'key_points': analysis.get('key_points', []),
                'emotional_tone': analysis.get('emotional_tone', 'neutral'),
                'suggested_title': analysis.get('suggested_title', ''),
                'tags': analysis.get('tags', [])
            }
            
            optimized_segments.append(enhanced_segment)
        
        # 根据AI分析结果进一步优化切片
        return self._optimize_segments(optimized_segments)
    
    def enhance_clip_metadata(self, clip_data: Dict) -> Dict:
        """
        增强切片元数据
        
        Args:
            clip_data: 切片数据
            
        Returns:
            增强后的切片数据
        """
        # 使用配置文件中的增强提示词
        prompt = PromptConfig.METADATA_ENHANCEMENT_PROMPT.format(
            original_title=clip_data.get('suggested_title', ''),
            content=clip_data.get('full_text', ''),
            topic=clip_data.get('topic', ''),
            key_points=', '.join(clip_data.get('key_points', [])),
            emotional_tone=clip_data.get('emotional_tone', 'neutral'),
            duration=clip_data.get('duration', 0)
        )
        
        try:
            full_prompt = f"你是一个专业的短视频内容创作助手，擅长创造吸引人的标题和社交媒体内容。\n\n{prompt}"
            
            response_text = self.client.generate_content(full_prompt)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                enhanced_data = json.loads(json_match.group())
                clip_data.update(enhanced_data)
            
        except Exception as e:
            logger.error(f"元数据增强失败: {str(e)}")
        
        return clip_data