import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { type NextRequest, NextResponse } from 'next/server';
import { AUTH_ENABLED } from '@/lib/auth-config';

export async function updateSession(request: NextRequest) {
  if (!AUTH_ENABLED) return NextResponse.next({ request });

  const headers = new Headers(request.headers);
  headers.delete('authorization');
  headers.delete('x-app-user-email');
  let refreshed: Array<{ name: string; value: string; options: CookieOptions }> = [];
  let response = NextResponse.next({ request: { headers } });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(cookiesToSet) {
          refreshed = cookiesToSet;
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          headers.set('cookie', request.cookies.toString());
          response = NextResponse.next({ request: { headers } });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );

  const path = request.nextUrl.pathname;
  const publicPath = path === '/login' || path === '/auth/confirm' || path === '/auth/signout';
  const withCookies = (result: NextResponse) => {
    refreshed.forEach(({ name, value, options }) => result.cookies.set(name, value, options));
    return result;
  };
  if (publicPath) return response;

  const { data: claims, error } = await supabase.auth.getClaims();
  const email = typeof claims?.claims.email === 'string' ? claims.claims.email.trim().toLowerCase() : '';
  const { data: allowed, error: allowError } = !error && email
    ? await supabase.from('app_users').select('email').eq('email', email).eq('working_status', 'permanent').maybeSingle()
    : { data: null, error: null };

  if (allowError) {
    return withCookies(NextResponse.json({ detail: 'Authorization service unavailable' }, { status: 503 }));
  }
  if (!allowed) {
    if (path.startsWith('/api/')) {
      return withCookies(NextResponse.json({ detail: 'Unauthorized' }, { status: 401 }));
    }
    const login = new URL('/login', request.url);
    login.searchParams.set('next', path);
    return withCookies(NextResponse.redirect(login));
  }

  if (path.startsWith('/api/') && path !== '/api/auth/me') {
    const { data: session } = await supabase.auth.getSession();
    const token = session.session?.access_token;
    if (!token) return withCookies(NextResponse.json({ detail: 'Unauthorized' }, { status: 401 }));
    headers.set('authorization', `Bearer ${token}`);
    const authorized = NextResponse.next({ request: { headers } });
    return withCookies(authorized);
  }
  return response;
}
