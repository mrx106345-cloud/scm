import { type HTMLAttributes } from 'react';
import cn from '@/lib/cn';

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'circular' | 'rounded';
  width?: string;
  height?: string;
}

export default function Skeleton({
  className,
  variant = 'rounded',
  width,
  height,
  ...props
}: SkeletonProps) {
  const baseStyles = 'animate-pulse bg-muted pointer-events-none';

  const variants = {
    text: 'rounded',
    circular: 'rounded-full',
    rounded: 'rounded-md',
  };

  return (
    <div
      className={cn(baseStyles, variants[variant], className)}
      style={{ width, height }}
      {...props}
    />
  );
}
