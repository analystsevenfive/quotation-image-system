"""Image preparation and saved placements shared by review and generation."""
import logging
import math
import threading
from app.services.pdf.visible_text import visible_words
import fitz
from app.services.pdf.fitter import calculate_safe_placement, get_image_dimensions
from app.services.pdf.placement import editing_bounds, normalized_box, from_normalized, validate_placement
from app.services.images.uploads import normalize_uploaded_image
from app.models.quotation import MatchStatus, MatchMethod, BoundingBox

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dim-based helpers: accept page width/height as plain numbers so we can
# work without a live fitz.Page object on warm-path calls.
# ---------------------------------------------------------------------------

def _bounds_d(item, pw, ph, template):
    """Compute editing bounds using numeric page dimensions."""
    return BoundingBox(
        x0=max(0, item.bbox.x0, template.desc_col_x0) + template.image_top_margin,
        y0=max(0, item.bbox.y0) + template.image_top_margin,
        x1=min(pw, item.bbox.x1, template.desc_col_x1, template.qty_col_x0) - template.image_right_margin,
        y1=min(ph, item.bbox.y1) - template.image_bottom_margin,
    )


def _norm_d(box, pw, ph):
    """Normalise a BoundingBox to [0,1] using numeric page dimensions."""
    if box is None:
        return None
    return {"x": box.x0 / pw, "y": box.y0 / ph,
            "width": box.width / pw, "height": box.height / ph}


def _denorm_d(rect, pw, ph):
    """Convert a normalised Placement rect to absolute BoundingBox coordinates."""
    return BoundingBox(
        x0=rect.x * pw, y0=rect.y * ph,
        x1=(rect.x + rect.width) * pw,
        y1=(rect.y + rect.height) * ph,
    )


def _validate_d(box, item, pw, ph, dimensions, template, words):
    """Validate placement using numeric page dims and cached words (no fitz.Page)."""
    if not all(math.isfinite(v) for v in (box.x0, box.y0, box.x1, box.y1)):
        raise ValueError("ตำแหน่งรูปไม่ถูกต้อง")
    bounds = _bounds_d(item, pw, ph, template)
    epsilon = 0.01
    if (box.x0 < bounds.x0 - epsilon or box.y0 < bounds.y0 - epsilon
            or box.x1 > bounds.x1 + epsilon or box.y1 > bounds.y1 + epsilon):
        raise ValueError("กรุณาวางรูปภายในกรอบ DESCRIPTION ของรายการนี้")
    if min(box.width, box.height) < 5:
        raise ValueError("รูปเล็กเกินไป กรุณาขยายรูปเล็กน้อย")
    aspect = dimensions[0] / dimensions[1]
    if abs(box.width / box.height / aspect - 1) > 0.005:
        raise ValueError("กรุณาปรับขนาดโดยรักษาสัดส่วนเดิมของรูป")
    if words and any(box.x0 < w[2] and box.x1 > w[0] and box.y0 < w[3] and box.y1 > w[1] for w in words):
        raise ValueError("รูปทับข้อความ กรุณาเลื่อนหรือย่อรูปให้อยู่ในช่องว่าง")


def _get_dims(quotation, index, data):
    """Return (width, height) for an image; compute-and-cache on first call."""
    cache = quotation._image_dims_cache
    if index not in cache:
        cache[index] = get_image_dimensions(data)
    return cache[index]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _save_history_bg(history_store, quotation):
    """Persist session state in a daemon background thread (fire-and-forget).

    Failures are logged but never surfaced to the caller.
    """
    def _run():
        try:
            history_store.save_quotation(quotation)
        except Exception:
            _log.exception("Background history save failed for %s", quotation.id)
    threading.Thread(target=_run, daemon=True).start()


def _maybe_save(service, quotation):
    if getattr(service, "history_store", None):
        _save_history_bg(service.history_store, quotation)


# ---------------------------------------------------------------------------
# Core image preparation
# ---------------------------------------------------------------------------

def prepare_images(service, quotation, indices=None):
    """Recalculate image placement bounding boxes.

    Pass *indices* to limit work to specific items (fast path).
    Omit for full recalculation (initial load, undo/redo).

    Warm-path: if all target pages are in _page_words_cache, skips
    fitz.open entirely and runs as pure Python.
    """
    page_words = quotation._page_words_cache
    targets = list(indices) if indices is not None else range(len(quotation.items))

    # Identify pages whose visible_words are not yet cached.
    pages_needed = {
        quotation.items[i].page_number
        for i in targets
        if 0 <= i < len(quotation.items)
        and quotation.items[i].page_number not in page_words
    }

    if pages_needed:
        # Cold path: open PDF once, cache words for all needed pages.
        with fitz.open(stream=quotation.source, filetype="pdf") as doc:
            for pnum in pages_needed:
                page_words[pnum] = visible_words(doc[pnum - 1])

    # Process items — no PDF open required beyond this point.
    for index in targets:
        if not 0 <= index < len(quotation.items):
            continue
        item = quotation.items[index]
        data = quotation.images.get(index)
        if data is None and item.matched_product:
            data = service.image(item.matched_product)
            if data:
                quotation.images[index] = data
                quotation._image_dims_cache.pop(index, None)
        item.image_bbox = None
        if data:
            dimensions = _get_dims(quotation, index, data)
            item.image_bbox = item.manual_image_bbox or calculate_safe_placement(
                item.bbox, *dimensions, page_words[item.page_number],
                service.renderer.template)
            item.error_message = None if item.image_bbox else "No safe image placement"
        elif item.matched_product:
            item.error_message = "Product image unavailable"


# ---------------------------------------------------------------------------
# Mutation operations
# ---------------------------------------------------------------------------

