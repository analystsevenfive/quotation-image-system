"""Phase 2 local API. Bind to loopback until Phase 4 authentication is added."""
import logging
import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool
from app.services.catalog import Catalog
from app.services.quotations import QuotationService
from app.services.editor import replace_image, save_placement, delete_image, delete_images
from app.services.images.uploads import MAX_IMAGE_UPLOAD
from app.services.matching.mappings import MappingStore
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

MAX_UPLOAD = 20 * 1024 * 1024


def create_app(service=None):
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
        origin = request.headers.get('origin')
        allowed_origins_env = os.environ.get('ALLOWED_ORIGINS')
        default_origins = {'http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:8000', 'http://127.0.0.1:8000'}
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
                return JSONResponse({'detail': 'รูปต้องมีขนาดไม่เกิน 10 MB' if image_upload else 'PDF must be 20 MB or smaller'}, status_code=413)

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
                raise HTTPException(413, 'PDF must be 20 MB or smaller')
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

    return app


app = create_app()
