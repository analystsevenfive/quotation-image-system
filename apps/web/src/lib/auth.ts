import "server-only";

import { createClient } from "@/utils/supabase/server";

export interface AuthorizedUser {
  id: string;
  email: string;
  name: string;
  empcode: string;
}

export async function getAuthorizedUser(): Promise<AuthorizedUser | null> {
  const supabase = await createClient();
  const { data: authData, error: authError } = await supabase.auth.getClaims();
  const email =
    typeof authData?.claims.email === "string"
      ? authData.claims.email.trim().toLowerCase()
      : "";
  const userId = typeof authData?.claims.sub === "string" ? authData.claims.sub : "";
  if (authError || !userId || !email) return null;

  const { data: profile, error: profileError } = await supabase
    .from("app_users")
    .select("email,name,empcode,working_status")
    .eq("email", email)
    .eq("working_status", "permanent")
    .maybeSingle();

  if (profileError || !profile) return null;

  return {
    id: userId,
    email,
    name: String(profile.name || ""),
    empcode: String(profile.empcode || ""),
  };
}
