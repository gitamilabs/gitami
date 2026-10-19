"use client";

import React from "react";
import Link from "next/link";
import { useAuthStore } from "../../store/authStore";
import { Button } from "../ui/Button";
import { Github, ArrowRight } from "lucide-react";
import { GitamiLogo } from "./GitamiLogo";

/**
 * Public marketing navigation bar.
 * Rendered exclusively on the public landing and unauthenticated pages.
 */
export const Navbar: React.FC = () => {
  const { token, login } = useAuthStore();

  return (
    <header className="sticky top-0 z-50 w-full h-14 border-b border-white/[0.06] bg-[#0c0d12]/85 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        <GitamiLogo href="/" size="md" />

        <nav className="hidden md:flex items-center gap-6 text-xs text-zinc-400">
          <a href="#features" className="hover:text-white transition-colors">
            Architecture
          </a>
          <a href="#stats" className="hover:text-white transition-colors">
            Performance
          </a>
          <a
            href="https://github.com/gitamilabs/gitami"
            target="_blank"
            rel="noreferrer"
            className="hover:text-white transition-colors flex items-center gap-1.5"
          >
            <Github className="w-3.5 h-3.5" />
            <span>GitHub</span>
          </a>
        </nav>

        <div className="flex items-center gap-3">
          {token ? (
            <Link href="/dashboard">
              <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                Go to Dashboard
              </Button>
            </Link>
          ) : (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Github className="w-4 h-4" />}
              onClick={() => login()}
            >
              Sign in with GitHub
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};
