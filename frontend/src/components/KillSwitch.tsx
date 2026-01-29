/**
 * Kill Switch Component
 * Emergency trading halt with confirmation dialog
 */

import { useState, useCallback } from 'react';
import { AlertTriangle, ShieldOff, ShieldCheck, X } from 'lucide-react';
import { cn } from '@/utils/cn';
import { decisionIntelApi } from '@/api';
import { useToastSafe } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/LoadingStates';

interface KillSwitchProps {
  compact?: boolean;
  className?: string;
}

export function KillSwitch({ compact = true, className }: KillSwitchProps) {
  const [isEngaged, setIsEngaged] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [reason, setReason] = useState('');
  const toast = useToastSafe();

  const checkStatus = useCallback(async () => {
    try {
      const response = await decisionIntelApi.getControlPlaneStatus();
      if (response.ok && response.data) {
        setIsEngaged(response.data.kill_switch_engaged);
      }
    } catch (e) {
      console.error('Failed to check kill switch status:', e);
    }
  }, []);

  const handleEngage = async () => {
    if (!reason.trim()) {
      toast?.warning('Please provide a reason for engaging the kill switch');
      return;
    }

    setIsLoading(true);
    try {
      const response = await decisionIntelApi.engageKillSwitch(reason);
      if (response.ok) {
        setIsEngaged(true);
        setShowConfirm(false);
        setReason('');
        toast?.error('Kill switch ENGAGED - All trading halted', 'Emergency Stop');
      } else {
        toast?.error(response.error?.message || 'Failed to engage kill switch');
      }
    } catch (e) {
      toast?.error('Network error - check backend connection');
    }
    setIsLoading(false);
  };

  const handleRelease = async () => {
    if (!reason.trim()) {
      toast?.warning('Please provide a reason for releasing the kill switch');
      return;
    }

    setIsLoading(true);
    try {
      const response = await decisionIntelApi.releaseKillSwitch(reason);
      if (response.ok) {
        setIsEngaged(false);
        setShowConfirm(false);
        setReason('');
        toast?.success('Kill switch released - Trading resumed');
      } else {
        toast?.error(response.error?.message || 'Failed to release kill switch');
      }
    } catch (e) {
      toast?.error('Network error - check backend connection');
    }
    setIsLoading(false);
  };

  // Compact button for header
  if (compact) {
    return (
      <>
        <button
          onClick={() => setShowConfirm(true)}
          className={cn(
            'px-2 py-1 text-[10px] font-bold rounded transition-colors flex items-center gap-1',
            isEngaged
              ? 'bg-red-600 text-white animate-pulse hover:bg-red-500'
              : 'bg-bearish/20 text-bearish hover:bg-bearish/30',
            className
          )}
          title={isEngaged ? 'Kill switch is ENGAGED - Click to manage' : 'Emergency trading halt'}
        >
          {isEngaged ? (
            <>
              <ShieldOff className="w-3 h-3" />
              HALTED
            </>
          ) : (
            <>
              <AlertTriangle className="w-3 h-3" />
              KILL
            </>
          )}
        </button>

        {/* Confirmation Modal */}
        {showConfirm && (
          <KillSwitchModal
            isEngaged={isEngaged}
            isLoading={isLoading}
            reason={reason}
            onReasonChange={setReason}
            onConfirm={isEngaged ? handleRelease : handleEngage}
            onCancel={() => {
              setShowConfirm(false);
              setReason('');
            }}
          />
        )}
      </>
    );
  }

  // Full panel version
  return (
    <div className={cn('p-4 rounded-lg border', className, 
      isEngaged ? 'bg-red-900/20 border-red-500' : 'bg-background-secondary border-border'
    )}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isEngaged ? (
            <ShieldOff className="w-5 h-5 text-red-500" />
          ) : (
            <ShieldCheck className="w-5 h-5 text-green-500" />
          )}
          <span className="font-medium text-foreground-primary">
            Kill Switch
          </span>
        </div>
        <span className={cn(
          'px-2 py-1 text-xs font-bold rounded',
          isEngaged ? 'bg-red-500 text-white' : 'bg-green-500/20 text-green-500'
        )}>
          {isEngaged ? 'ENGAGED' : 'READY'}
        </span>
      </div>

      <p className="text-sm text-foreground-muted mb-4">
        {isEngaged
          ? 'All trading operations are currently halted. Release to resume.'
          : 'Emergency halt for all trading operations.'
        }
      </p>

      <button
        onClick={() => setShowConfirm(true)}
        disabled={isLoading}
        className={cn(
          'w-full py-2 rounded font-medium transition-colors',
          isEngaged
            ? 'bg-green-600 hover:bg-green-500 text-white'
            : 'bg-red-600 hover:bg-red-500 text-white'
        )}
      >
        {isLoading ? (
          <Spinner size="sm" color="text-white" />
        ) : isEngaged ? (
          'Release Kill Switch'
        ) : (
          'Engage Kill Switch'
        )}
      </button>

      {showConfirm && (
        <KillSwitchModal
          isEngaged={isEngaged}
          isLoading={isLoading}
          reason={reason}
          onReasonChange={setReason}
          onConfirm={isEngaged ? handleRelease : handleEngage}
          onCancel={() => {
            setShowConfirm(false);
            setReason('');
          }}
        />
      )}
    </div>
  );
}

interface KillSwitchModalProps {
  isEngaged: boolean;
  isLoading: boolean;
  reason: string;
  onReasonChange: (reason: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

function KillSwitchModal({
  isEngaged,
  isLoading,
  reason,
  onReasonChange,
  onConfirm,
  onCancel,
}: KillSwitchModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className={cn(
        'w-full max-w-md p-6 rounded-xl shadow-2xl',
        isEngaged ? 'bg-gray-900 border border-green-500/30' : 'bg-gray-900 border border-red-500/30'
      )}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {isEngaged ? (
              <ShieldCheck className="w-8 h-8 text-green-500" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-red-500" />
            )}
            <div>
              <h3 className="text-lg font-bold text-white">
                {isEngaged ? 'Release Kill Switch' : 'Engage Kill Switch'}
              </h3>
              <p className="text-sm text-gray-400">
                {isEngaged ? 'Resume all trading operations' : 'Halt all trading immediately'}
              </p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Reason (required)
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
            placeholder={isEngaged ? "Why are you resuming trading?" : "Why are you halting trading?"}
            className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-gray-600"
            autoFocus
          />
        </div>

        {!isEngaged && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-500/30 rounded-lg">
            <p className="text-sm text-red-300">
              <strong>Warning:</strong> This will immediately halt all trading operations, cancel pending orders, and prevent new trades from being executed.
            </p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading || !reason.trim()}
            className={cn(
              'flex-1 py-2 rounded-lg font-medium transition-colors disabled:opacity-50',
              isEngaged
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-red-600 hover:bg-red-500 text-white'
            )}
          >
            {isLoading ? (
              <Spinner size="sm" color="text-white" />
            ) : isEngaged ? (
              'Release'
            ) : (
              'Engage Kill Switch'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default KillSwitch;
