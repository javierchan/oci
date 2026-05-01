import type { Metadata } from "next";
import type { ReactNode } from "react";
import Script from "next/script";

import { Nav } from "@/components/nav";
import { ToastStack } from "@/components/toast";
import { WorkspaceTopBar } from "@/components/workspace-topbar";

import "./globals.css";

export const metadata: Metadata = {
  title: "OCI DIS Blueprint",
  description: "OCI DIS Blueprint frontend workspace",
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps): JSX.Element {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var root = document.documentElement;
                  if (!root) {
                    return;
                  }
                  var theme = localStorage.getItem('oci-dis-theme');
                  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  root.classList.toggle('dark', theme === 'dark' || (theme !== 'light' && prefersDark));
                } catch (error) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased">
        <div className="min-h-screen lg:flex">
          <Nav />
          <div className="min-h-screen min-w-0 flex-1 bg-[var(--color-page-bg)]">
            <WorkspaceTopBar />
            <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-7 lg:py-6">{children}</main>
          </div>
        </div>
        <ToastStack />
      </body>
    </html>
  );
}
