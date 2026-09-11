export type Product = {id: number; sku: string; model: string | null; has_image: boolean};
export type Rect = {x:number; y:number; width:number; height:number};
export type PageGeometry = {width:number; height:number; text:Rect[]};
export type Item = {id: number; number: number; page: number; description: string; sku: string | null; status: 'matched'|'needs_review'|'missing'|'manual'; match_method?: string | null; product: Product|null; candidates: Product[]; image_inserted: boolean; warning: string|null; has_image:boolean; uploaded_image:boolean; image_url:string|null; placement:Rect|null; bounds:Rect; image_aspect:number|null; manual_placement:boolean};
export type Quotation = {id: string; filename: string; items: Item[]; generated: boolean; images_inserted: number; pages:PageGeometry[]; revision:number; can_undo?: boolean; can_redo?: boolean};


export type SavedMapping = {
  detected_value: string;
  normalized_value: string;
  product_id: number;
  product_sku: string | null;
  product_model: string | null;
  product_has_image: boolean;
  updated_at: number;
  note?: string;
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {...init, cache:'no-store'});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    let message = 'ทำรายการไม่สำเร็จ กรุณาลองใหม่';
    if (typeof body.detail === 'string') {
      message = body.detail;
    } else if (response.status === 502 || response.status === 504) {
      message = `ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ Backend ได้ (${response.status}) อาจเกิดจาก Render กำลังเริ่มทำงาน (Cold Start) หรือยังไม่ได้ตั้งค่า API_URL บน Vercel`;
    } else if (response.status === 403) {
      message = 'ถูกปฏิเสธการเชื่อมต่อ (403 Forbidden) จากการตั้งค่าสิทธิ์หรือ CORS';
    }
    throw new Error(message);
  }
  return response.json();
}
