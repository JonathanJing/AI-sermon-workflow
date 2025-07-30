"""
视频切片功能模块
基于时间戳和切片计划生成短视频文件
"""

import ffmpeg
from datetime import datetime
import os
import uuid
from typing import List, Dict, Optional
import subprocess
import json
from pathlib import Path

class VideoCutter:
    """视频切片器"""
    
    def __init__(self, output_dir: str = "data/clips"):
        """
        初始化视频切片器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.ensure_output_dir()
    
    def ensure_output_dir(self):
        """确保输出目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def cut_video_segments(self, video_path: str, clip_plan: List[Dict]) -> List[Dict]:
        """
        根据切片计划切割视频
        
        Args:
            video_path: 原始视频文件路径
            clip_plan: 切片计划列表
            
        Returns:
            切片结果列表
        """
        results = []
        
        for i, clip in enumerate(clip_plan):
            try:
                # 生成输出文件名
                clip_id = str(uuid.uuid4())
                output_filename = f"clip_{i+1:02d}_{clip_id}.mp4"
                output_path = self.output_dir / output_filename
                
                # 执行视频切片
                success = self._cut_single_segment(
                    video_path, 
                    clip['start_time'], 
                    clip['duration'], 
                    str(output_path)
                )
                
                if success:
                    # 获取视频信息
                    video_info = self._get_video_info(str(output_path))
                    
                    result = {
                        'clip_id': clip_id,
                        'index': i + 1,
                        'output_path': str(output_path),
                        'start_time': clip['start_time'],
                        'duration': clip['duration'],
                        'end_time': clip['end_time'],
                        'file_size': os.path.getsize(output_path),
                        'video_info': video_info,
                        'metadata': clip.get('ai_analysis', {}),
                        'title': clip.get('suggested_title', f'视频片段 {i+1}'),
                        'tags': clip.get('tags', []),
                        'quality_score': clip.get('quality_score', 0.5),
                        'full_text': clip.get('full_text', ''),
                        'success': True
                    }
                else:
                    result = {
                        'clip_id': clip_id,
                        'index': i + 1,
                        'success': False,
                        'error': '视频切片失败'
                    }
                
                results.append(result)
                
            except Exception as e:
                results.append({
                    'clip_id': str(uuid.uuid4()),
                    'index': i + 1,
                    'success': False,
                    'error': f'处理失败: {str(e)}'
                })
        
        return results
    
    def _cut_single_segment(self, input_path: str, start_time: float, 
                           duration: float, output_path: str) -> bool:
        """
        切割单个视频片段
        
        Args:
            input_path: 输入视频路径
            start_time: 开始时间（秒）
            duration: 持续时间（秒）
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        try:
            # 使用ffmpeg-python进行视频切片
            stream = ffmpeg.input(input_path, ss=start_time, t=duration)
            stream = ffmpeg.output(
                stream, 
                output_path,
                vcodec='libx264',
                acodec='aac',
                **{
                    'crf': '23',  # 质量参数
                    'preset': 'medium',  # 编码速度
                    'movflags': '+faststart'  # 优化网络播放
                }
            )
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            return True
            
        except Exception as e:
            print(f"视频切片失败: {str(e)}")
            # 尝试使用命令行方式
            return self._cut_with_command(input_path, start_time, duration, output_path)
    
    def _cut_with_command(self, input_path: str, start_time: float, 
                         duration: float, output_path: str) -> bool:
        """
        使用命令行方式切割视频
        
        Args:
            input_path: 输入视频路径
            start_time: 开始时间（秒）
            duration: 持续时间（秒）
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-crf', '23',
                '-preset', 'medium',
                '-movflags', '+faststart',
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            print(f"命令行切片失败: {str(e)}")
            return False
    
    def _get_video_info(self, video_path: str) -> Dict:
        """
        获取视频文件信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息字典
        """
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] 
                               if stream['codec_type'] == 'video'), None)
            audio_stream = next((stream for stream in probe['streams'] 
                               if stream['codec_type'] == 'audio'), None)
            
            info = {
                'duration': float(probe['format']['duration']),
                'file_size': int(probe['format']['size']),
                'bitrate': int(probe['format']['bit_rate']),
                'format_name': probe['format']['format_name']
            }
            
            if video_stream:
                info.update({
                    'width': int(video_stream['width']),
                    'height': int(video_stream['height']),
                    'fps': eval(video_stream['r_frame_rate']),
                    'video_codec': video_stream['codec_name']
                })
            
            if audio_stream:
                info.update({
                    'audio_codec': audio_stream['codec_name'],
                    'sample_rate': int(audio_stream['sample_rate']),
                    'channels': int(audio_stream['channels'])
                })
            
            return info
            
        except Exception as e:
            print(f"获取视频信息失败: {str(e)}")
            return {}
    
    def create_clips_summary(self, results: List[Dict], output_file: str = None) -> Dict:
        """
        创建切片结果摘要
        
        Args:
            results: 切片结果列表
            output_file: 输出文件路径（可选）
            
        Returns:
            摘要信息
        """
        successful_clips = [r for r in results if r.get('success', False)]
        failed_clips = [r for r in results if not r.get('success', False)]
        
        total_duration = sum(r.get('duration', 0) for r in successful_clips)
        total_size = sum(r.get('file_size', 0) for r in successful_clips)
        avg_quality = sum(r.get('quality_score', 0) for r in successful_clips) / len(successful_clips) if successful_clips else 0
        
        summary = {
            'total_clips': len(results),
            'successful_clips': len(successful_clips),
            'failed_clips': len(failed_clips),
            'total_duration': total_duration,
            'total_file_size': total_size,
            'average_quality_score': avg_quality,
            'clips': results,
            'timestamp': str(datetime.now())
        }
        
        # 保存摘要文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return summary
    
    def add_subtitles_to_clips(self, results: List[Dict], srt_data: List[Dict]) -> List[Dict]:
        """
        为切片添加字幕
        
        Args:
            results: 切片结果列表
            srt_data: SRT字幕数据
            
        Returns:
            包含字幕的切片结果
        """
        enhanced_results = []
        
        for result in results:
            if not result.get('success', False):
                enhanced_results.append(result)
                continue
            
            try:
                # 为此片段创建字幕文件
                clip_subtitles = self._extract_clip_subtitles(
                    result['start_time'], 
                    result['end_time'], 
                    srt_data
                )
                
                if clip_subtitles:
                    # 创建字幕文件
                    srt_path = result['output_path'].replace('.mp4', '.srt')
                    self._create_srt_file(clip_subtitles, srt_path, result['start_time'])
                    
                    # 添加字幕到视频（可选）
                    subtitled_path = result['output_path'].replace('.mp4', '_subtitled.mp4')
                    if self._add_subtitles_to_video(result['output_path'], srt_path, subtitled_path):
                        result['subtitled_path'] = subtitled_path
                    
                    result['subtitle_path'] = srt_path
                    result['subtitle_count'] = len(clip_subtitles)
                
                enhanced_results.append(result)
                
            except Exception as e:
                print(f"添加字幕失败: {str(e)}")
                enhanced_results.append(result)
        
        return enhanced_results
    
    def _extract_clip_subtitles(self, start_time: float, end_time: float, 
                               srt_data: List[Dict]) -> List[Dict]:
        """提取片段对应的字幕"""
        clip_subtitles = []
        
        for subtitle in srt_data:
            if (subtitle['start_time'] >= start_time and subtitle['end_time'] <= end_time):
                # 调整时间戳为相对于片段开始的时间
                adjusted_subtitle = subtitle.copy()
                adjusted_subtitle['start_time'] -= start_time
                adjusted_subtitle['end_time'] -= start_time
                clip_subtitles.append(adjusted_subtitle)
        
        return clip_subtitles
    
    def _create_srt_file(self, subtitles: List[Dict], output_path: str, offset: float = 0):
        """创建SRT字幕文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, subtitle in enumerate(subtitles, 1):
                start_time = self._seconds_to_srt_time(subtitle['start_time'])
                end_time = self._seconds_to_srt_time(subtitle['end_time'])
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{subtitle['text']}\n\n")
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def _add_subtitles_to_video(self, video_path: str, srt_path: str, output_path: str) -> bool:
        """将字幕嵌入到视频中"""
        try:
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(
                stream, 
                output_path,
                vf=f"subtitles={srt_path}",
                vcodec='libx264',
                acodec='copy'
            )
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            return True
        except Exception as e:
            print(f"添加字幕失败: {str(e)}")
            return False