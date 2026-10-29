"""Phase 2 local API. Bind to loopback until Phase 4 authentication is added."""
import logging
import os
import secrets
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool
from app.services.catalog import Catalog
from app.services.quotations import QuotationService
from app.services.editor import replace_image, save_placement, delete_image, delete_images
from app.services.images.uploads import MAX_IMAGE_UPLOAD
from app.services.matching.mappings import MappingStore
from app.services.shopify_sync import is_sync_running, get_last_sync_status, run_sync_background
from app.core.auth import authorized_user, has_sync_secret
from app.core.app_proxy import verified_proxy_params
from app.services.shopify_sync import DEFAULT_SHOP
from app.services.web_quote.service import HourlyRateLimiter, QuoteRateLimited, WebQuoteService, clean_terms
from app.services.web_quote.shopify_sources import CartUnavailable, valid_cart_token
from pathlib import Path

# Automatically load .env if present in workspace root
for env_file in [Path('.env'), Path('../../.env')]:
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

class BatchDeleteRequest(BaseModel):
    item_ids: list[int]

class CartQuoteRequest(BaseModel):
    cart_token: str = Field(max_length=300)
    payment_term: str = Field(default='', max_length=500)
    remark: str = Field(default='', max_length=2000)
    validity_days: int = Field(default=30, ge=1, le=365)

PROXY_PREFIX = '/api/proxy/'
# Storefront uploads run unattended, so they keep their own limits separate from staff uploads.
STOREFRONT_PDF_MAX = 100 * 1024 * 1024
STOREFRONT_PDF_PAGES = 300
STOREFRONT_UPLOADS_PER_HOUR = int(os.environ.get('WEB_IMAGE_UPLOADS_PER_HOUR', 20))

MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', 50))
MAX_UPLOAD = MAX_UPLOAD_MB * 1024 * 1024


