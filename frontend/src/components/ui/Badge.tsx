import React from "react";
import { cn } from "../../lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "purple" | "outline";
  size?: "sm" | "md";
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "primary",
  size = "sm",
  dot = false,
  className,
  ...props
}) => {
  const variantStyles = {
    primary: "bg-indigo-500/10 text-indigo-300 border-indigo-500/30 shadow-sm shadow-indigo-500/10",
    secondary: "bg-slate-800/80 text-slate-300 border-slate-700/60 shadow-sm",
    success: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30 shadow-sm shadow-emerald-500/10",
    warning: "bg-amber-500/10 text-amber-300 border-amber-500/30 shadow-sm shadow-amber-500/10",
    danger: "bg-rose-500/10 text-rose-300 border-rose-500/30 shadow-sm shadow-rose-500/10",
    info: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30 shadow-sm shadow-cyan-500/10",
    purple: "bg-purple-500/10 text-purple-300 border-purple-500/30 shadow-sm shadow-purple-500/10",
    outline: "bg-transparent text-slate-400 border-slate-700/80 hover:border-slate-600",
  };

  const dotColors = {
    primary: "bg-indigo-400",
    secondary: "bg-slate-400",
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    danger: "bg-rose-400",
    info: "bg-cyan-400",
    purple: "bg-purple-400",
    outline: "bg-slate-400",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-[11px] font-medium tracking-tight",
    md: "px-2.5 py-1 text-xs font-semibold tracking-tight",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border transition-all select-none",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn("w-1.5 h-1.5 rounded-full shrink-0", dotColors[variant])}
        />
      )}
      {children}
    </span>
  );
};

