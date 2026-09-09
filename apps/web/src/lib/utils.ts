import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTimeAgo(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) return "just now";
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return dateString;
  }
}

export function formatLatency(latencyMs: number): string {
  if (latencyMs < 1000) {
    return `${Math.round(latencyMs)}ms`;
  }
  return `${(latencyMs / 1000).toFixed(2)}s`;
}

export function getToolBadgeStyle(toolName: string): { bg: string; text: string; border: string } {
  switch (toolName) {
    case "hybrid_search":
      return { bg: "bg-indigo-950/60", text: "text-indigo-400", border: "border-indigo-800/60" };
    case "vector_search":
      return { bg: "bg-cyan-950/60", text: "text-cyan-400", border: "border-cyan-800/60" };
    case "get_blast_radius":
      return { bg: "bg-rose-950/60", text: "text-rose-400", border: "border-rose-800/60" };
    case "get_symbol_details":
      return { bg: "bg-purple-950/60", text: "text-purple-400", border: "border-purple-800/60" };
    case "get_file_dependencies":
      return { bg: "bg-emerald-950/60", text: "text-emerald-400", border: "border-emerald-800/60" };
    case "get_repo_structure":
      return { bg: "bg-amber-950/60", text: "text-amber-400", border: "border-amber-800/60" };
    default:
      return { bg: "bg-slate-800", text: "text-slate-300", border: "border-slate-700" };
  }
}

export function truncate(str: string, maxLength: number): string {
  if (!str) return "";
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength) + "...";
}
