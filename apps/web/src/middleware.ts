import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Root route redirect for authenticated users
  if (pathname === "/") {
    const token = request.cookies.get("gitami_token")?.value;
    if (token && token.trim().length > 0) {
      const teamSlug = request.cookies.get("gitami_team")?.value;
      return NextResponse.redirect(new URL(`/${teamSlug}`, request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/"],
};
