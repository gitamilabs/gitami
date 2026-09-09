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
    primary: "bg-blue-500/10 text-blue-400 border-blue-500/25",
    secondary: "bg-zinc-800 text-zinc-400 border-zinc-700/60",
    success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    danger: "bg-red-500/10 text-red-400 border-red-500/25",
    info: "bg-blue-500/10 text-blue-400 border-blue-500/25",
    purple: "bg-purple-500/10 text-purple-400 border-purple-500/25",
    outline: "bg-transparent text-zinc-400 border-zinc-700/80 hover:border-zinc-600",
  };

  const dotColors = {
    primary: "bg-blue-400",
    secondary: "bg-zinc-400",
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    danger: "bg-red-400",
    info: "bg-blue-400",
    purple: "bg-purple-400",
    outline: "bg-zinc-400",
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
