"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "../../store/authStore";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import {
  Shield,
  Bot,
  GitFork,
  Database,
  Share2,
  LogOut,
  Github,
  Activity,
  Menu,
  X,
  ExternalLink,
  Sparkles,
  Zap,
} from "lucide-react";
import { aiApi } from "../../lib/api";

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const { user, token, logout, login } = useAuthStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [aiStatus, setAiStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    const checkStatus = async () => {
      try {
        await aiApi.checkHealth();
        setAiStatus("online");
      } catch {
        setAiStatus("offline");
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const navLinks = [
    { href: "/dashboard", label: "Dashboard", icon: <Shield className="w-4 h-4" /> },
    { href: "/chat", label: "Agentic RAG", icon: <Bot className="w-4 h-4" /> },
    { href: "/repositories", label: "Repositories", icon: <GitFork className="w-4 h-4" /> },
    { href: "/graph", label: "Code Graph", icon: <Share2 className="w-4 h-4" /> },
    { href: "/ingest", label: "Ingest KB", icon: <Database className="w-4 h-4" /> },
  ];

  return (
    <header className="sticky top-0 z-50 w-full glass-panel border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-[1.5px] shadow-md shadow-indigo-500/25 group-hover:scale-105 transition-all duration-200">
              <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
                <Shield className="w-4.5 h-4.5 text-indigo-400 group-hover:text-cyan-400 transition-colors" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-white tracking-tight group-hover:text-indigo-200 transition-colors">
                Sentinel
              </span>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                AI v2.0
              </span>
            </div>
          </Link>

          {/* Desktop Nav Links */}
          {token && (
            <nav className="hidden md:flex items-center gap-1.5 pl-4 border-l border-slate-800/80">
              {navLinks.map((link) => {
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                      isActive
                        ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/40 shadow-sm shadow-indigo-500/10"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                    }`}
                  >
                    <span className={isActive ? "text-indigo-400" : "text-slate-500"}>
                      {link.icon}
                    </span>
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>

        {/* Right Actions & Auth */}
        <div className="flex items-center gap-3">
          {/* AI Engine Status Pill */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 text-[11px] font-mono shadow-inner">
            <span
              className={`w-2 h-2 rounded-full ${
                aiStatus === "online"
                  ? "bg-emerald-400 shadow-sm shadow-emerald-400 animate-pulse"
                  : aiStatus === "offline"
                  ? "bg-rose-400"
                  : "bg-amber-400 animate-pulse"
              }`}
            />
            <span className="text-slate-400 font-medium">KB Engine:</span>
            <span
              className={
                aiStatus === "online"
                  ? "text-emerald-400 font-bold"
                  : aiStatus === "offline"
                  ? "text-rose-400 font-bold"
                  : "text-amber-400 font-bold"
              }
            >
              {aiStatus.toUpperCase()}
            </span>
          </div>

          {token && user ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2.5 pl-2 sm:border-l sm:border-slate-800">
                {user.avatarUrl ? (
                  <img
                    src={user.avatarUrl}
                    alt={user.username}
                    className="w-8 h-8 rounded-full border border-indigo-500/40 ring-2 ring-indigo-500/20 object-cover shadow-sm"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white shadow-sm">
                    {user.username.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <div className="hidden sm:block text-left">
                  <p className="text-xs font-semibold text-slate-200 leading-tight">
                    {user.username}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono truncate max-w-[120px]">
                    {user.email || "GitHub User"}
                  </p>
                </div>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => logout()}
                className="text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 p-2 rounded-xl"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="glow"
                size="sm"
                leftIcon={<Github className="w-4 h-4" />}
                onClick={() => login()}
              >
                Sign in with GitHub
              </Button>
            </div>
          )}

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5 text-slate-300" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden glass-panel border-b border-slate-800 px-4 py-3 space-y-1 animate-fade-in">
          {token &&
            navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-semibold transition-colors ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/40"
                  }`}
                >
                  <span className={isActive ? "text-indigo-400" : "text-slate-400"}>
                    {link.icon}
                  </span>
                  {link.label}
                </Link>
              );
            })}
        </div>
      )}
    </header>
  );
};

