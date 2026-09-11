"""Local quotation sessions, isolated by an unguessable browser session token."""
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import fitz
from app.core.template import SEVEN_FIVE_TEMPLATE
from app.models.quotation import MatchMethod, MatchStatus, QuotationItem
from app.services.images.downloader import ImageDownloader
from app.services.pdf.parser import QuotationPDFParser
from app.services.pdf.renderer import QuotationPDFRenderer
from app.services.editor import prepare_images, editor_view
from app.services.matching.mappings import MappingStore
from app.services.history import QuotationHistoryStore


@dataclass
class Quotation:
    id: str
    owner: str
    filename: str
    source: bytes
    items: list
    created: float = field(default_factory=time.time)
    output: bytes | None = None
    images: dict = field(default_factory=dict)
    uploaded: set = field(default_factory=set)
    revision: int = 0
    lock: object = field(default_factory=threading.RLock)
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)
    # Derived caches — never persisted, never snapshotted for undo/redo.
    # visible_words() results per page (keyed by 1-based page number).
    # The PDF source is immutable per session so these never go stale.
    _page_words_cache: dict = field(default_factory=dict, repr=False)
    # Serialised pages metadata sent to the frontend (width/height/text).
    # Computed once on first editor_view() call and reused thereafter.
    _pages_meta_cache: object = field(default=None, repr=False)

    # Cache for PIL image dimensions per item index: {index: (width, height)}.
    # Cleared when images change (replace, delete, undo, redo).
    _image_dims_cache: dict = field(default_factory=dict, repr=False)

def snapshot_state(quotation):
    return {
        'items': [item.model_copy(deep=True) for item in quotation.items],
        'images': quotation.images.copy(),
        'uploaded': quotation.uploaded.copy(),
    }


def push_history(quotation, max_depth=30):
    quotation.undo_stack.append(snapshot_state(quotation))
    if len(quotation.undo_stack) > max_depth:
        quotation.undo_stack.pop(0)
    quotation.redo_stack.clear()


