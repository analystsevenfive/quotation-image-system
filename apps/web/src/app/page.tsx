'use client';
import dynamic from 'next/dynamic';
import {useCallback, useEffect, useRef, useState} from 'react';
import {ArrowRight, CheckCircle2, Download, FileText, ImagePlus, Loader2, Search, UploadCloud, X, RotateCcw, Crop, Trash2, BookmarkCheck} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {api, type Product, type Item, type Quotation, type Rect} from '@/lib/api';
import MappingsDialog from '@/components/mappings-dialog';

const PdfPreview = dynamic(()=>import('@/components/pdf-preview'), {ssr:false, loading:()=> <div className="p-20 text-center text-sm text-[var(--muted)]">กำลังเปิดเอกสาร…</div>});
const labels = {matched:'จับคู่แล้ว', manual:'เลือกแล้ว', needs_review:'รอตรวจสอบ', missing:'ไม่พบสินค้า'};

function Thumbnail({product,imageUrl}: {product:Product|null;imageUrl?:string|null}) {
  const [failed, setFailed] = useState(false);
  useEffect(()=>setFailed(false), [product?.id,imageUrl]);
  return (
    <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[14px] border border-[var(--border)] bg-[var(--surface-soft)] shadow-2xs">
      {(imageUrl||product?.has_image) && !failed ? (
        <img src={imageUrl||`/api/products/${product!.id}/image`} alt={product?.sku||'รูปที่อัปโหลด'} className="h-14 w-14 object-contain" onError={()=>setFailed(true)}/>
      ) : (
        <ImagePlus size={22} className="text-[var(--muted)]/40"/>
      )}
    </div>
  );
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

  return (
    <div className="min-h-screen">
      {/* Top Header */}
      <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-sm shadow-[0_2px_12px_rgba(11,35,27,0.03)]">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3.5 lg:px-10">
          <div className="flex items-center gap-3.5">
            <img
              src="/logo.png"
              alt="Seven Five"
              className="h-11 w-11 shrink-0 object-contain"
            />
            <div>
              <div className="flex items-center gap-2">
                <p className="font-extrabold tracking-tight text-[var(--brand-dark)] text-base">Quotation Studio</p>
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
              </div>
              <p className="text-[11px] font-semibold tracking-wider text-[var(--muted)] uppercase">SEVEN FIVE · PRODUCT IMAGES</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 text-xs text-[var(--text)] border-[var(--border)] hover:bg-[var(--brand-soft)] hover:text-[var(--brand-strong)] hover:border-[var(--brand)]"
              onClick={() => setMappingsOpen(true)}
            >
              <BookmarkCheck size={15} className="text-[var(--brand)]" />
              คู่สินค้าที่จำไว้
            </Button>
            {backendStatus === 'ready' && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-[var(--success-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--success)] border border-[#c3ebd2]">
                <span className="h-2 w-2 rounded-full bg-[var(--success)] animate-pulse" />
                ระบบพร้อมใช้งาน (Production Ready)
              </span>
            )}
            {backendStatus === 'checking' && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-[var(--warning-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--warning)] border border-[#eed09c]" title="กำลังเชื่อมต่อหรือปลุกเซิร์ฟเวอร์ Backend (Render Free Tier)">
                <Loader2 size={12} className="animate-spin text-[var(--warning)]" />
                กำลังเชื่อมต่อเซิร์ฟเวอร์…
              </span>
            )}
            {backendStatus === 'error' && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-[var(--danger-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--danger)] border border-[#fcc]" title="ไม่สามารถเชื่อมต่อ Backend ได้ โปรดตรวจสอบ API_URL บน Vercel">
                <span className="h-2 w-2 rounded-full bg-[var(--danger)]" />
                เชื่อมต่อ Backend ไม่สำเร็จ
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* Step Indicator */}
        <div className="mb-8 flex flex-wrap items-center gap-3 text-sm">
          {['อัปโหลดเอกสาร','ตรวจสอบสินค้า','ดาวน์โหลด PDF'].map((label,index)=>{
            const isActive = index === (quotation?.generated ? 2 : quotation ? 1 : 0);
            const isDone = index < (quotation?.generated ? 2 : quotation ? 1 : 0);
            return (
              <div key={label} className="flex items-center gap-2.5">
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all ${
                  isActive
                    ? 'bg-[var(--brand)] text-white shadow-sm ring-2 ring-[var(--brand-soft)]'
                    : isDone
                    ? 'bg-[var(--brand-soft)] text-[var(--brand-strong)]'
                    : 'bg-[var(--surface-soft)] text-[var(--muted)] border border-[var(--border)]'
                }`}>
                  {index+1}
                </span>
                <span className={`font-medium ${isActive ? 'text-[var(--brand-dark)] font-bold' : 'text-[var(--muted)]'}`}>{label}</span>
                {index<2&&<ArrowRight size={14} className="mx-2 text-[var(--border)]"/>}
              </div>
            );
          })}
        </div>

        {/* Global Notifications */}
        {error&&<div role="alert" className="mb-6 flex items-center justify-between rounded-[var(--radius-lg)] border border-[var(--danger)]/30 bg-[var(--danger-soft)] p-4 text-sm text-[var(--danger)] shadow-2xs">{error}<button aria-label="ปิดข้อความ" onClick={()=>setError('')} className="text-[var(--danger)] hover:opacity-75"><X size={18}/></button></div>}
        {busy&&<div role="status" className="mb-6 flex items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--brand)]/20 bg-[var(--brand-soft)] p-4 text-sm font-medium text-[var(--brand-dark)] shadow-2xs"><Loader2 size={18} className="animate-spin text-[var(--brand)]"/>{busy}</div>}

        {!quotation ? (
          /* Upload State */
          <section className="enter mx-auto max-w-3xl pt-6 text-center">
            <h1 className="text-3xl font-extrabold tracking-tight text-[var(--brand-dark)] leading-snug lg:text-4xl">เติมรูปสินค้าให้ใบเสนอราคา</h1>
            <div onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);void upload(e.dataTransfer.files[0])}} className={`mt-8 rounded-[var(--radius-xl)] border-2 border-dashed px-6 py-14 transition-all shadow-[var(--shadow)] ${drag?'border-[var(--brand)] bg-[var(--brand-soft)] scale-[1.01]':'border-[var(--border)] bg-[var(--surface)] hover:border-[var(--brand)]/50'}`}>
              <div className="mx-auto mb-6 flex h-18 w-18 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--brand-soft)] text-[var(--brand)] shadow-2xs"><UploadCloud size={34}/></div>
              <h2 className="text-lg font-bold text-[var(--brand-dark)]">ลากใบเสนอราคามาวางที่นี่</h2>
              <p className="mb-6 mt-2 text-sm text-[var(--muted)]">หรือเลือกไฟล์จากเครื่องของคุณ</p>
              <Button disabled={!!busy||gesturing} onClick={()=>input.current?.click()} className="shadow-sm"><FileText size={17}/>เลือกไฟล์ PDF</Button>
              <input ref={input} className="hidden" type="file" accept="application/pdf,.pdf" aria-label="เลือกใบเสนอราคา" onChange={e=>void upload(e.target.files?.[0])}/>
            </div>
          </section>
        ) : (
          /* Document Review & Editor State */
          <section className="enter">
            <div className="mb-6">
              <p className="mb-1 text-xs font-bold tracking-widest text-[var(--brand)] uppercase">{quotation.generated?'DOCUMENT READY':'REVIEW YOUR QUOTATION'}</p>
              <h1 className="max-w-2xl break-all text-2xl font-extrabold text-[var(--brand-dark)]">{quotation.filename}</h1>
              <p className="mt-1 text-sm text-[var(--muted)]">ตรวจสอบสินค้าและรูปภาพก่อนดาวน์โหลดเอกสาร</p>
            </div>

            {/* Stat Cards */}
            <div className="mb-6 grid grid-cols-2 gap-3.5 lg:grid-cols-4">
              {([[quotation.items.length,'รายการทั้งหมด'],[matched,'จับคู่สินค้าแล้ว'],[review,'รอตรวจสอบ']] as [number,string][]).map(([n,l])=>(
                <div key={l} className="rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] px-5 py-4 shadow-[var(--shadow-sm)]">
                  <span className="text-2xl font-extrabold text-[var(--brand-dark)] font-['Plus_Jakarta_Sans']">{n}</span>
                  <span className="ml-3 text-xs font-medium text-[var(--muted)]">{l}</span>
                </div>
              ))}
              {missing > 0 ? (
                <button
                  key="missing"
                  onClick={scrollToFirstMissing}
                  className="rounded-[var(--radius-xl)] border border-[#eed09c] bg-[var(--warning-soft)] px-5 py-4 text-left transition-all hover:border-[#d8a85d] hover:shadow-sm group cursor-pointer"
                  title="คลิกเพื่อไปยังรายการแรกที่ยังไม่มีรูป"
                >
                  <span className="text-2xl font-extrabold text-[#9a6700] font-['Plus_Jakarta_Sans']">{missing}</span>
                  <span className="ml-3 text-xs font-semibold text-[#9a6700]">ยังไม่มีรูปที่เลือก</span>
                  <span className="ml-1 text-xs text-[#9a6700] opacity-0 group-hover:opacity-100 transition-opacity">↓</span>
                </button>
              ) : (
                <div key="missing" className="rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] px-5 py-4 shadow-[var(--shadow-sm)]">
                  <span className="text-2xl font-extrabold text-[var(--brand)] font-['Plus_Jakarta_Sans']">{missing}</span>
                  <span className="ml-3 text-xs font-medium text-[var(--muted)]">ยังไม่มีรูปที่เลือก</span>
                </div>
              )}
            </div>

            {/* Ready Banner */}
            {quotation.generated && (
              <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-xl)] border border-[#c3ebd2] bg-[var(--success-soft)] p-5 shadow-2xs">
                <div className="flex items-center gap-3.5">
                  <CheckCircle2 className="h-6 w-6 text-[var(--success)] shrink-0"/>
                  <div>
                    <p className="font-bold text-[var(--brand-dark)]">PDF พร้อมดาวน์โหลด</p>
                    <p className="mt-0.5 text-sm text-[var(--success)]">เพิ่มรูปแล้ว {quotation.images_inserted} จาก {quotation.items.length} รายการ{quotation.images_inserted<quotation.items.length?' · รายการที่เหลือคงเอกสารเดิมไว้':''}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Split View: Stage + Aside List */}
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(330px,1fr)]">
              <PdfPreview
                key={quotation.id}
                quotation={quotation}
                page={page}
                onPage={changePage}
                selected={activeItem}
                selectedIds={selectedIds}
                onSelect={activate}
                onToggleSelect={toggleSelect}
                onClearSelect={clearSelect}
                disabled={!!busy}
                onSave={savePlacement}
                onUpload={uploadImage}
                cropTarget={cropTarget}
                onCropTargetHandled={()=>setCropTarget(null)}
                onGesture={setGesturing}
                canUndo={!!quotation.can_undo}
                canRedo={!!quotation.can_redo}
                onUndo={()=>void undo()}
                onRedo={()=>void redo()}
                onDelete={deleteImages}
              />
              <aside className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]">
                <div className="border-b border-[var(--border)] bg-[var(--surface-soft)]/60 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="font-bold text-[var(--brand-dark)]">สินค้าในใบเสนอราคา</h2>
                      <p className="mt-0.5 text-xs text-[var(--muted)]">เลือกรายการ แล้วลากรูป, ครอบตัด หรือเลือกหลายรูปเพื่อลบพร้อมกัน</p>
                    </div>
                    {quotation.items.some(i => i.has_image) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-[var(--muted)] hover:text-[var(--brand)]"
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
                    <div className="mt-3 flex items-center justify-between rounded-[var(--radius-md)] border border-[#c3ebd2] bg-[var(--brand-soft)] px-3 py-2 text-xs">
                      <span className="font-bold text-[var(--brand-dark)]">เลือกอยู่ {selectedIds.length} รายการ</span>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-[11px] text-[var(--muted)] hover:text-[var(--text)]"
                          onClick={clearSelect}
                        >
                          ยกเลิก
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          className="h-6 gap-1 bg-[var(--danger)] px-2.5 text-[11px] text-white hover:bg-[#991b1b]"
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
                <div ref={listRef} className="max-h-[58vh] divide-y divide-[var(--border)]/60 overflow-auto">
                  {quotation.items.map(item=>(
                    <article key={item.id} ref={el => { itemRefs.current[item.id] = el; }} className={`p-5 transition-colors duration-200 ${highlightId === item.id ? 'bg-[var(--warning-soft)] ring-2 ring-[var(--accent)] ring-inset' : item.id===activeItem || selectedIds.includes(item.id)?'bg-[var(--brand-soft)]/50 hover:bg-[var(--brand-soft)]/70':'hover:bg-[var(--surface-soft)]'}`}>
                      <div className="flex gap-3">
                        <div className="flex flex-col items-center gap-2 pt-0.5">
                          <input
                            type="checkbox"
                            data-testid={`checkbox-item-${item.id}`}
                            aria-label={`เลือกรูปรายการ ${item.number}`}
                            checked={selectedIds.includes(item.id)}
                            disabled={!item.has_image || !!busy || gesturing}
                            onChange={() => toggleSelect(item.id)}
                            className="h-4 w-4 rounded-[4px] border-[var(--border)] text-[var(--brand)] focus:ring-[var(--brand)] cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed accent-[#0c7255]"
                          />
                          <Thumbnail product={item.product} imageUrl={item.image_url}/>
                        </div>
                        <div className="min-w-0 flex-1">
                          <button className="text-left text-sm font-bold text-[var(--brand-dark)] hover:text-[var(--brand)]" disabled={!!busy||gesturing} onClick={()=>activate(item.id)}>{item.number}. {item.sku||'รายการเพิ่มเติม'}</button>
                          <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--muted)]">{item.description}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold border ${
                              item.status==='matched'||item.status==='manual'
                                ? 'bg-[var(--success-soft)] text-[var(--success)] border-[#c3ebd2]'
                                : 'bg-[var(--warning-soft)] text-[var(--warning)] border-[#eed09c]'
                            }`}>
                              {labels[item.status]}
                            </span>
                            {item.match_method === 'manual' && item.status === 'matched' && (
                              <span className="rounded-full bg-[var(--accent-soft)] px-2.5 py-0.5 text-[11px] font-semibold text-[#9a6700] border border-[#eed09c]">จำจากประวัติ</span>
                            )}
                            <span className="text-[11px] text-[var(--muted)]">หน้า {item.page}</span>
                          </div>
                          {item.product&&<p className="mt-2 text-xs text-[var(--muted)]">เลือก: <span className="font-semibold text-[var(--text)]">{item.product.sku}</span></p>}
                          {(!item.has_image||item.warning)&&<p className="mt-2 text-xs font-medium text-[var(--warning)]">{item.warning?'รูปไม่พร้อมใช้หรือพื้นที่ไม่พอ ระบบข้ามรูปนี้':'ยังไม่มีรูปสินค้า · สร้าง PDF ต่อได้'}</p>}
                          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                            <Button variant="ghost" size="sm" className="h-7 px-0 text-xs font-semibold text-[var(--brand)] hover:text-[var(--brand-strong)] hover:bg-transparent" disabled={!!busy||gesturing} onClick={()=>{activate(item.id);setEditing(item);setQuery(item.sku||'');setResults([])}}><Search size={13}/>{item.product?'เปลี่ยนสินค้า / รูป':'ค้นหาและเลือกสินค้า'}</Button>
                            <Button variant="ghost" size="sm" className="h-7 px-0 text-xs font-semibold text-[var(--brand)] hover:text-[var(--brand-strong)] hover:bg-transparent" disabled={!!busy||gesturing} onClick={()=>activate(item.id)}><ImagePlus size={13}/>จัดรูป / วางภาพ</Button>
                            {item.has_image&&<Button variant="ghost" size="sm" className="h-7 px-0 text-xs font-semibold text-[var(--brand)] hover:text-[var(--brand-strong)] hover:bg-transparent" disabled={!!busy||gesturing} onClick={()=>{activate(item.id);setCropTarget(item.id);}}><Crop size={13}/>ครอบตัดรูป</Button>}
                            {item.has_image&&<Button variant="ghost" size="sm" className="h-7 px-0 text-xs font-semibold text-[var(--danger)] hover:bg-transparent hover:text-[#991b1b]" disabled={!!busy||gesturing} onClick={()=>void deleteImages([item.id])}><Trash2 size={13}/>ลบรูป</Button>}
                            {item.uploaded_image&&item.product&&<Button variant="ghost" size="sm" className="h-7 px-0 text-xs text-[var(--muted)] hover:text-[var(--brand)] hover:bg-transparent" disabled={!!busy||gesturing} onClick={()=>void select(item.product!,item.id)}><RotateCcw size={12}/>คืนค่ารูป Catalog</Button>}
                          </div>
                          {item.uploaded_image&&<p className="mt-1 text-xs font-medium text-[var(--brand)]">ใช้รูปที่ปรับแต่ง / อัปโหลด / วางจากคลิปบอร์ด</p>}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="border-t border-[var(--border)] bg-[var(--surface-soft)]/60 p-5">
                  {quotation.generated ? (
                    <>
                      <Button asChild className="w-full bg-[var(--brand-dark)] hover:bg-[var(--brand-strong)] text-white shadow-sm font-semibold">
                        <a href={`/api/quotations/${quotation.id}/download`}><Download size={17}/>ดาวน์โหลด PDF</a>
                      </Button>
                      <Button
                        variant="outline"
                        className="mt-2.5 w-full border-[var(--border)] text-[var(--muted)] hover:text-[var(--brand-dark)] hover:bg-[var(--surface)] hover:border-[var(--brand)]/40 font-semibold"
                        disabled={!!busy||gesturing}
                        onClick={()=>{setQuotation(null);setSelectedIds([]);setError('')}}
                      >
                        <RotateCcw size={16}/>เริ่มเอกสารใหม่
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button className="w-full shadow-sm" disabled={!!busy||gesturing} onClick={()=>void generate()}>
                        <ImagePlus size={17}/>{missing?'สร้าง PDF โดยข้ามรูปที่ยังไม่มี':'สร้าง PDF พร้อมรูปสินค้า'}<ArrowRight size={16}/>
                      </Button>
                      <Button
                        variant="outline"
                        className="mt-2.5 w-full border-[var(--border)] text-[var(--muted)] hover:text-[var(--brand-dark)] hover:bg-[var(--surface)] hover:border-[var(--brand)]/40 font-semibold"
                        disabled={!!busy||gesturing}
                        onClick={()=>{setQuotation(null);setSelectedIds([]);setError('')}}
                      >
                        <RotateCcw size={16}/>เริ่มเอกสารใหม่
                      </Button>
                    </>
                  )}
                </div>
              </aside>
            </div>
          </section>
        )}

        {/* Search & Select SKU Dialog */}
        {editing&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-5" onClick={()=>!busy&&setEditing(null)}>
          <div role="dialog" aria-modal="true" aria-labelledby="search-title" className="max-h-[80vh] w-full max-w-xl overflow-auto rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[var(--shadow)]" onClick={e=>e.stopPropagation()}>
            <div className="mb-5 flex items-center justify-between">
              <h2 id="search-title" className="font-bold text-[var(--brand-dark)] text-base">เลือกสินค้าสำหรับรายการ {editing.number}</h2>
              <Button variant="ghost" size="icon" aria-label="ปิด" disabled={!!busy||gesturing} onClick={()=>setEditing(null)}><X size={18}/></Button>
            </div>
            <input autoFocus aria-label="ค้นหา SKU หรือรุ่นสินค้า" placeholder="ค้นหา SKU หรือรุ่นสินค้า…" value={query} onChange={e=>setQuery(e.target.value)} className="mb-4 w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-soft)] px-4 py-2.5 text-sm focus:bg-[var(--surface)] focus:border-[var(--brand)] focus:outline-none"/>
            {editing.candidates.length>0&&<p className="mb-2 text-xs font-medium text-[var(--warning)]">พบสินค้าที่เป็นไปได้หลายรายการ กรุณาเลือกให้ตรงกับใบเสนอราคา</p>}
            {searching&&<p className="py-3 text-sm text-[var(--muted)]">กำลังค้นหา…</p>}
            <div className="space-y-1">
              {[...new Map([...editing.candidates,...results].map(p=>[p.id,p])).values()].map(p=>(
                <button key={p.id} disabled={!!busy||gesturing} onClick={()=>void select(p)} className="flex w-full items-center gap-4 rounded-[var(--radius-lg)] p-3 text-left transition-colors hover:bg-[var(--brand-soft)] disabled:opacity-50 border border-transparent hover:border-[var(--brand)]/30 cursor-pointer">
                  <Thumbnail product={p}/>
                  <div>
                    <p className="text-sm font-bold text-[var(--brand-dark)]">{p.sku}</p>
                    <p className="mt-1 text-xs text-[var(--muted)]">{p.model}{!p.has_image?' · ไม่มีรูป':''}</p>
                  </div>
                  <ArrowRight className="ml-auto text-[var(--brand)]" size={16}/>
                </button>
              ))}
            </div>
            {!searching&&!results.length&&!editing.candidates.length&&<p className="p-6 text-center text-sm text-[var(--muted)]">ไม่พบสินค้า ลองค้นหารหัสหรือรุ่นอื่น</p>}
          </div>
        </div>}

        <MappingsDialog
          open={mappingsOpen}
          onClose={() => setMappingsOpen(false)}
        />
      </main>
    </div>
  );
}
