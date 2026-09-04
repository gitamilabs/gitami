"use client";

import React from "react";
import { Skeleton } from "./Skeleton";

/**
 * High-fidelity skeleton loader for the Projects Dashboard (/dashboard).
 */
export function ProjectsSkeleton() {
  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto w-full space-y-8 animate-fade-in">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Skeleton className="h-7 w-44 mb-2 bg-zinc-850" />
          <Skeleton className="h-4 w-72 bg-zinc-900" />
        </div>
        <div className="flex items-center gap-2.5">
          <Skeleton className="h-9 w-28 rounded-md bg-zinc-900" />
          <Skeleton className="h-9 w-36 rounded-md bg-zinc-800" />
        </div>
      </div>

      {/* Filter and search controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <Skeleton className="h-9 w-full sm:w-80 rounded-md bg-zinc-900" />
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Skeleton className="h-8 w-20 rounded-md bg-zinc-900" />
          <Skeleton className="h-8 w-20 rounded-md bg-zinc-900" />
          <Skeleton className="h-8 w-8 rounded-md bg-zinc-900" />
        </div>
      </div>

      {/* Grid of repository cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="p-5 rounded-xl border border-zinc-800/80 bg-zinc-950/60 flex flex-col justify-between h-[210px]"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <Skeleton className="w-8 h-8 rounded-lg bg-zinc-850" />
                  <div>
                    <Skeleton className="h-4 w-32 mb-1.5 bg-zinc-800" />
                    <Skeleton className="h-3 w-20 bg-zinc-900" />
                  </div>
                </div>
                <Skeleton className="h-5 w-14 rounded-full bg-zinc-900" />
              </div>

              <div className="space-y-2 mt-4">
                <Skeleton className="h-3 w-full bg-zinc-900" />
                <Skeleton className="h-3 w-4/5 bg-zinc-900/70" />
              </div>
            </div>

            <div className="pt-4 border-t border-zinc-900 flex items-center justify-between">
              <Skeleton className="h-4 w-24 bg-zinc-900" />
              <div className="flex items-center gap-2">
                <Skeleton className="h-7 w-16 rounded-md bg-zinc-900" />
                <Skeleton className="h-7 w-16 rounded-md bg-zinc-850" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * High-fidelity skeleton loader for the Agentic RAG Chat page (/chat).
 */
export function ChatSkeleton() {
  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-2rem)] max-w-5xl mx-auto w-full p-4 sm:p-6 space-y-4 animate-fade-in">
      {/* Top chat control bar */}
      <div className="p-3.5 rounded-xl border border-zinc-800/80 bg-zinc-950 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-7 h-7 rounded-lg bg-zinc-800" />
          <div className="space-y-1">
            <Skeleton className="h-4 w-40 bg-zinc-800" />
            <Skeleton className="h-3 w-28 bg-zinc-900" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-8 w-24 rounded-md bg-zinc-900" />
          <Skeleton className="h-8 w-8 rounded-md bg-zinc-900" />
        </div>
      </div>

      {/* Message stream area */}
      <div className="flex-1 space-y-6 overflow-hidden py-4">
        {/* User prompt message */}
        <div className="flex justify-end">
          <div className="max-w-md w-full p-4 rounded-2xl rounded-tr-sm bg-zinc-900/90 border border-zinc-800/80 space-y-2">
            <Skeleton className="h-3.5 w-3/4 bg-zinc-800" />
            <Skeleton className="h-3.5 w-1/2 bg-zinc-800" />
          </div>
        </div>

        {/* AI agent response */}
        <div className="flex justify-start">
          <div className="max-w-2xl w-full p-5 rounded-2xl rounded-tl-sm bg-zinc-950 border border-zinc-800/80 space-y-3.5">
            <div className="flex items-center gap-2.5 mb-1">
              <Skeleton className="w-5 h-5 rounded-md bg-indigo-500/20" />
              <Skeleton className="h-4 w-32 bg-zinc-800" />
              <Skeleton className="h-4 w-16 rounded-full bg-zinc-900" />
            </div>
            <Skeleton className="h-3.5 w-full bg-zinc-900" />
            <Skeleton className="h-3.5 w-11/12 bg-zinc-900" />
            <Skeleton className="h-3.5 w-4/5 bg-zinc-900" />

            {/* Code block skeleton */}
            <div className="p-3.5 rounded-lg bg-zinc-900/60 border border-zinc-850 space-y-2 mt-3">
              <Skeleton className="h-3 w-1/3 bg-zinc-800" />
              <Skeleton className="h-3 w-2/3 bg-zinc-800/60" />
              <Skeleton className="h-3 w-1/2 bg-zinc-800/60" />
            </div>
          </div>
        </div>
      </div>

      {/* Input bar */}
      <div className="p-3 rounded-xl border border-zinc-800/80 bg-zinc-950 flex items-center gap-3">
        <Skeleton className="h-9 flex-1 rounded-lg bg-zinc-900" />
        <Skeleton className="h-9 w-20 rounded-lg bg-zinc-800" />
      </div>
    </div>
  );
}

