#!/usr/bin/env python3
"""
AI切片器快速调优工具
解决"结果都来自前几分钟"的问题
"""

import os
import sys

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.video_clipping.prompt_config import PromptConfig, tune_quality_threshold, tune_time_distribution, tune_weights

def main():
    print("🎯 AI视频切片调优工具")
    print("=" * 50)
    print()
    
    print("📊 当前配置:")
    config = PromptConfig.SelectionStrategy
    print(f"• 时间分布: {'启用' if config.ENABLE_TIME_DISTRIBUTION else '禁用'}")
    print(f"• 时间分段数: {config.TIME_SEGMENTS}")
    print(f"• 每段最多选择: {config.MAX_CLIPS_PER_SEGMENT}")
    print(f"• 质量阈值: {config.MIN_QUALITY_SCORE}")
    print(f"• 完整性阈值: {config.MIN_COMPLETENESS}")
    print(f"• 吸引力阈值: {config.MIN_ENGAGEMENT}")
    print()
    
    while True:
        print("🔧 可用调优选项:")
        print("1. 修复'前几分钟'问题 - 启用更好的时间分布")
        print("2. 提高质量要求")
        print("3. 降低质量要求（获得更多候选）")
        print("4. 调整评分权重")
        print("5. 应用预设配置")
        print("6. 显示当前配置")
        print("0. 退出")
        print()
        
        choice = input("请选择 (0-6): ").strip()
        
        if choice == "1":
            print("\n🎯 修复'前几分钟'问题...")
            # 启用时间分布，增加分段数，降低质量要求以获得更多候选
            tune_time_distribution(enable=True, segments=8, max_per_segment=1)
            tune_quality_threshold(quality=0.3, completeness=0.4, engagement=0.2)
            print("✅ 已优化时间分布策略")
            print("• 将视频分为8段，每段最多选1个片段")
            print("• 降低质量要求以获得更多候选")
            print("• 现在切片将更均匀分布在整个视频中")
            
        elif choice == "2":
            print("\n⬆️ 提高质量要求...")
            tune_quality_threshold(quality=0.6, completeness=0.7, engagement=0.5)
            print("✅ 已提高质量阈值")
            print("• 只选择高质量片段")
            print("• 可能会减少候选数量")
            
        elif choice == "3":
            print("\n⬇️ 降低质量要求...")
            tune_quality_threshold(quality=0.2, completeness=0.3, engagement=0.1)
            print("✅ 已降低质量阈值")
            print("• 将获得更多候选片段")
            print("• 适合内容较少的视频")
            
        elif choice == "4":
            print("\n⚖️ 调整评分权重...")
            print("当前权重:", PromptConfig.SelectionStrategy.WEIGHTS)
            print("1. 优先内容质量")
            print("2. 优先吸引力") 
            print("3. 优先完整性")
            print("4. 平衡所有指标")
            
            weight_choice = input("选择权重策略 (1-4): ").strip()
            if weight_choice == "1":
                tune_weights(quality=0.4, completeness=0.2, engagement=0.2, independence=0.1, hook=0.05, conclusion=0.05)
                print("✅ 已设置为优先内容质量")
            elif weight_choice == "2":
                tune_weights(quality=0.2, completeness=0.15, engagement=0.4, independence=0.1, hook=0.1, conclusion=0.05)
                print("✅ 已设置为优先吸引力")
            elif weight_choice == "3":
                tune_weights(quality=0.2, completeness=0.4, engagement=0.15, independence=0.15, hook=0.05, conclusion=0.05)
                print("✅ 已设置为优先完整性")
            elif weight_choice == "4":
                tune_weights()  # 使用默认平衡权重
                print("✅ 已恢复平衡权重")
            
        elif choice == "5":
            print("\n📋 预设配置:")
            print("1. balanced - 平衡配置（默认）")
            print("2. high_quality - 高质量优先")
            print("3. diverse - 多样性优先")
            print("4. engaging - 吸引力优先")
            
            preset = input("选择预设 (1-4): ").strip()
            preset_map = {"1": "balanced", "2": "high_quality", "3": "diverse", "4": "engaging"}
            
            if preset in preset_map:
                result = PromptConfig.apply_preset(preset_map[preset])
                print(f"✅ {result}")
            
        elif choice == "6":
            print("\n📊 当前完整配置:")
            config = PromptConfig.SelectionStrategy
            print(f"时间分布策略: {config.ENABLE_TIME_DISTRIBUTION}")
            print(f"时间分段数: {config.TIME_SEGMENTS}")
            print(f"每段最多片段: {config.MAX_CLIPS_PER_SEGMENT}")
            print(f"质量阈值: {config.MIN_QUALITY_SCORE}")
            print(f"完整性阈值: {config.MIN_COMPLETENESS}")
            print(f"独立性阈值: {config.MIN_INDEPENDENCE}")
            print(f"吸引力阈值: {config.MIN_ENGAGEMENT}")
            print(f"评分权重: {config.WEIGHTS}")
            
        elif choice == "0":
            break
            
        print("\n" + "="*50 + "\n")
    
    print("\n🎉 调优完成！")
    print("💡 提示: 配置更改立即生效，无需重启服务")
    print("🚀 现在可以测试新的切片效果了")

if __name__ == "__main__":
    main()