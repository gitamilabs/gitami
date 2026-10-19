"use client";

import React, { useState } from "react";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { TopBar } from "../../components/layout/TopBar";
import { AddProjectModal } from "../../components/repositories/AddProjectModal";
import { useRepoStore } from "../../store/repoStore";
import { useAuthStore } from "../../store/authStore";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const { token } = useAuthStore();
  const { fetchConnectedRepos, fetchIndexedRepos } = useRepoStore();

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-[#0c0d12] text-zinc-100 overflow-hidden">
        {/* Persistent GitAmi Sidebar */}
        <Sidebar onOpenAddProject={() => setIsAddModalOpen(true)} />

        {/* Main Content Area with Persistent TopBar */}
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <TopBar onOpenAddProject={() => setIsAddModalOpen(true)} />
          <main className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col">
            {children}
          </main>
        </div>

        {/* Global Add Project Modal */}
        <AddProjectModal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          onSuccess={() => {
            if (token) {
              fetchConnectedRepos(token, true);
              fetchIndexedRepos(token, true);
            }
          }}
        />
      </div>
    </ProtectedRoute>
  );
}
