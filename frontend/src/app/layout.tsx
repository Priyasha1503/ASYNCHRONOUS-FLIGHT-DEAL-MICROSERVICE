import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";

import { Providers } from "@/app/providers";
import { SiteFooter } from "@/components/site/footer";
import { SiteHeader } from "@/components/site/header";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
  axes: ["SOFT", "opsz"],
});

export const metadata: Metadata = {
  title: { default: "SkyScout AI — flight price intelligence", template: "%s · SkyScout AI" },
  description:
    "Find the cheapest flight that actually meets your requirements, understand why it was recommended, and monitor fares against your target price.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf8fd" },
    { media: "(prefers-color-scheme: dark)", color: "#110a20" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable}`}>
      <body className="flex min-h-dvh flex-col">
        <Providers>
          <SiteHeader />
          <main id="main" className="flex-1">
            {children}
          </main>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
