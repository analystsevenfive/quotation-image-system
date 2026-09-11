"""Image preparation and saved placements shared by review and generation."""
import logging
import threading
from app.services.pdf.visible_text import visible_words
import fitz
from app.services.pdf.fitter import calculate_safe_placement, get_image_dimensions
from app.services.pdf.placement import editing_bounds, normalized_box, from_normalized, validate_placement
from app.services.images.uploads import normalize_uploaded_image
from app.models.quotation import MatchStatus, MatchMethod, BoundingBox

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _save_history_bg(history_store, quotation):
    """Persist session state in a background thread (fire-and-forget).

    History I/O is non-critical: failures are logged but never surfaced to the
    caller, so the user-facing response is never delayed by disk or network.
    """
    def _run():
        try:
            history_store.save_quotation(quotation)
        except Exception:
            _log.exception('Background history save failed for %s', quotation.id)

    threading.Thread(target=_run, daemon=True).start()


def _maybe_save(service, quotation):
    if getattr(service, 'history_store', None):
        _save_history_bg(service.history_store, quotation)


# ---------------------------------------------------------------------------
# Core image preparation
# ---------------------------------------------------------------------------

def prepare_images(service, quotation, indices=None):
    """Recalculate image placement bounding boxes.

    Parameters
    ----------
    indices:
        When provided, only the listed item indices are recalculated.
        This is the fast path for single-item edits (drag, upload,
        select-product) — avoids iterating 100 items just to touch 1.
        Pass ``None`` (default) to recalculate every item, e.g. on initial
        load or after undo/redo where many items may have changed.

    Performance notes
    -----------------
    * ``quotation._page_words_cache`` caches visible_words() per page number.
      The PDF source is immutable per session, so these results never change.
    * Opening the fitz document is unavoidable for the first call per page,
      but subsequent calls for the *same* pages skip visible_words() entirely.
    """
    page_words = quotation._page_words_cache   # shared cache, never stale
    targets = list(indices) if indices is not None else range(len(quotation.items))

    with fitz.open(stream=quotation.source, filetype='pdf') as doc:
        for index in targets:
            if not 0 <= index < len(quotation.items):
                continue
            item = quotation.items[index]
            data = quotation.images.get(index)
            if data is None and item.matched_product:
                data = service.image(item.matched_product)
                if data:
                    quotation.images[index] = data
            item.image_bbox = None
            if data:
                page = doc[item.page_number - 1]
                if item.page_number not in page_words:
                    page_words[item.page_number] = visible_words(page)
                dimensions = get_image_dimensions(data)
                item.image_bbox = item.manual_image_bbox or calculate_safe_placement(
                    item.bbox, *dimensions, page_words[item.page_number],
                    service.renderer.template)
                item.error_message = None if item.image_bbox else 'No safe image placement'
            elif item.matched_product:
                item.error_message = 'Product image unavailable'


# ---------------------------------------------------------------------------
# Mutation operations
# ---------------------------------------------------------------------------

def replace_image(service, quotation, index, data):
    if not 0 <= index < len(quotation.items):
        raise KeyError(index)
    clean = normalize_uploaded_image(data)
    with quotation.lock:
        if sum(len(v) for k, v in quotation.images.items() if k != index) + len(clean) > 64 * 1024 * 1024:
            raise ValueError('รูปในเอกสารรวมกันเกิน 64 MB กรุณาย่อรูปก่อนอัปโหลด')
        service.push_history(quotation)
        quotation.images[index] = clean
        quotation.uploaded.add(index)
        item = quotation.items[index]
        item.manual_image_bbox = None
        item.match_status, item.match_method = MatchStatus.MANUAL, MatchMethod.MANUAL
        item.selected_image_url = None
        item.image_inserted = False
        quotation.output = None
        quotation.revision += 1
    # Recalculate ONLY this item — outside the lock.
    # The uploaded image bytes are already in quotation.images[index], so no
    # CDN fetch is needed; this call resolves placement in < 20 ms.
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
    # prepare_images intentionally skipped: every affected item is fully
    # cleaned up inside the lock above.  Opening the PDF just to confirm
    # "still no image" would waste 50–500 ms for zero benefit.
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
            raise ValueError('กรุณาเลือกรูปหรืออัปโหลดรูปก่อนปรับตำแหน่ง')
        with fitz.open(stream=quotation.source, filetype='pdf') as doc:
            page = doc[item.page_number - 1]
            box = from_normalized(rect, page) if rect else None
            if box:
                validate_placement(box, item, page, get_image_dimensions(data),
                                   service.renderer.template)
            service.push_history(quotation)
            item.manual_image_bbox = box
    item.image_inserted = False
    quotation.output = None
    quotation.revision += 1
    # Recalculate ONLY this item — replaces the previous full 100-item pass.
    prepare_images(service, quotation, [index])
    _maybe_save(service, quotation)


# ---------------------------------------------------------------------------
# Read-only view (called after every mutation to build the API response)
# ---------------------------------------------------------------------------

def editor_view(service, quotation):
    with fitz.open(stream=quotation.source, filetype='pdf') as doc:
        result = []
        for index, item in enumerate(quotation.items):
            page = doc[item.page_number - 1]
            bounds = editing_bounds(item, page, service.renderer.template)
            data = quotation.images.get(index)
            width, height = get_image_dimensions(data) if data else (0, 0)
            result.append({
                'has_image': bool(data), 'uploaded_image': index in quotation.uploaded,
                'image_url': f'/api/quotations/{quotation.id}/items/{index}/image?v={quotation.revision}'
                             if data else None,
                'placement': normalized_box(item.image_bbox, page),
                'bounds': normalized_box(bounds, page),
                'image_aspect': width / height if height else None,
                'manual_placement': item.manual_image_bbox is not None,
            })

        # Pages metadata (dimensions + text positions) is derived purely from
        # the immutable PDF source.  Compute once and cache; all subsequent
        # calls return the cached list in O(1) without re-opening the document.
        if quotation._pages_meta_cache is None:
            page_words = quotation._page_words_cache
            pages = []
            for pnum, page in enumerate(doc, 1):
                if pnum not in page_words:
                    page_words[pnum] = visible_words(page)
                words = page_words[pnum]
                pages.append({
                    'width': page.rect.width, 'height': page.rect.height,
                    'text': [normalized_box(BoundingBox(x0=w[0], y0=w[1], x1=w[2], y1=w[3]), page)
                             for w in words],
                })
            quotation._pages_meta_cache = pages

        return result, quotation._pages_meta_cache
