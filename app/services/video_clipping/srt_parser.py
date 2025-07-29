"""
SRT字幕文件解析器
解析SRT文件，提取时间戳和文本内容
"""

import pysrt
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import re

class SRTParser:
    """SRT字幕文件解析器"""
    
    def __init__(self):
        self.subtitles = []
        self.parsed_data = []
    
    def parse_file(self, srt_file_path: str) -> List[Dict]:
        """
        解析SRT文件
        
        Args:
            srt_file_path: SRT文件路径
            
        Returns:
            解析后的字幕数据列表
        """
        try:
            self.subtitles = pysrt.open(srt_file_path, encoding='utf-8')
            self.parsed_data = []
            
            for subtitle in self.subtitles:
                parsed_item = {
                    'index': subtitle.index,
                    'start_time': self._time_to_seconds(subtitle.start),
                    'end_time': self._time_to_seconds(subtitle.end),
                    'duration': self._time_to_seconds(subtitle.end) - self._time_to_seconds(subtitle.start),
                    'text': self._clean_text(subtitle.text),
                    'raw_text': subtitle.text
                }
                self.parsed_data.append(parsed_item)
                
            return self.parsed_data
            
        except Exception as e:
            raise Exception(f"解析SRT文件失败: {str(e)}")
    
    def _time_to_seconds(self, time_obj) -> float:
        """将时间对象转换为秒数"""
        return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000.0
    
    def _clean_text(self, text: str) -> str:
        """清理文本，移除特殊符号"""
        # 移除▁符号和多余空格
        cleaned = re.sub(r'▁', ' ', text)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()
    
    def get_text_segments(self, min_duration: float = 5.0, max_duration: float = 60.0) -> List[Dict]:
        """
        获取合适长度的文本段落
        
        Args:
            min_duration: 最小时长（秒）
            max_duration: 最大时长（秒）
            
        Returns:
            文本段落列表
        """
        if not self.parsed_data:
            return []
        
        segments = []
        current_segment = {
            'start_time': self.parsed_data[0]['start_time'],
            'texts': [],
            'indices': []
        }
        
        for item in self.parsed_data:
            current_segment['texts'].append(item['text'])
            current_segment['indices'].append(item['index'])
            current_segment['end_time'] = item['end_time']
            
            current_duration = current_segment['end_time'] - current_segment['start_time']
            
            # 如果达到最大时长或检测到段落结束标志
            if (current_duration >= max_duration or 
                self._is_segment_end(item['text'])) and current_duration >= min_duration:
                
                current_segment['duration'] = current_duration
                current_segment['full_text'] = ' '.join(current_segment['texts'])
                segments.append(current_segment.copy())
                
                # 开始新段落
                current_segment = {
                    'start_time': item['end_time'],
                    'texts': [],
                    'indices': []
                }
        
        # 处理最后一个段落
        if current_segment['texts']:
            current_segment['end_time'] = self.parsed_data[-1]['end_time']
            current_segment['duration'] = current_segment['end_time'] - current_segment['start_time']
            if current_segment['duration'] >= min_duration:
                current_segment['full_text'] = ' '.join(current_segment['texts'])
                segments.append(current_segment)
        
        return segments
    
    def _is_segment_end(self, text: str) -> bool:
        """判断是否为段落结束"""
        # 检测句号、问号、感叹号等段落结束标志
        end_markers = ['。', '！', '？', '.', '!', '?']
        return any(marker in text for marker in end_markers)
    
    def get_subtitle_by_time(self, start_time: float, end_time: float) -> List[Dict]:
        """根据时间范围获取字幕"""
        return [item for item in self.parsed_data 
                if item['start_time'] >= start_time and item['end_time'] <= end_time]