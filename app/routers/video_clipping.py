"""
视频切片API路由
提供视频自动切片的完整API接口
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import uuid
import json
from datetime import datetime
import logging

from ..services.video_clipping.srt_parser import SRTParser
from ..services.video_clipping.ai_slicer import AISlicer
from ..services.video_clipping.video_cutter import VideoCutter
from ..services.video_clipping.validator import VideoValidator
from ..services.video_clipping.title_tagger import TitleTagger
from ..services.gemini_client import get_global_client
from ..config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video-clipping", tags=["视频切片"])

# 数据模型
class ClippingRequest(BaseModel):
    """切片请求模型"""
    srt_file_path: str
    video_file_path: str
    min_duration: float = 10.0
    max_duration: float = 60.0
    target_count: int = 5
    enable_validation: bool = True
    enable_title_generation: bool = True
    quality_threshold: float = 0.5

# 简化配置 - 使用默认设置
# 不再需要手动配置，系统自动使用环境设置

class ClippingStatus(BaseModel):
    """切片状态模型"""
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: float
    message: str
    created_at: str
    updated_at: str

# 全局状态
jobs_status = {}  # 任务状态跟踪

# 移除配置接口 - 使用默认配置
# 系统启动时自动初始化

@router.post("/clip", summary="创建视频切片任务")
async def create_clipping_job(
    background_tasks: BackgroundTasks,
    request: ClippingRequest
):
    """创建视频切片任务"""
    # 检查Gemini客户端是否可用
    if not get_global_client():
        raise HTTPException(status_code=400, detail="Gemini客户端未初始化，请检查API密钥")
    
    # 验证文件存在
    if not os.path.exists(request.srt_file_path):
        raise HTTPException(status_code=404, detail="SRT文件不存在")
    
    if not os.path.exists(request.video_file_path):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    # 创建任务ID
    job_id = str(uuid.uuid4())
    
    # 初始化任务状态
    jobs_status[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0.0,
        "message": "任务已创建，等待处理",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "request": request.dict(),
        "results": None
    }
    
    # 添加后台任务
    background_tasks.add_task(process_clipping_job, job_id, request)
    
    return {
        "success": True,
        "job_id": job_id,
        "message": "切片任务已创建",
        "status_url": f"/video-clipping/status/{job_id}"
    }

@router.get("/status/{job_id}", summary="查询任务状态")
async def get_job_status(job_id: str):
    """查询切片任务状态"""
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return jobs_status[job_id]

@router.get("/jobs", summary="获取所有任务")
async def get_all_jobs():
    """获取所有切片任务"""
    return {
        "jobs": list(jobs_status.values()),
        "total": len(jobs_status)
    }

@router.get("/results/{job_id}", summary="获取切片结果")
async def get_clipping_results(job_id: str):
    """获取切片任务的详细结果"""
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    job = jobs_status[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")
    
    return job["results"]

@router.get("/download/{job_id}/{clip_index}", summary="下载切片文件")
async def download_clip(job_id: str, clip_index: int):
    """下载指定的切片文件"""
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    job = jobs_status[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")
    
    results = job["results"]
    if not results or "clips" not in results:
        raise HTTPException(status_code=404, detail="切片结果不存在")
    
    clips = results["clips"]
    if clip_index >= len(clips) or clip_index < 0:
        raise HTTPException(status_code=404, detail="切片索引无效")
    
    clip = clips[clip_index]
    if not clip.get("success", False):
        raise HTTPException(status_code=404, detail="切片文件生成失败")
    
    file_path = clip.get("output_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="切片文件不存在")
    
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=f"clip_{clip_index+1}_{job_id[:8]}.mp4"
    )

@router.post("/upload", summary="上传文件并创建切片任务")
async def upload_and_clip(
    background_tasks: BackgroundTasks,
    srt_file: UploadFile = File(...),
    video_file: UploadFile = File(...),
    min_duration: float = Form(10.0),
    max_duration: float = Form(60.0),
    target_count: int = Form(5),
    enable_validation: bool = Form(True),
    enable_title_generation: bool = Form(True)
):
    """上传SRT和视频文件并创建切片任务"""
    # 检查Gemini客户端是否可用
    if not get_global_client():
        raise HTTPException(status_code=400, detail="Gemini客户端未初始化，请检查API密钥")
    
    try:
        # 创建上传目录
        upload_dir = os.path.join(settings.OUTPUT_DIR, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        # 保存上传的文件
        job_id = str(uuid.uuid4())
        
        # 保存SRT文件
        srt_filename = f"{job_id}_{srt_file.filename}"
        srt_path = os.path.join(upload_dir, srt_filename)
        with open(srt_path, "wb") as f:
            content = await srt_file.read()
            f.write(content)
        
        # 保存视频文件
        video_filename = f"{job_id}_{video_file.filename}"
        video_path = os.path.join(upload_dir, video_filename)
        with open(video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # 创建切片请求
        request = ClippingRequest(
            srt_file_path=srt_path,
            video_file_path=video_path,
            min_duration=min_duration,
            max_duration=max_duration,
            target_count=target_count,
            enable_validation=enable_validation,
            enable_title_generation=enable_title_generation
        )
        
        # 初始化任务状态
        jobs_status[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": 0.0,
            "message": "文件上传完成，等待处理",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "request": request.dict(),
            "uploaded_files": {
                "srt_file": srt_filename,
                "video_file": video_filename
            },
            "results": None
        }
        
        # 添加后台任务
        background_tasks.add_task(process_clipping_job, job_id, request)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "文件上传成功，切片任务已创建",
            "uploaded_files": {
                "srt_file": srt_filename,
                "video_file": video_filename
            },
            "status_url": f"/video-clipping/status/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.delete("/job/{job_id}", summary="删除任务")
async def delete_job(job_id: str):
    """删除切片任务和相关文件"""
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        job = jobs_status[job_id]
        
        # 删除生成的切片文件
        if job.get("results") and job["results"].get("clips"):
            for clip in job["results"]["clips"]:
                if clip.get("success") and clip.get("output_path"):
                    if os.path.exists(clip["output_path"]):
                        os.remove(clip["output_path"])
                    
                    # 删除字幕文件
                    if clip.get("subtitle_path") and os.path.exists(clip["subtitle_path"]):
                        os.remove(clip["subtitle_path"])
                    
                    # 删除带字幕的视频文件
                    if clip.get("subtitled_path") and os.path.exists(clip["subtitled_path"]):
                        os.remove(clip["subtitled_path"])
        
        # 删除上传的文件
        if job.get("uploaded_files"):
            upload_dir = os.path.join(settings.OUTPUT_DIR, "uploads")
            for file_type, filename in job["uploaded_files"].items():
                file_path = os.path.join(upload_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        # 删除任务记录
        del jobs_status[job_id]
        
        return {
            "success": True,
            "message": "任务已删除"
        }
        
    except Exception as e:
        logger.error(f"删除任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")

@router.post("/reprocess/{job_id}", summary="重新处理已有任务")
async def reprocess_job(job_id: str, background_tasks: BackgroundTasks):
    """使用现有job_id重新触发切片处理"""
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    job = jobs_status[job_id]
    
    # 检查是否有原始请求数据
    if "request" not in job:
        raise HTTPException(status_code=400, detail="任务缺少原始请求信息")
    
    # 检查Gemini客户端是否可用
    if not get_global_client():
        raise HTTPException(status_code=400, detail="Gemini客户端未初始化，请检查API密钥")
    
    # 重建请求对象
    request_data = job["request"]
    request = ClippingRequest(**request_data)
    
    # 验证文件是否仍然存在
    if not os.path.exists(request.srt_file_path):
        raise HTTPException(status_code=404, detail="原SRT文件已不存在")
    
    if not os.path.exists(request.video_file_path):
        raise HTTPException(status_code=404, detail="原视频文件已不存在")
    
    # 重置任务状态
    jobs_status[job_id].update({
        "status": "pending",
        "progress": 0.0,
        "message": "重新处理任务",
        "updated_at": datetime.now().isoformat(),
        "results": None
    })
    
    # 添加后台任务
    background_tasks.add_task(process_clipping_job, job_id, request)
    
    return {
        "success": True,
        "job_id": job_id,
        "message": "任务已重新开始处理",
        "status_url": f"/video-clipping/status/{job_id}"
    }

@router.get("/summary", summary="获取服务摘要")
async def get_service_summary():
    """获取服务状态摘要"""
    total_jobs = len(jobs_status)
    completed_jobs = len([j for j in jobs_status.values() if j["status"] == "completed"])
    failed_jobs = len([j for j in jobs_status.values() if j["status"] == "failed"])
    processing_jobs = len([j for j in jobs_status.values() if j["status"] == "processing"])
    
    return {
        "service_configured": get_global_client() is not None,
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "processing_jobs": processing_jobs,
        "pending_jobs": total_jobs - completed_jobs - failed_jobs - processing_jobs,
        "output_directory": settings.OUTPUT_DIR
    }

# 后台任务处理函数
async def process_clipping_job(job_id: str, request: ClippingRequest):
    """处理切片任务的后台函数"""
    try:
        # 更新状态为处理中
        update_job_status(job_id, "processing", 0.1, "开始处理...")
        
        # 获取全局Gemini客户端
        gemini_client = get_global_client()
        if not gemini_client:
            raise Exception("Gemini客户端未初始化")
        
        # 初始化服务组件
        ai_slicer = AISlicer(gemini_client)
        video_cutter = VideoCutter(settings.OUTPUT_DIR)
        validator = VideoValidator(gemini_client if request.enable_validation else None)
        title_tagger = TitleTagger(gemini_client) if request.enable_title_generation else None
        
        # 步骤1：生成切片计划
        update_job_status(job_id, "processing", 0.2, "分析SRT文件，生成切片计划...")
        clip_plan = ai_slicer.generate_clip_plan(
            request.srt_file_path,
            request.min_duration,
            request.max_duration,
            request.target_count
        )
        
        if not clip_plan:
            update_job_status(job_id, "failed", 0.0, "无法生成有效的切片计划")
            return
        
        # 步骤2：执行视频切片
        update_job_status(job_id, "processing", 0.4, f"切片视频，共{len(clip_plan)}个片段...")
        clip_results = video_cutter.cut_video_segments(request.video_file_path, clip_plan)
        
        # 步骤3：质量验证
        validation_results = None
        if request.enable_validation:
            update_job_status(job_id, "processing", 0.6, "验证切片质量...")
            validation_results = validator.validate_clip_batch(clip_results)
        
        # 步骤4：生成标题和标签
        if request.enable_title_generation and title_tagger:
            update_job_status(job_id, "processing", 0.8, "生成标题和标签...")
            for i, clip_result in enumerate(clip_results):
                if clip_result.get("success", False):
                    try:
                        social_package = title_tagger.create_social_media_package(
                            clip_result.get("full_text", ""),
                            clip_result.get("metadata", {})
                        )
                        clip_result["social_media"] = social_package
                    except Exception as e:
                        logger.warning(f"切片{i}标题生成失败: {str(e)}")
        
        # 步骤5：创建摘要
        update_job_status(job_id, "processing", 0.9, "生成结果摘要...")
        summary = video_cutter.create_clips_summary(clip_results)
        
        # 步骤6：完成任务
        final_results = {
            "job_id": job_id,
            "clips": clip_results,
            "summary": summary,
            "validation": validation_results,
            "clip_plan": clip_plan,
            "request_params": request.dict()
        }
        
        # 保存结果到文件
        results_path = os.path.join(settings.OUTPUT_DIR, f"{job_id}_results.json")
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)
        
        final_results["results_file"] = results_path
        
        update_job_status(job_id, "completed", 1.0, "切片任务完成", final_results)
        
    except Exception as e:
        logger.error(f"处理任务{job_id}失败: {str(e)}")
        update_job_status(job_id, "failed", 0.0, f"处理失败: {str(e)}")

def update_job_status(job_id: str, status: str, progress: float, message: str, results: Dict = None):
    """更新任务状态"""
    if job_id in jobs_status:
        jobs_status[job_id].update({
            "status": status,
            "progress": progress,
            "message": message,
            "updated_at": datetime.now().isoformat()
        })
        
        if results:
            jobs_status[job_id]["results"] = results