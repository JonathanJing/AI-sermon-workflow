"""
AI智能切片算法
使用Gemini 2.5-pro识别语义完整的段落，生成最佳切片方案
"""

from typing import List, Dict, Optional
import json
import re
import logging
from .srt_parser import SRTParser
from ..gemini_client import GeminiClient

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
    
    def _analyze_single_segment(self, segment: Dict) -> Dict:
        """
        使用AI分析单个文本段落
        
        Args:
            segment: 文本段落数据
            
        Returns:
            AI分析结果
        """
        prompt = f"""
        请分析以下中文文本段落（来自视频字幕），并提供详细的分析结果：

        文本内容：
        {segment['full_text']}

        时长：{segment['duration']:.1f}秒

        请以JSON格式返回分析结果，包含以下字段：
        1. quality_score: 内容质量评分（0-1，1为最高）
        2. topic: 主要话题（简短描述）
        3. key_points: 关键要点列表（最多3个）
        4. emotional_tone: 情感色调（positive/neutral/negative）
        5. suggested_title: 建议标题（不超过20字）
        6. tags: 相关标签列表（最多5个）
        7. completeness: 内容完整性评分（0-1）
        8. engagement: 吸引力评分（0-1）
        9. reason: 评分理由（简短说明）

        请确保返回有效的JSON格式。
        """
        
        try:
            full_prompt = f"你是一个专业的视频内容分析师，专门分析中文视频字幕内容。请始终返回有效的JSON格式。\n\n{prompt}"
            
            response_text = self.client.generate_content(full_prompt)
            
            # 尝试提取JSON内容
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning(f"JSON解析失败，使用默认响应: {json_match.group()}")
                    return self._get_default_analysis()
            else:
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning(f"响应不是有效JSON，使用默认响应: {response_text}")
                    return self._get_default_analysis()
                
        except Exception as e:
            logger.error(f"AI分析失败: {str(e)}")
            # 返回默认分析结果
            return {
                'quality_score': 0.5,
                'topic': '未知主题',
                'key_points': ['内容待分析'],
                'emotional_tone': 'neutral',
                'suggested_title': segment['full_text'][:20] + '...',
                'tags': ['视频片段'],
                'completeness': 0.5,
                'engagement': 0.5,
                'reason': 'AI分析失败，使用默认评分'
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
        
        # AI分析优化
        optimized_segments = self.analyze_segments(segments)
        
        # 根据质量评分排序，选择最佳片段
        sorted_segments = sorted(optimized_segments, 
                               key=lambda x: x.get('ai_analysis', {}).get('quality_score', 0), 
                               reverse=True)
        
        # 选择前N个最佳片段
        selected_segments = sorted_segments[:target_count]
        
        # 按时间顺序重新排序
        final_plan = sorted(selected_segments, key=lambda x: x['start_time'])
        
        return final_plan
    
    def enhance_clip_metadata(self, clip_data: Dict) -> Dict:
        """
        增强切片元数据
        
        Args:
            clip_data: 切片数据
            
        Returns:
            增强后的切片数据
        """
        # 生成更详细的标题和描述
        prompt = f"""
        基于以下视频片段信息，生成更好的标题和描述：

        原始标题：{clip_data.get('suggested_title', '')}
        内容：{clip_data.get('full_text', '')}
        主题：{clip_data.get('topic', '')}
        关键要点：{', '.join(clip_data.get('key_points', []))}

        请生成：
        1. 3个不同风格的标题选项（吸引人、准确、简洁）
        2. 一段50字以内的描述
        3. 5个相关的社交媒体标签

        以JSON格式返回。
        """
        
        try:
            full_prompt = f"你是一个专业的短视频内容创作助手。\n\n{prompt}"
            
            response_text = self.client.generate_content(full_prompt)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                enhanced_data = json.loads(json_match.group())
                clip_data.update(enhanced_data)
            
        except Exception as e:
            print(f"元数据增强失败: {str(e)}")
        
        return clip_data