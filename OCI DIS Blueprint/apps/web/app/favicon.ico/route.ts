/* Redirect legacy favicon.ico requests to the app icon asset. */

import { NextResponse } from "next/server";

export function GET(request: Request): NextResponse {
  return NextResponse.redirect(new URL("/icon.svg", request.url), 307);
}
