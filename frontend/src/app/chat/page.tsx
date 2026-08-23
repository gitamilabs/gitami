"use client";

import React, { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Sidebar } from "../../components/layout/Sidebar";
import { ChatWindow } from "../../components/chat/ChatWindow";
import { useChatStore } from "../../store/chatStore";

function ChatContent() {
  const searchParams = useSearchParams();
  const { setSelectedRepo, setSelectedBranch } = useChatStore();

  useEffect(() => {
    const repoParam = searchParams.get("repo");
    const branchParam = searchParams.get("branch");

    if (repoParam) setSelectedRepo(repoParam);
    if (branchParam) setSelectedBranch(branchParam);
  }, [searchParams, setSelectedRepo, setSelectedBranch]);

  return (
    <div className="flex max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 gap-6">
      <Sidebar />
      <div className="flex-1 min-w-0">
        <ChatWindow />
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center font-mono text-xs text-slate-400">Loading AI Agent Chat...</div>}>
      <ChatContent />
    </Suspense>
  );
}
