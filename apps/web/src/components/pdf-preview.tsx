"use client";
import {useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent} from 'react';
import {Document, Page, pdfjs} from 'react-pdf';
import {ChevronLeft, ChevronRight, Upload, RotateCcw, Minus, Plus, Move, ZoomIn, ZoomOut, Clipboard, Crop, Check, X, Loader2, Undo2, Redo2, Hand, Trash2} from 'lucide-react';
import {Button} from './ui/button';
import type {Item, Quotation, Rect} from '@/lib/api';
import {initialPlacement, moveRect, resizeRect, isSafe} from '@/lib/placement';
pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();

type Props = {
  quotation: Quotation;
  page: number;
  onPage: (page: number) => void;
  selected: number | null;
  selectedIds?: number[];
  onSelect: (id: number) => void;
  onToggleSelect?: (id: number) => void;
  onClearSelect?: () => void;
  disabled: boolean;
  onSave: (id: number, rect: Rect | null) => Promise<void>;
  onUpload: (id: number, file: File) => Promise<void>;
  cropTarget?: number | null;
  onCropTargetHandled?: () => void;
  onGesture: (active: boolean) => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  onDelete?: (ids: number[]) => Promise<void> | void;
};

type Gesture = {
  item: Item;
  start: Rect;
  current: Rect;
  x: number;
  y: number;
  width: number;
  height: number;
  mode: 'move' | 'resize';
  pointer: number;
};

type CropGesture = {
  handle: 'crop-move' | 'crop-nw' | 'crop-ne' | 'crop-sw' | 'crop-se' | 'crop-n' | 'crop-s' | 'crop-w' | 'crop-e';
  startX: number;
  startY: number;
  startRect: Rect;
  boxW: number;
  boxH: number;
  pointerId: number;
};

const style = (r: Rect): CSSProperties => ({
  left: `${r.x * 100}%`,
  top: `${r.y * 100}%`,
  width: `${r.width * 100}%`,
  height: `${r.height * 100}%`,
});