def create_app(service=None, web_quote_service=None):
    @asynccontextmanager
    async def lifespan(app):
        if service is None:
            url = os.environ.get('DATABASE_URL')
            catalog = Catalog.from_postgres(url) if url else Catalog.from_json(os.environ.get('PRODUCTS_JSON', '.data/products.json'))
            mapping_store = MappingStore(os.environ.get('MAPPINGS_FILE', '.data/mappings.json'))
            app.state.service = QuotationService(catalog, mapping_store=mapping_store)
        yield

    app = FastAPI(title='Quotation Images', lifespan=lifespan)
    app.state.service = service
    app.state.web_quote_service = web_quote_service
    app.state.image_upload_limiter = HourlyRateLimiter(STOREFRONT_UPLOADS_PER_HOUR)
    allowed_hosts = ['localhost', '127.0.0.1', 'testserver']
    allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
    if allowed_hosts_env:
        if allowed_hosts_env == '*':
            allowed_hosts = ['*']
        else:
            allowed_hosts.extend(h.strip() for h in allowed_hosts_env.split(',') if h.strip())
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware('http')
    async def private_session(request: Request, call_next):
        if request.url.path.startswith(PROXY_PREFIX):
            # Storefront requests arrive from Shopify's app proxy; each route verifies its signature.
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        if os.environ.get('AUTH_ENABLED') == 'true' and request.url.path.startswith('/api/') and request.url.path != '/api/health':
            sync_path = request.url.path in {'/api/sync/shopify', '/api/sync/good-bill-names'}
            if not (sync_path and has_sync_secret(request)):
                authorization = request.headers.get('authorization', '')
                token = authorization.removeprefix('Bearer ').strip() if authorization.startswith('Bearer ') else ''
                try:
                    user = await authorized_user(token)
                except (httpx.HTTPError, ValueError):
                    logging.getLogger(__name__).exception('Supabase authorization unavailable')
                    return JSONResponse({'detail': 'Authorization service unavailable'}, status_code=503)
                if not user:
                    return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
                request.state.user = user
        origin = request.headers.get('origin')
        allowed_origins_env = os.environ.get('ALLOWED_ORIGINS')
        default_origins = {'http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:3001', 'http://127.0.0.1:3001', 'http://localhost:8000', 'http://127.0.0.1:8000'}
        if allowed_origins_env and allowed_origins_env != '*':
            default_origins.update(o.strip() for o in allowed_origins_env.split(',') if o.strip())
        is_allowed_origin = (allowed_origins_env == '*') or (origin in default_origins)

        if request.method == 'OPTIONS':
            res = Response(status_code=204)
            if origin and is_allowed_origin:
                res.headers['Access-Control-Allow-Origin'] = origin
                res.headers['Access-Control-Allow-Credentials'] = 'true'
                res.headers['Access-Control-Allow-Headers'] = '*'
                res.headers['Access-Control-Allow-Methods'] = '*'
            return res

        image_upload = request.url.path.startswith('/api/quotations/') and request.url.path.endswith('/image')
        if request.method == 'POST' and (request.url.path == '/api/quotations' or image_upload):
            try:
                length = int(request.headers.get('content-length', '0'))
            except ValueError:
                return JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)
            limit = MAX_IMAGE_UPLOAD if image_upload else MAX_UPLOAD
            if length > limit + 65536:
                return JSONResponse({'detail': 'รูปต้องมีขนาดไม่เกิน 10 MB' if image_upload else f'PDF must be {MAX_UPLOAD_MB} MB or smaller'}, status_code=413)

        if origin and not is_allowed_origin:
            return JSONResponse({'detail': 'Origin not allowed'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site' and not origin and not is_allowed_origin:
            return JSONResponse({'detail': 'Cross-site access not allowed'}, status_code=403)

        owner = request.cookies.get('quotation_session')
        if not owner or len(owner) != 64:
            owner = secrets.token_hex(32)
        request.state.owner = owner
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if origin and is_allowed_origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Access-Control-Allow-Methods'] = '*'
        is_https = request.url.scheme == 'https' or request.headers.get('x-forwarded-proto') == 'https'
        response.set_cookie(
            'quotation_session',
            owner,
            httponly=True,
            samesite='none' if is_https else 'lax',
            secure=is_https,
            max_age=86400
        )
        return response

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        logging.getLogger(__name__).exception('Quotation request failed')
        return JSONResponse({'detail': 'Unable to complete this request. Please try again.'}, status_code=500)

    def get(request, identifier):
        try:
            return request.app.state.service.get(identifier, request.state.owner)
        except KeyError:
            raise HTTPException(404, 'Quotation not found or session expired') from None

    @app.get('/api/health')
    def health(request: Request):
        return {'status': 'ok', 'products': len(request.app.state.service.catalog.products)}

    @app.post('/api/quotations', status_code=201)
    async def upload(request: Request, file: UploadFile):
        try:
            data = await file.read(MAX_UPLOAD + 1)
            if len(data) > MAX_UPLOAD:
                raise HTTPException(413, f'PDF must be {MAX_UPLOAD_MB} MB or smaller')
            if file.content_type not in ('application/pdf', 'application/octet-stream'):
                raise HTTPException(415, 'Please upload a PDF file')
            svc = request.app.state.service
            try:
                quotation = await run_in_threadpool(svc.create, request.state.owner, file.filename or 'quotation.pdf', data)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            return svc.view(quotation)
        finally:
            await file.close()

    @app.get('/api/quotations/{identifier}')
    def detail(identifier: str, request: Request):
        return request.app.state.service.view(get(request, identifier))

    @app.get('/api/quotations/{identifier}/preview')
    def preview(identifier: str, request: Request):
        q = get(request, identifier)
        return Response(q.output or q.source, media_type='application/pdf')

    @app.get('/api/quotations/{identifier}/original')
    def original(identifier: str, request: Request):
        return Response(get(request, identifier).source, media_type='application/pdf')

    class Placement(BaseModel):
        model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
        x: float = Field(ge=0, le=1)
        y: float = Field(ge=0, le=1)
        width: float = Field(gt=0, le=1)
        height: float = Field(gt=0, le=1)

    @app.put('/api/quotations/{identifier}/items/{index}/placement')
    def placement(identifier: str, index: int, body: Placement, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        try:
            save_placement(svc, q, index, body)
        except KeyError:
            raise HTTPException(404, 'Item not found') from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return svc.view(q)

    @app.delete('/api/quotations/{identifier}/items/{index}/placement')
    def reset_placement(identifier: str, index: int, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        try:
            save_placement(svc, q, index, None)
        except KeyError:
            raise HTTPException(404, 'Item not found') from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return svc.view(q)

    @app.post('/api/quotations/{identifier}/items/{index}/image')
    async def upload_image(identifier: str, index: int, request: Request, file: UploadFile):
        try:
            q = get(request, identifier)
            svc = request.app.state.service
            data = await file.read(MAX_IMAGE_UPLOAD + 1)
            if len(data) > MAX_IMAGE_UPLOAD:
                raise HTTPException(413, 'รูปต้องมีขนาดไม่เกิน 10 MB')
            try:
                await run_in_threadpool(replace_image, svc, q, index, data)
            except KeyError:
                raise HTTPException(404, 'Item not found') from None
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            return svc.view(q)
        finally:
            await file.close()

    @app.delete('/api/quotations/{identifier}/items/{index}/image')
    def remove_item_image(identifier: str, index: int, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        try:
            delete_image(svc, q, index)
        except KeyError:
            raise HTTPException(404, 'Item not found') from None
        return svc.view(q)

    @app.post('/api/quotations/{identifier}/items/batch-delete-images')
    def batch_remove_images(identifier: str, body: BatchDeleteRequest, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        delete_images(svc, q, body.item_ids)
        return svc.view(q)

    @app.get('/api/quotations/{identifier}/items/{index}/image')
    def item_image(identifier: str, index: int, request: Request):
        q = get(request, identifier)
        with q.lock:
            data = q.images.get(index)
        if not data:
            raise HTTPException(404, 'Image unavailable')
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            content_type = Image.MIME.get(image.format, 'image/png')
        return Response(data, media_type=content_type)

    @app.post('/api/quotations/{identifier}/generate')
    def generate(identifier: str, request: Request):
        q = get(request, identifier)
        request.app.state.service.generate(q)
        return request.app.state.service.view(q)

    @app.get('/api/quotations/{identifier}/download')
    def download(identifier: str, request: Request):
        q = get(request, identifier)
        if q.output is None:
            raise HTTPException(409, 'Generate the PDF first')
        return Response(q.output, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="quotation-with-images.pdf"'})

    class Selection(BaseModel):
        product_id: int

    @app.post('/api/quotations/{identifier}/items/{index}/select-product')
    def select(identifier: str, index: int, body: Selection, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        try:
            svc.select(q, index, body.product_id)
        except KeyError:
            raise HTTPException(404, 'Product or item not found') from None
        return svc.view(q)

    @app.post('/api/quotations/{identifier}/undo')
    def undo(identifier: str, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        if not svc.undo(q):
            raise HTTPException(400, 'ไม่มีประวัติให้ย้อนกลับ')
        return svc.view(q)

    @app.post('/api/quotations/{identifier}/redo')
    def redo(identifier: str, request: Request):
        q = get(request, identifier)
        svc = request.app.state.service
        if not svc.redo(q):
            raise HTTPException(400, 'ไม่มีประวัติให้ทำซ้ำ')
        return svc.view(q)

    @app.get('/api/products/search')
    def search(request: Request, q: str = ''):
        svc = request.app.state.service
        return [svc.product_view(p) for p in svc.catalog.search(q[:100])]

    @app.get('/api/products/{identifier}/image')
    def product_image(identifier: int, request: Request):
        svc = request.app.state.service
        product = svc.catalog.by_id.get(identifier)
        data = svc.image(product) if product else None
        if not data:
            raise HTTPException(404, 'Image unavailable')
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            content_type = Image.MIME.get(image.format, 'image/png')
        return Response(data, media_type=content_type)

    @app.get('/api/mappings')
    def list_mappings(request: Request):
        svc = request.app.state.service
        if not getattr(svc, 'mapping_store', None):
            return []
        raw_list = svc.mapping_store.list_all()
        result = []
        for m in raw_list:
            pid = m.get('product_id')
            product = svc.catalog.by_id.get(pid) if pid else None
            result.append({
                **m,
                'product_sku': product.sku if product else None,
                'product_model': product.model if product else None,
                'product_has_image': bool(product.image_url) if product else False,
            })
        return result

    @app.delete('/api/mappings/{key:path}')
    def delete_mapping_item(key: str, request: Request):
        svc = request.app.state.service
        if not getattr(svc, 'mapping_store', None):
            raise HTTPException(404, 'Mapping store not available')
        removed = svc.mapping_store.delete(key)
        if not removed:
            raise HTTPException(404, 'Mapping not found')
        return {'status': 'deleted', 'key': key}

    @app.post('/api/catalog/reload')
    def reload_catalog(request: Request):
        url = os.environ.get('DATABASE_URL')
        if not url:
            raise HTTPException(500, 'DATABASE_URL is not configured')
        from app.services.catalog import Catalog
        catalog = Catalog.from_postgres(url)
        svc = request.app.state.service
        if svc:
            mapping_store = getattr(svc, 'mapping_store', None)
            if mapping_store:
                catalog.set_mapping_store(mapping_store)
            svc.catalog = catalog
        return {'status': 'ok', 'products': len(catalog.products)}

    @app.post('/api/sync/shopify')
    async def trigger_shopify_sync(request: Request, background_tasks: BackgroundTasks):
        sync_secret = os.environ.get('SYNC_SECRET')
        if sync_secret:
            auth_header = request.headers.get('Authorization') or request.headers.get('X-Sync-Secret')
            query_token = request.query_params.get('secret')
            provided = query_token or (auth_header.replace('Bearer ', '').strip() if auth_header else '')
            if provided != sync_secret:
                raise HTTPException(401, 'Unauthorized sync request')

        if is_sync_running():
            return JSONResponse({'status': 'running', 'message': 'Sync is already in progress'}, status_code=409)

        background_tasks.add_task(
            run_sync_background,
            database_url=os.environ.get('DATABASE_URL'),
            refresh_service=request.app.state.service,
        )
        return {'status': 'started', 'message': 'Shopify catalog synchronization initiated in background'}

    @app.get('/api/sync/status')
    def get_sync_status(request: Request):
        running = is_sync_running()
        last_log = get_last_sync_status(os.environ.get('DATABASE_URL'))
        return {
            'is_running': running,
            'last_sync': last_log,
        }

    @app.post('/api/sync/good-bill-names')
    async def sync_good_bill_names(request: Request):
        from app.services.good_bill_name_sync import update_good_bill_names_in_db, fetch_from_google_sheet_csv
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise HTTPException(500, 'DATABASE_URL is not configured')

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, 'Invalid JSON body')

        if isinstance(body, dict) and body.get('fetch_from_sheet'):
            sheet_id = body.get('sheet_id', '1Z48qT3LXYozhlh_ZBHzn9e4x1kfX_bOLHQtaksj-ZXU')
            sheet_name = body.get('sheet_name', 'Main Product')
            records = fetch_from_google_sheet_csv(sheet_id=sheet_id, sheet_name=sheet_name)
            if records is None:
                raise HTTPException(400, 'Could not read Google Sheet. Ensure sheet sharing is set to "Anyone with the link can view" or send records directly.')
            count = update_good_bill_names_in_db(records, database_url=db_url)
            return {'status': 'success', 'updated': count, 'source': 'google_sheet'}

        if isinstance(body, list):
            count = update_good_bill_names_in_db(body, database_url=db_url)
            return {'status': 'success', 'updated': count, 'source': 'direct_payload'}

        raise HTTPException(400, 'Invalid request payload. Expected a list of {good_id, good_bill_name} or {fetch_from_sheet: true}')

    def storefront_customer(request: Request) -> tuple[str, JSONResponse | None]:
        """Returns the signed-in customer's ID from a verified app proxy request, or an error response."""
        params = verified_proxy_params(
            request.query_params.multi_items(),
            os.environ.get('SHOPIFY_CLIENT_SECRET', ''),
            os.environ.get('SHOPIFY_SHOP', DEFAULT_SHOP),
        )
        if params is None:
            return '', JSONResponse({'code': 'forbidden'}, status_code=403)
        customer_id = params.get('logged_in_customer_id', '')
        if not customer_id.isdigit():
            return '', JSONResponse({'code': 'login_required'}, status_code=401)
        return customer_id, None

    @app.post(PROXY_PREFIX + 'cart-quote')
    async def cart_quote(body: CartQuoteRequest, request: Request):
        customer_id, error = storefront_customer(request)
        if error:
            return error
        if not valid_cart_token(body.cart_token):
            return JSONResponse({'code': 'cart_unavailable'}, status_code=422)

        if request.app.state.web_quote_service is None:
            request.app.state.web_quote_service = WebQuoteService.from_env()
        terms = clean_terms(body.payment_term, body.remark, body.validity_days)
        try:
            quote, pdf = await run_in_threadpool(request.app.state.web_quote_service.create, customer_id, body.cart_token, terms)
        except QuoteRateLimited:
            return JSONResponse({'code': 'rate_limited'}, status_code=429)
        except CartUnavailable:
            logging.getLogger(__name__).warning('Cart quote unavailable for customer %s', customer_id, exc_info=True)
            return JSONResponse({'code': 'cart_unavailable'}, status_code=422)
        return Response(pdf, media_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="{quote.number}.pdf"',
            'X-Quote-Number': quote.number,
        })

    @app.post(PROXY_PREFIX + 'quote-images')
    async def quote_images(request: Request):
        """Inserts product images into a customer's quotation PDF, sent as the raw request body."""
        customer_id, error = storefront_customer(request)
        if error:
            return error
        try:
            request.app.state.image_upload_limiter.check(customer_id)
        except QuoteRateLimited:
            return JSONResponse({'code': 'rate_limited'}, status_code=429)
        data = bytearray()
        async for chunk in request.stream():
            data += chunk
            if len(data) > STOREFRONT_PDF_MAX:
                return JSONResponse({'code': 'too_large'}, status_code=413)
        try:
            quotation = await run_in_threadpool(request.app.state.service.process_once, bytes(data), STOREFRONT_PDF_PAGES)
        except ValueError:
            logging.getLogger(__name__).info('Storefront quotation rejected for customer %s', customer_id, exc_info=True)
            return JSONResponse({'code': 'unsupported_pdf'}, status_code=422)
        return Response(quotation.output, media_type='application/pdf', headers={
            'Content-Disposition': 'attachment; filename="quotation-with-images.pdf"',
            'X-Images-Inserted': str(sum(item.image_inserted for item in quotation.items)),
        })

    return app


app = create_app()
