"use client";
import { useEffect, useState } from 'react';
import { BookmarkCheck, Loader2, Search, Trash2, X, ArrowRight, Package } from 'lucide-react';
import { Button } from './ui/button';
import { api, type SavedMapping } from '@/lib/api';

type Props = {
  open: boolean;
  onClose: () => void;
  onMappingChanged?: () => void;
};

export default function MappingsDialog({ open, onClose, onMappingChanged }: Props) {
  const [mappings, setMappings] = useState<SavedMapping[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    loadMappings();
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  async function loadMappings() {
    setLoading(true);
    try {
      const data = await api<SavedMapping[]>('/mappings');
      setMappings(data);
    } catch {
      setMappings([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(key: string) {
    if (!confirm(`ต้องการยกเลิกการจำคู่สินค้านี้ (${key}) ใช่หรือไม่?`)) return;
    setDeletingKey(key);
    try {
      await api(`/mappings/${encodeURIComponent(key)}`, { method: 'DELETE' });
      setMappings((prev) => prev.filter((m) => m.detected_value !== key && m.normalized_value !== key));
      onMappingChanged?.();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setDeletingKey(null);
    }
  }

  if (!open) return null;

  const filtered = mappings.filter(
    (m) =>
      m.detected_value.toLowerCase().includes(search.toLowerCase()) ||
      (m.product_sku && m.product_sku.toLowerCase().includes(search.toLowerCase())) ||
      (m.product_model && m.product_model.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="mappings-title"
        className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--brand-soft)] text-[var(--brand)] shadow-2xs">
              <BookmarkCheck size={20} />
            </div>
            <div>
              <h2 id="mappings-title" className="font-bold text-[var(--brand-dark)] text-base">
                คู่สินค้าที่ระบบจำไว้ (Saved SKU Mappings)
              </h2>
              <p className="text-xs text-[var(--muted)] mt-0.5">
                รายการ SKU ที่เคยจับคู่ด้วยตัวเอง ระบบจะจับคู่ให้อัตโนมัติเมื่อพบในใบเสนอราคาฉบับใหม่
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon" aria-label="ปิด" onClick={onClose} className="rounded-full text-[var(--muted)] hover:text-[var(--text)]">
            <X size={18} />
          </Button>
        </div>

        {/* Search Bar */}
        <div className="border-b border-[var(--border)] bg-[var(--surface-soft)]/50 px-6 py-3.5">
          <div className="relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="ค้นหา SKU ในใบเสนอราคา หรือรหัสสินค้าแคตตาล็อก…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] py-2.5 pl-9 pr-4 text-xs text-[var(--text)] placeholder:text-[var(--muted)]/60 focus:border-[var(--brand)] focus:outline-none shadow-2xs"
            />
          </div>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex h-48 items-center justify-center gap-2 text-xs text-[var(--muted)]">
              <Loader2 size={16} className="animate-spin text-[var(--brand)]" />
              <span>กำลังโหลดข้อมูลการจำคู่สินค้า…</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center text-center">
              <Package size={34} className="text-[var(--muted)]/40" />
              <p className="mt-3 text-sm font-semibold text-[var(--brand-dark)]">
                {search ? 'ไม่พบการจับคู่ที่ค้นหา' : 'ยังไม่มีการจำคู่สินค้า'}
              </p>
              <p className="mt-1 text-xs text-[var(--muted)] max-w-sm">
                เมื่อคุณเลือกสินค้าให้กับ SKU ที่ระบบหาไม่พบในหน้าตรวจสินค้า ระบบจะบันทึกการจับคู่นั้นไว้ที่นี่โดยอัตโนมัติ
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {filtered.map((item) => {
                const dateStr = item.updated_at
                  ? new Date(item.updated_at * 1000).toLocaleDateString('th-TH', {
                      dateStyle: 'medium',
                    })
                  : '';

                return (
                  <div
                    key={item.detected_value}
                    data-testid={`mapping-row-${item.detected_value}`}
                    className="flex items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4 transition-all hover:border-[var(--brand)]/40 hover:bg-[var(--brand-soft)]/15 shadow-2xs"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-[var(--surface-soft)] border border-[var(--border)] px-2 py-0.5 font-mono text-xs font-bold text-[var(--brand-dark)]">
                          {item.detected_value}
                        </span>
                        <ArrowRight size={13} className="text-[var(--accent)]" />
                        <span className="rounded-md bg-[var(--brand-soft)] border border-[#c3ebd2] px-2 py-0.5 font-mono text-xs font-bold text-[var(--brand-strong)]">
                          {item.product_sku || `ID: ${item.product_id}`}
                        </span>
                        {item.product_model && (
                          <span className="text-xs text-[var(--muted)]">({item.product_model})</span>
                        )}
                      </div>
                      {dateStr && (
                        <p className="mt-1 text-[11px] text-[var(--muted)]">จำไว้เมื่อ: {dateStr}</p>
                      )}
                    </div>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 text-[var(--muted)] hover:text-[var(--danger)] hover:bg-[var(--danger-soft)] rounded-[10px]"
                      title="ยกเลิกการจำคู่นี้"
                      aria-label={`ยกเลิกการจำคู่นี้ ${item.detected_value}`}
                      disabled={deletingKey === item.detected_value}
                      onClick={() => void handleDelete(item.detected_value)}
                    >
                      {deletingKey === item.detected_value ? (
                        <Loader2 size={13} className="animate-spin text-[var(--danger)]" />
                      ) : (
                        <Trash2 size={14} />
                      )}
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
