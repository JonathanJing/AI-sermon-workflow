"""
标题生成和标签系统
使用Gemini 2.5-pro为视频片段自动生成吸引人的标题和相关标签
"""

import re
import json
import logging
from typing import List, Dict, Optional, Set
import jieba
import jieba.analyse
from collections import Counter
from ..gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class TitleTagger:
    """标题生成和标签系统"""
    
    def __init__(self, gemini_client: GeminiClient):
        """
        初始化标题标签生成器
        
        Args:
            gemini_client: Gemini客户端实例
        """
        self.client = gemini_client
        
        # 预定义标签库
        self.predefined_tags = {
            '宗教': ['基督教', '信仰', '圣经', '祷告', '赞美', '见证', '牧师', '讲道'],
            '情感': ['感动', '温暖', '治愈', '励志', '正能量', '温馨', '深度', '反思'],
            '生活': ['人生', '智慧', '成长', '家庭', '工作', '人际关系', '价值观'],
            '节日': ['圣诞节', '复活节', '感恩节', '新年', '母亲节', '父亲节'],
            '主题': ['爱', '希望', '宽恕', '救赎', '平安', '喜乐', '信心', '勇气']
        }
        
        # 常用关键词
        self.common_keywords = set([
            '上帝', '主', '耶稣', '圣灵', '天父', '救主', '基督',
            '爱', '信心', '希望', '平安', '喜乐', '恩典', '祝福',
            '生命', '真理', '道路', '光明', '永生', '救恩'
        ])
    
    def generate_titles(self, text_content: str, 
                       existing_metadata: Dict = None, 
                       title_count: int = 5) -> List[Dict]:
        """
        生成多个标题选项
        
        Args:
            text_content: 文本内容
            existing_metadata: 现有元数据
            title_count: 生成标题数量
            
        Returns:
            标题列表，每个包含标题和相关信息
        """
        # 提取关键信息
        key_info = self._extract_key_information(text_content, existing_metadata)
        
        # 使用AI生成多样化标题
        ai_titles = self._generate_ai_titles(text_content, key_info, title_count)
        
        # 基于模板生成标题
        template_titles = self._generate_template_titles(key_info)
        
        # 合并和评分
        all_titles = ai_titles + template_titles
        scored_titles = self._score_titles(all_titles, text_content, key_info)
        
        # 返回最佳标题
        return sorted(scored_titles, key=lambda x: x['score'], reverse=True)[:title_count]
    
    def _extract_key_information(self, text_content: str, existing_metadata: Dict = None) -> Dict:
        """提取关键信息"""
        key_info = {
            'keywords': [],
            'topics': [],
            'emotions': [],
            'key_phrases': [],
            'length': len(text_content)
        }
        
        # 使用jieba进行关键词提取
        try:
            keywords = jieba.analyse.extract_tags(text_content, topK=10)
            key_info['keywords'] = keywords
            
            # 提取关键短语
            key_phrases = jieba.analyse.textrank(text_content, topK=5)
            key_info['key_phrases'] = key_phrases
            
        except Exception as e:
            logger.warning(f"关键词提取失败: {str(e)}")
        
        # 从现有元数据中提取信息
        if existing_metadata:
            key_info['topics'] = existing_metadata.get('key_points', [])
            key_info['emotion'] = existing_metadata.get('emotional_tone', 'neutral')
            key_info['topic'] = existing_metadata.get('topic', '')
        
        # 识别预定义关键词
        found_keywords = set()
        text_lower = text_content.lower()
        for keyword in self.common_keywords:
            if keyword in text_content:
                found_keywords.add(keyword)
        key_info['religious_keywords'] = list(found_keywords)
        
        return key_info
    
    def _generate_ai_titles(self, text_content: str, key_info: Dict, count: int) -> List[Dict]:
        """使用AI生成标题"""
        prompt = f"""
        基于以下视频片段文本，生成{count}个不同风格的标题：

        文本内容：
        {text_content}

        关键信息：
        - 主要话题：{key_info.get('topic', '')}
        - 关键词：{', '.join(key_info.get('keywords', [])[:5])}
        - 情感色调：{key_info.get('emotion', 'neutral')}

        请生成以下不同风格的标题：
        1. 吸引眼球型（突出情感和冲击力）
        2. 描述性（准确描述内容）
        3. 疑问式（引发思考）
        4. 数字式（包含具体数字或步骤）
        5. 励志型（正能量和激励）

        要求：
        - 每个标题不超过25个字
        - 标题要准确反映内容
        - 适合中文社交媒体传播
        - 避免使用过于宗教化的词汇

        返回JSON格式：
        {{
            "titles": [
                {{"title": "标题1", "style": "吸引眼球型", "reason": "设计理由"}},
                {{"title": "标题2", "style": "描述性", "reason": "设计理由"}},
                ...
            ]
        }}
        """
        
        try:
            full_prompt = f"你是一个专业的短视频标题创作专家，擅长创作吸引人的中文标题。\n\n{prompt}"
            
            response_text = self.client.generate_content(full_prompt)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    titles = []
                    for item in result.get('titles', []):
                        titles.append({
                            'title': item['title'],
                            'style': item.get('style', 'AI生成'),
                            'reason': item.get('reason', ''),
                            'source': 'ai',
                            'score': 0.8  # 默认AI生成分数
                        })
                    return titles
                except json.JSONDecodeError:
                    logger.warning(f"AI标题生成JSON解析失败: {json_match.group()}")
        
        except Exception as e:
            logger.error(f"AI标题生成失败: {str(e)}")
        
        return []
    
    def _generate_template_titles(self, key_info: Dict) -> List[Dict]:
        """基于模板生成标题"""
        templates = [
            "关于{topic}的{emotion}思考",
            "{keyword}带给我们的启示",
            "一段话让你明白{topic}",
            "当我们谈论{keyword}时，我们在谈论什么",
            "生活中的{topic}智慧",
            "{keyword}：不一样的理解",
            "深度解读：{topic}的意义",
            "为什么{keyword}如此重要？",
            "从{topic}中学到的人生道理",
            "{keyword}的力量"
        ]
        
        template_titles = []
        topic = key_info.get('topic', '人生')
        keywords = key_info.get('keywords', ['智慧'])
        
        for template in templates[:5]:  # 限制数量
            try:
                if '{topic}' in template and '{keyword}' in template:
                    title = template.format(
                        topic=topic[:10],  # 限制长度
                        keyword=keywords[0] if keywords else '智慧'
                    )
                elif '{topic}' in template:
                    title = template.format(topic=topic[:10])
                elif '{keyword}' in template:
                    title = template.format(keyword=keywords[0] if keywords else '智慧')
                else:
                    continue
                
                if len(title) <= 25:  # 标题长度限制
                    template_titles.append({
                        'title': title,
                        'style': '模板生成',
                        'reason': f'基于模板: {template}',
                        'source': 'template',
                        'score': 0.6  # 默认模板分数
                    })
            except Exception as e:
                continue
        
        return template_titles
    
    def _score_titles(self, titles: List[Dict], text_content: str, key_info: Dict) -> List[Dict]:
        """为标题评分"""
        for title_data in titles:
            title = title_data['title']
            score = title_data.get('score', 0.5)
            
            # 长度评分
            length = len(title)
            if 8 <= length <= 20:
                score += 0.1
            elif length > 25:
                score -= 0.2
            
            # 关键词匹配评分
            keywords = key_info.get('keywords', [])
            matched_keywords = sum(1 for keyword in keywords if keyword in title)
            score += matched_keywords * 0.05
            
            # 情感词汇评分
            positive_words = ['启示', '智慧', '力量', '希望', '温暖', '感动', '成长']
            emotion_score = sum(0.03 for word in positive_words if word in title)
            score += emotion_score
            
            # 数字和特殊符号评分
            if re.search(r'\d+', title):
                score += 0.05
            if '?' in title or '！' in title:
                score += 0.03
            
            # 避免过于平淡的标题
            boring_words = ['关于', '一个', '这个', '那个']
            if any(word in title for word in boring_words):
                score -= 0.05
            
            title_data['score'] = round(max(0.0, min(1.0, score)), 3)
        
        return titles
    
    def generate_tags(self, text_content: str, 
                     existing_metadata: Dict = None,
                     max_tags: int = 10) -> List[Dict]:
        """
        生成标签
        
        Args:
            text_content: 文本内容
            existing_metadata: 现有元数据
            max_tags: 最大标签数量
            
        Returns:
            标签列表
        """
        all_tags = []
        
        # AI生成标签
        ai_tags = self._generate_ai_tags(text_content, existing_metadata)
        all_tags.extend(ai_tags)
        
        # 基于关键词生成标签
        keyword_tags = self._generate_keyword_tags(text_content)
        all_tags.extend(keyword_tags)
        
        # 预定义标签匹配
        predefined_tags = self._match_predefined_tags(text_content)
        all_tags.extend(predefined_tags)
        
        # 去重和评分
        unique_tags = self._deduplicate_and_score_tags(all_tags, text_content)
        
        # 返回最佳标签
        return sorted(unique_tags, key=lambda x: x['score'], reverse=True)[:max_tags]
    
    def _generate_ai_tags(self, text_content: str, existing_metadata: Dict = None) -> List[Dict]:
        """使用AI生成标签"""
        prompt = f"""
        基于以下文本内容，生成10个相关的标签：

        文本内容：
        {text_content}

        请生成适合短视频平台的标签，包括：
        - 内容主题标签
        - 情感类标签
        - 受众类标签
        - 场景类标签

        要求：
        - 标签要简洁（2-4个字）
        - 适合中文社交媒体
        - 有助于内容传播和发现
        - 避免过于宗教化

        返回JSON格式：
        {{
            "tags": ["标签1", "标签2", "标签3", ...]
        }}
        """
        
        try:
            full_prompt = f"你是一个专业的内容标签生成专家。\n\n{prompt}"
            
            response_text = self.client.generate_content(full_prompt)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return [{'tag': tag, 'source': 'ai', 'score': 0.8} 
                       for tag in result.get('tags', [])]
        
        except Exception as e:
            print(f"AI标签生成失败: {str(e)}")
        
        return []
    
    def _generate_keyword_tags(self, text_content: str) -> List[Dict]:
        """基于关键词生成标签"""
        try:
            keywords = jieba.analyse.extract_tags(text_content, topK=8)
            return [{'tag': keyword, 'source': 'keyword', 'score': 0.6}
                   for keyword in keywords if len(keyword) >= 2]
        except Exception as e:
            print(f"关键词标签生成失败: {str(e)}")
            return []
    
    def _match_predefined_tags(self, text_content: str) -> List[Dict]:
        """匹配预定义标签"""
        matched_tags = []
        
        for category, tags in self.predefined_tags.items():
            for tag in tags:
                if tag in text_content:
                    matched_tags.append({
                        'tag': tag,
                        'source': 'predefined',
                        'category': category,
                        'score': 0.7
                    })
        
        return matched_tags
    
    def _deduplicate_and_score_tags(self, tags: List[Dict], text_content: str) -> List[Dict]:
        """去重和重新评分标签"""
        # 按标签名称去重
        unique_tags = {}
        for tag_data in tags:
            tag_name = tag_data['tag']
            if tag_name not in unique_tags or tag_data['score'] > unique_tags[tag_name]['score']:
                unique_tags[tag_name] = tag_data
        
        # 重新评分
        for tag_name, tag_data in unique_tags.items():
            # 基于出现频率调整分数
            count = text_content.count(tag_name)
            if count > 1:
                tag_data['score'] += 0.1 * min(count - 1, 3)
            
            # 基于标签长度调整
            if len(tag_name) == 2:
                tag_data['score'] += 0.05
            elif len(tag_name) > 6:
                tag_data['score'] -= 0.1
        
        return list(unique_tags.values())
    
    def create_social_media_package(self, text_content: str, 
                                   existing_metadata: Dict = None) -> Dict:
        """
        创建社交媒体发布包
        
        Args:
            text_content: 文本内容
            existing_metadata: 现有元数据
            
        Returns:
            社交媒体包，包含标题、标签、描述等
        """
        # 生成标题
        titles = self.generate_titles(text_content, existing_metadata, 3)
        
        # 生成标签
        tags = self.generate_tags(text_content, existing_metadata, 8)
        
        # 生成描述
        description = self._generate_description(text_content, existing_metadata)
        
        # 选择最佳标题
        best_title = titles[0] if titles else {'title': '精彩片段', 'score': 0.5}
        
        # 创建发布包
        package = {
            'primary_title': best_title['title'],
            'title_options': [t['title'] for t in titles],
            'tags': [t['tag'] for t in tags],
            'hashtags': '#' + ' #'.join([t['tag'] for t in tags[:5]]),
            'description': description,
            'social_media_text': self._create_social_media_text(
                best_title['title'], description, tags[:5]
            ),
            'metadata': {
                'title_scores': {t['title']: t['score'] for t in titles},
                'tag_scores': {t['tag']: t['score'] for t in tags},
                'generation_timestamp': str(datetime.now()) if 'datetime' in globals() else 'unknown'
            }
        }
        
        return package
    
    def _generate_description(self, text_content: str, existing_metadata: Dict = None) -> str:
        """生成描述文本"""
        # 提取前50个字作为基础描述
        base_description = text_content[:50] + '...' if len(text_content) > 50 else text_content
        
        # 如果有AI分析的关键点，使用它们
        if existing_metadata and existing_metadata.get('key_points'):
            key_points = existing_metadata['key_points'][:2]  # 最多两个要点
            description = f"{base_description} 主要讲述：{', '.join(key_points)}"
        else:
            description = base_description
        
        return description
    
    def _create_social_media_text(self, title: str, description: str, tags: List[Dict]) -> str:
        """创建社交媒体发布文本"""
        hashtags = ' '.join([f"#{tag['tag']}" for tag in tags])
        
        social_text = f"""🎬 {title}

{description}

{hashtags}

#短视频 #精彩片段 #值得收藏"""
        
        return social_text