import React from "react";
import Link from "next/link";

interface GitamiLogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  href?: string;
  className?: string;
}

export const GitamiLogo: React.FC<GitamiLogoProps> = ({
  size = "md",
  showText = true,
  href,
  className = "",
}) => {
  const iconSizes = {
    sm: "w-6 h-6",
    md: "w-7 h-7",
    lg: "w-8 h-8",
  };

  const textSizes = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-lg",
  };

  const logoMark = (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {/* GitAmi Mark: Precision Git node geometry with subtle gradient */}
      <div
        className={`${iconSizes[size]} rounded-lg bg-gradient-to-br from-indigo-500 via-indigo-600 to-violet-700 flex items-center justify-center shadow-sm shadow-indigo-500/20 border border-indigo-400/30 shrink-0`}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="w-4 h-4 text-white"
        >
          {/* Main vertical trunk */}
          <line x1="6" y1="3" x2="6" y2="15" />
          {/* Source node */}
          <circle cx="6" cy="18" r="3" fill="currentColor" />
          {/* Branched node */}
          <circle cx="18" cy="9" r="3" fill="currentColor" />
          {/* Branch curve */}
          <path d="M6 9a9 9 0 0 1 9-3h3" />
        </svg>
      </div>

      {showText && (
        <span className={`font-bold tracking-tight text-white ${textSizes[size]}`}>
          Git<span className="text-indigo-400">Ami</span>
        </span>
      )}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex items-center group">
        {logoMark}
      </Link>
    );
  }

  return logoMark;
};
