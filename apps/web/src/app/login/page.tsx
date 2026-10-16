'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { createClient } from '@/utils/supabase/client';

function LoginForm() {
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function signIn() {
    setBusy(true);
    setError('');
    const callback = new URL('/auth/confirm', window.location.origin);
    const next = params.get('next');
    if (next?.startsWith('/') && !next.startsWith('//')) callback.searchParams.set('next', next);
    const { error: authError } = await createClient().auth.signInWithOAuth({
      provider: 'google', options: { redirectTo: callback.toString() },
    });
    if (authError) {
      setError('เข้าสู่ระบบด้วย Google ไม่สำเร็จ กรุณาลองอีกครั้ง');
      setBusy(false);
    }
  }
  const callbackError = params.get('error');
  return <main className="flex min-h-screen items-center justify-center bg-[#edf3f0] px-5">
    <section className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo.png" alt="Seven Five" className="mb-8 h-16 w-auto object-contain" />
      <h1 className="text-2xl font-bold text-[#0b3b31]">เข้าสู่ระบบ Quotation Studio</h1>
      <p className="mt-3 text-sm text-gray-600">ใช้บัญชี Google ที่ได้รับสิทธิ์ในระบบ Seven Five</p>
      <button type="button" onClick={signIn} disabled={busy} className="mt-7 w-full rounded-lg bg-[#0b3b31] px-5 py-3 font-semibold text-white disabled:opacity-60">
        {busy ? 'กำลังเชื่อมต่อ Google...' : 'เข้าสู่ระบบด้วย Google'}
      </button>
      {(error || callbackError) && <p role="alert" className="mt-4 text-sm text-red-700">{error || (callbackError === 'not_allowed' ? 'บัญชีนี้ไม่มีสิทธิ์เข้าใช้งาน' : 'เข้าสู่ระบบไม่สำเร็จ กรุณาลองอีกครั้ง')}</p>}
    </section>
  </main>;
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
