import React from "react";
import { cn } from "../../lib/utils";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline" | "glow";
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
      "bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 active:scale-[0.98]",
    glow: "bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white shadow-lg shadow-indigo-500/25 active:scale-[0.98]",
    secondary:
      "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 active:scale-[0.98]",
    danger:
      "bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 active:scale-[0.98]",
    ghost:
      "bg-transparent hover:bg-slate-800/60 text-slate-300 hover:text-white active:scale-[0.98]",
    outline:
      "bg-transparent hover:bg-slate-800/40 text-slate-300 border border-slate-700 hover:border-slate-600 active:scale-[0.98]",
  };

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs font-medium rounded-lg gap-1.5",
    md: "px-4 py-2 text-sm font-medium rounded-xl gap-2",
    lg: "px-6 py-2.5 text-base font-semibold rounded-xl gap-2.5",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none cursor-pointer",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-current" />
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
};
