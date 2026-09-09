"use client";

import React from "react";
import Link from "next/link";
import { useAuthStore } from "../../store/authStore";
import { Button } from "../ui/Button";
import { Shield, Github } from "lucide-react";

/**
 * Marketing-only top bar. Once a user is signed in, the Sidebar owns
 * workspace identity, navigation, and the user footer — no global navbar
 * is rendered for the authenticated app (matches the target dashboard look).
 */
export const Navbar: React.FC = () => {
  const { token, login } = useAuthStore();

  if (token) return null;

  return (
    <header className="sticky top-0 z-50 w-full h-14 border-b border-zinc-800/80 bg-black/70 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-md bg-white flex items-center justify-center">
            <Shield className="w-4 h-4 text-black" />
          </div>
          <span className="font-semibold text-sm text-white tracking-tight">
            Sentinel
          </span>
        </Link>

        <Button
          variant="primary"
          size="sm"
          leftIcon={<Github className="w-4 h-4" />}
          onClick={() => login()}
        >
          Sign in with GitHub
        </Button>
      </div>
    </header>
  );
};
