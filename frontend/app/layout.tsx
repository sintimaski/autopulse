import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DASHBOARD_THEME_PREFERENCE_STORAGE_KEY } from "../lib/dashboardThemeConstants";
import { RumClient } from "./RumClient";

import "./globals.css";

/** Runs before first paint so `html.dark` matches stored theme / system preference (no white flash). */
const DASHBOARD_THEME_BOOT_SCRIPT = `(function(){try{var k=${JSON.stringify(DASHBOARD_THEME_PREFERENCE_STORAGE_KEY)};var v=localStorage.getItem(k);var dark=v==="dark"||(v!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",dark);}catch(e){}})();`;

export const metadata: Metadata = {
  title: {
    default: "AutoPulse Dashboard",
    template: "%s | AutoPulse Dashboard",
  },
  description: "Fast diagnosis dashboard for AutoPulse MVP.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: DASHBOARD_THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-screen antialiased">
        <RumClient />
        {children}
      </body>
    </html>
  );
}
