import React from "react";
import { cn } from "../../lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className, ...props }) => {
  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-zinc-800/70 border border-zinc-800/50",
        className
      )}
      {...props}
    />
  );
};
