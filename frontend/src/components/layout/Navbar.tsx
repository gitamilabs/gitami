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
    <header className="sticky top-0 z-50 w-full glass-panel border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Shield className="w-5 h-5 text-indigo-400 group-hover:text-cyan-400 transition-colors" />
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg bg-gradient-to-r from-white via-slate-200 to-indigo-200 bg-clip-text text-transparent tracking-tight">
                  Sentinel
                </span>
                <Badge variant="primary" size="sm" className="hidden sm:inline-flex text-[10px] py-0 px-1.5 font-mono">
                  AI v2.0
                </Badge>
              </div>
            </div>
          </Link>

          {/* Desktop Nav Links */}
          {token && (
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/30"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                    }`}
                  >
                    {link.icon}
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
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                aiStatus === "online"
                  ? "bg-emerald-400 shadow-sm shadow-emerald-400 animate-pulse"
                  : aiStatus === "offline"
                  ? "bg-rose-400"
                  : "bg-amber-400 animate-pulse"
              }`}
            />
            <span className="text-slate-400">AI KB Engine:</span>
            <span
              className={
                aiStatus === "online"
                  ? "text-emerald-400 font-semibold"
                  : aiStatus === "offline"
                  ? "text-rose-400 font-semibold"
                  : "text-amber-400 font-semibold"
              }
            >
              {aiStatus.toUpperCase()}
            </span>
          </div>

          {token && user ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2.5 pl-2 border-l border-slate-800">
                {user.avatarUrl ? (
                  <img
                    src={user.avatarUrl}
                    alt={user.username}
                    className="w-8 h-8 rounded-full border border-indigo-500/40 ring-2 ring-indigo-500/10"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
                    {user.username.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <div className="hidden sm:block text-left">
                  <p className="text-xs font-medium text-slate-200 leading-tight">
                    {user.username}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono">
                    {user.email || "GitHub User"}
                  </p>
                </div>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => logout()}
                className="text-slate-400 hover:text-rose-400"
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
            className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden glass-panel border-b border-slate-800 px-4 py-3 space-y-1 animate-fade-in">
          {token &&
            navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium ${
                  pathname === link.href
                    ? "bg-indigo-600/20 text-indigo-300"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/40"
                }`}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
        </div>
      )}
    </header>
  );
};
