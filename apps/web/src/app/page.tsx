'use client';
import dynamic from 'next/dynamic';
import {useCallback, useEffect, useRef, useState} from 'react';
import {ArrowRight, Check, CheckCircle2, Download, FileText, ImagePlus, Loader2, Search, UploadCloud, X, RotateCcw, Crop, Trash2, BookmarkCheck} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {api, type Product, type Item, type Quotation, type Rect} from '@/lib/api';
import MappingsDialog from '@/components/mappings-dialog';

const PdfPreview = dynamic(()=>import('@/components/pdf-preview'), {ssr:false, loading:()=> <div className="p-20 text-center">กำลังเปิดเอกสาร…</div>});
const labels = {matched:'จับคู่แล้ว', manual:'เลือกแล้ว', needs_review:'รอตรวจสอบ', missing:'ไม่พบสินค้า'};

function Thumbnail({product,imageUrl}: {product:Product|null;imageUrl?:string|null}) {
  const [failed, setFailed] = useState(false);
  useEffect(()=>setFailed(false), [product?.id,imageUrl]);
  return <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl border border-stone-100 bg-white">{(imageUrl||product?.has_image) && !failed ? <img src={imageUrl||`/api/products/${product!.id}/image`} alt={product?.sku||'รูปที่อัปโหลด'} className="h-14 w-14 object-contain" onError={()=>setFailed(true)}/> : <ImagePlus size={22} className="text-stone-300"/>}</div>;
}

