/**
 * News & Events Module Types
 * QUANT_INDUSTRY_V1
 */

export type SentimentType = 'positive' | 'negative' | 'neutral';
export type NewsCategory = 'earnings' | 'economic' | 'corporate' | 'market' | 'regulatory' | 'geopolitical';
export type EventImpact = 'high' | 'medium' | 'low';

// News
export interface NewsArticle {
  id: string;
  timestamp: string;
  headline: string;
  summary: string;
  content?: string;
  source: string;
  sourceUrl?: string;
  author?: string;
  symbols: string[];
  category: NewsCategory;
  sentiment: SentimentType;
  sentimentScore: number;
  relevanceScore: number;
  keywords: string[];
  entities: Array<{
    name: string;
    type: 'company' | 'person' | 'location' | 'topic';
    sentiment: SentimentType;
  }>;
  imageUrl?: string;
  isBreaking: boolean;
}

export interface NewsFeed {
  articles: NewsArticle[];
  totalCount: number;
  lastUpdate: string;
  sentiment: {
    positive: number;
    negative: number;
    neutral: number;
    overall: SentimentType;
  };
}

// Sentiment
export interface SentimentMetrics {
  symbol?: string;
  timestamp: string;
  overallSentiment: number; // -1 to 1
  sentimentLabel: SentimentType;
  newsScore: number;
  socialScore: number;
  analystScore: number;
  insiderScore: number;
  volumeWeightedScore: number;
  momentum: number;
  changeFromYesterday: number;
  percentile: number;
  components: {
    news: {
      score: number;
      articleCount: number;
      positivePct: number;
      negativePct: number;
    };
    social: {
      score: number;
      mentionCount: number;
      bullishPct: number;
      bearishPct: number;
    };
    analyst: {
      score: number;
      upgradeCount: number;
      downgradeCount: number;
      avgPriceTarget: number;
    };
  };
}

// Earnings
export interface EarningsEvent {
  id: string;
  symbol: string;
  companyName: string;
  reportDate: string;
  reportTime: 'before_market' | 'after_market' | 'during_market' | 'unknown';
  fiscalQuarter: string;
  fiscalYear: number;
  estimatedEps: number;
  actualEps?: number;
  surpriseEps?: number;
  surprisePct?: number;
  estimatedRevenue: number;
  actualRevenue?: number;
  revenuesSurprise?: number;
  revenuesSurprisePct?: number;
  conferenceCallTime?: string;
  conferenceCallUrl?: string;
  guidance?: {
    epsLow?: number;
    epsHigh?: number;
    revenueLow?: number;
    revenueHigh?: number;
    sentiment: SentimentType;
  };
  analystRatings: {
    buy: number;
    hold: number;
    sell: number;
    avgTarget: number;
    highTarget: number;
    lowTarget: number;
  };
  historicalBeats: number;
  historicalMisses: number;
  avgMoveOnEarnings: number;
  impliedMove: number;
}

// Economic Events
export interface EconomicEvent {
  id: string;
  timestamp: string;
  name: string;
  country: string;
  currency: string;
  category: string;
  importance: EventImpact;
  actual?: number;
  forecast?: number;
  previous?: number;
  unit?: string;
  revision?: number;
  description?: string;
  marketImpact?: {
    equity: SentimentType;
    bond: SentimentType;
    forex: SentimentType;
    commodity: SentimentType;
  };
  affectedSymbols: string[];
}

export interface EconomicCalendar {
  events: EconomicEvent[];
  startDate: string;
  endDate: string;
  countries: string[];
  upcomingHighImpact: EconomicEvent[];
}

// Event Signals
export interface EventSignal {
  id: string;
  timestamp: string;
  symbol?: string;
  eventType: 'earnings_beat' | 'earnings_miss' | 'guidance_raised' | 'guidance_lowered' | 
             'analyst_upgrade' | 'analyst_downgrade' | 'insider_buy' | 'insider_sell' |
             'economic_surprise' | 'breaking_news' | 'sentiment_shift';
  direction: 'bullish' | 'bearish';
  strength: number;
  description: string;
  sourceEvent: string;
  expectedImpact: {
    direction: 'up' | 'down';
    magnitude: number;
    confidence: number;
    horizon: string;
  };
  relatedSymbols: string[];
  alertLevel: 'info' | 'warning' | 'critical';
}

// Headline Analysis
export interface HeadlineAnalysis {
  headline: string;
  timestamp: string;
  sentiment: SentimentType;
  sentimentScore: number;
  confidence: number;
  entities: Array<{
    text: string;
    type: string;
    sentiment: SentimentType;
    relevance: number;
  }>;
  keywords: Array<{
    word: string;
    weight: number;
    sentiment: SentimentType;
  }>;
  topics: string[];
  suggestedAction?: string;
  historicalSimilar: Array<{
    headline: string;
    date: string;
    priceChange: number;
  }>;
}

// Dashboard State
export interface NewsEventsState {
  newsFeed: NewsFeed | null;
  sentimentMetrics: SentimentMetrics | null;
  earningsCalendar: EarningsEvent[];
  economicCalendar: EconomicCalendar | null;
  eventSignals: EventSignal[];
  headlineAnalysis: HeadlineAnalysis | null;
  selectedSymbol: string;
  selectedDateRange: {
    start: string;
    end: string;
  };
  isLoading: boolean;
  error: string | null;
}
