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
    indigo: "border-blue-500/25 bg-blue-500/10 text-blue-400",
    cyan: "border-blue-500/25 bg-blue-500/10 text-blue-400",
    emerald: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
    purple: "border-purple-500/25 bg-purple-500/10 text-purple-400",
    amber: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  };

  return (
    <div
      className={cn(
        "glass-card glass-card-hover rounded-xl p-5 sm:p-6 flex flex-col justify-between",
        className
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider font-mono">
            {title}
          </p>
          <h3 className="text-2xl sm:text-3xl font-bold text-white tracking-tight mt-1">
            {value}
          </h3>
        </div>
        <div
          className={cn(
            "p-3 rounded-lg border flex items-center justify-center shrink-0",
            accentStyles[accentColor]
          )}
        >
          {icon}
        </div>
      </div>

      {(subtitle || trend) && (
        <div className="mt-4 flex items-center justify-between text-xs text-zinc-500 pt-3.5 border-t border-zinc-800/80 font-sans">
          {subtitle && <span className="truncate">{subtitle}</span>}
          {trend && (
            <span
              className={cn(
                "px-2 py-0.5 rounded-full text-[11px] font-medium font-mono shrink-0",
                trend.isPositive
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/25"
                  : "bg-red-500/10 text-red-400 border border-red-500/25"
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
