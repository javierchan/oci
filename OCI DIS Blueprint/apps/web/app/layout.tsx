import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Nav } from "@/components/nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "OCI DIS Blueprint",
  description: "OCI DIS Blueprint frontend workspace",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps): JSX.Element {
  return (
    <html lang="en">
      <body className="bg-stone-100 text-slate-950 antialiased">
        <div className="min-h-screen lg:flex">
          <Nav />
          <div className="min-h-screen flex-1">
            <header className="border-b border-black/5 bg-stone-100/90 px-6 py-5 backdrop-blur lg:px-10">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Phase 1 Parity</p>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
                    Frontend Control Surface
                  </h2>
                </div>
                <p className="max-w-2xl text-sm leading-6 text-slate-600">
                  Connected to the live FastAPI stack for project intake, import review, QA correction, and volumetry monitoring.
                </p>
              </div>
            </header>
            <main className="px-6 py-8 lg:px-10">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
