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
