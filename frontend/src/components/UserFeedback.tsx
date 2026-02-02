/**
 * UserFeedback.tsx - Signal Rating and Trade Annotation Component
 *
 * This component provides a user interface for collecting feedback on
 * trading signals and annotating trades for model improvement.
 *
 * Features:
 * - Signal rating (1-5 stars)
 * - Trade annotation with tags
 * - Feedback history view
 * - Feedback aggregation display
 */

import React, { useState, useEffect } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import {
  Star,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  CheckCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Send,
  X,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

// Types
interface Signal {
  id: string;
  symbol: string;
  modelName: string;
  signalValue: number;
  signalType: 'buy' | 'sell' | 'hold';
  timestamp: string;
  confidence: number;
}

interface SignalFeedback {
  signalId: string;
  rating: number;
  outcome: 'profitable' | 'loss' | 'scratch' | 'not_taken' | 'pending';
  comment: string;
  timestamp: string;
}

interface TradeAnnotation {
  tradeId: string;
  annotationType: string;
  score: number;
  notes: string;
  tags: string[];
}

interface FeedbackStats {
  totalFeedback: number;
  avgRating: number;
  profitableSignals: number;
  lossSignals: number;
  winRate: number;
}

// Star Rating Component
const StarRating: React.FC<{
  rating: number;
  onRatingChange: (rating: number) => void;
  readonly?: boolean;
  size?: 'sm' | 'md' | 'lg';
}> = ({ rating, onRatingChange, readonly = false, size = 'md' }) => {
  const [hoverRating, setHoverRating] = useState(0);

  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={readonly}
          onMouseEnter={() => !readonly && setHoverRating(star)}
          onMouseLeave={() => !readonly && setHoverRating(0)}
          onClick={() => !readonly && onRatingChange(star)}
          className={`${readonly ? 'cursor-default' : 'cursor-pointer hover:scale-110'} transition-transform`}
        >
          <Star
            className={`${sizeClasses[size]} ${
              star <= (hoverRating || rating)
                ? 'fill-yellow-400 text-yellow-400'
                : 'text-gray-300'
            }`}
          />
        </button>
      ))}
    </div>
  );
};

