/* Redirect legacy favicon.ico requests to the app icon asset. */

import { NextResponse } from "next/server";

export function GET(): NextResponse {
  return new NextResponse(null, {
    status: 307,
    headers: { Location: "/oracle-brandmark.svg" },
  });
}
