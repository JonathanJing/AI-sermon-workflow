#!/usr/bin/env python3
"""
Batch transcription CLI tool

Usage:
    python scripts/batch_transcribe.py input.csv
    python -m scripts.batch_transcribe input.csv
"""

import sys
import csv
import logging
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
import click
import httpx
from datetime import datetime

# Add the app directory to the path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models import TranscriptionRequest, SourceType, JobStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchTranscriber:
    """Batch transcription processor"""
    
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or f"http://{settings.api.host}:{settings.api.port}/api/v1"
        self.api_key = api_key or settings.api.key
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def submit_job(self, source_type: str, source: str, title: str = None) -> str:
        """Submit a transcription job"""
        try:
            request_data = {
                "source_type": source_type,
                "title": title
            }
            
            if source_type == "youtube":
                request_data["url"] = source
            else:
                request_data["file_path"] = source
            
            response = await self.client.post(
                f"{self.api_url}/jobs/transcribe",
                json=request_data
            )
            
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return result["job_id"]
            
        except Exception as e:
            logger.error(f"Failed to submit job: {str(e)}")
            raise
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status"""
        try:
            response = await self.client.get(f"{self.api_url}/jobs/{job_id}")
            
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code} - {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            raise
    
    async def wait_for_completion(self, job_id: str, timeout: int = 3600) -> Dict[str, Any]:
        """Wait for job completion"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                status = await self.get_job_status(job_id)
                
                if status["status"] == "succeeded":
                    return status
                elif status["status"] == "failed":
                    raise Exception(f"Job failed: {status.get('error_message', 'Unknown error')}")
                
                # Wait before checking again
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error checking job status: {str(e)}")
                await asyncio.sleep(10)
        
        raise Exception(f"Job {job_id} timed out after {timeout} seconds")
    
    async def process_batch(self, jobs: List[Dict[str, Any]], concurrent_jobs: int = 3) -> List[Dict[str, Any]]:
        """Process a batch of jobs"""
        results = []
        
        # Create semaphore to limit concurrent jobs
        semaphore = asyncio.Semaphore(concurrent_jobs)
        
        async def process_single_job(job_data: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    logger.info(f"Processing job: {job_data.get('title', job_data.get('source'))}")
                    
                    # Submit job
                    job_id = await self.submit_job(
                        source_type=job_data["source_type"],
                        source=job_data["source"],
                        title=job_data.get("title")
                    )
                    
                    logger.info(f"Job submitted with ID: {job_id}")
                    
                    # Wait for completion
                    result = await self.wait_for_completion(job_id)
                    
                    logger.info(f"Job {job_id} completed successfully")
                    
                    return {
                        "input": job_data,
                        "job_id": job_id,
                        "status": "completed",
                        "result": result
                    }
                    
                except Exception as e:
                    logger.error(f"Job failed: {str(e)}")
                    return {
                        "input": job_data,
                        "job_id": None,
                        "status": "failed",
                        "error": str(e)
                    }
        
        # Process jobs concurrently
        tasks = [process_single_job(job) for job in jobs]
        results = await asyncio.gather(*tasks)
        
        return results


def load_csv_file(file_path: str) -> List[Dict[str, Any]]:
    """Load jobs from CSV file"""
    jobs = []
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Validate required fields
                if not row.get('source_type') or not row.get('source'):
                    logger.warning(f"Skipping invalid row: {row}")
                    continue
                
                # Validate source type
                if row['source_type'] not in ['youtube', 'file']:
                    logger.warning(f"Invalid source_type: {row['source_type']}")
                    continue
                
                jobs.append({
                    'source_type': row['source_type'],
                    'source': row['source'],
                    'title': row.get('title', ''),
                    'metadata': {k: v for k, v in row.items() if k not in ['source_type', 'source', 'title']}
                })
        
        logger.info(f"Loaded {len(jobs)} jobs from {file_path}")
        return jobs
        
    except FileNotFoundError:
        logger.error(f"CSV file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading CSV file: {str(e)}")
        raise


def save_results(results: List[Dict[str, Any]], output_path: str):
    """Save results to CSV file"""
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'input_source_type', 'input_source', 'input_title',
                'job_id', 'status', 'error',
                'duration_seconds', 'file_size_mb', 'stt_cost_usd',
                'audio_download_url', 'transcript_download_url',
                'srt_download_url', 'vtt_download_url'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                row = {
                    'input_source_type': result['input']['source_type'],
                    'input_source': result['input']['source'],
                    'input_title': result['input'].get('title', ''),
                    'job_id': result.get('job_id', ''),
                    'status': result['status'],
                    'error': result.get('error', '')
                }
                
                # Add result details if successful
                if result['status'] == 'completed' and result.get('result'):
                    job_result = result['result']
                    if job_result.get('results'):
                        results_data = job_result['results']
                        row.update({
                            'duration_seconds': results_data.get('duration_seconds', ''),
                            'file_size_mb': results_data.get('file_size_mb', ''),
                            'stt_cost_usd': results_data.get('stt_cost_usd', ''),
                            'audio_download_url': results_data.get('audio_download_url', ''),
                            'transcript_download_url': results_data.get('transcript_download_url', ''),
                            'srt_download_url': results_data.get('srt_download_url', ''),
                            'vtt_download_url': results_data.get('vtt_download_url', '')
                        })
                
                writer.writerow(row)
        
        logger.info(f"Results saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving results: {str(e)}")
        raise


@click.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', default=None, help='Output CSV file path')
@click.option('--api-url', default=None, help='API URL')
@click.option('--api-key', default=None, help='API key')
@click.option('--concurrent-jobs', '-c', default=3, help='Number of concurrent jobs')
@click.option('--timeout', '-t', default=3600, help='Timeout per job in seconds')
async def main(input_file: str, output: str, api_url: str, api_key: str, concurrent_jobs: int, timeout: int):
    """
    Batch transcription CLI tool
    
    INPUT_FILE: CSV file with columns: source_type, source, title (optional)
    
    Example CSV format:
    source_type,source,title
    youtube,https://www.youtube.com/watch?v=VIDEOID,Sunday Sermon
    file,/path/to/audio.mp3,Wednesday Service
    """
    
    # Generate output filename if not provided
    if not output:
        input_path = Path(input_file)
        output = str(input_path.parent / f"{input_path.stem}_results.csv")
    
    logger.info(f"Starting batch transcription: {input_file} -> {output}")
    logger.info(f"Concurrent jobs: {concurrent_jobs}, Timeout: {timeout}s")
    
    try:
        # Load jobs from CSV
        jobs = load_csv_file(input_file)
        
        if not jobs:
            logger.error("No valid jobs found in input file")
            return
        
        # Process jobs
        async with BatchTranscriber(api_url=api_url, api_key=api_key) as transcriber:
            results = await transcriber.process_batch(jobs, concurrent_jobs)
        
        # Save results
        save_results(results, output)
        
        # Print summary
        completed = len([r for r in results if r['status'] == 'completed'])
        failed = len([r for r in results if r['status'] == 'failed'])
        
        logger.info(f"Batch processing completed: {completed} succeeded, {failed} failed")
        
        if failed > 0:
            logger.warning("Some jobs failed. Check the results file for details.")
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    # Handle both sync and async execution
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Batch processing interrupted by user")
        sys.exit(1) 