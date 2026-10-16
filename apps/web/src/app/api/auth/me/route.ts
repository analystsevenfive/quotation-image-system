import { NextResponse } from "next/server";
import { AUTH_ENABLED } from "@/lib/auth-config";
import { getAuthorizedUser } from "@/lib/auth";

export async function GET() {
  if (!AUTH_ENABLED) {
    return NextResponse.json(null);
  }

  const user = await getAuthorizedUser();
  if (!user) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 });
  }

  return NextResponse.json(
    { name: user.name, email: user.email },
    { headers: { "Cache-Control": "private, no-store" } }
  );
}
