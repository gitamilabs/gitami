"use client";

import React, { useEffect, useState } from "react";
import { aiApi } from "@/lib/api";
import { AIServiceConfig } from "@/lib/types";
import { Cpu, Bot, Database, Sparkles, Server } from "lucide-react";

export const AISettings: React.FC = () => {
  const [aiConfig, setAiConfig] = useState<AIServiceConfig | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const loadConfig = async () => {
      setLoadingConfig(true);
      try {
        const cfg = await aiApi.getConfig();
        if (isMounted) setAiConfig(cfg);
      } catch (e: any) {
        console.warn("Could not load AI config:", e);
      } finally {
        if (isMounted) setLoadingConfig(false);
      }
    };
    loadConfig();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 border-b border-white/[0.06] pb-4">
          <Cpu className="w-5 h-5 text-indigo-400" />
          <div>
            <h2 className="text-sm font-bold text-white tracking-tight">
              AI Orchestrator & Vector Engine
            </h2>
            <p className="text-xs text-zinc-400">
              Live runtime configuration loaded from the GitAmi AI service
            </p>
          </div>
        </div>

        {loadingConfig ? (
          <div className="p-12 text-center text-xs font-mono text-zinc-500 space-y-2">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p>Inspecting AI service runtime configuration...</p>
          </div>
        ) : aiConfig ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            {/* Vector DB Card */}
            <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-emerald-400">
                  <Database className="w-4 h-4" />
                  <span>Active Vector Database</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  Active
                </span>
              </div>
              <p className="text-lg font-mono font-extrabold text-white">
                {aiConfig.vector_db.toUpperCase()}
              </p>
              <p className="text-[11px] text-zinc-400">
                Embedder Model: <span className="font-mono text-zinc-200">{aiConfig.embedder}</span>
              </p>
              {aiConfig.storage.pinecone_index && (
                <p className="text-[11px] text-zinc-400">
                  Pinecone Index: <span className="font-mono text-zinc-200">{aiConfig.storage.pinecone_index}</span>
                </p>
              )}
              {aiConfig.storage.qdrant_collection && (
                <p className="text-[11px] text-zinc-400">
                  Qdrant Collection: <span className="font-mono text-zinc-200">{aiConfig.storage.qdrant_collection}</span>
                </p>
              )}
            </div>

            {/* Primary LLM Orchestrator Card */}
            <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-indigo-400">
                  <Bot className="w-4 h-4" />
                  <span>Primary LLM Orchestrator</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  Google GenAI
                </span>
              </div>
              <p className="text-base font-mono font-bold text-white truncate">
                {aiConfig.models.primary_orchestrator}
              </p>
              <div className="text-[11px] text-zinc-400 space-y-1">
                <p className="text-zinc-500">Candidate Models:</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {aiConfig.models.gemini_models.slice(0, 4).map((m) => (
                    <span key={m} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Worker Node Card */}
            <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-2 md:col-span-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-cyan-400">
                  <Server className="w-4 h-4" />
                  <span>High-Throughput Sub-task Worker</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  Fast Inference
                </span>
              </div>
              <p className="text-base font-mono font-bold text-white">
                {aiConfig.models.worker_model}
              </p>
              <div className="flex flex-wrap gap-1 pt-1">
                {aiConfig.models.groq_models.map((m) => (
                  <span key={m} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-zinc-500 bg-[#0c0d12] rounded-xl border border-white/[0.06]">
            GitAmi AI Service is currently offline or unreachable. Ensure the service is running on port 8000.
          </div>
        )}
      </div>
    </div>
  );
};
