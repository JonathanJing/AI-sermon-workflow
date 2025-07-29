"""
视频质量验证模块
使用Gemini 2.5-pro对生成的短视频进行多维度质量评分和验证
"""

import os
import ffmpeg
import numpy as np
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime
import re
from ..gemini_client import GeminiClient

class VideoValidator:
    """视频质量验证器"""
    
    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        """
        初始化验证器
        
        Args:
            gemini_client: Gemini客户端（用于AI质量评估）
        """
        self.ai_client = gemini_client
        self.quality_thresholds = {
            'min_duration': 5.0,     # 最小时长（秒）
            'max_duration': 90.0,    # 最大时长（秒）
            'min_file_size': 1024,   # 最小文件大小（字节）
            'min_resolution': 480,   # 最小分辨率（高度）
            'min_bitrate': 100000,   # 最小比特率
            'content_score': 0.3,    # 最小内容质量分
            'audio_level': -30.0     # 最小音频电平（dB）
        }
    
    def validate_clip(self, clip_result: Dict) -> Dict:
        """
        验证单个视频片段
        
        Args:
            clip_result: 视频片段结果数据
            
        Returns:
            验证结果
        """
        if not clip_result.get('success', False):
            return {
                'valid': False,
                'score': 0.0,
                'issues': ['视频生成失败'],
                'details': {}
            }
        
        validation_result = {
            'valid': True,
            'score': 0.0,
            'issues': [],
            'details': {},
            'scores': {}
        }
        
        # 技术质量验证
        tech_score = self._validate_technical_quality(clip_result, validation_result)
        
        # 内容质量验证
        content_score = self._validate_content_quality(clip_result, validation_result)
        
        # 持续时间验证
        duration_score = self._validate_duration(clip_result, validation_result)
        
        # 音频质量验证
        audio_score = self._validate_audio_quality(clip_result, validation_result)
        
        # AI内容分析（如果可用）
        ai_score = self._validate_ai_content(clip_result, validation_result)
        
        # 计算综合得分
        scores = {
            'technical': tech_score,
            'content': content_score, 
            'duration': duration_score,
            'audio': audio_score,
            'ai_analysis': ai_score
        }
        
        validation_result['scores'] = scores
        
        # 加权综合得分
        weights = {
            'technical': 0.25,
            'content': 0.30,
            'duration': 0.15,
            'audio': 0.15,
            'ai_analysis': 0.15
        }
        
        total_score = sum(scores[key] * weights[key] for key in weights.keys())
        validation_result['score'] = round(total_score, 3)
        
        # 判断是否有效
        validation_result['valid'] = (
            total_score >= 0.5 and 
            len(validation_result['issues']) == 0
        )
        
        return validation_result
    
    def _validate_technical_quality(self, clip_result: Dict, validation_result: Dict) -> float:
        """验证技术质量"""
        score = 1.0
        video_info = clip_result.get('video_info', {})
        
        # 检查文件大小
        file_size = clip_result.get('file_size', 0)
        if file_size < self.quality_thresholds['min_file_size']:
            validation_result['issues'].append(f'文件大小过小: {file_size} bytes')
            score -= 0.3
        
        # 检查分辨率
        height = video_info.get('height', 0)
        if height < self.quality_thresholds['min_resolution']:
            validation_result['issues'].append(f'分辨率过低: {height}p')
            score -= 0.3
        
        # 检查比特率
        bitrate = video_info.get('bitrate', 0)
        if bitrate < self.quality_thresholds['min_bitrate']:
            validation_result['issues'].append(f'比特率过低: {bitrate}')
            score -= 0.2
        
        # 检查帧率
        fps = video_info.get('fps', 0)
        if fps < 15:
            validation_result['issues'].append(f'帧率过低: {fps}fps')
            score -= 0.2
        
        validation_result['details']['technical'] = {
            'file_size': file_size,
            'resolution': f"{video_info.get('width', 0)}x{height}",
            'bitrate': bitrate,
            'fps': fps,
            'codec': video_info.get('video_codec', 'unknown')
        }
        
        return max(0.0, score)
    
    def _validate_content_quality(self, clip_result: Dict, validation_result: Dict) -> float:
        """验证内容质量"""
        content_score = clip_result.get('quality_score', 0.5)
        
        # 检查文本长度
        text_length = len(clip_result.get('full_text', ''))
        if text_length < 10:
            validation_result['issues'].append('文本内容过短')
            content_score -= 0.3
        
        # 检查是否有关键信息
        metadata = clip_result.get('metadata', {})
        completeness = metadata.get('completeness', 0.5)
        engagement = metadata.get('engagement', 0.5)
        
        if completeness < 0.3:
            validation_result['issues'].append('内容完整性不足')
        
        if engagement < 0.3:
            validation_result['issues'].append('内容吸引力不足')
        
        validation_result['details']['content'] = {
            'text_length': text_length,
            'completeness': completeness,
            'engagement': engagement,
            'topic': metadata.get('topic', ''),
            'key_points_count': len(metadata.get('key_points', []))
        }
        
        return content_score
    
    def _validate_duration(self, clip_result: Dict, validation_result: Dict) -> float:
        """验证时长"""
        duration = clip_result.get('duration', 0)
        score = 1.0
        
        if duration < self.quality_thresholds['min_duration']:
            validation_result['issues'].append(f'时长过短: {duration:.1f}s')
            score = 0.0
        elif duration > self.quality_thresholds['max_duration']:
            validation_result['issues'].append(f'时长过长: {duration:.1f}s')
            score = 0.5
        else:
            # 理想时长范围：15-60秒
            if 15 <= duration <= 60:
                score = 1.0
            elif 10 <= duration < 15:
                score = 0.8
            elif 60 < duration <= 90:
                score = 0.7
            else:
                score = 0.5
        
        validation_result['details']['duration'] = {
            'duration': duration,
            'ideal_range': '15-60秒',
            'acceptable_range': '10-90秒'
        }
        
        return score
    
    def _validate_audio_quality(self, clip_result: Dict, validation_result: Dict) -> float:
        """验证音频质量"""
        score = 1.0
        video_path = clip_result.get('output_path')
        
        if not video_path or not os.path.exists(video_path):
            validation_result['issues'].append('无法访问视频文件')
            return 0.0
        
        try:
            # 分析音频电平
            audio_stats = self._analyze_audio_level(video_path)
            
            mean_volume = audio_stats.get('mean_volume', -50.0)
            max_volume = audio_stats.get('max_volume', -50.0)
            
            # 检查音量是否过低
            if mean_volume < self.quality_thresholds['audio_level']:
                validation_result['issues'].append(f'音量过低: {mean_volume:.1f}dB')
                score -= 0.4
            
            # 检查是否有静音
            if max_volume < -40.0:
                validation_result['issues'].append('可能包含静音段')
                score -= 0.3
            
            validation_result['details']['audio'] = {
                'mean_volume': mean_volume,
                'max_volume': max_volume,
                'sample_rate': clip_result.get('video_info', {}).get('sample_rate', 0),
                'channels': clip_result.get('video_info', {}).get('channels', 0)
            }
            
        except Exception as e:
            validation_result['issues'].append(f'音频分析失败: {str(e)}')
            score = 0.5
        
        return max(0.0, score)
    
    def _analyze_audio_level(self, video_path: str) -> Dict:
        """分析音频电平"""
        try:
            # 使用ffmpeg分析音频
            probe = ffmpeg.probe(video_path, select_streams='a')
            
            # 获取音频统计信息
            cmd = (
                ffmpeg
                .input(video_path)
                .audio
                .filter('volumedetect')
                .output('-', format='null')
            )
            
            result = ffmpeg.run(cmd, capture_stdout=True, capture_stderr=True)
            stderr = result.stderr.decode('utf-8')
            
            # 解析volumedetect输出
            mean_volume = -50.0
            max_volume = -50.0
            
            for line in stderr.split('\n'):
                if 'mean_volume:' in line:
                    mean_volume = float(line.split('mean_volume:')[1].split('dB')[0].strip())
                elif 'max_volume:' in line:
                    max_volume = float(line.split('max_volume:')[1].split('dB')[0].strip())
            
            return {
                'mean_volume': mean_volume,
                'max_volume': max_volume
            }
            
        except Exception as e:
            print(f"音频分析失败: {str(e)}")
            return {'mean_volume': -30.0, 'max_volume': -20.0}  # 默认值
    
    def _validate_ai_content(self, clip_result: Dict, validation_result: Dict) -> float:
        """AI内容质量分析"""
        if not self.ai_client:
            return 0.7  # 默认分数
        
        try:
            text_content = clip_result.get('full_text', '')
            if not text_content:
                return 0.3
            
            prompt = f"""
            你是一个专业的视频内容质量评估师。请评估以下视频片段文本的质量，从多个维度进行打分（0-1分）：

            文本内容：
            {text_content}

            请评估：
            1. 内容完整性（是否有完整的意思表达）
            2. 信息密度（信息量是否充足）
            3. 语言流畅性（表达是否自然流畅）
            4. 话题专注性（是否围绕一个主题）
            5. 观众吸引力（是否能吸引观众注意）

            返回JSON格式：
            {{
                "completeness": 0.8,
                "information_density": 0.7,
                "fluency": 0.9,
                "topic_focus": 0.8,
                "engagement": 0.6,
                "overall_score": 0.76,
                "reason": "评分理由"
            }}
            """
            
            response_text = self.ai_client.generate_content(prompt)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                ai_analysis = json.loads(json_match.group())
                validation_result['details']['ai_analysis'] = ai_analysis
                return ai_analysis.get('overall_score', 0.5)
            
        except Exception as e:
            print(f"AI内容分析失败: {str(e)}")
        
        return 0.5  # 默认分数
    
    def validate_clip_batch(self, clip_results: List[Dict]) -> Dict:
        """
        批量验证视频片段
        
        Args:
            clip_results: 视频片段结果列表
            
        Returns:
            批量验证结果
        """
        batch_result = {
            'total_clips': len(clip_results),
            'valid_clips': 0,
            'invalid_clips': 0,
            'average_score': 0.0,
            'clip_validations': [],
            'summary': {
                'common_issues': {},
                'score_distribution': {},
                'recommendations': []
            }
        }
        
        scores = []
        all_issues = []
        
        for clip_result in clip_results:
            validation = self.validate_clip(clip_result)
            batch_result['clip_validations'].append(validation)
            
            if validation['valid']:
                batch_result['valid_clips'] += 1
            else:
                batch_result['invalid_clips'] += 1
            
            scores.append(validation['score'])
            all_issues.extend(validation['issues'])
        
        # 计算统计信息
        if scores:
            batch_result['average_score'] = round(np.mean(scores), 3)
            
            # 分数分布
            score_ranges = {
                '优秀(0.8-1.0)': len([s for s in scores if s >= 0.8]),
                '良好(0.6-0.8)': len([s for s in scores if 0.6 <= s < 0.8]),
                '一般(0.4-0.6)': len([s for s in scores if 0.4 <= s < 0.6]),
                '较差(0.0-0.4)': len([s for s in scores if s < 0.4])
            }
            batch_result['summary']['score_distribution'] = score_ranges
        
        # 常见问题统计
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        batch_result['summary']['common_issues'] = issue_counts
        
        # 生成建议
        batch_result['summary']['recommendations'] = self._generate_recommendations(
            batch_result, issue_counts
        )
        
        return batch_result
    
    def _generate_recommendations(self, batch_result: Dict, issue_counts: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于常见问题生成建议
        if '音量过低' in ' '.join(issue_counts.keys()):
            recommendations.append('建议调整音频录制设备或后期处理音量')
        
        if '分辨率过低' in ' '.join(issue_counts.keys()):
            recommendations.append('建议使用更高分辨率的视频源')
        
        if '时长过短' in ' '.join(issue_counts.keys()):
            recommendations.append('建议合并相邻的短片段或调整切片参数')
        
        if '内容完整性不足' in ' '.join(issue_counts.keys()):
            recommendations.append('建议优化AI切片算法，确保语义完整性')
        
        # 基于整体质量给建议
        avg_score = batch_result.get('average_score', 0.5)
        if avg_score < 0.6:
            recommendations.append('整体质量偏低，建议检查原始视频质量和切片参数')
        
        valid_rate = batch_result['valid_clips'] / batch_result['total_clips'] if batch_result['total_clips'] > 0 else 0
        if valid_rate < 0.7:
            recommendations.append('有效片段比例较低，建议调整质量阈值或改进切片策略')
        
        return recommendations
    
    def export_validation_report(self, batch_result: Dict, output_path: str):
        """导出验证报告"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'validation_summary': batch_result,
            'quality_thresholds': self.quality_thresholds
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"验证报告已导出到: {output_path}")