import type { Metadata } from "next";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { THEME_SCRIPT } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = { title: "CrackMate", description: "Free, open-source interview preparation" };
export const viewport = { width: "device-width", initialScale: 1, themeColor: "#12001a" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} /></head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
