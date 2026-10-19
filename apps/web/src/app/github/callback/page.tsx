"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { useAuthStore } from "../../../store/authStore";
import { useTeamStore } from "../../../store/teamStore";
import { githubApi, teamsApi } from "../../../lib/api";

function GitHubCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token } = useAuthStore();
  const { fetchTeams } = useTeamStore();

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const installationId = searchParams.get("installation_id");
    const state = searchParams.get("state");
    const error = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");

    if (error || errorDescription) {
      setStatus("error");
      setErrorMessage(errorDescription || error || "GitHub installation was cancelled.");
      return;
    }

    if (!token) {
      // If token not yet loaded from localStorage, wait for next tick
      return;
    }

    const processSync = async () => {
      try {
        if (installationId) {
          await githubApi.handleInstallationCallback(token, installationId);
        } else {
          await githubApi.syncInstallations(token);
        }

        const teams = await fetchTeams(token);
        const defaultTeamSlug = teams[0]?.slug || "personal";

        setStatus("success");

        // If state was provided, decode team and project context
        if (state) {
          try {
            // State is a base64/JWT token; decode payload safely in browser
            const payloadBase64 = state.split(".")[1];
            if (payloadBase64) {
              const decodedJson = JSON.parse(atob(payloadBase64));
              if (decodedJson.teamSlug && decodedJson.projectSlug) {
                setTimeout(() => {
                  router.replace(
                    `/${decodedJson.teamSlug}/${decodedJson.projectSlug}/repositories?installed=true`
                  );
                }, 800);
                return;
              }
            }
          } catch {
            // ignore decoding error
          }
        }

        // Default redirect
        setTimeout(() => {
          router.replace(`/${defaultTeamSlug}`);
        }, 800);
      } catch (err: any) {
        console.error("GitHub App callback sync error:", err);
        setStatus("error");
        setErrorMessage(err.message || "Failed to sync GitHub installation");
      }
    };

    processSync();
  }, [searchParams, token, fetchTeams, router]);

  return (
    <div className="min-h-[75vh] flex items-center justify-center p-4">
      <div className="bg-[#11131a] rounded-xl p-8 max-w-md w-full text-center border border-white/[0.08] shadow-2xl space-y-4">
        {status === "loading" && (
          <div className="space-y-3">
            <Loader2 className="w-10 h-10 text-indigo-400 animate-spin mx-auto" />
            <h2 className="text-base font-bold text-white">
              Connecting GitHub Repositories...
            </h2>
            <p className="text-xs text-zinc-400 font-mono">
              Synchronizing repositories with GitAmi workspace
            </p>
          </div>
        )}

        {status === "success" && (
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 className="w-7 h-7" />
            </div>
            <h2 className="text-base font-bold text-white">
              Repositories Connected!
            </h2>
            <p className="text-xs text-zinc-400">
              Redirecting you back to your workspace...
            </p>
          </div>
        )}

        {status === "error" && (
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mx-auto text-rose-400">
              <AlertCircle className="w-7 h-7" />
            </div>
            <h2 className="text-base font-bold text-white">Connection Failed</h2>
            <p className="text-xs text-rose-300 font-mono">{errorMessage}</p>
            <button
              onClick={() => router.push("/")}
              className="mt-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Return to Workspace
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[75vh] flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        </div>
      }
    >
      <GitHubCallbackContent />
    </Suspense>
  );
}
