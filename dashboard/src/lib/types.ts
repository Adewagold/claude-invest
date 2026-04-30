export interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pl: number;
  market_value: number;
}

export interface Portfolio {
  equity: number;
  cash: number;
  buying_power: number;
  daily_pnl: number;
  positions: Position[];
  position_count: number;
}

export interface Trade {
  id: number;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  timestamp: string;
  order_id: string;
  trade_type: string;
  status: string;
}

export interface Decision {
  id: number;
  timestamp: string;
  ticker: string;
  action: string;
  reasoning: string;
  signals_snapshot: string;
}

export interface Signal {
  id: number;
  ticker: string;
  timestamp: string;
  sentiment_score: number | null;
  rsi: number | null;
  macd: number | null;
  volume_ratio: number | null;
  trend: string | null;
}

export interface DiscoveryEntry {
  id: number;
  timestamp: string;
  ticker: string;
  volume_score: number | null;
  news_score: number | null;
  sentiment: number | null;
  action_taken: string;
}

export interface PortfolioSnapshot {
  id: number;
  timestamp: string;
  total_value: number;
  cash: number;
  positions_value: number;
  daily_pnl: number | null;
}

export interface Stats {
  latest_value: number;
  latest_daily_pnl: number;
  total_snapshots: number;
}

export interface Config {
  mode: string;
  capital: number;
  max_positions: number;
  max_per_ticker: number;
  position_size_pct: number;
  daily_loss_limit: number;
  pdt_tracking: boolean;
  exit_strategy: {
    stop_loss_pct: number;
    trailing_stop_pct: number;
    signal_exit: boolean;
  };
  polling: {
    market_open_interval: number;
    market_close_interval: number;
    midday_interval: number;
    crypto_interval: number;
  };
  discovery: {
    min_relative_volume: number;
    min_news_count: number;
    sentiment_threshold: number;
  };
  trading_style: string;
}

export interface LearningReport {
  generated_at: string;
  total_trades: number;
  overall_win_rate: number;
  signal_combos: DimensionBucket[];
  time_of_day: DimensionBucket[];
  hold_duration: DimensionBucket[];
  market_regime: DimensionBucket[];
  asset_class: AssetClassBucket[];
  cross_dimensional: CrossDimensional[];
}

export interface DimensionBucket {
  wins: number;
  losses: number;
  total: number;
  win_rate: number;
  avg_pnl: number;
  confidence: string;
  bucket?: string;
  combo?: string;
  regime?: string;
}

export interface AssetClassBucket extends DimensionBucket {
  asset_class: string;
  strategy_id: string;
}

export interface CrossDimensional extends DimensionBucket {
  insight: string;
  actionable: boolean;
}

export interface ChangeLogEntry {
  id: number;
  timestamp: string;
  parameter_path: string;
  old_value: string;
  new_value: string;
  reason: string;
  trade_count: number;
  auto_applied: boolean;
  reverted: boolean;
  reverted_at: string | null;
  revert_reason: string | null;
}

export interface PerformanceSeries {
  date: string;
  wins: number;
  losses: number;
  pnl: number;
  win_rate: number;
}

export interface CoreHolding {
  symbol: string;
  sector: string;
  qty: number;
  cost_basis: number;
  current_value: number;
  weight: number;
  target_weight: number;
  drift: number;
}

export interface CoreStatus {
  core_capital: number;
  cash_remaining: number;
  holdings: CoreHolding[];
  next_rebalance_date: string | null;
}

export interface CoreScheduleEntry {
  symbol: string;
  sector: string;
  weight: number;
  last_buy_date: string | null;
  days_since_buy: number | null;
  next_buy_date: string;
  due: boolean;
}

export interface RebalancePreviewItem {
  symbol: string;
  action: string;
  qty: number;
  reason: string;
  old_weight: number;
  new_weight: number;
}
