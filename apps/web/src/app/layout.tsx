import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { RouteProgressBar } from "../components/ui/RouteProgressBar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "GitAmi — Autonomous Software Intelligence & Code Knowledge Engine",
  description:
    "AST-level software graph intelligence with Neo4j, Context Engine retrieval, semantic vector memory, and autonomous engineering agents.",
};

export const viewport: Viewport = {
  themeColor: "#0c0d12",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} dark`}
    >
      <body className="min-h-screen bg-[#0c0d12] text-zinc-200 antialiased selection:bg-indigo-950 selection:text-white font-sans">
        <RouteProgressBar />
        {children}
      </body>
    </html>
  );
}
