"use client";

import React, { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ChatWindow } from "../../../components/chat/ChatWindow";
import { useChatStore } from "../../../store/chatStore";
import { ChatSkeleton } from "../../../components/ui/PageSkeletons";

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
    <div className="flex-1 flex flex-col p-4 sm:p-6">
      <ChatWindow />
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<ChatSkeleton />}>
      <ChatContent />
    </Suspense>
  );
}
