"""Persistent Manual Product Mappings Store (Phase 3)."""
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
from app.services.matching.normalizer import normalize_sku


class MappingStore:
    """Thread-safe persistent storage for user-defined SKU to Product mappings."""

    def __init__(self, file_path: str = ".data/mappings.json"):
        self.file_path = Path(file_path)
        self.lock = threading.RLock()
        self._mappings: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        with self.lock:
            if not self.file_path.exists():
                self._mappings = {}
                return
            try:
                content = self.file_path.read_text(encoding="utf-8")
                if not content.strip():
                    self._mappings = {}
                    return
                data = json.loads(content)
                self._mappings = data if isinstance(data, dict) else {}
            except Exception:
                self._mappings = {}

    def _save(self) -> None:
        with self.lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.file_path.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(self._mappings, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp_file, self.file_path)

    def get(self, detected_value: Optional[str]) -> Optional[int]:
        """Look up product_id for detected_value (raw or normalized)."""
        if not detected_value:
            return None
        raw = detected_value.strip()
        norm = normalize_sku(raw)
        with self.lock:
            if raw in self._mappings:
                return self._mappings[raw].get("product_id")
            if norm in self._mappings:
                return self._mappings[norm].get("product_id")
        return None

    def set(self, detected_value: str, product_id: int, note: str = "") -> None:
        """Record or update a mapping."""
        if not detected_value:
            return
        raw = detected_value.strip()
        norm = normalize_sku(raw)
        now = time.time()
        record = {
            "detected_value": raw,
            "normalized_value": norm,
            "product_id": product_id,
            "updated_at": now,
            "note": note,
        }
        with self.lock:
            self._mappings[raw] = record
            if norm and norm != raw:
                self._mappings[norm] = record
            self._save()

    def delete(self, detected_value: str) -> bool:
        """Delete a mapping."""
        if not detected_value:
            return False
        raw = detected_value.strip()
        norm = normalize_sku(raw)
        removed = False
        with self.lock:
            if raw in self._mappings:
                del self._mappings[raw]
                removed = True
            if norm in self._mappings:
                del self._mappings[norm]
                removed = True
            if removed:
                self._save()
        return removed

    def list_all(self) -> List[dict]:
        """List distinct mappings sorted by most recently updated."""
        with self.lock:
            seen = set()
            result = []
            for record in self._mappings.values():
                key = (record.get("normalized_value") or record.get("detected_value"), record.get("product_id"))
                if key not in seen:
                    seen.add(key)
                    result.append(record)
            result.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
            return result
