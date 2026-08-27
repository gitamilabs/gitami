import React from "react";
import { cn } from "../../lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  accentColor?: "indigo" | "cyan" | "emerald" | "purple" | "amber";
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  accentColor = "indigo",
  className,
}) => {
  const accentStyles = {
    indigo: {
      border: "border-indigo-500/30 bg-indigo-500/10 text-indigo-400 shadow-sm shadow-indigo-500/20",
      glow: "from-indigo-500/15 via-transparent to-transparent",
    },
    cyan: {
      border: "border-cyan-500/30 bg-cyan-500/10 text-cyan-400 shadow-sm shadow-cyan-500/20",
      glow: "from-cyan-500/15 via-transparent to-transparent",
    },
    emerald: {
      border: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 shadow-sm shadow-emerald-500/20",
      glow: "from-emerald-500/15 via-transparent to-transparent",
    },
    purple: {
      border: "border-purple-500/30 bg-purple-500/10 text-purple-400 shadow-sm shadow-purple-500/20",
      glow: "from-purple-500/15 via-transparent to-transparent",
    },
    amber: {
      border: "border-amber-500/30 bg-amber-500/10 text-amber-400 shadow-sm shadow-amber-500/20",
      glow: "from-amber-500/15 via-transparent to-transparent",
    },
  };

  const currentAccent = accentStyles[accentColor];

  return (
    <div
      className={cn(
        "glass-card glass-card-hover rounded-3xl p-5 sm:p-6 relative overflow-hidden flex flex-col justify-between group",
        className
      )}
    >
      {/* Ambient Top Glow */}
      <div
        className={cn(
          "absolute -top-10 -right-10 w-32 h-32 bg-gradient-to-br rounded-full blur-2xl pointer-events-none opacity-60 group-hover:opacity-100 transition-opacity duration-300",
          currentAccent.glow
        )}
      />

      <div className="flex items-start justify-between gap-4 relative z-10">
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider font-mono">
            {title}
          </p>
          <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mt-1 font-mono">
            {value}
          </h3>
        </div>
        <div
          className={cn(
            "p-3 rounded-2xl border flex items-center justify-center shrink-0 transition-transform group-hover:scale-105 duration-200",
            currentAccent.border
          )}
        >
          {icon}
        </div>
      </div>

      {(subtitle || trend) && (
        <div className="mt-4 flex items-center justify-between text-xs text-slate-400 pt-3.5 border-t border-slate-800/80 relative z-10 font-sans">
          {subtitle && <span className="truncate">{subtitle}</span>}
          {trend && (
            <span
              className={cn(
                "px-2 py-0.5 rounded-full text-[11px] font-semibold font-mono shrink-0",
                trend.isPositive
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
              )}
            >
              {trend.value}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

