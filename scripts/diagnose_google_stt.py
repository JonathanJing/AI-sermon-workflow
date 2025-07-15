#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot Google Cloud Speech-to-Text setup
"""

import sys
import logging
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.stt.google_stt import GoogleSTTService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_environment():
    """Check environment variables and configuration"""
    logger.info("=== Environment Check ===")
    
    issues = []
    
    # Check Google Cloud credentials
    credentials_path = settings.google_cloud.credentials_path
    if not credentials_path:
        issues.append("GOOGLE_APPLICATION_CREDENTIALS not set")
    else:
        if not Path(credentials_path).exists():
            issues.append(f"Credentials file not found: {credentials_path}")
        else:
            logger.info(f"✅ Credentials file found: {credentials_path}")
    
    # Check project ID
    project_id = settings.google_cloud.project_id
    if not project_id:
        issues.append("GOOGLE_CLOUD_PROJECT not set")
    else:
        logger.info(f"✅ Project ID set: {project_id}")
    
    # Check language code
    language_code = settings.stt.language_code
    logger.info(f"✅ Language code: {language_code}")
    
    # Check environment variables directly
    env_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    env_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    logger.info(f"Environment variables:")
    logger.info(f"  GOOGLE_APPLICATION_CREDENTIALS: {env_creds}")
    logger.info(f"  GOOGLE_CLOUD_PROJECT: {env_project}")
    
    if issues:
        logger.error("❌ Configuration issues found:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    
    logger.info("✅ Environment configuration looks good")
    return True


def check_imports():
    """Check if required libraries can be imported"""
    logger.info("=== Import Check ===")
    
    try:
        from google.cloud import speech_v1p1beta1
        logger.info("✅ google-cloud-speech imported successfully")
    except ImportError as e:
        logger.error(f"❌ google-cloud-speech import failed: {e}")
        return False
    
    try:
        from google.cloud import storage
        logger.info("✅ google-cloud-storage imported successfully")
    except ImportError as e:
        logger.warning(f"⚠️ google-cloud-storage import failed: {e}")
        logger.warning("This is optional - needed only for long audio files (>60s)")
    
    try:
        from google.api_core import exceptions
        logger.info("✅ google-api-core imported successfully")
    except ImportError as e:
        logger.error(f"❌ google-api-core import failed: {e}")
        return False
    
    return True


def check_stt_service():
    """Test STT service initialization"""
    logger.info("=== STT Service Check ===")
    
    try:
        stt_service = GoogleSTTService()
        
        if not stt_service.client:
            logger.error("❌ STT client not initialized")
            return False
        
        logger.info("✅ STT service initialized successfully")
        
        # Test health check
        health = stt_service.health_check()
        logger.info(f"Health check result: {health}")
        
        if health.get("status") == "healthy":
            logger.info("✅ STT service is healthy")
            return True
        else:
            logger.error("❌ STT service is not healthy")
            return False
            
    except Exception as e:
        logger.error(f"❌ STT service initialization failed: {e}")
        return False


def check_credentials_content():
    """Check if credentials file has proper content"""
    logger.info("=== Credentials Content Check ===")
    
    credentials_path = settings.google_cloud.credentials_path
    if not credentials_path:
        logger.error("❌ No credentials path configured")
        return False
    
    creds_path = Path(credentials_path)
    if not creds_path.exists():
        logger.error(f"❌ Credentials file not found: {credentials_path}")
        return False
    
    try:
        import json
        with open(credentials_path, 'r') as f:
            creds = json.load(f)
        
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in creds]
        
        if missing_fields:
            logger.error(f"❌ Missing required fields in credentials: {missing_fields}")
            return False
        
        logger.info(f"✅ Credentials file has required fields")
        logger.info(f"  - Type: {creds.get('type')}")
        logger.info(f"  - Project ID: {creds.get('project_id')}")
        logger.info(f"  - Client email: {creds.get('client_email')}")
        
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in credentials file: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error reading credentials file: {e}")
        return False


def run_comprehensive_diagnosis():
    """Run comprehensive diagnosis"""
    logger.info("Google Cloud Speech-to-Text Diagnostic Tool")
    logger.info("=" * 50)
    
    checks = [
        ("Environment Configuration", check_environment),
        ("Import Dependencies", check_imports),
        ("Credentials Content", check_credentials_content),
        ("STT Service Initialization", check_stt_service),
    ]
    
    results = []
    for check_name, check_func in checks:
        logger.info(f"\n{check_name}...")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            logger.error(f"❌ {check_name} failed with exception: {e}")
            results.append((check_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("DIAGNOSIS SUMMARY")
    logger.info("=" * 50)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {check_name}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        logger.info("🎉 All checks passed! Google STT should be working.")
        return True
    else:
        logger.info("❌ Some checks failed. Please fix the issues above.")
        
        # Provide specific guidance
        logger.info("\n📋 TROUBLESHOOTING STEPS:")
        logger.info("1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install")
        logger.info("2. Create service account: https://cloud.google.com/iam/docs/service-accounts-create")
        logger.info("3. Enable Speech-to-Text API: https://console.cloud.google.com/apis/library/speech.googleapis.com")
        logger.info("4. Download service account key as JSON")
        logger.info("5. Set environment variables:")
        logger.info("   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json")
        logger.info("   export GOOGLE_CLOUD_PROJECT=your-project-id")
        logger.info("6. Restart the application")
        
        return False


if __name__ == "__main__":
    success = run_comprehensive_diagnosis()
    sys.exit(0 if success else 1)