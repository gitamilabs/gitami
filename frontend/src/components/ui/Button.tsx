import React from "react";
import { cn } from "../../lib/utils";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline" | "glow" | "cyan";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  leftIcon,
  rightIcon,
  className,
  disabled,
  ...props
}) => {
  const variantStyles = {
    primary:
      "bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/25 border border-indigo-500/50 shadow-inner-light active:scale-[0.98]",
    glow: "bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:via-indigo-400 hover:to-cyan-400 text-white shadow-lg shadow-indigo-500/30 border border-indigo-400/40 shadow-inner-light active:scale-[0.98]",
    cyan: "bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-600/25 border border-cyan-500/50 shadow-inner-light active:scale-[0.98]",
    secondary:
      "bg-slate-800/90 hover:bg-slate-700 text-slate-200 border border-slate-700/80 hover:border-slate-600 shadow-inner-light active:scale-[0.98]",
    danger:
      "bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 hover:border-rose-500/50 active:scale-[0.98]",
    ghost:
      "bg-transparent hover:bg-slate-800/60 text-slate-300 hover:text-white active:scale-[0.98]",
    outline:
      "bg-transparent hover:bg-slate-800/40 text-slate-300 hover:text-white border border-slate-700 hover:border-indigo-500/60 active:scale-[0.98]",
  };

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs font-semibold rounded-xl gap-1.5",
    md: "px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl gap-2",
    lg: "px-5 py-2.5 text-sm sm:text-base font-semibold rounded-2xl gap-2.5",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none cursor-pointer select-none font-sans",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-current shrink-0" />
      ) : (
        leftIcon && <span className="shrink-0">{leftIcon}</span>
      )}
      {children}
      {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
    </button>
  );
};

