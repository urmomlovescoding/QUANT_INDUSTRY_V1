/**
 * Empty State Component
 * Displays when there's no data to show
 */

import { ReactNode } from 'react';
import { 
  Inbox, 
  AlertCircle, 
  SearchX, 
  TrendingUp, 
  BarChart2,
  Brain,
  Activity,
  RefreshCw
} from 'lucide-react';
import { cn } from '@/utils/cn';

type EmptyStateVariant = 
  | 'default'
  | 'signals'
  | 'positions'
  | 'data'
  | 'search'
  | 'chart'
  | 'brain'
  | 'error';

interface EmptyStateProps {
  variant?: EmptyStateVariant;
  title?: string;
  description?: string;
  icon?: ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  compact?: boolean;
}

const variantConfig: Record<EmptyStateVariant, { 
  icon: typeof Inbox; 
  title: string; 
  description: string;
  iconColor: string;
}> = {
  default: {
    icon: Inbox,
    title: 'No data available',
    description: 'There\'s nothing to display here yet.',
    iconColor: 'text-gray-500',
  },
  signals: {
    icon: Activity,
    title: 'No active signals',
    description: 'The trading brain hasn\'t generated any signals yet. Check back soon.',
    iconColor: 'text-blue-400',
  },
  positions: {
    icon: TrendingUp,
    title: 'No open positions',
    description: 'You don\'t have any active positions. Execute a signal to open one.',
    iconColor: 'text-green-400',
  },
  data: {
    icon: BarChart2,
    title: 'No data loaded',
    description: 'Connect to a data provider or check your API configuration.',
    iconColor: 'text-amber-400',
  },
  search: {
    icon: SearchX,
    title: 'No results found',
    description: 'Try adjusting your search criteria or filters.',
    iconColor: 'text-purple-400',
  },
  chart: {
    icon: BarChart2,
    title: 'No chart data',
    description: 'Unable to load chart data. Check your data source.',
    iconColor: 'text-cyan-400',
  },
  brain: {
    icon: Brain,
    title: 'Brain not initialized',
    description: 'The trading brain needs to be trained before generating predictions.',
    iconColor: 'text-purple-400',
  },
  error: {
    icon: AlertCircle,
    title: 'Unable to load',
    description: 'Something went wrong while loading this data.',
    iconColor: 'text-red-400',
  },
};

export function EmptyState({
  variant = 'default',
  title,
  description,
  icon,
  action,
  className,
  compact = false,
}: EmptyStateProps) {
  const config = variantConfig[variant];
  const Icon = icon ? () => <>{icon}</> : config.icon;
  
  const displayTitle = title || config.title;
  const displayDescription = description || config.description;

  if (compact) {
    return (
      <div className={cn(
        'flex items-center justify-center gap-3 py-6 text-center',
        className
      )}>
        <Icon className={cn('w-5 h-5', config.iconColor)} />
        <div className="text-left">
          <p className="text-sm font-medium text-foreground-primary">{displayTitle}</p>
          {displayDescription && (
            <p className="text-xs text-foreground-muted mt-0.5">{displayDescription}</p>
          )}
        </div>
        {action && (
          <button
            onClick={action.onClick}
            className="ml-4 text-xs text-accent-primary hover:underline"
          >
            {action.label}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={cn(
      'flex flex-col items-center justify-center py-12 px-6 text-center',
      className
    )}>
      <div className={cn(
        'w-16 h-16 rounded-full flex items-center justify-center mb-4',
        'bg-background-tertiary'
      )}>
        <Icon className={cn('w-8 h-8', config.iconColor)} />
      </div>
      
      <h3 className="text-lg font-semibold text-foreground-primary mb-2">
        {displayTitle}
      </h3>
      
      {displayDescription && (
        <p className="text-sm text-foreground-muted max-w-sm">
          {displayDescription}
        </p>
      )}
      
      {action && (
        <button
          onClick={action.onClick}
          className={cn(
            'mt-6 flex items-center gap-2 px-4 py-2',
            'bg-accent-primary text-white rounded-lg',
            'hover:bg-accent-primary/90 transition-colors',
            'text-sm font-medium'
          )}
        >
          {variant === 'error' && <RefreshCw className="w-4 h-4" />}
          {action.label}
        </button>
      )}
    </div>
  );
}

/**
 * Loading or empty state wrapper
 */
interface DataStateProps {
  isLoading?: boolean;
  isEmpty?: boolean;
  error?: string | null;
  loadingComponent?: ReactNode;
  emptyComponent?: ReactNode;
  errorComponent?: ReactNode;
  children: ReactNode;
  onRetry?: () => void;
}

export function DataState({
  isLoading,
  isEmpty,
  error,
  loadingComponent,
  emptyComponent,
  errorComponent,
  children,
  onRetry,
}: DataStateProps) {
  if (isLoading) {
    return <>{loadingComponent || <EmptyState variant="default" title="Loading..." />}</>;
  }

  if (error) {
    return <>
      {errorComponent || (
        <EmptyState 
          variant="error" 
          description={error}
          action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
        />
      )}
    </>;
  }

  if (isEmpty) {
    return <>{emptyComponent || <EmptyState variant="default" />}</>;
  }

  return <>{children}</>;
}

export default EmptyState;
