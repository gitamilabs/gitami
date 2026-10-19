"use client";

import React from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function ProjectChatPage() {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0c0d12]">
      <ChatWindow />
    </div>
  );
}