def replace_image(service, quotation, index, data):
    if not 0 <= index < len(quotation.items):
        raise KeyError(index)
    clean = normalize_uploaded_image(data)
    with quotation.lock:
        if sum(len(v) for k, v in quotation.images.items() if k != index) + len(clean) > 64 * 1024 * 1024:
            raise ValueError("รูปในเอกสารรวมกันเกิน 64 MB กรุณาย่อรูปก่อนอัปโหลด")
        service.push_history(quotation)
        quotation.images[index] = clean
        quotation._image_dims_cache.pop(index, None)
        quotation.uploaded.add(index)
        item = quotation.items[index]
        item.manual_image_bbox = None
        item.match_status, item.match_method = MatchStatus.MANUAL, MatchMethod.MANUAL
        item.selected_image_url = None
        item.image_inserted = False
        quotation.output = None
        quotation.revision += 1
    prepare_images(service, quotation, [index])
    _maybe_save(service, quotation)


def delete_images(service, quotation, indices):
    with quotation.lock:
        to_delete = []
        for index in indices:
            if 0 <= index < len(quotation.items):
                item = quotation.items[index]
                if index in quotation.images or item.matched_product or item.selected_image_url:
                    to_delete.append(index)
        if not to_delete:
            return
        service.push_history(quotation)
        for index in to_delete:
            quotation.images.pop(index, None)
            quotation._image_dims_cache.pop(index, None)
            quotation.uploaded.discard(index)
            item = quotation.items[index]
            item.matched_product = None
            item.selected_image_url = None
            item.manual_image_bbox = None
            item.image_bbox = None
            item.image_inserted = False
            item.match_status = MatchStatus.MISSING
            item.match_method = MatchMethod.MANUAL
            item.error_message = None
        quotation.output = None
        quotation.revision += 1
    # prepare_images skipped: all affected items fully cleaned up above.
    _maybe_save(service, quotation)


def delete_image(service, quotation, index):
    if not 0 <= index < len(quotation.items):
        raise KeyError(index)
    delete_images(service, quotation, [index])


def save_placement(service, quotation, index, rect):
    with quotation.lock:
        if not 0 <= index < len(quotation.items):
            raise KeyError(index)
        item = quotation.items[index]
        data = quotation.images.get(index)
        if not data:
            raise ValueError("กรุณาเลือกรูปหรืออัปโหลดรูปก่อนปรับตำแหน่ง")

        dims = _get_dims(quotation, index, data)
        pages_meta = quotation._pages_meta_cache

        if pages_meta and 0 <= item.page_number - 1 < len(pages_meta):
            # Warm path: cached page dims available — no fitz.open needed.
            pm = pages_meta[item.page_number - 1]
            pw, ph = pm["width"], pm["height"]
            box = _denorm_d(rect, pw, ph) if rect else None
            if box:
                words = quotation._page_words_cache.get(item.page_number, [])
                _validate_d(box, item, pw, ph, dims, service.renderer.template, words)
        else:
            # Cold path: first edit before editor_view has run (rare).
            with fitz.open(stream=quotation.source, filetype="pdf") as doc:
                page = doc[item.page_number - 1]
                box = from_normalized(rect, page) if rect else None
                if box:
                    validate_placement(box, item, page, dims, service.renderer.template)

        service.push_history(quotation)
        item.manual_image_bbox = box
    item.image_inserted = False
    quotation.output = None
    quotation.revision += 1
    prepare_images(service, quotation, [index])
    _maybe_save(service, quotation)


# ---------------------------------------------------------------------------
# Read-only view (builds the API response after every mutation)
# ---------------------------------------------------------------------------

def _build_item_views(service, quotation):
    """Build per-item view dicts from cached metadata — no PDF file opened."""
    pages_meta = quotation._pages_meta_cache
    template = service.renderer.template
    result = []
    for index, item in enumerate(quotation.items):
        pm = pages_meta[item.page_number - 1]
        pw, ph = pm["width"], pm["height"]
        bounds = _bounds_d(item, pw, ph, template)
        data = quotation.images.get(index)
        if data:
            width, height = _get_dims(quotation, index, data)
        else:
            width, height = 0, 0
        result.append({
            "has_image": bool(data),
            "uploaded_image": index in quotation.uploaded,
            "image_url": f"/api/quotations/{quotation.id}/items/{index}/image?v={quotation.revision}"
                         if data else None,
            "placement": _norm_d(item.image_bbox, pw, ph),
            "bounds": _norm_d(bounds, pw, ph),
            "image_aspect": width / height if height else None,
            "manual_placement": item.manual_image_bbox is not None,
        })
    return result


def editor_view(service, quotation):
    """Build the full editor view for the API response.

    Warm path (pages_meta_cache populated after the first call per session):
      - No fitz.open, no PIL open, no text parsing.
      - Total cost: O(n) pure-Python dict/list work.

    Cold path (very first call after upload):
      - Opens PDF once to fill page_words_cache and pages_meta_cache.
      - All subsequent calls use the warm path.
    """
    if quotation._pages_meta_cache is not None:
        return _build_item_views(service, quotation), quotation._pages_meta_cache

    # Cold path: populate caches, then build result.
    page_words = quotation._page_words_cache
    with fitz.open(stream=quotation.source, filetype="pdf") as doc:
        pages = []
        for pnum, page in enumerate(doc, 1):
            if pnum not in page_words:
                page_words[pnum] = visible_words(page)
            words = page_words[pnum]
            pages.append({
                "width": page.rect.width, "height": page.rect.height,
                "text": [normalized_box(BoundingBox(x0=w[0], y0=w[1], x1=w[2], y1=w[3]), page)
                         for w in words],
            })
        quotation._pages_meta_cache = pages

    return _build_item_views(service, quotation), quotation._pages_meta_cache
