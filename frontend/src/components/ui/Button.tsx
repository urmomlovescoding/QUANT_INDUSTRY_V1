/**
 * Button Component - Consistent styled buttons
 */

import { forwardRef, ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/utils/cn'
import { Spinner } from './Loading'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  fullWidth?: boolean
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-accent-primary text-white hover:bg-accent-primary/90 active:bg-accent-primary/80',
  secondary:
    'bg-background-tertiary text-foreground-primary hover:bg-background-hover active:bg-background-active border border-border',
  ghost:
    'bg-transparent text-foreground-secondary hover:bg-background-hover hover:text-foreground-primary',
  danger:
    'bg-bearish/10 text-bearish hover:bg-bearish/20 active:bg-bearish/30 border border-bearish/30',
  success:
    'bg-bullish/10 text-bullish hover:bg-bullish/20 active:bg-bullish/30 border border-bullish/30',
}

const sizeStyles: Record<ButtonSize, string> = {
  xs: 'text-xs px-2 py-1 gap-1',
  sm: 'text-sm px-3 py-1.5 gap-1.5',
  md: 'text-sm px-4 py-2 gap-2',
  lg: 'text-base px-5 py-2.5 gap-2',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      fullWidth = false,
      className,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          'inline-flex items-center justify-center font-medium rounded-lg transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-accent-primary/50',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          variantStyles[variant],
          sizeStyles[size],
          fullWidth && 'w-full',
          className
        )}
        {...props}
      >
        {isLoading ? (
          <>
            <Spinner size="sm" />
            <span>Loading...</span>
          </>
        ) : (
          <>
            {leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
            {children}
            {rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
          </>
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'

// Icon Button variant
interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon: ReactNode
  label: string
  isLoading?: boolean
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      variant = 'ghost',
      size = 'md',
      icon,
      label,
      isLoading = false,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const sizeClasses = {
      xs: 'p-1',
      sm: 'p-1.5',
      md: 'p-2',
      lg: 'p-2.5',
    }

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        aria-label={label}
        title={label}
        className={cn(
          'inline-flex items-center justify-center rounded-lg transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-accent-primary/50',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          variantStyles[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {isLoading ? <Spinner size="sm" /> : icon}
      </button>
    )
  }
)

IconButton.displayName = 'IconButton'
