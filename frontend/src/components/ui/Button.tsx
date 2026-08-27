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
    primary: "bg-white hover:bg-zinc-200 text-black shadow-xs active:scale-[0.98]",
    glow: "bg-blue-600 hover:bg-blue-500 text-white shadow-xs border border-blue-500/50 active:scale-[0.98]",
    cyan: "bg-blue-600 hover:bg-blue-500 text-white shadow-xs border border-blue-500/50 active:scale-[0.98]",
    secondary:
      "bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 hover:border-zinc-700 active:scale-[0.98]",
    danger:
      "bg-red-500/10 hover:bg-red-500/15 text-red-400 border border-red-500/25 hover:border-red-500/40 active:scale-[0.98]",
    ghost: "bg-transparent hover:bg-zinc-900 text-zinc-400 hover:text-white active:scale-[0.98]",
    outline:
      "bg-transparent hover:bg-zinc-900/60 text-zinc-300 hover:text-white border border-zinc-800 hover:border-zinc-600 active:scale-[0.98]",
  };

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs font-medium rounded-lg gap-1.5",
    md: "px-4 py-2 text-xs sm:text-sm font-medium rounded-lg gap-2",
    lg: "px-5 py-2.5 text-sm sm:text-base font-medium rounded-xl gap-2.5",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none cursor-pointer select-none font-sans",
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
