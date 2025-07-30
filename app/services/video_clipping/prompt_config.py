"""
AI切片器提示词配置文件
用于调优AI分析和切片选择策略
"""

class PromptConfig:
    """提示词和策略配置"""
    
    # ===========================================
    # 核心分析提示词
    # ===========================================
    
    CONTENT_ANALYSIS_PROMPT = """
    请分析以下中文文本段落（来自视频字幕），并提供详细的分析结果：

    文本内容：
    {text_content}

    时长：{duration:.1f}秒
    位置：视频第{position_minutes:.1f}分钟

    请以JSON格式返回分析结果，包含以下字段：
    1. quality_score: 内容质量评分（0-1，1为最高）
    2. topic: 主要话题（简短描述）
    3. key_points: 关键要点列表（最多3个）
    4. emotional_tone: 情感色调（positive/neutral/negative）
    5. suggested_title: 建议标题（不超过20字）
    6. tags: 相关标签列表（最多5个）
    7. completeness: 内容完整性评分（0-1）
    8. engagement: 吸引力评分（0-1）
    9. independence: 独立性评分（0-1，内容是否能独立理解）
    10. hook_potential: 开头吸引力（0-1）
    11. conclusion_strength: 结尾完整性（0-1）
    12. reason: 评分理由（简短说明）

    评分标准：
    - quality_score: 内容有意义、信息量丰富
    - completeness: 语义完整、不需要前后文
    - engagement: 有趣、有价值、能吸引观众
    - independence: 可以作为独立片段理解
    - hook_potential: 开头是否引人入胜
    - conclusion_strength: 结尾是否自然完整

    请确保返回有效的JSON格式。
    """
    
    SYSTEM_ROLE_PROMPT = "你是一个专业的视频内容分析师，专门分析中文视频字幕内容。你善于识别有价值、完整且有吸引力的视频片段。请始终返回有效的JSON格式。"
    
    # ===========================================
    # 切片选择策略配置
    # ===========================================
    
    class SelectionStrategy:
        """切片选择策略配置"""
        
        # 质量阈值
        MIN_QUALITY_SCORE = 0.4  # 最低质量要求
        MIN_COMPLETENESS = 0.5   # 最低完整性要求
        MIN_INDEPENDENCE = 0.6   # 最低独立性要求
        MIN_ENGAGEMENT = 0.3     # 最低吸引力要求
        
        # 时间分布策略
        ENABLE_TIME_DISTRIBUTION = True  # 启用时间分布
        TIME_SEGMENTS = 5  # 将视频分为N段
        MAX_CLIPS_PER_SEGMENT = 2  # 每段最多选择的片段数
        
        # 综合评分权重
        WEIGHTS = {
            'quality_score': 0.25,
            'completeness': 0.20,
            'engagement': 0.20,
            'independence': 0.15,
            'hook_potential': 0.10,
            'conclusion_strength': 0.10
        }
        
        # 去重策略
        SIMILARITY_THRESHOLD = 0.7  # 相似度阈值，超过则去重
        ENABLE_DIVERSITY = True     # 启用主题多样性
        
        # 位置偏好
        POSITION_BONUS = {
            'beginning': 0.1,  # 开头片段加分
            'middle': 0.0,     # 中间片段正常
            'end': 0.05        # 结尾片段小幅加分
        }
    
    # ===========================================
    # 元数据增强提示词
    # ===========================================
    
    METADATA_ENHANCEMENT_PROMPT = """
    基于以下视频片段信息，生成更好的标题和描述：

    原始标题：{original_title}
    内容：{content}
    主题：{topic}
    关键要点：{key_points}
    情感色调：{emotional_tone}
    时长：{duration}秒

    请生成以JSON格式返回：
    {{
        "titles": {{
            "catchy": "吸引人的标题（适合社交媒体）",
            "descriptive": "准确描述性标题",
            "concise": "简洁标题"
        }},
        "description": "50字以内的描述",
        "hashtags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
        "social_media_caption": "适合社交媒体的文案（含表情符号）",
        "target_audience": "目标受众描述"
    }}
    """
    
    # ===========================================
    # 调试和监控配置
    # ===========================================
    
    class Debug:
        """调试配置"""
        ENABLE_DETAILED_LOGGING = True
        LOG_SELECTION_PROCESS = True
        SAVE_ANALYSIS_RESULTS = True
        EXPLAIN_SELECTIONS = True
    
    # ===========================================
    # 快速调优预设
    # ===========================================
    
    @classmethod
    def apply_preset(cls, preset_name: str):
        """应用预设配置"""
        presets = {
            'balanced': {
                'MIN_QUALITY_SCORE': 0.4,
                'MIN_COMPLETENESS': 0.5,
                'ENABLE_TIME_DISTRIBUTION': True,
                'TIME_SEGMENTS': 5
            },
            'high_quality': {
                'MIN_QUALITY_SCORE': 0.6,
                'MIN_COMPLETENESS': 0.7,
                'MIN_INDEPENDENCE': 0.7,
                'ENABLE_TIME_DISTRIBUTION': True,
                'TIME_SEGMENTS': 3
            },
            'diverse': {
                'MIN_QUALITY_SCORE': 0.3,
                'MIN_COMPLETENESS': 0.4,
                'ENABLE_TIME_DISTRIBUTION': True,
                'TIME_SEGMENTS': 8,
                'ENABLE_DIVERSITY': True
            },
            'engaging': {
                'MIN_ENGAGEMENT': 0.5,
                'MIN_QUALITY_SCORE': 0.4,
                'WEIGHTS': {
                    'engagement': 0.4,
                    'hook_potential': 0.2,
                    'quality_score': 0.2,
                    'completeness': 0.2
                }
            }
        }
        
        if preset_name in presets:
            for key, value in presets[preset_name].items():
                if hasattr(cls.SelectionStrategy, key):
                    setattr(cls.SelectionStrategy, key, value)
        
        return f"已应用预设: {preset_name}"

