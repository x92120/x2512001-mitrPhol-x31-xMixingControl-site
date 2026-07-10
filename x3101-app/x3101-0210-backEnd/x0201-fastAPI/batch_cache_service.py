"""
batch_cache_service.py — Local Recipe Cache (P2 Emergency Fallback)
Purpose: When MySQL is unreachable, serve recipe from local JSON file.
Cache is written at batch start and used as last-resort fallback.
Author: PIYAPONG N. | 2026-07-10
"""
import json, os, logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "batch_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def save_batch_cache(batch_id: str, data: Dict[str, Any]) -> bool:
    """
    Save batch recipe + metadata to local JSON cache.
    Called at batch start (when DB is still alive).
    """
    try:
        path = os.path.join(CACHE_DIR, f"{batch_id}.json")
        payload = {
            "batch_id": batch_id,
            "cached_at": datetime.now().isoformat(),
            **data
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"[BatchCache] Saved cache for batch {batch_id} → {path}")
        return True
    except Exception as e:
        logger.error(f"[BatchCache] Failed to save {batch_id}: {e}")
        return False


def load_batch_cache(batch_id: str) -> Optional[Dict[str, Any]]:
    """
    Load batch recipe from local cache.
    Returns None if cache not found.
    """
    try:
        path = os.path.join(CACHE_DIR, f"{batch_id}.json")
        if not os.path.exists(path):
            logger.warning(f"[BatchCache] No cache file for batch {batch_id}")
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"[BatchCache] Loaded cache for batch {batch_id} (cached at {data.get('cached_at')})")
        return data
    except Exception as e:
        logger.error(f"[BatchCache] Failed to load {batch_id}: {e}")
        return None


def get_latest_cache() -> Optional[Dict[str, Any]]:
    """
    Get the most recently cached batch (used when batch_id unknown after crash).
    """
    try:
        files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
        if not files:
            return None
        latest = max(files, key=lambda f: os.path.getmtime(os.path.join(CACHE_DIR, f)))
        return load_batch_cache(latest.replace(".json", ""))
    except Exception as e:
        logger.error(f"[BatchCache] get_latest_cache error: {e}")
        return None


def list_cached_batches() -> list:
    """Return list of cached batch_ids with metadata."""
    try:
        result = []
        for fname in sorted(os.listdir(CACHE_DIR)):
            if not fname.endswith(".json"): continue
            path = os.path.join(CACHE_DIR, fname)
            try:
                with open(path) as f:
                    d = json.load(f)
                result.append({
                    "batch_id": d.get("batch_id"),
                    "cached_at": d.get("cached_at"),
                    "sku_id": d.get("sku_id"),
                    "plant_id": d.get("plant_id"),
                    "step_count": len(d.get("steps", [])),
                })
            except Exception:
                pass
        return result
    except Exception as e:
        logger.error(f"[BatchCache] list error: {e}")
        return []