/**
 * High-fidelity skeleton loader for the PR Review page (/prs).
 */
export function PRSkeleton() {
  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto w-full space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Skeleton className="h-7 w-48 mb-2 bg-zinc-850" />
          <Skeleton className="h-4 w-80 bg-zinc-900" />
        </div>
        <div className="flex items-center gap-2.5">
          <Skeleton className="h-9 w-40 rounded-md bg-zinc-900" />
          <Skeleton className="h-9 w-24 rounded-md bg-zinc-850" />
        </div>
      </div>

      {/* PR Cards list */}
      <div className="space-y-4 pt-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-5 rounded-xl border border-zinc-800/80 bg-zinc-950/70 flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
          >
            <div className="space-y-2.5 flex-1">
              <div className="flex items-center gap-3">
                <Skeleton className="h-5 w-16 rounded-full bg-zinc-900" />
                <Skeleton className="h-4 w-64 bg-zinc-800" />
              </div>
              <div className="flex items-center gap-4">
                <Skeleton className="h-3 w-32 bg-zinc-900" />
                <Skeleton className="h-3 w-24 bg-zinc-900" />
                <Skeleton className="h-3 w-40 bg-zinc-900" />
              </div>
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end">
              <Skeleton className="h-6 w-20 rounded-full bg-zinc-900" />
              <Skeleton className="h-8 w-28 rounded-md bg-zinc-850" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * High-fidelity skeleton loader for the Code Graph explorer (/graph).
 */
export function GraphSkeleton() {
  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden animate-fade-in">
      {/* Top stats bar */}
      <div className="h-14 border-b border-zinc-800/80 bg-black/60 px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-6 h-6 rounded-md bg-zinc-800" />
          <Skeleton className="h-4 w-44 bg-zinc-800" />
        </div>
        <div className="flex items-center gap-3">
          <Skeleton className="h-7 w-28 rounded-md bg-zinc-900" />
          <Skeleton className="h-7 w-20 rounded-md bg-zinc-900" />
          <Skeleton className="h-7 w-20 rounded-md bg-zinc-900" />
        </div>
      </div>

      {/* Main interactive area with canvas placeholder */}
      <div className="flex-1 relative bg-black/40 flex items-center justify-center">
        <div className="absolute inset-0 bg-dot-grid opacity-20 pointer-events-none" />

        {/* Floating simulated graph nodes */}
        <div className="relative w-full max-w-3xl h-96 flex items-center justify-center">
          <div className="absolute top-1/4 left-1/4 p-4 rounded-xl border border-zinc-800 bg-zinc-950/90 w-48 space-y-2">
            <Skeleton className="h-3.5 w-3/4 bg-zinc-800" />
            <Skeleton className="h-2.5 w-1/2 bg-zinc-900" />
          </div>
          <div className="absolute top-1/2 right-1/4 p-4 rounded-xl border border-zinc-800 bg-zinc-950/90 w-52 space-y-2">
            <Skeleton className="h-3.5 w-2/3 bg-zinc-800" />
            <Skeleton className="h-2.5 w-4/5 bg-zinc-900" />
          </div>
          <div className="absolute bottom-1/4 left-1/3 p-4 rounded-xl border border-zinc-800 bg-zinc-950/90 w-44 space-y-2">
            <Skeleton className="h-3.5 w-4/5 bg-zinc-800" />
            <Skeleton className="h-2.5 w-1/3 bg-zinc-900" />
          </div>

          <div className="flex flex-col items-center gap-3 z-10">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center animate-pulse">
              <Skeleton className="w-5 h-5 rounded-md bg-zinc-700" />
            </div>
            <p className="text-xs font-mono text-zinc-400">Loading Neo4j AST Graph...</p>
          </div>
        </div>
      </div>
    </div>
  );
}