export default function Home() {
  const [quotation,setQuotation] = useState<Quotation|null>(null);
  const [busy,setBusy] = useState('');
  const [error,setError] = useState('');
  const [drag,setDrag] = useState(false);
  const [page,setPage] = useState(1);
  const [editing,setEditing] = useState<Item|null>(null);
  const [cropTarget,setCropTarget] = useState<number|null>(null);
  const [query,setQuery] = useState('');
  const [results,setResults] = useState<Product[]>([]);
  const [searching,setSearching] = useState(false);
  const [activeItem,setActiveItem] = useState<number|null>(null);
  const [selectedIds,setSelectedIds] = useState<number[]>([]);
  const [mappingsOpen,setMappingsOpen] = useState(false);
  const [gesturing,setGesturing] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking'|'ready'|'error'>('checking');
  const [highlightId, setHighlightId] = useState<number|null>(null);
  const mutationGate = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const itemRefs = useRef<Record<number, HTMLElement|null>>({});
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToFirstMissing = useCallback(() => {
    if (!quotation) return;
    const first = quotation.items.find(i => !i.has_image);
    if (!first) return;
    const el = itemRefs.current[first.id];
    if (el) {
      el.scrollIntoView({behavior: 'smooth', block: 'center'});
      setHighlightId(first.id);
      setTimeout(() => setHighlightId(null), 1800);
    }
  }, [quotation]);

  useEffect(() => {
    let active = true;
    fetch('/api/health')
      .then(res => {
        if (!active) return;
        setBackendStatus(res.ok ? 'ready' : 'error');
      })
      .catch(() => {
        if (active) setBackendStatus('error');
      });
    return () => { active = false; };
  }, []);
  useEffect(()=> { if (!editing) return; const abort = new AbortController(); setSearching(true); const timer=setTimeout(()=> {
    api<Product[]>(`/products/search?q=${encodeURIComponent(query)}`, {signal:abort.signal}).then(setResults).catch(e=>{if(e.name!=='AbortError')setError(e.message)}).finally(()=>{if(!abort.signal.aborted)setSearching(false)});
  },250); return ()=>{clearTimeout(timer);abort.abort()}; },[query,editing]);
  useEffect(()=>{if(!editing)return; const handler=(e:KeyboardEvent)=>{if(e.key==='Escape')setEditing(null)};document.addEventListener('keydown',handler);return()=>document.removeEventListener('keydown',handler)},[editing]);
  async function upload(file?:File) {
    if(!file || busy) return;
    setError('');
    if(!file.name.toLowerCase().endsWith('.pdf') || file.size>20*1024*1024){setError('กรุณาเลือก PDF ขนาดไม่เกิน 20 MB');return;}
    setBusy('กำลังอัปโหลด อ่านใบเสนอราคา และจับคู่สินค้า…');
    try {const form = new FormData();form.append('file',file);setQuotation(await api<Quotation>('/quotations',{method:'POST',body:form}));setPage(1);setActiveItem(0);setSelectedIds([]);}catch(e){setError((e as Error).message)}finally{setBusy('');if(input.current)input.current.value='';}
  }
  async function generate() {
    if(!quotation)return;setBusy('กำลังเตรียมรูปสินค้าและสร้าง PDF…');setError('');
    try {setQuotation(await api<Quotation>(`/quotations/${quotation.id}/generate`,{method:'POST'}))}catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  async function select(product:Product, targetItemId?:number) {
    const itemId = targetItemId ?? editing?.id;
    if(!quotation||itemId===undefined)return;setBusy('กำลังเปลี่ยนสินค้า…');setError('');
    try{setQuotation(await api<Quotation>(`/quotations/${quotation.id}/items/${itemId}/select-product`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:product.id})}));setEditing(null)}catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  function activate(id:number) {
    const item=quotation?.items.find(i=>i.id===id);
    if(item){setActiveItem(id);setPage(item.page);setSelectedIds([id]);}
  }
  function changePage(next:number) {
    setPage(next);setActiveItem(quotation?.items.find(i=>i.page===next)?.id??null);
  }
  async function savePlacement(id:number,rect:Rect|null) {
    if(!quotation||mutationGate.current)return;
    mutationGate.current=true;setBusy('กำลังบันทึกตำแหน่งรูป…');setError('');
    try {
      setQuotation(await api<Quotation>(`/quotations/${quotation.id}/items/${id}/placement`,rect?{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(rect)}:{method:'DELETE'}));
    }catch(e){setError((e as Error).message);throw e;}finally{setBusy('');mutationGate.current=false;}
  }
  async function uploadImage(id:number,file:File) {
    if(!quotation||mutationGate.current)return;
    if(file.size>10*1024*1024){setError('กรุณาใช้รูปขนาดไม่เกิน 10 MB');return;}
    mutationGate.current=true;setBusy('กำลังเพิ่มรูปลงในรายการที่เลือก…');setError('');
    try {
      const form=new FormData();form.append('file',file,file.name||'clipboard.png');
      const updated = await api<Quotation>(`/quotations/${quotation.id}/items/${id}/image`,{method:'POST',body:form});
      setQuotation(updated);activate(id);
    }catch(e){setError((e as Error).message)}finally{setBusy('');mutationGate.current=false;}
  }
  const quotationRef = useRef(quotation);
  quotationRef.current = quotation;
  const busyRef = useRef(busy);
  busyRef.current = busy;
  const gesturingRef = useRef(gesturing);
  gesturingRef.current = gesturing;

  async function undo() {
    const q = quotationRef.current;
    if(!q||!q.can_undo||mutationGate.current)return;
    mutationGate.current=true;setBusy('กำลังย้อนกลับ…');setError('');
    try {
      setQuotation(await api<Quotation>(`/quotations/${q.id}/undo`,{method:'POST'}));
    }catch(e){setError((e as Error).message)}finally{setBusy('');mutationGate.current=false;}
  }
  async function redo() {
    const q = quotationRef.current;
    if(!q||!q.can_redo||mutationGate.current)return;
    mutationGate.current=true;setBusy('กำลังทำซ้ำ…');setError('');
    try {
      setQuotation(await api<Quotation>(`/quotations/${q.id}/redo`,{method:'POST'}));
    }catch(e){setError((e as Error).message)}finally{setBusy('');mutationGate.current=false;}
  }
  async function deleteImages(ids: number[]) {
    const q = quotationRef.current;
    if(!q||ids.length===0||mutationGate.current)return;
    mutationGate.current=true;setBusy(ids.length>1?`กำลังลบรูปภาพ ${ids.length} รูป…`:'กำลังลบรูปภาพ…');setError('');
    try {
      if (ids.length === 1) {
        setQuotation(await api<Quotation>(`/quotations/${q.id}/items/${ids[0]}/image`,{method:'DELETE'}));
      } else {
        setQuotation(await api<Quotation>(`/quotations/${q.id}/items/batch-delete-images`,{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({item_ids:ids}),
        }));
      }
      setSelectedIds(prev=>prev.filter(id=>!ids.includes(id)));
    }catch(e){setError((e as Error).message)}finally{setBusy('');mutationGate.current=false;}
  }
  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter(x => x !== id);
      }
      if (prev.length === 0 && activeItem !== null && activeItem !== id) {
        return [activeItem, id];
      }
      return [...prev, id];
    });
    const item = quotation?.items.find(i => i.id === id);
    if (item) {
      setActiveItem(id);
      setPage(item.page);
    }
  }
  function selectAllWithImages() {
    if (!quotation) return;
    setSelectedIds(quotation.items.filter(i => i.has_image).map(i => i.id));
  }
  function clearSelect() {
    setSelectedIds([]);
  }
  useEffect(() => {
    if (typeof document !== 'undefined') {
      const active = document.activeElement as HTMLElement | null;
      if (active && (active.tagName === 'BUTTON' || (active as any).disabled)) {
        active.blur?.();
        document.body.tabIndex = -1;
        document.body.focus?.();
      }
    }
  }, [quotation]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }
      const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.userAgent);
      const isMod = isMac ? e.metaKey : e.ctrlKey;
      if (!isMod) return;

      const q = quotationRef.current;
      if (!q) return;

      const key = e.key.toLowerCase();
      const isZ = key === 'z' || e.code === 'KeyZ';
      const isY = key === 'y' || e.code === 'KeyY';
      if (isZ && !e.shiftKey) {
        e.preventDefault();
        if (q.can_undo && !busyRef.current && !gesturingRef.current) {
          void undo();
        }
      } else if ((isY && !e.shiftKey) || (isZ && e.shiftKey)) {
        e.preventDefault();
        if (q.can_redo && !busyRef.current && !gesturingRef.current) {
          void redo();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const matched=quotation?.items.filter(i=>i.status==='matched'||i.status==='manual').length||0;
  const review=quotation?.items.filter(i=>i.status==='needs_review').length||0;
  const missing=quotation?.items.filter(i=>!i.has_image).length||0;
  return <div className="min-h-screen">
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-4 lg:px-10">
        <div className="flex items-center gap-3">
          <img
            src="/logo.png"
            alt="Seven Five"
            className="h-11 w-11 shrink-0 object-contain"
          />
          <div>
            <p className="font-bold tracking-tight">Quotation Studio</p>
            <p className="text-xs text-stone-500">SEVEN FIVE · PRODUCT IMAGES</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            className="h-9 gap-1.5 text-xs text-stone-700 hover:text-teal-800"
            onClick={() => setMappingsOpen(true)}
          >
            <BookmarkCheck size={15} />
            คู่สินค้าที่จำไว้
          </Button>
          {backendStatus === 'ready' && (
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-3 py-1.5 text-xs font-medium text-teal-800">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-600 animate-pulse" />
              ระบบพร้อมใช้งาน (Production Ready)
            </span>
          )}
          {backendStatus === 'checking' && (
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800" title="กำลังเชื่อมต่อหรือปลุกเซิร์ฟเวอร์ Backend (Render Free Tier)">
              <Loader2 size={12} className="animate-spin" />
              กำลังเชื่อมต่อเซิร์ฟเวอร์…
            </span>
          )}
          {backendStatus === 'error' && (
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700" title="ไม่สามารถเชื่อมต่อ Backend ได้ โปรดตรวจสอบ API_URL บน Vercel">
              <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
              เชื่อมต่อ Backend ไม่สำเร็จ
            </span>
          )}
        </div>
      </div>
    </header>
    <main className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
      <div className="mb-9 flex flex-wrap items-center gap-3 text-sm">{['อัปโหลดเอกสาร','ตรวจสอบสินค้า','ดาวน์โหลด PDF'].map((label,index)=><div key={label} className="flex items-center gap-3"><span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${index===(quotation?.generated?2:quotation?1:0)?'bg-teal-800 text-white':'bg-stone-200 text-stone-500'}`}>{index+1}</span><span className="text-stone-600">{label}</span>{index<2&&<ArrowRight size={14} className="mx-2 text-stone-300"/>}</div>)}</div>
      {error&&<div role="alert" className="mb-6 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}<button aria-label="ปิดข้อความ" onClick={()=>setError('')}><X size={18}/></button></div>}
      {busy&&<div role="status" className="mb-6 flex items-center gap-3 rounded-xl bg-teal-50 p-4 text-sm text-teal-900"><Loader2 size={18} className="animate-spin"/>{busy}</div>}
      {!quotation ? <section className="enter mx-auto max-w-3xl pt-8 text-center">
        <h1 className="text-3xl font-semibold leading-snug lg:text-4xl">เติมรูปสินค้าให้ใบเสนอราคา</h1>
        <div onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);void upload(e.dataTransfer.files[0])}} className={`mt-9 rounded-3xl border-2 border-dashed px-6 py-14 transition-colors ${drag?'border-teal-600 bg-teal-50':'border-stone-300 bg-white'}`}>
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-50 text-teal-800"><UploadCloud size={30}/></div><h2 className="text-lg font-semibold">ลากใบเสนอราคามาวางที่นี่</h2><p className="mb-6 mt-2 text-sm text-stone-500">หรือเลือกไฟล์จากเครื่องของคุณ</p><Button disabled={!!busy||gesturing} onClick={()=>input.current?.click()}><FileText size={17}/>เลือกไฟล์ PDF</Button><input ref={input} className="hidden" type="file" accept="application/pdf,.pdf" aria-label="เลือกใบเสนอราคา" onChange={e=>void upload(e.target.files?.[0])}/><p className="mt-5 text-xs text-stone-400">PDF ที่เลือกข้อความได้ · สูงสุด 20 MB · แม่แบบ Seven Five</p>
        </div><div className="mt-7 grid gap-4 text-left text-sm text-stone-500 sm:grid-cols-3">{['รักษาความคมชัดต้นฉบับ','ตรวจและเปลี่ยนสินค้าได้','สร้างต่อได้แม้รูปไม่ครบ'].map(t=><div key={t} className="flex items-center gap-2"><Check size={16} className="text-teal-700"/>{t}</div>)}</div>
      </section>:<section className="enter">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-5"><div><p className="mb-2 text-xs font-semibold tracking-widest text-teal-700">{quotation.generated?'DOCUMENT READY':'REVIEW YOUR QUOTATION'}</p><h1 className="max-w-2xl break-all text-2xl font-semibold">{quotation.filename}</h1><p className="mt-2 text-sm text-stone-500">ตรวจสอบสินค้าและรูปภาพก่อนดาวน์โหลดเอกสาร</p></div><Button variant="outline" disabled={!!busy||gesturing} onClick={()=>{setQuotation(null);setSelectedIds([]);setError('')}}><RotateCcw size={16}/>เริ่มเอกสารใหม่</Button></div>
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {([[quotation.items.length,'รายการทั้งหมด'],[matched,'จับคู่สินค้าแล้ว'],[review,'รอตรวจสอบ']] as [number,string][]).map(([n,l])=><div key={l} className="rounded-2xl border border-stone-200 bg-white px-5 py-4"><span className="text-2xl font-semibold">{n}</span><span className="ml-3 text-xs text-stone-500">{l}</span></div>)}
          {missing > 0 ? (
            <button
              key="missing"
              onClick={scrollToFirstMissing}
              className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-left transition-colors hover:border-amber-400 hover:bg-amber-100 group"
              title="คลิกเพื่อไปยังรายการแรกที่ยังไม่มีรูป"
            >
              <span className="text-2xl font-semibold text-amber-700">{missing}</span>
              <span className="ml-3 text-xs text-amber-700">ยังไม่มีรูปที่เลือก</span>
              <span className="ml-1 text-xs text-amber-500 opacity-0 group-hover:opacity-100 transition-opacity">↓</span>
            </button>
          ) : (
            <div key="missing" className="rounded-2xl border border-stone-200 bg-white px-5 py-4"><span className="text-2xl font-semibold text-teal-700">{missing}</span><span className="ml-3 text-xs text-stone-500">ยังไม่มีรูปที่เลือก</span></div>
          )}
        </div>
        {quotation.generated&&<div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-teal-200 bg-teal-50 p-5"><div className="flex items-center gap-3"><CheckCircle2 className="text-teal-700"/><div><p className="font-semibold text-teal-900">PDF พร้อมดาวน์โหลด</p><p className="mt-1 text-sm text-teal-800">เพิ่มรูปแล้ว {quotation.images_inserted} จาก {quotation.items.length} รายการ{quotation.images_inserted<quotation.items.length?' · รายการที่เหลือคงเอกสารเดิมไว้':''}</p></div></div></div>}
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(330px,1fr)]">
          <PdfPreview key={quotation.id} quotation={quotation} page={page} onPage={changePage} selected={activeItem} selectedIds={selectedIds} onSelect={activate} onToggleSelect={toggleSelect} onClearSelect={clearSelect} disabled={!!busy} onSave={savePlacement} onUpload={uploadImage} cropTarget={cropTarget} onCropTargetHandled={()=>setCropTarget(null)} onGesture={setGesturing} canUndo={!!quotation.can_undo} canRedo={!!quotation.can_redo} onUndo={()=>void undo()} onRedo={()=>void redo()} onDelete={deleteImages}/>
          <aside className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
            <div className="border-b border-stone-100 px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold">สินค้าในใบเสนอราคา</h2>
                  <p className="mt-0.5 text-xs text-stone-500">เลือกรายการ แล้วลากรูป, ครอบตัด หรือเลือกหลายรูปเพื่อลบพร้อมกัน</p>
                </div>
                {quotation.items.some(i => i.has_image) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-stone-600 hover:text-teal-800"
                    disabled={!!busy || gesturing}
                    onClick={() => {
                      const imageCount = quotation.items.filter(i => i.has_image).length;
                      if (selectedIds.length === imageCount && imageCount > 0) {
                        clearSelect();
                      } else {
                        selectAllWithImages();
                      }
                    }}
                  >
                    {selectedIds.length === quotation.items.filter(i => i.has_image).length && selectedIds.length > 0
                      ? 'ยกเลิกเลือกทั้งหมด'
                      : 'เลือกทั้งหมดที่มีรูป'}
                  </Button>
                )}
              </div>
              {selectedIds.length > 0 && (
                <div className="mt-3 flex items-center justify-between rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs">
                  <span className="font-medium text-teal-900">เลือกอยู่ {selectedIds.length} รายการ</span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[11px] text-stone-600 hover:text-stone-900"
                      onClick={clearSelect}
                    >
                      ยกเลิก
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-6 gap-1 bg-red-600 px-2 text-[11px] text-white hover:bg-red-700"
                      disabled={!!busy || gesturing}
                      onClick={() => void deleteImages(selectedIds)}
                    >
                      <Trash2 size={11} />
                      ลบที่เลือก ({selectedIds.length})
                    </Button>
                  </div>
                </div>
              )}
            </div>
            <div ref={listRef} className="max-h-[58vh] divide-y divide-stone-100 overflow-auto">
              {quotation.items.map(item=><article key={item.id} ref={el => { itemRefs.current[item.id] = el; }} className={`p-5 transition-colors duration-300 ${highlightId === item.id ? 'bg-amber-100 ring-2 ring-amber-400 ring-inset' : item.id===activeItem || selectedIds.includes(item.id)?'bg-teal-50/60':''}`}>
                <div className="flex gap-3">
                  <div className="flex flex-col items-center gap-2 pt-0.5">
                    <input
                      type="checkbox"
                      data-testid={`checkbox-item-${item.id}`}
                      aria-label={`เลือกรูปรายการ ${item.number}`}
                      checked={selectedIds.includes(item.id)}
                      disabled={!item.has_image || !!busy || gesturing}
                      onChange={() => toggleSelect(item.id)}
                      className="h-4 w-4 rounded border-stone-300 text-teal-600 focus:ring-teal-500 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                    />
                    <Thumbnail product={item.product} imageUrl={item.image_url}/>
                  </div>
                  <div className="min-w-0 flex-1">
                    <button className="text-left text-sm font-semibold hover:text-teal-700" disabled={!!busy||gesturing} onClick={()=>activate(item.id)}>{item.number}. {item.sku||'รายการเพิ่มเติม'}</button>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-stone-500">{item.description}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-1 text-[11px] ${item.status==='matched'||item.status==='manual'?'bg-teal-50 text-teal-800':'bg-amber-50 text-amber-800'}`}>{labels[item.status]}</span>
                      {item.match_method === 'manual' && item.status === 'matched' && (
                        <span className="rounded-full bg-cyan-50 px-2 py-1 text-[11px] font-medium text-cyan-900 border border-cyan-200">จำจากประวัติ</span>
                      )}
                      <span className="text-[11px] text-stone-400">หน้า {item.page}</span>
                    </div>
                    {item.product&&<p className="mt-2 text-xs text-stone-500">เลือก: {item.product.sku}</p>}
                    {(!item.has_image||item.warning)&&<p className="mt-2 text-xs text-amber-700">{item.warning?'รูปไม่พร้อมใช้หรือพื้นที่ไม่พอ ระบบข้ามรูปนี้':'ยังไม่มีรูปสินค้า · สร้าง PDF ต่อได้'}</p>}
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <Button variant="ghost" size="sm" className="h-7 px-0 text-xs text-teal-800" disabled={!!busy||gesturing} onClick={()=>{activate(item.id);setEditing(item);setQuery(item.sku||'');setResults([])}}><Search size={13}/>{item.product?'เปลี่ยนสินค้า / รูป':'ค้นหาและเลือกสินค้า'}</Button>
                      <Button variant="ghost" size="sm" className="h-7 px-0 text-xs text-teal-800" disabled={!!busy||gesturing} onClick={()=>activate(item.id)}><ImagePlus size={13}/>จัดรูป / วางภาพ</Button>
                      {item.has_image&&<Button variant="ghost" size="sm" className="h-7 px-0 text-xs text-teal-800" disabled={!!busy||gesturing} onClick={()=>{activate(item.id);setCropTarget(item.id);}}><Crop size={13}/>ครอบตัดรูป</Button>}
                      {item.has_image&&<Button variant="ghost" size="sm" className="h-7 px-0 text-xs text-red-600 hover:bg-transparent hover:text-red-700" disabled={!!busy||gesturing} onClick={()=>void deleteImages([item.id])}><Trash2 size={13}/>ลบรูป</Button>}
                      {item.uploaded_image&&item.product&&<Button variant="ghost" size="sm" className="h-7 px-0 text-xs text-stone-500 hover:text-teal-800" disabled={!!busy||gesturing} onClick={()=>void select(item.product!,item.id)}><RotateCcw size={12}/>คืนค่ารูป Catalog</Button>}
                    </div>
                    {item.uploaded_image&&<p className="mt-1 text-xs text-teal-700">ใช้รูปที่ปรับแต่ง / อัปโหลด / วางจากคลิปบอร์ด</p>}
                  </div>
                </div>
              </article>)}
            </div>
            <div className="border-t border-stone-200 bg-stone-50 p-5">
              {missing>0&&<p className="mb-3 text-xs leading-5 text-stone-500">ยังไม่มีรูปที่เลือก {missing} รายการ คุณสามารถสร้างเอกสารต่อได้</p>}
              <Button variant={quotation.generated ? 'outline' : 'default'} className="w-full" disabled={!!busy||gesturing} onClick={()=>void generate()}><ImagePlus size={17}/>{quotation.generated?'สร้าง PDF อีกครั้ง':missing?'สร้าง PDF โดยข้ามรูปที่ยังไม่มี':'สร้าง PDF พร้อมรูปสินค้า'}<ArrowRight size={16}/></Button>
              {quotation.generated && (
                <Button asChild className="mt-2.5 w-full bg-teal-800 hover:bg-teal-900 text-white shadow-sm">
                  <a href={`/api/quotations/${quotation.id}/download`}><Download size={17}/>ดาวน์โหลด PDF</a>
                </Button>
              )}
            </div>
          </aside>
        </div>
      </section>}
      {editing&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-5" onClick={()=>!busy&&setEditing(null)}><div role="dialog" aria-modal="true" aria-labelledby="search-title" className="max-h-[80vh] w-full max-w-xl overflow-auto rounded-2xl bg-white p-6 shadow-xl" onClick={e=>e.stopPropagation()}><div className="mb-5 flex items-center justify-between"><h2 id="search-title" className="font-semibold">เลือกสินค้าสำหรับรายการ {editing.number}</h2><Button variant="ghost" size="icon" aria-label="ปิด" disabled={!!busy||gesturing} onClick={()=>setEditing(null)}><X size={18}/></Button></div><input autoFocus aria-label="ค้นหา SKU หรือรุ่นสินค้า" placeholder="ค้นหา SKU หรือรุ่นสินค้า…" value={query} onChange={e=>setQuery(e.target.value)} className="mb-4 w-full rounded-xl border border-stone-300 px-4 py-3 text-sm"/>{editing.candidates.length>0&&<p className="mb-2 text-xs text-amber-700">พบสินค้าที่เป็นไปได้หลายรายการ กรุณาเลือกให้ตรงกับใบเสนอราคา</p>}{searching&&<p className="py-3 text-sm text-stone-500">กำลังค้นหา…</p>}{[...new Map([...editing.candidates,...results].map(p=>[p.id,p])).values()].map(p=><button key={p.id} disabled={!!busy||gesturing} onClick={()=>void select(p)} className="flex w-full items-center gap-4 rounded-xl p-3 text-left hover:bg-teal-50 disabled:opacity-50"><Thumbnail product={p}/><div><p className="text-sm font-semibold">{p.sku}</p><p className="mt-1 text-xs text-stone-500">{p.model}{!p.has_image?' · ไม่มีรูป':''}</p></div><ArrowRight className="ml-auto text-teal-700" size={16}/></button>)}{!searching&&!results.length&&!editing.candidates.length&&<p className="p-6 text-center text-sm text-stone-500">ไม่พบสินค้า ลองค้นหารหัสหรือรุ่นอื่น</p>}</div></div>}
      <MappingsDialog
        open={mappingsOpen}
        onClose={() => setMappingsOpen(false)}
      />
    </main>
  </div>;
}
