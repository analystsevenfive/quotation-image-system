"""Image preparation and saved placements shared by review and generation."""
from app.services.pdf.visible_text import visible_words
import fitz
from app.services.pdf.fitter import calculate_safe_placement, get_image_dimensions
from app.services.pdf.placement import editing_bounds, normalized_box, from_normalized, validate_placement
from app.services.images.uploads import normalize_uploaded_image
from app.models.quotation import MatchStatus, MatchMethod, BoundingBox


def prepare_images(service, quotation):
    with fitz.open(stream=quotation.source, filetype='pdf') as doc:
        page_words = {}
        for index, item in enumerate(quotation.items):
            data = quotation.images.get(index)
            if data is None and item.matched_product:
                data = service.image(item.matched_product)
                if data:
                    quotation.images[index] = data
            item.image_bbox = None
            if data:
                page = doc[item.page_number-1]
                if item.page_number not in page_words:
                    page_words[item.page_number] = visible_words(page)
                dimensions = get_image_dimensions(data)
                item.image_bbox = item.manual_image_bbox or calculate_safe_placement(
                    item.bbox, *dimensions, page_words[item.page_number], service.renderer.template)
                item.error_message = None if item.image_bbox else 'No safe image placement'
            elif item.matched_product:
                item.error_message = 'Product image unavailable'


def replace_image(service, quotation, index, data):
    if not 0 <= index < len(quotation.items):
        raise KeyError(index)
    clean = normalize_uploaded_image(data)
    with quotation.lock:
        if sum(len(v) for k, v in quotation.images.items() if k != index) + len(clean) > 64*1024*1024:
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
        prepare_images(service, quotation)
        if getattr(service, 'history_store', None):
            service.history_store.save_quotation(quotation)


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
        prepare_images(service, quotation)
        if getattr(service, 'history_store', None):
            service.history_store.save_quotation(quotation)


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
            page = doc[item.page_number-1]
            box = from_normalized(rect, page) if rect else None
            if box:
                validate_placement(box, item, page, get_image_dimensions(data), service.renderer.template)
            service.push_history(quotation)
            item.manual_image_bbox = box
        item.image_inserted = False
        quotation.output = None
        quotation.revision += 1
        prepare_images(service, quotation)
        if getattr(service, 'history_store', None):
            service.history_store.save_quotation(quotation)


def editor_view(service, quotation):
    with fitz.open(stream=quotation.source, filetype='pdf') as doc:
        result = []
        for index, item in enumerate(quotation.items):
            page = doc[item.page_number-1]
            bounds = editing_bounds(item, page, service.renderer.template)
            data = quotation.images.get(index)
            width, height = get_image_dimensions(data) if data else (0, 0)
            result.append({
                'has_image': bool(data), 'uploaded_image': index in quotation.uploaded,
                'image_url': f'/api/quotations/{quotation.id}/items/{index}/image?v={quotation.revision}' if data else None,
                'placement': normalized_box(item.image_bbox, page),
                'bounds': normalized_box(bounds, page),
                'image_aspect': width/height if height else None,
                'manual_placement': item.manual_image_bbox is not None,
            })
        pages = [{'width': page.rect.width, 'height': page.rect.height,
                  'text': [normalized_box(BoundingBox(x0=w[0], y0=w[1], x1=w[2], y1=w[3]), page)
                           for w in visible_words(page)]}
                 for page in doc]
        return result, pages
