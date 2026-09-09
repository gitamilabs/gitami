"use client";

import React from "react";
import { Shield, Sparkles, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

interface PageLoaderProps {
  label?: string;
  sublabel?: string;
  fullscreen?: boolean;
  className?: string;
}

export const PageLoader: React.FC<PageLoaderProps> = ({
  label = "Initializing Sentinel Engine...",
  sublabel = "Establishing AST graph & vector pipeline",
  fullscreen = false,
  className,
}) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center select-none",
        fullscreen
          ? "fixed inset-0 z-50 bg-black/90 backdrop-blur-md"
          : "min-h-[50vh] w-full p-8",
        className
      )}
    >
      {/* Ambient background glow */}
      <div className="relative flex items-center justify-center mb-6">
        <div className="absolute w-28 h-28 bg-indigo-500/15 rounded-full blur-2xl pointer-events-none animate-pulse" />
        <div className="absolute w-20 h-20 rounded-full border border-indigo-500/20 animate-sentinel-ring pointer-events-none" />
        <div className="absolute w-14 h-14 rounded-full border border-cyan-500/30 animate-spin pointer-events-none [animation-duration:6s]" />

        {/* Center Emblem */}
        <div className="relative w-12 h-12 rounded-xl bg-gradient-to-b from-zinc-900 to-black border border-zinc-700/80 shadow-xl flex items-center justify-center">
          <Shield className="w-5 h-5 text-white" />
          <Sparkles className="w-2.5 h-2.5 text-cyan-400 absolute -top-1 -right-1 animate-pulse" />
        </div>
      </div>

      {/* Progress Line */}
      <div className="w-48 h-1 bg-zinc-900 rounded-full overflow-hidden mb-4 border border-zinc-800/80 relative">
        <div className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-indigo-500 to-cyan-400 rounded-full animate-sentinel-scan" />
      </div>

      {/* Status Label */}
      <p className="text-xs font-semibold text-zinc-200 tracking-tight mb-1">
        {label}
      </p>
      {sublabel && (
        <p className="text-[11px] text-zinc-500 font-mono text-center max-w-xs">
          {sublabel}
        </p>
      )}
    </div>
  );
};
