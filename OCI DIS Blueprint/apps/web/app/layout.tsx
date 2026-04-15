import type { Metadata } from "next";
import type { ReactNode } from "react";
import Script from "next/script";

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
      <head>
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('oci-dis-theme');
                  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  if (theme === 'dark' || (theme !== 'light' && prefersDark)) {
                    document.documentElement.classList.add('dark');
                  }
                } catch (error) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased">
        <div className="min-h-screen lg:flex">
          <Nav />
          <div className="min-h-screen flex-1 bg-[var(--color-surface)]">
            <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 px-6 py-5 backdrop-blur lg:px-10">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="app-label">Phase 1 Parity</p>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                    Frontend Control Surface
                  </h2>
                </div>
                <p className="max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
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
