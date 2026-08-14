import type { Metadata } from "next";
import type { ReactNode } from "react";
import Script from "next/script";

import { WorkspaceShell } from "@/components/workspace-shell";
import { APP_DESCRIPTION, APP_ICON_PATH, APP_NAME } from "@/lib/app-brand";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: APP_NAME,
    template: `%s | ${APP_NAME}`,
  },
  applicationName: APP_NAME,
  description: APP_DESCRIPTION,
  appleWebApp: {
    capable: true,
    title: APP_NAME,
    statusBarStyle: "default",
  },
  icons: {
    icon: [{ url: APP_ICON_PATH, type: "image/svg+xml" }],
    shortcut: APP_ICON_PATH,
    apple: APP_ICON_PATH,
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
                  root.dataset.experienceMode = localStorage.getItem('oci-dis-experience-mode') === 'guided' ? 'guided' : 'expert';
                } catch (error) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased">
        <WorkspaceShell>{children}</WorkspaceShell>
      </body>
    </html>
  );
}