export default function PdfPreview({
  quotation,
  page,
  onPage,
  selected,
  selectedIds = [],
  onSelect,
  onToggleSelect,
  onClearSelect,
  disabled,
  onSave,
  onUpload,
  cropTarget,
  onCropTargetHandled,
  onGesture,
  canUndo = false,
  canRedo = false,
  onUndo,
  onRedo,
  onDelete,
}: Props) {
  const [rendered, setRendered] = useState(false);
  const [available, setAvailable] = useState(640);
  const [zoom, setZoom] = useState(1);
  const [draft, setDraft] = useState<{id: number; rect: Rect} | null>(null);
  const [message, setMessage] = useState('');
  const [cropMode, setCropMode] = useState<{itemId: number; rect: Rect} | null>(null);
  const [savingCrop, setSavingCrop] = useState(false);

  const viewport = useRef<HTMLDivElement>(null);
  const layer = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const cropGesture = useRef<CropGesture | null>(null);
  const upload = useRef<HTMLInputElement>(null);
  const uploadTarget = useRef<number | null>(null);
  const overlayRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const lastClickRef = useRef<{id: number; time: number}>({id: -1, time: 0});

  const [isSpaceDown, setIsSpaceDown] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const panRef = useRef<{
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
    pointerId: number;
  } | null>(null);

  const activeRef = useRef<Item | undefined>(undefined);
  const cropModeRef = useRef(cropMode);
  cropModeRef.current = cropMode;
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  const onDeleteRef = useRef(onDelete);
  onDeleteRef.current = onDelete;
  const selectedIdsRef = useRef(selectedIds);
  selectedIdsRef.current = selectedIds;

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }
      if (e.code === 'Space') {
        if (target && target.tagName === 'BUTTON') {
          target.blur();
        }
        e.preventDefault();
        if (!e.repeat) {
          setIsSpaceDown(true);
        }
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (!cropModeRef.current && !disabledRef.current) {
          const ids = selectedIdsRef.current.length > 0
            ? selectedIdsRef.current
            : (activeRef.current?.has_image ? [activeRef.current.id] : []);
          if (ids.length > 0) {
            e.preventDefault();
            void onDeleteRef.current?.(ids);
          }
        }
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        setIsSpaceDown(false);
        if (panRef.current) {
          panRef.current = null;
          setIsPanning(false);
        }
      }
    };

    const onBlur = () => {
      setIsSpaceDown(false);
      if (panRef.current) {
        panRef.current = null;
        setIsPanning(false);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    window.addEventListener('blur', onBlur);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', onBlur);
    };
  }, []);

  useEffect(() => {
    const node = viewport.current;
    if (!node) return;

    const onPointerDown = (e: PointerEvent) => {
      if ((isSpaceDown && e.button === 0) || e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        panRef.current = {
          startX: e.clientX,
          startY: e.clientY,
          scrollLeft: node.scrollLeft,
          scrollTop: node.scrollTop,
          pointerId: e.pointerId,
        };
        setIsPanning(true);

        const onPointerMove = (ev: PointerEvent) => {
          if (!panRef.current) return;
          ev.preventDefault();
          const dx = ev.clientX - panRef.current.startX;
          const dy = ev.clientY - panRef.current.startY;
          node.scrollLeft = panRef.current.scrollLeft - dx;
          node.scrollTop = panRef.current.scrollTop - dy;
        };

        const onPointerUp = () => {
          window.removeEventListener('pointermove', onPointerMove);
          window.removeEventListener('pointerup', onPointerUp);
          window.removeEventListener('pointercancel', onPointerUp);
          panRef.current = null;
          setIsPanning(false);
        };

        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
        window.addEventListener('pointercancel', onPointerUp);
      }
    };

    node.addEventListener('pointerdown', onPointerDown, { capture: true });
    return () => {
      node.removeEventListener('pointerdown', onPointerDown, { capture: true });
    };
  }, [isSpaceDown]);

  const geometry = quotation.pages[page - 1];
  const active = quotation.items.find((i) => i.id === selected && i.page === page);
  activeRef.current = active;
  const activeRect = active ? (draft?.id === active.id ? draft.rect : initialPlacement(active, geometry)) : null;
  const width = Math.max(240, Math.floor(available * zoom));

  useEffect(() => {
    const node = viewport.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setAvailable(Math.max(240, entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setRendered(false);
    setDraft(null);
    setMessage('');
    setCropMode(null);
  }, [page]);

  useEffect(() => {
    setDraft(null);
  }, [quotation.revision]);

  // Trigger crop mode when cropTarget prop changes
  useEffect(() => {
    if (cropTarget !== undefined && cropTarget !== null) {
      const targetItem = quotation.items.find((i) => i.id === cropTarget);
      if (targetItem && targetItem.has_image) {
        setCropMode({itemId: cropTarget, rect: {x: 0.05, y: 0.05, width: 0.9, height: 0.9}});
        setMessage('');
      }
      onCropTargetHandled?.();
    }
  }, [cropTarget, quotation.items, onCropTargetHandled]);

  // Keyboard shortcut for crop mode: Enter to apply, Escape to cancel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!cropMode) return;
      if (e.key === 'Escape' && !savingCrop) {
        e.preventDefault();
        cancelCrop();
      } else if (e.key === 'Enter' && !savingCrop) {
        e.preventDefault();
        void applyCrop();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [cropMode, savingCrop]);

  // Paste image handler from clipboard
  useEffect(() => {
    const listener = (event: ClipboardEvent) => {
      if (disabled || !active || document.querySelector('[role="dialog"]') || cropMode) return;
      const target = event.target as HTMLElement;
      if (target?.closest('input,textarea,[contenteditable="true"]')) return;
      const image = Array.from(event.clipboardData?.items || [])
        .find((i) => i.kind === 'file' && i.type.startsWith('image/'))
        ?.getAsFile();
      if (image) {
        event.preventDefault();
        setMessage('');
        void onUpload(active.id, image);
      }
    };
    document.addEventListener('paste', listener);
    return () => document.removeEventListener('paste', listener);
  }, [disabled, active, onUpload, cropMode]);

  function start(event: ReactPointerEvent<HTMLElement>, item: Item, rect: Rect, mode: 'move' | 'resize') {
    if (disabled || event.button !== 0 || cropMode) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.shiftKey || event.ctrlKey || event.metaKey) {
      onToggleSelect?.(item.id);
      return;
    }
    const bounds = layer.current?.getBoundingClientRect();
    if (!bounds) return;
    onSelect(item.id);
    onGesture(true);
    setMessage('');
    gesture.current = {
      item,
      start: rect,
      current: rect,
      x: event.clientX,
      y: event.clientY,
      width: bounds.width,
      height: bounds.height,
      mode,
      pointer: event.pointerId,
    };
    setDraft({id: item.id, rect});
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function move(event: ReactPointerEvent<HTMLElement>) {
    const g = gesture.current;
    if (!g || g.pointer !== event.pointerId) return;
    const dx = (event.clientX - g.x) / g.width;
    const dy = (event.clientY - g.y) / g.height;
    let rect: Rect;
    if (g.mode === 'move') {
      rect = moveRect(g.start, dx, dy, g.item.bounds);
    } else {
      const rx = dx / g.start.width;
      const ry = dy / g.start.height;
      rect = resizeRect(g.start, 1 + (Math.abs(rx) > Math.abs(ry) ? rx : ry), g.item.bounds, geometry);
    }
    g.current = rect;
    setDraft({id: g.item.id, rect});
  }

  async function finish(event: ReactPointerEvent<HTMLElement>, cancel = false) {
    const g = gesture.current;
    if (!g || g.pointer !== event.pointerId) return;
    const movedDist = Math.hypot(event.clientX - g.x, event.clientY - g.y);
    gesture.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (cancel) {
      setDraft(null);
      onGesture(false);
      return;
    }

    if (movedDist < 5) {
      const now = Date.now();
      if (lastClickRef.current.id === g.item.id && now - lastClickRef.current.time < 400) {
        startCrop(g.item);
        lastClickRef.current = {id: -1, time: 0};
      } else {
        lastClickRef.current = {id: g.item.id, time: now};
      }
      setDraft(null);
      onGesture(false);
      return;
    }

    if (!isSafe(g.current, g.item.bounds, geometry)) {
      setMessage('รูปทับข้อความหรืออยู่นอกพื้นที่ กรุณาลองเลื่อนหรือย่อใหม่');
      setDraft(null);
      onGesture(false);
      return;
    }
    try {
      await onSave(g.item.id, g.current);
    } catch {
      /* Parent displays the API error. */
    } finally {
      setDraft(null);
      onGesture(false);
    }
  }

  async function resize(factor: number) {
    if (!active || !activeRect || disabled || cropMode) return;
    const rect = resizeRect(activeRect, factor, active.bounds, geometry);
    if (!isSafe(rect, active.bounds, geometry)) {
      setMessage('ขนาดนี้ทับข้อความ ลองเลื่อนรูปไปยังช่องว่างก่อนขยาย');
      return;
    }
    setMessage('');
    setDraft({id: active.id, rect});
    try {
      await onSave(active.id, rect);
    } catch {
    } finally {
      setDraft(null);
    }
  }

  async function nudge(event: React.KeyboardEvent, item: Item, rect: Rect) {
    if (cropMode) return;
    const directions: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const direction = directions[event.key];
    if (!direction || disabled) return;
    event.preventDefault();
    const step = event.shiftKey ? 5 : 1;
    const next = moveRect(rect, (direction[0] * step) / geometry.width, (direction[1] * step) / geometry.height, item.bounds);
    if (!isSafe(next, item.bounds, geometry)) {
      setMessage('รูปทับข้อความ กรุณาเลื่อนไปทางอื่น');
      return;
    }
    try {
      await onSave(item.id, next);
    } catch {}
  }

  function chooseUpload() {
    if (active) {
      uploadTarget.current = active.id;
      upload.current?.click();
    }
  }

  // --- Canva-Style Inline Cropping Logic ---

  function startCrop(item: Item) {
    if (disabled || !item.has_image) return;
    onSelect(item.id);
    setCropMode({itemId: item.id, rect: {x: 0.05, y: 0.05, width: 0.9, height: 0.9}});
    setMessage('');
  }

  function cancelCrop() {
    setCropMode(null);
    setMessage('');
  }

  function resetCrop() {
    if (!cropMode) return;
    setCropMode({itemId: cropMode.itemId, rect: {x: 0, y: 0, width: 1, height: 1}});
  }

  function startCropDrag(e: ReactPointerEvent<HTMLElement>, handle: CropGesture['handle']) {
    if (disabled || savingCrop || !cropMode || isSpaceDown) return;
    e.preventDefault();
    e.stopPropagation();

    const overlay = overlayRefs.current[cropMode.itemId];
    if (!overlay) return;

    const b = overlay.getBoundingClientRect();
    cropGesture.current = {
      handle,
      startX: e.clientX,
      startY: e.clientY,
      startRect: {...cropMode.rect},
      boxW: Math.max(20, b.width),
      boxH: Math.max(20, b.height),
      pointerId: e.pointerId,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onCropPointerMove(e: ReactPointerEvent<HTMLElement>) {
    const g = cropGesture.current;
    if (!g || g.pointerId !== e.pointerId || !cropMode) return;

    const dx = (e.clientX - g.startX) / g.boxW;
    const dy = (e.clientY - g.startY) / g.boxH;
    const start = g.startRect;
    const minSize = 0.05;

    if (g.handle === 'crop-move') {
      const maxX = 1 - start.width;
      const maxY = 1 - start.height;
      const nextX = Math.max(0, Math.min(maxX, start.x + dx));
      const nextY = Math.max(0, Math.min(maxY, start.y + dy));
      setCropMode({itemId: cropMode.itemId, rect: {...start, x: nextX, y: nextY}});
      return;
    }

    let nextX = start.x;
    let nextY = start.y;
    let nextW = start.width;
    let nextH = start.height;

    if (g.handle.includes('w')) {
      const right = start.x + start.width;
      nextX = Math.min(right - minSize, Math.max(0, start.x + dx));
      nextW = right - nextX;
    } else if (g.handle.includes('e')) {
      nextW = Math.min(1 - start.x, Math.max(minSize, start.width + dx));
    }

    if (g.handle.includes('n')) {
      const bottom = start.y + start.height;
      nextY = Math.min(bottom - minSize, Math.max(0, start.y + dy));
      nextH = bottom - nextY;
    } else if (g.handle.includes('s')) {
      nextH = Math.min(1 - start.y, Math.max(minSize, start.height + dy));
    }

    setCropMode({itemId: cropMode.itemId, rect: {x: nextX, y: nextY, width: nextW, height: nextH}});
  }

  function onCropPointerUp(e: ReactPointerEvent<HTMLElement>) {
    const g = cropGesture.current;
    if (!g || g.pointerId !== e.pointerId) return;
    cropGesture.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  async function applyCrop() {
    if (!cropMode || savingCrop) return;
    const item = quotation.items.find((i) => i.id === cropMode.itemId);
    if (!item || !item.image_url) {
      setCropMode(null);
      return;
    }

    setSavingCrop(true);
    setMessage('');

    try {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error('ไม่สามารถโหลดภาพสำหรับครอบตัดได้'));
        img.src = item.image_url!;
      });

      const natW = img.naturalWidth;
      const natH = img.naturalHeight;

      const sx = Math.max(0, Math.floor(cropMode.rect.x * natW));
      const sy = Math.max(0, Math.floor(cropMode.rect.y * natH));
      const sw = Math.min(natW - sx, Math.max(1, Math.round(cropMode.rect.width * natW)));
      const sh = Math.min(natH - sy, Math.max(1, Math.round(cropMode.rect.height * natH)));

      const canvas = document.createElement('canvas');
      canvas.width = sw;
      canvas.height = sh;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('ไม่สามารถสร้าง canvas ได้');

      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);

      const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, 'image/png'));
      if (!blob) throw new Error('ไม่สามารถประมวลผลรูปที่ครอบตัดได้');

      const file = new File([blob], `cropped-item-${item.number}.png`, {type: 'image/png'});
      await onUpload(item.id, file);
      setCropMode(null);
    } catch (err) {
      setMessage((err as Error).message || 'เกิดข้อผิดพลาดในการครอบตัด');
    } finally {
      setSavingCrop(false);
    }
  }

  return (
    <div data-testid="pdf-preview" data-rendered={rendered} className="overflow-hidden rounded-[var(--radius-xl)] border border-[var(--border)] bg-[#e2e8e5] shadow-[var(--shadow)]">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <span className="text-sm font-bold text-[var(--brand-dark)]">จัดรูปบนใบเสนอราคา</span>
        <div className="flex items-center gap-1 text-xs text-[var(--muted)]">
          <Button
            variant={isSpaceDown ? 'outline' : 'ghost'}
            size="icon"
            aria-label="เครื่องมือเลื่อนมุมมอง (Spacebar)"
            title="เครื่องมือเลื่อนมุมมอง (กด Spacebar ค้างเพื่อเลื่อน)"
            onClick={() => setIsSpaceDown((prev) => !prev)}
            className={isSpaceDown ? 'bg-[var(--brand-soft)] text-[var(--brand-strong)] border-[var(--brand)]' : 'text-[var(--muted)]'}
          >
            <Hand size={16} />
          </Button>
          <div className="mx-0.5 h-4 w-px bg-[var(--border)]" />
          <Button variant="ghost" size="icon" aria-label="ซูมออก" disabled={zoom <= 1 || disabled || !!cropMode} onClick={() => setZoom((z) => Math.max(1, z - 0.25))}>
            <ZoomOut size={16} />
          </Button>
          <span className="w-10 text-center font-semibold font-mono text-[var(--text)]">{Math.round(zoom * 100)}%</span>
          <Button variant="ghost" size="icon" aria-label="ซูมเข้า" disabled={zoom >= 2 || disabled || !!cropMode} onClick={() => setZoom((z) => Math.min(2, z + 0.25))}>
            <ZoomIn size={16} />
          </Button>
          <Button variant="ghost" size="icon" aria-label="หน้าก่อนหน้า" disabled={page <= 1 || disabled || !!cropMode} onClick={() => onPage(page - 1)}>
            <ChevronLeft size={16} />
          </Button>
          <span className="font-semibold text-[var(--brand-dark)]">
            {page} / {quotation.pages.length}
          </span>
          <Button variant="ghost" size="icon" aria-label="หน้าถัดไป" disabled={page >= quotation.pages.length || disabled || !!cropMode} onClick={() => onPage(page + 1)}>
            <ChevronRight size={16} />
          </Button>
        </div>
      </div>

      {/* Toolbar / Actions */}
      <div className="border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        {cropMode ? (
          /* Inline Crop Active Toolbar */
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--brand-soft)] border border-[#c3ebd2] px-3 py-1.5 text-xs font-bold text-[var(--brand-dark)]">
                <Crop size={14} className="text-[var(--brand)]" />
                โหมดครอบตัดภาพ: รายการ {active?.number} ({active?.sku || 'สินค้า'})
              </span>
              <span className="text-xs text-[var(--muted)] hidden sm:inline">ลากกรอบมุมหรือขอบเพื่อครอบตัด</span>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => void applyCrop()} disabled={savingCrop}>
                {savingCrop ? <Loader2 size={14} className="animate-spin mr-1.5" /> : <Check size={14} className="mr-1.5" />}
                เสร็จสิ้นการครอบตัด
              </Button>
              <Button variant="outline" size="sm" onClick={cancelCrop} disabled={savingCrop}>
                <X size={14} className="mr-1.5" />
                ยกเลิก
              </Button>
              <Button variant="ghost" size="sm" onClick={resetCrop} disabled={savingCrop}>
                <RotateCcw size={13} className="mr-1.5" />
                เลือกทั้งภาพ
              </Button>
            </div>
          </div>
        ) : selectedIds.length > 1 ? (
          /* Batch Selection Toolbar */
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="rounded-[var(--radius-md)] bg-[var(--brand-soft)] border border-[#c3ebd2] px-3 py-1.5 text-xs font-bold text-[var(--brand-dark)]">
                เลือกแล้ว {selectedIds.length} รูป
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`ลบรูปที่เลือก (${selectedIds.length})`}
                title={`ลบรูปภาพที่เลือก ${selectedIds.length} รายการ (Delete)`}
                disabled={disabled}
                onClick={(e) => {
                  (e.currentTarget as HTMLElement)?.blur();
                  void onDelete?.(selectedIds);
                }}
                className="text-[var(--danger)] hover:bg-[var(--danger-soft)] hover:text-[#991b1b] font-semibold"
              >
                <Trash2 size={14} />
                ลบรูปที่เลือก ({selectedIds.length})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                aria-label="ยกเลิกการเลือก"
                disabled={disabled}
                onClick={() => onClearSelect?.()}
                className="text-[var(--muted)] hover:text-[var(--text)]"
              >
                <X size={14} />
                ยกเลิก
              </Button>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                aria-label="ย้อนกลับ (Ctrl+Z)"
                title="ย้อนกลับ (Ctrl+Z)"
                disabled={!canUndo || disabled}
                onClick={(e) => {
                  e.currentTarget.blur();
                  onUndo?.();
                }}
                className="text-[var(--text)]"
              >
                <Undo2 size={14} />
                ย้อนกลับ
              </Button>
              <Button
                variant="outline"
                size="sm"
                aria-label="ทำซ้ำ (Ctrl+Y)"
                title="ทำซ้ำ (Ctrl+Y)"
                disabled={!canRedo || disabled}
                onClick={(e) => {
                  e.currentTarget.blur();
                  onRedo?.();
                }}
                className="text-[var(--text)]"
              >
                <Redo2 size={14} />
                ทำซ้ำ
              </Button>
            </div>
          </div>
        ) : (
          /* Normal Editing Toolbar */
          <>
            {selectedIds.length > 1 ? (
              <div className="mb-3 flex items-center justify-between rounded-[var(--radius-md)] border border-[#c3ebd2] bg-[var(--brand-soft)] px-3 py-1.5 text-xs text-[var(--brand-dark)]">
                <span className="font-bold">
                  เลือกอยู่ {selectedIds.length} รายการ
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-[var(--muted)] hover:text-[var(--text)]"
                    onClick={onClearSelect}
                  >
                    ยกเลิกการเลือก
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="h-7 gap-1 bg-[var(--danger)] text-xs text-white hover:bg-[#991b1b]"
                    onClick={() => void onDelete?.(selectedIds)}
                  >
                    <Trash2 size={13} />
                    ลบรูปที่เลือก ({selectedIds.length})
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mb-3 flex items-center gap-2 text-xs font-semibold text-[var(--brand-dark)]">
                <Move size={14} className="text-[var(--brand)]" />
                {active ? `กำลังแก้รูป: รายการ ${active.number} · ${active.sku || 'รูปที่เลือก'}` : 'เลือกรายการสินค้าทางขวาเพื่อจัดรูป'}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" disabled={!active || disabled} onClick={chooseUpload}>
                <Upload size={14} />
                อัปโหลดรูป
              </Button>
              <Button variant="outline" size="sm" disabled={!active?.has_image || disabled} onClick={() => active && startCrop(active)}>
                <Crop size={14} />
                ครอบตัด
              </Button>
              <Button variant="outline" size="sm" aria-label="ย่อรูป" disabled={!activeRect || disabled} onClick={() => void resize(0.9)}>
                <Minus size={14} />
                ย่อ
              </Button>
              <Button variant="outline" size="sm" aria-label="ขยายรูป" disabled={!activeRect || disabled} onClick={() => void resize(1.1)}>
                <Plus size={14} />
                ขยาย
              </Button>
              <Button variant="ghost" size="sm" disabled={!active?.has_image || disabled} onClick={() => active && void onSave(active.id, null).catch(() => {})}>
                <RotateCcw size={13} />
                จัดอัตโนมัติ
              </Button>
              <Button
                variant="ghost"
                size="sm"
                aria-label={selectedIds.length > 1 ? `ลบรูปที่เลือก (${selectedIds.length}) (Delete)` : 'ลบรูปภาพ (Delete)'}
                title={selectedIds.length > 1 ? `ลบรูปที่เลือก (${selectedIds.length}) (Delete)` : 'ลบรูปภาพ (Delete)'}
                disabled={(selectedIds.length === 0 && !active?.has_image) || disabled}
                onClick={(e) => {
                  (e.currentTarget as HTMLElement)?.blur();
                  const ids = selectedIds.length > 0 ? selectedIds : (active ? [active.id] : []);
                  if (ids.length > 0) void onDelete?.(ids);
                }}
                className="text-[var(--danger)] hover:bg-[var(--danger-soft)] hover:text-[#991b1b]"
              >
                <Trash2 size={13} />
                {selectedIds.length > 1 ? `ลบรูป (${selectedIds.length})` : 'ลบรูป'}
              </Button>

              <div className="mx-1 h-5 w-px bg-[var(--border)]" />

              <Button
                variant="outline"
                size="sm"
                aria-label="ย้อนกลับ (Ctrl+Z)"
                title="ย้อนกลับ (Ctrl+Z)"
                disabled={!canUndo || disabled}
                onClick={(e) => {
                  e.currentTarget.blur();
                  onUndo?.();
                }}
                className="text-[var(--text)]"
              >
                <Undo2 size={14} />
                ย้อนกลับ
              </Button>
              <Button
                variant="outline"
                size="sm"
                aria-label="ทำซ้ำ (Ctrl+Y)"
                title="ทำซ้ำ (Ctrl+Y)"
                disabled={!canRedo || disabled}
                onClick={(e) => {
                  e.currentTarget.blur();
                  onRedo?.();
                }}
                className="text-[var(--text)]"
              >
                <Redo2 size={14} />
                ทำซ้ำ
              </Button>
            </div>
            <p className="mt-3 flex items-center gap-2 text-xs leading-5 text-[var(--muted)]">
              <Clipboard size={13} className="shrink-0 text-[var(--accent)]" />
              ดับเบิลคลิกรูปเพื่อครอบตัดแบบ Canva · ลากรูปเพื่อย้าย · Shift+คลิก หรือติ๊กกล่องเพื่อเลือกหลายรูป · Delete ลบรูป · Ctrl+Z ย้อนกลับ · Ctrl+Y ทำซ้ำ · Ctrl+V วางภาพ
            </p>
          </>
        )}
        <input ref={upload} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label="เลือกรูปจากเครื่อง" onChange={(e) => {
          const file = e.target.files?.[0];
          const id = uploadTarget.current;
          if (file && id !== null) void onUpload(id, file);
          e.target.value = '';
        }} />
        {message && <p role="status" className="mt-2 text-xs font-semibold text-[var(--warning)]">{message}</p>}
      </div>

      {/* PDF Stage Viewport */}
      <div
        ref={viewport}
        data-testid="pdf-viewport"
        className={`pdf-stage relative min-h-96 overflow-auto p-5 lg:max-h-[75vh] select-none ${
          isPanning ? 'cursor-grabbing' : isSpaceDown ? 'cursor-grab' : ''
        }`}
        onDragOver={(e) => {
          if (active && !disabled && !cropMode && !isSpaceDown) e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files[0];
          if (active && file && !disabled && !cropMode && !isSpaceDown) void onUpload(active.id, file);
        }}
      >
        {/* Floating Pan Indicator */}
        {isSpaceDown && (
          <div
            data-testid="pan-mode-indicator"
            className="pointer-events-none sticky top-2 left-2 z-40 inline-flex items-center gap-1.5 rounded-full bg-stone-900/85 px-3 py-1 text-xs font-medium text-white shadow-lg backdrop-blur"
          >
            <Hand size={13} className="text-teal-400" />
            <span>{isPanning ? 'กำลังเลื่อนดูเอกสาร…' : 'กด Spacebar ค้างแล้วลากเพื่อเลื่อนดูเอกสาร'}</span>
          </div>
        )}

        <div ref={layer} className="relative mx-auto" style={{width, minWidth: width, aspectRatio: `${geometry.width}/${geometry.height}`}}>
          <Document file={`/api/quotations/${quotation.id}/original`} loading={<p className="p-12">กำลังโหลดเอกสาร…</p>} error={<p className="p-12 text-red-700">เปิดตัวอย่างไม่ได้ กรุณาลองโหลดหน้าใหม่</p>}>
            <Page pageNumber={page} width={width} renderTextLayer={false} renderAnnotationLayer={false} onRenderSuccess={() => setRendered(true)} />
          </Document>

          {rendered && (
            <div className="pointer-events-none absolute inset-0">
              {active && <div data-testid="item-bounds" className="absolute border border-dashed border-[var(--brand)]/60 bg-[var(--brand-soft)]/20" style={style(active.bounds)} />}

              {quotation.items
                .filter((i) => i.page === page && i.image_url)
                .map((item) => {
                  const rect = draft?.id === item.id ? draft.rect : initialPlacement(item, geometry);
                  if (!rect) return null;
                  const isSelected = selectedIds.includes(item.id) || item.id === active?.id;
                  const isCroppingThis = cropMode?.itemId === item.id;
                  const safe = isSafe(rect, item.bounds, geometry);

                  return (
                    <div
                      key={item.id}
                      ref={(el) => {
                        overlayRefs.current[item.id] = el;
                      }}
                      data-testid={`image-overlay-${item.id}`}
                      role="button"
                      tabIndex={disabled ? -1 : 0}
                      aria-label={`จัดรูปสินค้า ${item.number}`}
                      aria-pressed={isSelected}
                      className={`select-none ${
                        isSpaceDown ? 'pointer-events-none' : 'pointer-events-auto'
                      } absolute ${
                        isCroppingThis ? 'z-30' : disabled ? 'cursor-wait' : 'cursor-move'
                      } ${isSelected && !isCroppingThis ? `z-10 outline-2 ${safe ? 'outline-[var(--brand)]' : 'outline-[var(--danger)]'}` : ''}`}
                      style={style(rect)}
                      onPointerDown={(e) => {
                        if (isSpaceDown || isCroppingThis) return;
                        start(e, item, rect, 'move');
                      }}
                      onPointerMove={isCroppingThis ? onCropPointerMove : move}
                      onPointerUp={(e) => {
                        if (isCroppingThis) {
                          onCropPointerUp(e);
                        } else {
                          void finish(e);
                        }
                      }}
                      onPointerCancel={(e) => {
                        if (isCroppingThis) {
                          onCropPointerUp(e);
                        } else {
                          void finish(e, true);
                        }
                      }}
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        if (isCroppingThis) {
                          void applyCrop();
                        } else {
                          startCrop(item);
                        }
                      }}
                      onFocus={() => onSelect(item.id)}
                      onKeyDown={(e) => void nudge(e, item, rect)}
                    >
                      {isSelected && selectedIds.length > 1 && (
                        <span className="absolute -top-2.5 -left-2.5 z-20 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--brand)] text-white shadow ring-2 ring-white text-[10px] font-bold">
                          <Check size={11} strokeWidth={3} />
                        </span>
                      )}
                      {/* Image Base */}
                      <img
                        src={item.image_url!}
                        alt={item.sku || `รูปสินค้า ${item.number}`}
                        draggable={false}
                        className={`pointer-events-none h-full w-full object-contain ${isCroppingThis ? 'opacity-90' : ''}`}
                      />

                      {/* Normal Selection Handles */}
                      {isSelected && !isCroppingThis && (
                        <>
                          <span className={`pointer-events-none absolute -top-5 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-bold text-white shadow-xs ${safe ? 'bg-[var(--brand)]' : 'bg-[var(--danger)]'}`}>
                            รายการ {item.number}
                            {!safe ? ' · ทับข้อความ' : ''}
                          </span>
                          <button
                            data-testid="resize-handle"
                            aria-label={`ลากเพื่อปรับขนาดรูป ${item.number}`}
                            disabled={disabled || isSpaceDown}
                            tabIndex={-1}
                            className="absolute -right-2 -bottom-2 h-4 w-4 touch-none rounded-xs border-2 border-white bg-[var(--brand)] shadow"
                            style={{cursor: 'nwse-resize'}}
                            onPointerDown={(e) => {
                              if (isSpaceDown) return;
                              start(e, item, rect, 'resize');
                            }}
                            onPointerMove={(e) => {
                              e.stopPropagation();
                              move(e);
                            }}
                            onPointerUp={(e) => {
                              e.stopPropagation();
                              void finish(e);
                            }}
                            onPointerCancel={(e) => {
                              e.stopPropagation();
                              void finish(e, true);
                            }}
                          />
                        </>
                      )}

                      {/* Canva-Style Inline Crop Overlay */}
                      {isCroppingThis && (
                        <div className="absolute inset-0 overflow-visible touch-none">
                          {/* 4 Shaded backdrops around crop box */}
                          <div className="pointer-events-none absolute left-0 right-0 top-0 bg-black/55" style={{height: `${cropMode.rect.y * 100}%`}} />
                          <div className="pointer-events-none absolute left-0 right-0 bottom-0 bg-black/55" style={{top: `${(cropMode.rect.y + cropMode.rect.height) * 100}%`}} />
                          <div
                            className="pointer-events-none absolute left-0 bg-black/55"
                            style={{
                              top: `${cropMode.rect.y * 100}%`,
                              width: `${cropMode.rect.x * 100}%`,
                              height: `${cropMode.rect.height * 100}%`,
                            }}
                          />
                          <div
                            className="pointer-events-none absolute right-0 bg-black/55"
                            style={{
                              top: `${cropMode.rect.y * 100}%`,
                              left: `${(cropMode.rect.x + cropMode.rect.width) * 100}%`,
                              height: `${cropMode.rect.height * 100}%`,
                            }}
                          />

                          {/* Crop Box Frame */}
                          <div
                            data-testid="inline-crop-box"
                            className="absolute border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.6)] cursor-move touch-none"
                            style={{
                              left: `${cropMode.rect.x * 100}%`,
                              top: `${cropMode.rect.y * 100}%`,
                              width: `${cropMode.rect.width * 100}%`,
                              height: `${cropMode.rect.height * 100}%`,
                            }}
                            onPointerDown={(e) => startCropDrag(e, 'crop-move')}
                          >
                            {/* Rule of Thirds Grid */}
                            <div className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
                              <div className="border-r border-b border-white/40" />
                              <div className="border-r border-b border-white/40" />
                              <div className="border-b border-white/40" />
                              <div className="border-r border-b border-white/40" />
                              <div className="border-r border-b border-white/40" />
                              <div className="border-b border-white/40" />
                              <div className="border-r border-b border-white/40" />
                              <div className="border-r border-b border-white/40" />
                              <div />
                            </div>

                            {/* 4 Canva-Style Corner L-Brackets */}
                            <div
                              data-testid="crop-handle-nw"
                              className="absolute -left-1 -top-1 h-3.5 w-3.5 border-t-3 border-l-3 border-white drop-shadow cursor-nwse-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-nw')}
                            />
                            <div
                              data-testid="crop-handle-ne"
                              className="absolute -right-1 -top-1 h-3.5 w-3.5 border-t-3 border-r-3 border-white drop-shadow cursor-nesw-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-ne')}
                            />
                            <div
                              data-testid="crop-handle-sw"
                              className="absolute -left-1 -bottom-1 h-3.5 w-3.5 border-b-3 border-l-3 border-white drop-shadow cursor-nesw-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-sw')}
                            />
                            <div
                              data-testid="crop-handle-se"
                              className="absolute -right-1 -bottom-1 h-3.5 w-3.5 border-b-3 border-r-3 border-white drop-shadow cursor-nwse-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-se')}
                            />

                            {/* 4 Canva-Style Edge Bars */}
                            <div
                              data-testid="crop-handle-n"
                              className="absolute left-1/2 -top-1 h-1.5 w-5 -translate-x-1/2 rounded-full bg-white border border-stone-400 drop-shadow cursor-ns-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-n')}
                            />
                            <div
                              data-testid="crop-handle-s"
                              className="absolute left-1/2 -bottom-1 h-1.5 w-5 -translate-x-1/2 rounded-full bg-white border border-stone-400 drop-shadow cursor-ns-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-s')}
                            />
                            <div
                              data-testid="crop-handle-w"
                              className="absolute -left-1 top-1/2 h-5 w-1.5 -translate-y-1/2 rounded-full bg-white border border-stone-400 drop-shadow cursor-ew-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-w')}
                            />
                            <div
                              data-testid="crop-handle-e"
                              className="absolute -right-1 top-1/2 h-5 w-1.5 -translate-y-1/2 rounded-full bg-white border border-stone-400 drop-shadow cursor-ew-resize touch-none"
                              onPointerDown={(e) => startCropDrag(e, 'crop-e')}
                            />
                          </div>

                          {/* Floating Action Pill above the image */}
                          <div className="pointer-events-auto absolute -top-8 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-full bg-stone-900/90 px-3 py-1 text-xs text-white shadow-xl backdrop-blur-xs z-30 whitespace-nowrap">
                            <button
                              data-testid="apply-inline-crop-pill"
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                void applyCrop();
                              }}
                              disabled={savingCrop}
                              className="flex items-center gap-1 font-semibold text-teal-400 hover:text-teal-300"
                            >
                              {savingCrop ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                              เสร็จสิ้น
                            </button>
                            <span className="text-stone-500">|</span>
                            <button
                              data-testid="cancel-inline-crop-pill"
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                cancelCrop();
                              }}
                              disabled={savingCrop}
                              className="flex items-center gap-1 text-stone-300 hover:text-white"
                            >
                              <X size={12} />
                              ยกเลิก
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>
      <p className="border-t border-stone-200 bg-white px-4 py-3 text-xs leading-5 text-stone-500">
        กรอบเส้นประคือพื้นที่วางรูปของรายการ · ปรับแล้วบันทึกอัตโนมัติ · ดับเบิลคลิกรูปเพื่อครอบตัด
      </p>
    </div>
  );
}
