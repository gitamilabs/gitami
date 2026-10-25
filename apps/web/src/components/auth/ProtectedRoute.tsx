"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../../store/authStore";
import { Button } from "../ui/Button";
import { PageLoader } from "../ui/PageLoader";
import { Github, ShieldAlert } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const router = useRouter();
  const { token, isInitialized, isLoading, login, initialize } = useAuthStore();

  useEffect(() => {
    if (!isInitialized) {
      initialize();
    }
  }, [isInitialized, initialize]);

  useEffect(() => {
    if (isInitialized && !isLoading && !token) {
      router.replace("/");
    }
  }, [isInitialized, isLoading, token, router]);

  if (!isInitialized || isLoading || !token) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <PageLoader
          label="Authenticating GitAmi Session..."
          sublabel="Verifying cryptographically signed session & permissions"
        />
      </div>
    );
  }

  return <>{children}</>;
};
