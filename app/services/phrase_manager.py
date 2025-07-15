import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


class PhraseManager:
    """Service for managing religious and domain-specific phrases for STT"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "phrases.json"
        self.phrases_data = self._load_phrases()
    
    def _load_phrases(self) -> Dict[str, Any]:
        """Load phrases from JSON configuration file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded {data.get('metadata', {}).get('total_phrases', 0)} phrases from {self.config_path}")
                return data
        except FileNotFoundError:
            logger.error(f"Phrases config file not found: {self.config_path}")
            return self._get_default_phrases()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in phrases config: {e}")
            return self._get_default_phrases()
        except Exception as e:
            logger.error(f"Error loading phrases config: {e}")
            return self._get_default_phrases()
    
    def _get_default_phrases(self) -> Dict[str, Any]:
        """Return default phrases if config file is unavailable"""
        return {
            "religious_terms": {
                "chinese": ["阿门", "哈利路亚", "主耶稣", "神", "圣经", "福音", "祷告", "赞美"],
                "english": ["Amen", "Hallelujah", "Jesus Christ", "God", "Bible", "Gospel", "Prayer", "Praise"]
            },
            "categories": {
                "basic_terms": ["阿门", "哈利路亚", "主耶稣", "神", "圣经", "福音", "祷告", "赞美"]
            },
            "metadata": {
                "version": "1.0",
                "description": "Default religious phrases",
                "languages_supported": ["chinese", "english"],
                "total_phrases": 16
            }
        }
    
    def get_phrases_for_language(self, language_code: str) -> List[str]:
        """Get phrases for specific language code"""
        try:
            # Map language codes to our config keys
            language_mapping = {
                "cmn-Hans-CN": "chinese",
                "cmn-Hant-TW": "chinese", 
                "zh-CN": "chinese",
                "zh-TW": "chinese",
                "en-US": "english",
                "en-GB": "english"
            }
            
            language_key = language_mapping.get(language_code, "chinese")
            phrases = self.phrases_data.get("religious_terms", {}).get(language_key, [])
            
            logger.info(f"Retrieved {len(phrases)} phrases for language {language_code}")
            return phrases
            
        except Exception as e:
            logger.error(f"Error getting phrases for language {language_code}: {e}")
            return []
    
    def get_phrases_by_category(self, category: str) -> List[str]:
        """Get phrases by category"""
        try:
            categories = self.phrases_data.get("categories", {})
            phrases = categories.get(category, [])
            
            logger.info(f"Retrieved {len(phrases)} phrases for category {category}")
            return phrases
            
        except Exception as e:
            logger.error(f"Error getting phrases for category {category}: {e}")
            return []
    
    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        return list(self.phrases_data.get("categories", {}).keys())
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return self.phrases_data.get("metadata", {}).get("languages_supported", [])
    
    def add_phrase(self, phrase: str, language: str, category: Optional[str] = None) -> bool:
        """Add a new phrase to the configuration"""
        try:
            # Add to language-specific terms
            if language not in self.phrases_data["religious_terms"]:
                self.phrases_data["religious_terms"][language] = []
            
            if phrase not in self.phrases_data["religious_terms"][language]:
                self.phrases_data["religious_terms"][language].append(phrase)
                logger.info(f"Added phrase '{phrase}' to language {language}")
            
            # Add to category if specified
            if category:
                if category not in self.phrases_data["categories"]:
                    self.phrases_data["categories"][category] = []
                
                if phrase not in self.phrases_data["categories"][category]:
                    self.phrases_data["categories"][category].append(phrase)
                    logger.info(f"Added phrase '{phrase}' to category {category}")
            
            return self._save_phrases()
            
        except Exception as e:
            logger.error(f"Error adding phrase '{phrase}': {e}")
            return False
    
    def remove_phrase(self, phrase: str, language: str, category: Optional[str] = None) -> bool:
        """Remove a phrase from the configuration"""
        try:
            # Remove from language-specific terms
            if language in self.phrases_data["religious_terms"]:
                if phrase in self.phrases_data["religious_terms"][language]:
                    self.phrases_data["religious_terms"][language].remove(phrase)
                    logger.info(f"Removed phrase '{phrase}' from language {language}")
            
            # Remove from category if specified
            if category and category in self.phrases_data["categories"]:
                if phrase in self.phrases_data["categories"][category]:
                    self.phrases_data["categories"][category].remove(phrase)
                    logger.info(f"Removed phrase '{phrase}' from category {category}")
            
            return self._save_phrases()
            
        except Exception as e:
            logger.error(f"Error removing phrase '{phrase}': {e}")
            return False
    
    def update_category(self, category: str, phrases: List[str]) -> bool:
        """Update an entire category with new phrases"""
        try:
            self.phrases_data["categories"][category] = phrases
            logger.info(f"Updated category {category} with {len(phrases)} phrases")
            return self._save_phrases()
            
        except Exception as e:
            logger.error(f"Error updating category {category}: {e}")
            return False
    
    def _save_phrases(self) -> bool:
        """Save phrases data back to JSON file"""
        try:
            # Update metadata
            if "metadata" not in self.phrases_data:
                self.phrases_data["metadata"] = {}
            
            # Count total phrases
            total_phrases = 0
            for lang_phrases in self.phrases_data.get("religious_terms", {}).values():
                total_phrases += len(lang_phrases)
            
            self.phrases_data["metadata"]["total_phrases"] = total_phrases
            self.phrases_data["metadata"]["last_updated"] = "2025-07-15"
            
            # Save to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.phrases_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved phrases configuration to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving phrases configuration: {e}")
            return False
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the phrases configuration"""
        return self.phrases_data.get("metadata", {})
    
    def reload_config(self) -> bool:
        """Reload phrases configuration from file"""
        try:
            self.phrases_data = self._load_phrases()
            logger.info("Phrases configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error reloading phrases configuration: {e}")
            return False
    
    def search_phrases(self, query: str, language: Optional[str] = None) -> List[str]:
        """Search for phrases containing the query string"""
        try:
            results = []
            
            # Search in specific language or all languages
            if language:
                phrases = self.phrases_data.get("religious_terms", {}).get(language, [])
                results.extend([p for p in phrases if query.lower() in p.lower()])
            else:
                for lang_phrases in self.phrases_data.get("religious_terms", {}).values():
                    results.extend([p for p in lang_phrases if query.lower() in p.lower()])
            
            # Remove duplicates while preserving order
            seen = set()
            unique_results = []
            for phrase in results:
                if phrase not in seen:
                    seen.add(phrase)
                    unique_results.append(phrase)
            
            logger.info(f"Found {len(unique_results)} phrases matching '{query}'")
            return unique_results
            
        except Exception as e:
            logger.error(f"Error searching phrases for '{query}': {e}")
            return []
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate the phrases configuration"""
        try:
            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "stats": {}
            }
            
            # Check required sections
            required_sections = ["religious_terms", "categories", "metadata"]
            for section in required_sections:
                if section not in self.phrases_data:
                    validation_result["errors"].append(f"Missing required section: {section}")
                    validation_result["valid"] = False
            
            # Check for empty phrase lists
            for lang, phrases in self.phrases_data.get("religious_terms", {}).items():
                if not phrases:
                    validation_result["warnings"].append(f"Empty phrase list for language: {lang}")
            
            # Calculate statistics
            total_phrases = 0
            for lang_phrases in self.phrases_data.get("religious_terms", {}).values():
                total_phrases += len(lang_phrases)
            
            validation_result["stats"] = {
                "total_phrases": total_phrases,
                "languages": len(self.phrases_data.get("religious_terms", {})),
                "categories": len(self.phrases_data.get("categories", {}))
            }
            
            return validation_result
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "stats": {}
            }