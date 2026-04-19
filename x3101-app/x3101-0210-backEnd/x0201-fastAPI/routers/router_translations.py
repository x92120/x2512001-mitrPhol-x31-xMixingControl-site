"""
Translations Router
===================
Serves i18n translations from multiple local JSON files in the 'locales' folder.
Translations are grouped by their key prefix (e.g., prodPlan.json, preBatch.json).

Endpoints:
  GET  /translations/              → all translations (all locales and sections)
  GET  /translations/{locale}      → all key-value pairs for a locale
  PUT  /translations/{locale}/{key} → update/create a single translation
  POST /translations/bulk          → bulk upsert translations
"""

import json
import os
import logging
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Translations"])

# Base Directory Setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
I18N_DIR = os.path.join(BASE_DIR, "x01-frontEnd", "x0101-xMixing", "app", "i18n")
LOCALES_DIR = os.path.join(I18N_DIR, "locales")
IMPORT_PATH = os.path.join(I18N_DIR, "translations_import.json")

# Ensure locales directory exists
if not os.path.exists(LOCALES_DIR):
    os.makedirs(LOCALES_DIR)

# Thread safety for file operations
file_lock = threading.Lock()

def get_prefix(key: str) -> str:
    """Extract section prefix from translation key."""
    return key.split('.')[0] if '.' in key else 'common'

def get_file_path(prefix: str) -> str:
    """Get absolute path for a section's JSON file."""
    return os.path.join(LOCALES_DIR, f"{prefix}.json")

def load_translations():
    """Aggregate all translations from files in the locales directory."""
    full_dict = {"en": {}, "th": {}}
    
    with file_lock:
        if not os.listdir(LOCALES_DIR):
            logger.warning(f"Locales directory empty. No translations loaded.")
            return full_dict

        for filename in os.listdir(LOCALES_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(LOCALES_DIR, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Merge into full_dict
                        for locale in ["en", "th"]:
                            if locale in data:
                                full_dict[locale].update(data[locale])
                except Exception as e:
                    logger.error(f"Error loading {filename}: {e}")
                    
    return full_dict

def update_single_file(prefix: str, locale: str, key: str, value: str):
    """Update or create a translation entry in a specific section file."""
    file_path = get_file_path(prefix)
    
    with file_lock:
        data = {"en": {}, "th": {}}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading {file_path} for update: {e}")
        
        if locale not in data:
            data[locale] = {}
        
        data[locale][key] = value
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            return False

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/translations/")
def get_all_translations():
    """Get all translations aggregated from all section files."""
    return load_translations()


@router.get("/translations/stats")
def get_translation_stats():
    """Get statistics about translations across all files."""
    data = load_translations()
    
    en_keys = set(data.get("en", {}).keys())
    th_keys = set(data.get("th", {}).keys())
    
    all_keys = en_keys.union(th_keys)
    missing_th = [k for k in en_keys if k not in th_keys]

    return {
        "total_keys": len(all_keys),
        "en_count": len(en_keys),
        "th_count": len(th_keys),
        "missing_in_th": missing_th,
        "sections_count": len([f for f in os.listdir(LOCALES_DIR) if f.endswith('.json')])
    }


class BulkTranslation(BaseModel):
    key: str
    locale: str
    value: str


@router.post("/translations/bulk")
def bulk_upsert_translations(items: list[BulkTranslation]):
    """Bulk upsert translations. Sorts items by prefix to minimize file writes."""
    # Group by prefix
    by_prefix = {}
    for item in items:
        prefix = get_prefix(item.key)
        if prefix not in by_prefix:
            by_prefix[prefix] = []
        by_prefix[prefix].append(item)

    success_count = 0
    with file_lock:
        for prefix, items_in_prefix in by_prefix.items():
            file_path = get_file_path(prefix)
            data = {"en": {}, "th": {}}
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception: pass
            
            for item in items_in_prefix:
                if item.locale not in data:
                    data[item.locale] = {}
                data[item.locale][item.key] = item.value
                success_count += 1
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Bulk write failed for {prefix}: {e}")
    
    return {"status": "ok", "upserted": success_count}


@router.get("/translations/{locale}")
def get_translations_by_locale(locale: str):
    """Get all translations for a specific locale."""
    data = load_translations()
    if locale not in data:
        if locale in ("en", "th"):
            return {}
        raise HTTPException(status_code=400, detail="Locale must be 'en' or 'th'")
    
    return data[locale]


class TranslationUpdate(BaseModel):
    value: str


@router.put("/translations/{locale}/{key:path}")
def update_translation(locale: str, key: str, body: TranslationUpdate):
    """Update a single translation value in the appropriate section file."""
    if locale not in ("en", "th"):
        raise HTTPException(status_code=400, detail="Locale must be 'en' or 'th'")

    prefix = get_prefix(key)
    if update_single_file(prefix, locale, key, body.value):
        return {"status": "ok", "key": key, "locale": locale, "value": body.value, "file": f"{prefix}.json"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save translation to file")

