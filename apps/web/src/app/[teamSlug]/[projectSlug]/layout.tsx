"use client";

import React, { useEffect } from "react";
import { useParams } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore } from "@/store/projectStore";

export default function ProjectWorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token } = useAuthStore();
  const { fetchProjectDetails } = useProjectStore();

  // Load project details on mount and slug change
  useEffect(() => {
    if (token && projectSlug) {
      fetchProjectDetails(token, projectSlug);
    }
  }, [token, projectSlug, fetchProjectDetails]);

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-[#0c0d12] text-zinc-200 overflow-hidden select-none">
        {/* Persistent GitAmi Sidebar */}
        <Sidebar />

        {/* Main Content Workspace with Contextual TopBar */}
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col">
            {children}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
