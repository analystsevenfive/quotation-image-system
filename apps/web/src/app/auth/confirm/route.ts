import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const requestedDestination = request.nextUrl.searchParams.get("next");
  const next =
    requestedDestination?.startsWith("/") && !requestedDestination.startsWith("//")
      ? requestedDestination
      : "/";
  const destination = new URL(next, request.url);
  const login = new URL("/login", request.url);

  if (!code) {
    login.searchParams.set("error", "invalid_link");
    return NextResponse.redirect(login);
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    login.searchParams.set("error", "oauth_failed");
    return NextResponse.redirect(login);
  }

  const { data: authData } = await supabase.auth.getUser();
  const email = authData.user?.email?.toLowerCase();
  const { data: allowed } = email
    ? await supabase
        .from("app_users")
        .select("email")
        .eq("email", email)
        .eq("working_status", "permanent")
        .maybeSingle()
    : { data: null };

  if (!allowed) {
    await supabase.auth.signOut();
    login.searchParams.set("error", "not_allowed");
    return NextResponse.redirect(login);
  }

  return NextResponse.redirect(destination);
}
