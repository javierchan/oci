import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";


const SESSION_COOKIE = "oci_dis_session";


export function middleware(request: NextRequest): NextResponse {
  if (request.nextUrl.pathname === "/login") {
    return NextResponse.next();
  }
  if (!request.cookies.has(SESSION_COOKIE)) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.search = "";
    const nextPath = `${request.nextUrl.pathname}${request.nextUrl.search}`;
    loginUrl.searchParams.set("next", nextPath);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}


export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
