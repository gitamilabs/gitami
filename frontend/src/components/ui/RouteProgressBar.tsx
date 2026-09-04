"use client";

import React, { useEffect, useState, useTransition, Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";

function ProgressContent() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending] = useTransition();

  const [visible, setVisible] = useState(false);
  const [progress, setProgress] = useState(0);

  // Complete progress on route/searchParam changes
  useEffect(() => {
    if (visible) {
      setProgress(100);
      const timer = setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [pathname, searchParams]);

  // Intercept internal link clicks to show instant loading feedback
  useEffect(() => {
    let progressInterval: NodeJS.Timeout | null = null;
    let autoDismissTimer: NodeJS.Timeout | null = null;

    const startProgress = () => {
      setVisible(true);
      setProgress(20);

      // Auto-dismiss safety timer after 3.5s in case navigation is cancelled or slow
      if (autoDismissTimer) clearTimeout(autoDismissTimer);
      autoDismissTimer = setTimeout(() => {
        setProgress(100);
        setTimeout(() => {
          setVisible(false);
          setProgress(0);
        }, 250);
      }, 3500);

      // Smooth simulated progress ramp up
      if (progressInterval) clearInterval(progressInterval);
      progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 88) {
            if (progressInterval) clearInterval(progressInterval);
            return 88;
          }
          const increment = Math.max(1, (90 - prev) * 0.15);
          return Math.min(88, prev + increment);
        });
      }, 100);
    };

    const handleLinkClick = (e: MouseEvent) => {
      // Ignore clicks with modifier keys
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.defaultPrevented) return;

      const target = (e.target as HTMLElement).closest("a");
      if (!target) return;

      const href = target.getAttribute("href");
      if (!href) return;

      // Ignore external links, downloads, hash-only anchors, target="_blank"
      if (
        href.startsWith("http://") ||
        href.startsWith("https://") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:") ||
        href.startsWith("#") ||
        target.getAttribute("target") === "_blank" ||
        target.hasAttribute("download")
      ) {
        return;
      }

      // If linking to the exact same URL, skip
      const currentUrl = window.location.pathname + window.location.search;
      if (href === currentUrl) return;

      startProgress();
    };

    window.addEventListener("click", handleLinkClick, { capture: true });

    return () => {
      window.removeEventListener("click", handleLinkClick, { capture: true });
      if (progressInterval) clearInterval(progressInterval);
      if (autoDismissTimer) clearTimeout(autoDismissTimer);
    };
  }, []);

  if (!visible && progress === 0) return null;

  return (
    <div
      aria-hidden="true"
      className="fixed top-0 left-0 right-0 z-[9999] pointer-events-none transition-opacity duration-300"
      style={{ opacity: visible ? 1 : 0 }}
    >
      <div
        className="h-[2px] w-full route-progress-bar transition-all duration-200 ease-out"
        style={{
          width: `${progress}%`,
          transitionProperty: "width",
          transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      />
    </div>
  );
}

export function RouteProgressBar() {
  return (
    <Suspense fallback={null}>
      <ProgressContent />
    </Suspense>
  );
}