// Outcome Badge Component
const OutcomeBadge: React.FC<{ outcome: SignalFeedback['outcome'] }> = ({ outcome }) => {
  const styles = {
    profitable: 'bg-green-100 text-green-800',
    loss: 'bg-red-100 text-red-800',
    scratch: 'bg-gray-100 text-gray-800',
    not_taken: 'bg-blue-100 text-blue-800',
    pending: 'bg-yellow-100 text-yellow-800',
  };

  const icons = {
    profitable: <TrendingUp className="w-3 h-3" />,
    loss: <TrendingDown className="w-3 h-3" />,
    scratch: <AlertCircle className="w-3 h-3" />,
    not_taken: <X className="w-3 h-3" />,
    pending: <Clock className="w-3 h-3" />,
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${styles[outcome]}`}>
      {icons[outcome]}
      {outcome.replace('_', ' ')}
    </span>
  );
};

// Signal Feedback Form Component
const SignalFeedbackForm: React.FC<{
  signal: Signal;
  onSubmit: (feedback: Omit<SignalFeedback, 'timestamp'>) => void;
  onCancel: () => void;
}> = ({ signal, onSubmit, onCancel }) => {
  const [rating, setRating] = useState(3);
  const [outcome, setOutcome] = useState<SignalFeedback['outcome']>('pending');
  const [comment, setComment] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      signalId: signal.id,
      rating,
      outcome,
      comment,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-4 border">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-lg">Rate Signal</h3>
          <p className="text-sm text-gray-500">
            {signal.symbol} - {signal.modelName}
          </p>
        </div>
        <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
          <X className="w-5 h-5" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Signal Info */}
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">Signal</span>
            <span className={`font-semibold ${
              signal.signalType === 'buy' ? 'text-green-600' :
              signal.signalType === 'sell' ? 'text-red-600' : 'text-gray-600'
            }`}>
              {signal.signalType.toUpperCase()} ({signal.signalValue.toFixed(2)})
            </span>
          </div>
          <div className="flex justify-between items-center mt-1">
            <span className="text-sm text-gray-600">Confidence</span>
            <span className="text-sm font-medium">{(signal.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Rating */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Signal Quality Rating
          </label>
          <StarRating rating={rating} onRatingChange={setRating} size="lg" />
        </div>

        {/* Outcome */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Trade Outcome
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(['profitable', 'loss', 'scratch', 'not_taken', 'pending'] as const).map((o) => (
              <button
                key={o}
                type="button"
                onClick={() => setOutcome(o)}
                className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  outcome === o
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                {o.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Comment */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Comment (optional)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What did you observe about this signal?"
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            rows={3}
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
          >
            <Send className="w-4 h-4" />
            Submit Feedback
          </button>
        </div>
      </form>
    </div>
  );
};

// Trade Annotation Form Component
const TradeAnnotationForm: React.FC<{
  tradeId: string;
  onSubmit: (annotation: TradeAnnotation) => void;
  onCancel: () => void;
}> = ({ tradeId, onSubmit, onCancel }) => {
  const [annotationType, setAnnotationType] = useState('entry_quality');
  const [score, setScore] = useState(3);
  const [notes, setNotes] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const annotationTypes = [
    { value: 'entry_quality', label: 'Entry Quality' },
    { value: 'exit_quality', label: 'Exit Quality' },
    { value: 'sizing', label: 'Position Sizing' },
    { value: 'timing', label: 'Market Timing' },
    { value: 'risk_management', label: 'Risk Management' },
  ];

  const availableTags = [
    'good_entry', 'bad_entry', 'early', 'late', 'oversized',
    'undersized', 'missed_opportunity', 'false_signal', 'trend_following',
    'mean_reversion', 'momentum', 'volatility',
  ];

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      tradeId,
      annotationType,
      score,
      notes,
      tags: selectedTags,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-4 border">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-lg">Annotate Trade</h3>
          <p className="text-sm text-gray-500">Trade ID: {tradeId}</p>
        </div>
        <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
          <X className="w-5 h-5" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Annotation Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Annotation Type
          </label>
          <select
            value={annotationType}
            onChange={(e) => setAnnotationType(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {annotationTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        {/* Score */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Score
          </label>
          <StarRating rating={score} onRatingChange={setScore} size="lg" />
        </div>

        {/* Tags */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Tags
          </label>
          <div className="flex flex-wrap gap-2">
            {availableTags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={`px-2 py-1 rounded-full text-xs font-medium transition-colors ${
                  selectedTags.includes(tag)
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {tag.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add detailed notes about this trade..."
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            rows={3}
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center justify-center gap-2"
          >
            <MessageSquare className="w-4 h-4" />
            Save Annotation
          </button>
        </div>
      </form>
    </div>
  );
};

// Feedback Stats Component
const FeedbackStatsCard: React.FC<{ stats: FeedbackStats }> = ({ stats }) => {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-semibold text-gray-900 mb-4">Feedback Summary</h3>
      <div className="grid grid-cols-2 gap-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">{stats.totalFeedback}</div>
          <div className="text-xs text-gray-500">Total Feedback</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-center gap-1">
            <span className="text-2xl font-bold text-yellow-500">{stats.avgRating.toFixed(1)}</span>
            <Star className="w-5 h-5 fill-yellow-400 text-yellow-400" />
          </div>
          <div className="text-xs text-gray-500">Avg Rating</div>
        </div>
        <div className="text-center p-3 bg-green-50 rounded-lg">
          <div className="text-2xl font-bold text-green-600">{stats.profitableSignals}</div>
          <div className="text-xs text-gray-500">Profitable</div>
        </div>
        <div className="text-center p-3 bg-red-50 rounded-lg">
          <div className="text-2xl font-bold text-red-600">{stats.lossSignals}</div>
          <div className="text-xs text-gray-500">Loss</div>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t">
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Win Rate</span>
          <span className="text-lg font-bold text-blue-600">{(stats.winRate * 100).toFixed(1)}%</span>
        </div>
        <div className="mt-2 bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 rounded-full h-2 transition-all"
            style={{ width: `${stats.winRate * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};

// Main UserFeedback Component
const UserFeedback: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'signals' | 'annotations' | 'history'>('signals');
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [feedbackHistory, setFeedbackHistory] = useState<SignalFeedback[]>([]);
  const [showStats, setShowStats] = useState(true);

  // Mock data - in production would come from API
  const pendingSignals: Signal[] = [
    {
      id: 'SIG-001',
      symbol: 'AAPL',
      modelName: 'momentum_v2',
      signalValue: 0.75,
      signalType: 'buy',
      timestamp: new Date().toISOString(),
      confidence: 0.85,
    },
    {
      id: 'SIG-002',
      symbol: 'GOOGL',
      modelName: 'mean_reversion',
      signalValue: -0.45,
      signalType: 'sell',
      timestamp: new Date().toISOString(),
      confidence: 0.72,
    },
  ];

  const stats: FeedbackStats = {
    totalFeedback: 156,
    avgRating: 3.8,
    profitableSignals: 89,
    lossSignals: 45,
    winRate: 0.66,
  };

  const handleSignalFeedback = (feedback: Omit<SignalFeedback, 'timestamp'>) => {
    const newFeedback: SignalFeedback = {
      ...feedback,
      timestamp: new Date().toISOString(),
    };
    setFeedbackHistory((prev) => [newFeedback, ...prev]);
    setSelectedSignal(null);
    // TODO: Call API to save feedback in production
  };

  const handleTradeAnnotation = (annotation: TradeAnnotation) => {
    // TODO: Call API to save annotation in production
    setSelectedTradeId(null);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-gray-900">Feedback Center</h2>
        <button
          onClick={() => setShowStats(!showStats)}
          className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          {showStats ? 'Hide' : 'Show'} Stats
          {showStats ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Stats */}
      {showStats && <FeedbackStatsCard stats={stats} />}

      {/* Tabs - Using Radix UI */}
      <Tabs.Root defaultValue="signals">
        <Tabs.List className="flex border-b" aria-label="Feedback sections">
          {(['signals', 'annotations', 'history'] as const).map((tab) => (
            <Tabs.Trigger
              key={tab}
              value={tab}
              className="px-4 py-2 text-sm font-medium border-b-2 transition-colors border-transparent text-gray-500 hover:text-gray-700 data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        {/* Content */}
        <Tabs.Content value="signals" className="focus:outline-none mt-3">
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-700">Pending Signals</h3>
            {pendingSignals.map((signal) => (
              <div
                key={signal.id}
                className="bg-white rounded-lg shadow p-4 flex justify-between items-center hover:shadow-md transition-shadow"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{signal.symbol}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      signal.signalType === 'buy' ? 'bg-green-100 text-green-800' :
                      signal.signalType === 'sell' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {signal.signalType.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500">
                    {signal.modelName} • Confidence: {(signal.confidence * 100).toFixed(0)}%
                  </div>
                </div>
                <button
                  onClick={() => setSelectedSignal(signal)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium flex items-center gap-2"
                >
                  <Star className="w-4 h-4" />
                  Rate
                </button>
              </div>
            ))}
          </div>
        </Tabs.Content>

        <Tabs.Content value="annotations" className="focus:outline-none mt-3">
          <div className="text-center py-8 text-gray-500">
            Trade annotations coming soon
          </div>
        </Tabs.Content>

        <Tabs.Content value="history" className="focus:outline-none mt-3">
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-700">Recent Feedback</h3>
            {feedbackHistory.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No feedback recorded yet
              </div>
            ) : (
              feedbackHistory.map((feedback, index) => (
                <div key={index} className="bg-white rounded-lg shadow p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{feedback.signalId}</span>
                        <OutcomeBadge outcome={feedback.outcome} />
                      </div>
                      <div className="mt-1">
                        <StarRating rating={feedback.rating} onRatingChange={() => {}} readonly size="sm" />
                      </div>
                      {feedback.comment && (
                        <p className="text-sm text-gray-600 mt-2">{feedback.comment}</p>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(feedback.timestamp).toLocaleString()}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </Tabs.Content>
      </Tabs.Root>

      {/* Signal Feedback Modal */}
      {selectedSignal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <SignalFeedbackForm
            signal={selectedSignal}
            onSubmit={handleSignalFeedback}
            onCancel={() => setSelectedSignal(null)}
          />
        </div>
      )}

      {/* Trade Annotation Modal */}
      {selectedTradeId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <TradeAnnotationForm
            tradeId={selectedTradeId}
            onSubmit={handleTradeAnnotation}
            onCancel={() => setSelectedTradeId(null)}
          />
        </div>
      )}
    </div>
  );
};

export default UserFeedback;
