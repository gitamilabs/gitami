"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "../../../store/authStore";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "../../../components/ui/Button";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setToken, fetchUser } = useAuthStore();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    const error = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");

    if (error || errorDescription) {
      setStatus("error");
      setErrorMessage(errorDescription || error || "GitHub authentication failed.");
      return;
    }

    if (token) {
      setToken(token);
      fetchUser()
        .then(() => {
          setStatus("success");
          setTimeout(() => {
            router.push("/dashboard");
          }, 1000);
        })
        .catch((err) => {
          console.error("Failed to fetch user profile after callback:", err);
          setStatus("error");
          setErrorMessage(err.message || "Failed to load user profile");
        });
    } else {
      setStatus("error");
      setErrorMessage("No authentication token provided in callback URL.");
    }
  }, [searchParams, setToken, fetchUser, router]);

  return (
    <div className="min-h-[75vh] flex items-center justify-center p-4">
      <div className="glass-panel rounded-2xl p-8 max-w-md w-full text-center border border-slate-800 shadow-2xl">
        {status === "loading" && (
          <div className="space-y-4">
            <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mx-auto" />
            <h2 className="text-xl font-bold text-slate-100">
              Authenticating with GitHub...
            </h2>
            <p className="text-xs text-slate-400 font-mono">
              Verifying cryptographic JWT session token
            </p>
          </div>
        )}

        {status === "success" && (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-100">
              Authentication Successful!
            </h2>
            <p className="text-xs text-slate-400">
              Redirecting you to the Sentinel dashboard...
            </p>
          </div>
        )}

        {status === "error" && (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mx-auto text-rose-400">
              <AlertCircle className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-100">
              Authentication Failed
            </h2>
            <p className="text-xs text-rose-300 font-mono">{errorMessage}</p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => router.push("/")}
              className="mt-4"
            >
              Return to Home
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[75vh] flex items-center justify-center">
          <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
