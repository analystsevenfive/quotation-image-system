"""Persistent Quotation History Store (Phase 4)."""
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
from app.models.quotation import QuotationItem


class QuotationHistoryStore:
    """Thread-safe storage for quotation history, PDF files, and session states."""

    def __init__(self, root_dir: str = ".data/history"):
        self.root = Path(root_dir)
        self.files_dir = self.root / "files"
        self.sessions_dir = self.root / "sessions"
        self.images_dir = self.root / "images"
        self.manifest_file = self.root / "manifest.json"
        self.lock = threading.RLock()

        self._manifest: Dict[str, dict] = {}
        self._init_dirs()
        self._load_manifest()

    def _init_dirs(self) -> None:
        with self.lock:
            self.files_dir.mkdir(parents=True, exist_ok=True)
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            self.images_dir.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self) -> None:
        with self.lock:
            if not self.manifest_file.exists():
                self._manifest = {}
                return
            try:
                content = self.manifest_file.read_text(encoding="utf-8")
                data = json.loads(content)
                self._manifest = data if isinstance(data, dict) else {}
            except Exception:
                self._manifest = {}

    def _save_manifest(self) -> None:
        with self.lock:
            tmp = self.manifest_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.manifest_file)

    def save_quotation(self, quotation) -> dict:
        """Persist quotation metadata, original PDF, output PDF, and session snapshot."""
        with self.lock:
            qid = quotation.id

            # 1. Save original PDF if not present
            orig_path = self.files_dir / f"{qid}_original.pdf"
            if not orig_path.exists() and getattr(quotation, "source", None):
                orig_path.write_bytes(quotation.source)

            # 2. Save output PDF if available
            output_path = self.files_dir / f"{qid}_generated.pdf"
            has_output = False
            output_size = 0
            if getattr(quotation, "output", None):
                output_path.write_bytes(quotation.output)
                has_output = True
                output_size = len(quotation.output)
            elif output_path.exists():
                has_output = True
                output_size = output_path.stat().st_size

            # 3. Save images
            q_images_dir = self.images_dir / qid
            q_images_dir.mkdir(parents=True, exist_ok=True)
            saved_images_indices = []
            if hasattr(quotation, "images") and isinstance(quotation.images, dict):
                for idx, img_bytes in quotation.images.items():
                    if img_bytes:
                        (q_images_dir / f"{idx}.img").write_bytes(img_bytes)
                        saved_images_indices.append(idx)

            # 4. Save session state JSON
            session_data = {
                "id": qid,
                "owner": getattr(quotation, "owner", ""),
                "filename": getattr(quotation, "filename", ""),
                "created": getattr(quotation, "created", time.time()),
                "revision": getattr(quotation, "revision", 0),
                "items": [item.model_dump() for item in quotation.items] if hasattr(quotation, "items") else [],
                "uploaded": list(getattr(quotation, "uploaded", set())),
                "saved_images": saved_images_indices,
            }
            session_path = self.sessions_dir / f"{qid}.json"
            session_path.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")

            # 5. Compute metadata
            items = getattr(quotation, "items", [])
            items_count = len(items)
            matched_count = sum(1 for i in items if i.match_status in ("matched", "manual"))
            missing_count = sum(1 for i in items if not i.selected_image_url and not getattr(quotation, "images", {}).get(i.item_number - 1))

            now = time.time()
            existing = self._manifest.get(qid, {})
            meta = {
                "id": qid,
                "filename": getattr(quotation, "filename", "quotation.pdf"),
                "created_at": getattr(quotation, "created", existing.get("created_at", now)),
                "updated_at": now,
                "owner": getattr(quotation, "owner", existing.get("owner", "")),
                "items_count": items_count,
                "matched_count": matched_count,
                "missing_count": missing_count,
                "images_inserted": sum(1 for i in items if getattr(i, "image_inserted", False)),
                "has_output": has_output,
                "output_size": output_size,
                "status": "ready" if has_output else "in_review",
            }
            self._manifest[qid] = meta
            self._save_manifest()
            return meta

    def list_recent(self, limit: int = 50) -> List[dict]:
        """List history entries sorted by updated_at descending."""
        with self.lock:
            records = list(self._manifest.values())
            records.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
            return records[:limit]

    def get_metadata(self, quotation_id: str) -> Optional[dict]:
        with self.lock:
            return self._manifest.get(quotation_id)

    def get_original_pdf(self, quotation_id: str) -> Optional[bytes]:
        path = self.files_dir / f"{quotation_id}_original.pdf"
        if path.exists():
            return path.read_bytes()
        return None

    def get_output_pdf(self, quotation_id: str) -> Optional[bytes]:
        path = self.files_dir / f"{quotation_id}_generated.pdf"
        if path.exists():
            return path.read_bytes()
        return None

    def load_session(self, quotation_id: str) -> Optional[dict]:
        """Load session state and reconstructable data."""
        with self.lock:
            session_path = self.sessions_dir / f"{quotation_id}.json"
            if not session_path.exists():
                return None
            try:
                session_data = json.loads(session_path.read_text(encoding="utf-8"))
            except Exception:
                return None

            # Load original source
            source = self.get_original_pdf(quotation_id)
            if not source:
                return None
            session_data["source"] = source

            # Load output if present
            session_data["output"] = self.get_output_pdf(quotation_id)

            # Load images
            images = {}
            q_images_dir = self.images_dir / quotation_id
            if q_images_dir.exists():
                for img_file in q_images_dir.glob("*.img"):
                    try:
                        idx = int(img_file.stem)
                        images[idx] = img_file.read_bytes()
                    except ValueError:
                        pass
            session_data["images"] = images
            return session_data

    def delete(self, quotation_id: str) -> bool:
        """Delete quotation from history and remove associated files."""
        with self.lock:
            removed = self._manifest.pop(quotation_id, None) is not None
            self._save_manifest()

            for p in (
                self.files_dir / f"{quotation_id}_original.pdf",
                self.files_dir / f"{quotation_id}_generated.pdf",
                self.sessions_dir / f"{quotation_id}.json",
            ):
                if p.exists():
                    p.unlink(missing_ok=True)

            q_images_dir = self.images_dir / quotation_id
            if q_images_dir.exists():
                shutil.rmtree(q_images_dir, ignore_errors=True)

            return removed
