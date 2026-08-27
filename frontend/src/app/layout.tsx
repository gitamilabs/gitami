import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Navbar } from "../components/layout/Navbar";

export const metadata: Metadata = {
  title: "Sentinel AI — Autonomous Codebase Knowledge Base & Agentic RAG",
  description:
    "AST-level static code graph intelligence with Neo4j, ChromaDB semantic vector embeddings, and Gemini/Groq Dual-LLM agents.",
};

export const viewport: Viewport = {
  themeColor: "#080c14",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[#080c14] text-slate-100 antialiased selection:bg-indigo-500/30 selection:text-indigo-200 font-sans">
        <div className="fixed inset-0 bg-grid-pattern pointer-events-none opacity-50 -z-10" />
        <div className="fixed inset-0 bg-radial-gradient pointer-events-none -z-10" />
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}

