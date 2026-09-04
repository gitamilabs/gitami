import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "../components/layout/Navbar";
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
  title: "Sentinel AI — Autonomous Codebase Knowledge Base & Agentic RAG",
  description:
    "AST-level static code graph intelligence with Neo4j, ChromaDB semantic vector embeddings, and Gemini/Groq Dual-LLM agents.",
};

export const viewport: Viewport = {
  themeColor: "#000000",
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
      <body className="min-h-screen bg-black text-zinc-100 antialiased selection:bg-zinc-800 selection:text-white font-sans">
        <RouteProgressBar />
        <div className="fixed inset-0 bg-dot-grid pointer-events-none opacity-40 -z-10" />
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}
