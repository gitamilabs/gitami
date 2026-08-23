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
    indigo: "border-indigo-500/20 bg-indigo-500/5 text-indigo-400",
    cyan: "border-cyan-500/20 bg-cyan-500/5 text-cyan-400",
    emerald: "border-emerald-500/20 bg-emerald-500/5 text-emerald-400",
    purple: "border-purple-500/20 bg-purple-500/5 text-purple-400",
    amber: "border-amber-500/20 bg-amber-500/5 text-amber-400",
  };

  return (
    <div
      className={cn(
        "glass-card glass-card-hover rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            {title}
          </p>
          <h3 className="text-2xl font-bold text-slate-100 mt-1">{value}</h3>
        </div>
        <div
          className={cn(
            "p-2.5 rounded-xl border flex items-center justify-center",
            accentStyles[accentColor]
          )}
        >
          {icon}
        </div>
      </div>

      {(subtitle || trend) && (
        <div className="mt-4 flex items-center justify-between text-xs text-slate-400 pt-3 border-t border-slate-800/80">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span
              className={cn(
                "font-medium",
                trend.isPositive ? "text-emerald-400" : "text-rose-400"
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
