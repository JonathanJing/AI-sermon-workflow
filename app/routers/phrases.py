from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from app.services.phrase_manager import PhraseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phrases", tags=["phrases"])

# Initialize phrase manager
phrase_manager = PhraseManager()


class PhraseRequest(BaseModel):
    phrase: str
    language: str
    category: Optional[str] = None


class CategoryUpdateRequest(BaseModel):
    category: str
    phrases: List[str]


class PhraseSearchRequest(BaseModel):
    query: str
    language: Optional[str] = None


@router.get("/", response_model=Dict[str, Any])
async def get_all_phrases():
    """Get all phrases organized by language and category"""
    try:
        return phrase_manager.phrases_data
    except Exception as e:
        logger.error(f"Error getting all phrases: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve phrases")


@router.get("/language/{language_code}", response_model=List[str])
async def get_phrases_by_language(language_code: str):
    """Get phrases for a specific language"""
    try:
        phrases = phrase_manager.get_phrases_for_language(language_code)
        return phrases
    except Exception as e:
        logger.error(f"Error getting phrases for language {language_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve phrases for language {language_code}")


@router.get("/category/{category}", response_model=List[str])
async def get_phrases_by_category(category: str):
    """Get phrases for a specific category"""
    try:
        phrases = phrase_manager.get_phrases_by_category(category)
        if not phrases:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
        return phrases
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting phrases for category {category}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve phrases for category {category}")


@router.get("/categories", response_model=List[str])
async def get_all_categories():
    """Get list of all available categories"""
    try:
        return phrase_manager.get_all_categories()
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve categories")


@router.get("/languages", response_model=List[str])
async def get_supported_languages():
    """Get list of supported languages"""
    try:
        return phrase_manager.get_supported_languages()
    except Exception as e:
        logger.error(f"Error getting supported languages: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve supported languages")


@router.post("/", response_model=Dict[str, str])
async def add_phrase(request: PhraseRequest):
    """Add a new phrase"""
    try:
        success = phrase_manager.add_phrase(
            phrase=request.phrase,
            language=request.language,
            category=request.category
        )
        
        if success:
            return {"message": f"Phrase '{request.phrase}' added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add phrase")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding phrase '{request.phrase}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add phrase: {str(e)}")


@router.delete("/", response_model=Dict[str, str])
async def remove_phrase(request: PhraseRequest):
    """Remove a phrase"""
    try:
        success = phrase_manager.remove_phrase(
            phrase=request.phrase,
            language=request.language,
            category=request.category
        )
        
        if success:
            return {"message": f"Phrase '{request.phrase}' removed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove phrase")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing phrase '{request.phrase}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove phrase: {str(e)}")


@router.put("/category", response_model=Dict[str, str])
async def update_category(request: CategoryUpdateRequest):
    """Update an entire category with new phrases"""
    try:
        success = phrase_manager.update_category(
            category=request.category,
            phrases=request.phrases
        )
        
        if success:
            return {"message": f"Category '{request.category}' updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update category")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating category '{request.category}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")


@router.post("/search", response_model=List[str])
async def search_phrases(request: PhraseSearchRequest):
    """Search for phrases containing the query string"""
    try:
        results = phrase_manager.search_phrases(
            query=request.query,
            language=request.language
        )
        return results
    except Exception as e:
        logger.error(f"Error searching phrases for '{request.query}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search phrases: {str(e)}")


@router.get("/metadata", response_model=Dict[str, Any])
async def get_metadata():
    """Get metadata about the phrases configuration"""
    try:
        return phrase_manager.get_metadata()
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metadata")


@router.post("/reload", response_model=Dict[str, str])
async def reload_config():
    """Reload phrases configuration from file"""
    try:
        success = phrase_manager.reload_config()
        if success:
            return {"message": "Phrases configuration reloaded successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reload configuration")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {str(e)}")


@router.get("/validate", response_model=Dict[str, Any])
async def validate_config():
    """Validate the phrases configuration"""
    try:
        validation_result = phrase_manager.validate_config()
        return validation_result
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate configuration")


@router.get("/export", response_model=Dict[str, Any])
async def export_phrases():
    """Export all phrases for backup or migration"""
    try:
        return phrase_manager.phrases_data
    except Exception as e:
        logger.error(f"Error exporting phrases: {e}")
        raise HTTPException(status_code=500, detail="Failed to export phrases")


@router.post("/import", response_model=Dict[str, str])
async def import_phrases(phrases_data: Dict[str, Any]):
    """Import phrases from backup or external source"""
    try:
        # Validate the imported data structure
        required_keys = ["religious_terms", "categories", "metadata"]
        for key in required_keys:
            if key not in phrases_data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid data structure: missing '{key}' section"
                )
        
        # Replace current data
        phrase_manager.phrases_data = phrases_data
        
        # Save to file
        success = phrase_manager._save_phrases()
        if success:
            return {"message": "Phrases imported successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save imported phrases")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing phrases: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import phrases: {str(e)}")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for phrase management service"""
    try:
        metadata = phrase_manager.get_metadata()
        return {
            "status": "healthy",
            "phrase_manager": "operational",
            "total_phrases": metadata.get("total_phrases", 0),
            "languages": len(phrase_manager.get_supported_languages()),
            "categories": len(phrase_manager.get_all_categories())
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Service unhealthy")