class QuotationService:
    def __init__(self, catalog, template=SEVEN_FIVE_TEMPLATE, downloader=None, max_sessions=50, mapping_store=None, history_store=None):
        self.catalog = catalog
        self.mapping_store = mapping_store or getattr(catalog, 'mapping_store', None)
        if self.mapping_store:
            self.catalog.set_mapping_store(self.mapping_store)
        self.history_store = history_store
        self.parser = QuotationPDFParser(template)
        self.renderer = QuotationPDFRenderer(template)
        self.downloader = downloader or ImageDownloader()
        self.quotations = {}
        self.lock = threading.RLock()
        self.max_sessions = max_sessions

    def create(self, owner, filename, source):
        if not source.startswith(b'%PDF-'):
            raise ValueError('Please upload a valid PDF file')
        try:
            with fitz.open(stream=source, filetype='pdf') as document:
                if document.needs_pass:
                    raise ValueError('Password-protected PDFs are not supported')
                if len(document) > 100:
                    raise ValueError('PDF must contain at most 100 pages')
                if any(page.rotation for page in document):
                    raise ValueError('กรุณาใช้ PDF แนวตั้งต้นฉบับที่ไม่มีการหมุนหน้า เพื่อให้ตำแหน่งรูปตรงกับเอกสาร')
            page_words = {}
            items = self.parser.parse(source, page_words_cache=page_words)
        except ValueError:
            raise
        except Exception:
            raise ValueError('Cannot read this PDF. Use a PDF with selectable text.') from None
        if not items:
            raise ValueError('No quotation items found. Check that the quotation uses the supported template.')
        for item in items:
            match = self.catalog.matcher.match(item.detected_sku, item.detected_model)
            item.match_status, item.match_method = match.status, match.method
            item.matched_product, item.candidate_products = match.product, match.candidates
            item.match_confidence = match.confidence
            item.selected_image_url = match.product.image_url if match.product else None
        quotation = Quotation(
            secrets.token_hex(16),
            owner,
            Path(filename.replace('\\', '/')).name,
            source,
            items,
            _page_words_cache=page_words,
        )
        prepare_images(self, quotation)
        with self.lock:
            self.quotations = {k: q for k, q in self.quotations.items() if time.time() - q.created < 86400}
            if len(self.quotations) >= self.max_sessions:
                raise ValueError('Workspace is full. Restart the local API to clear temporary quotations.')
            self.quotations[quotation.id] = quotation
        if self.history_store:
            self.history_store.save_quotation(quotation)
        return quotation

    def get(self, identifier, owner=None):
        with self.lock:
            q = self.quotations.get(identifier)
            if q:
                if owner and q.owner != owner:
                    raise KeyError(identifier)
                return q
            # Try reloading from history_store if present
            if self.history_store:
                session_data = self.history_store.load_session(identifier)
                if session_data:
                    if owner and session_data.get('owner') and session_data.get('owner') != owner:
                        raise KeyError(identifier)
                    items = [QuotationItem.model_validate(i) for i in session_data.get('items', [])]
                    reloaded = Quotation(
                        id=session_data['id'],
                        owner=session_data.get('owner', owner or ''),
                        filename=session_data.get('filename', 'quotation.pdf'),
                        source=session_data['source'],
                        items=items,
                        created=session_data.get('created', time.time()),
                        output=session_data.get('output'),
                        images=session_data.get('images', {}),
                        uploaded=set(session_data.get('uploaded', [])),
                        revision=session_data.get('revision', 0),
                    )
                    prepare_images(self, reloaded)
                    self.quotations[reloaded.id] = reloaded
                    return reloaded
            raise KeyError(identifier)

    def delete_history(self, identifier, owner=None):
        with self.lock:
            self.quotations.pop(identifier, None)
            if self.history_store:
                return self.history_store.delete(identifier)
            return False

    def push_history(self, quotation, max_depth=30):
        push_history(quotation, max_depth)

    def undo(self, quotation):
        with quotation.lock:
            if not quotation.undo_stack:
                return False
            quotation.redo_stack.append(snapshot_state(quotation))
            prev = quotation.undo_stack.pop()
            quotation.items = prev['items']
            quotation.images = prev['images']
            quotation._image_dims_cache.clear()  # images changed - dims stale
            quotation.uploaded = prev['uploaded']
            quotation.output = None
            quotation.revision += 1
            prepare_images(self, quotation)
            if self.history_store:
                self.history_store.save_quotation(quotation)
            return True

    def redo(self, quotation):
        with quotation.lock:
            if not quotation.redo_stack:
                return False
            quotation.undo_stack.append(snapshot_state(quotation))
            next_state = quotation.redo_stack.pop()
            quotation.items = next_state['items']
            quotation.images = next_state['images']
            quotation.uploaded = next_state['uploaded']
            quotation._image_dims_cache.clear()  # images changed - dims stale
            quotation.output = None
            quotation.revision += 1
            prepare_images(self, quotation)
            if self.history_store:
                self.history_store.save_quotation(quotation)
            return True

    def select(self, quotation, index, product_id):
        with quotation.lock:
            if index < 0 or index >= len(quotation.items) or product_id not in self.catalog.by_id:
                raise KeyError('Product or item not found')
            self.push_history(quotation)
            item = quotation.items[index]
            item.matched_product = self.catalog.by_id[product_id]
            item.selected_image_url = item.matched_product.image_url
            item.match_status, item.match_method = MatchStatus.MANUAL, MatchMethod.MANUAL
            item.error_message, item.image_inserted = None, False
            item.manual_image_bbox = None
            quotation.images.pop(index, None)
            quotation.uploaded.discard(index)
            quotation.revision += 1
            quotation.output = None

            # Persist manual SKU mapping (Phase 3)
            sku_key = item.detected_sku or item.detected_model or item.description
            if sku_key and self.mapping_store:
                self.mapping_store.set(sku_key, product_id)

            prepare_images(self, quotation, [index])
            if self.history_store:
                self.history_store.save_quotation(quotation)

    def image(self, product):
        url = product.image_url or ''
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError:
            return None
        # Web requests never read local paths or fetch arbitrary hosts/redirects.
        if parsed.scheme != 'https' or parsed.hostname != 'cdn.shopify.com' or port not in (None, 443) or parsed.username:
            return None
        return self.downloader.get_image(url)

    def generate(self, quotation):
        with quotation.lock:
            prepare_images(self, quotation)
            images = {}
            for index, item in enumerate(quotation.items):
                item.error_message = None
                data = quotation.images.get(index)
                if data:
                    images[(item.page_number, item.item_number)] = data
                elif item.matched_product:
                    item.error_message = 'Product image unavailable'
            quotation.output = self.renderer.render(quotation.source, quotation.items, images)
            if self.history_store:
                self.history_store.save_quotation(quotation)

    @staticmethod
    def product_view(product):
        return {'id': product.id, 'sku': product.sku, 'model': product.model,
                'has_image': bool(product.image_url)}

    def view(self, quotation):
        with quotation.lock:
            editor_items, pages = editor_view(self, quotation)
            items = [{'id': index, 'number': item.item_number, 'page': item.page_number,
                      **editor_items[index],
                      'description': item.description, 'sku': item.detected_sku,
                      'status': item.match_status, 'match_method': item.match_method,
                      'product': self.product_view(item.matched_product) if item.matched_product else None,
                      'candidates': [self.product_view(p) for p in item.candidate_products],
                      'image_inserted': item.image_inserted,
                      'warning': 'Cannot place image safely or image unavailable' if item.error_message else None}
                     for index, item in enumerate(quotation.items)]
            return {'id': quotation.id, 'filename': quotation.filename, 'items': items,
                    'pages': pages, 'revision': quotation.revision,
                    'generated': quotation.output is not None,
                    'images_inserted': sum(i.image_inserted for i in quotation.items),
                    'can_undo': bool(quotation.undo_stack),
                    'can_redo': bool(quotation.redo_stack)}