# ===========================================
# 便捷调优函数
# ===========================================

def tune_quality_threshold(quality=0.4, completeness=0.5, engagement=0.3):
    """快速调整质量阈值"""
    PromptConfig.SelectionStrategy.MIN_QUALITY_SCORE = quality
    PromptConfig.SelectionStrategy.MIN_COMPLETENESS = completeness
    PromptConfig.SelectionStrategy.MIN_ENGAGEMENT = engagement
    return f"质量阈值已调整: 质量={quality}, 完整性={completeness}, 吸引力={engagement}"

def tune_time_distribution(enable=True, segments=5, max_per_segment=2):
    """快速调整时间分布策略"""
    PromptConfig.SelectionStrategy.ENABLE_TIME_DISTRIBUTION = enable
    PromptConfig.SelectionStrategy.TIME_SEGMENTS = segments
    PromptConfig.SelectionStrategy.MAX_CLIPS_PER_SEGMENT = max_per_segment
    return f"时间分布已调整: 启用={enable}, 分段={segments}, 每段最多={max_per_segment}"

def tune_weights(quality=0.25, completeness=0.20, engagement=0.20, independence=0.15, hook=0.10, conclusion=0.10):
    """快速调整评分权重"""
    PromptConfig.SelectionStrategy.WEIGHTS = {
        'quality_score': quality,
        'completeness': completeness,
        'engagement': engagement,
        'independence': independence,
        'hook_potential': hook,
        'conclusion_strength': conclusion
    }
    return f"权重已调整: {PromptConfig.SelectionStrategy.WEIGHTS}"

# ===========================================
# 使用示例
# ===========================================

if __name__ == "__main__":
    print("=== AI切片器提示词配置 ===")
    print("可用预设:", ['balanced', 'high_quality', 'diverse', 'engaging'])
    print("\n快速调优示例:")
    print("# 提高质量要求")
    print("tune_quality_threshold(quality=0.6, completeness=0.7)")
    print("\n# 启用更好的时间分布")
    print("tune_time_distribution(enable=True, segments=8)")
    print("\n# 优先吸引力")
    print("PromptConfig.apply_preset('engaging')")