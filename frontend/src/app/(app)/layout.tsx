"use client";

import React from "react";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-black text-zinc-100">
        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0 overflow-x-hidden">
          {children}
        </main>
      </div>
    </ProtectedRoute>
  );
}
