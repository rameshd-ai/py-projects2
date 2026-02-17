"""
Market state detector for multi-timeframe OHLCV data.

Inputs:
- 1m, 5m, 15m OHLCV pandas.DataFrame

Metrics:
- ADX
- ATR %
- Volume / average volume ratio

Outputs:
- regime in ['TREND_UP','TREND_DOWN','RANGE','LOW_VOL','HIGH_VOL']
- quality_score in [0, 100]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Regime = Literal["TREND_UP", "TREND_DOWN", "RANGE", "LOW_VOL", "HIGH_VOL"]


@dataclass
class TimeframeMetrics:
    adx: float
    atr_pct: float
    volume_ratio: float
    trend_bias: float


@dataclass
class MarketState:
    regime: Regime
    quality_score: float
    metrics_1m: TimeframeMetrics
    metrics_5m: TimeframeMetrics
    metrics_15m: TimeframeMetrics
    adx_weighted: float
    atr_pct_weighted: float
    volume_ratio_weighted: float
    trend_bias_weighted: float


def _validate_ohlcv(df: pd.DataFrame, name: str) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas.DataFrame")
    if not required.issubset(set(df.columns.str.lower())):
        # Normalize possible case mismatch first.
        cols_map = {c.lower(): c for c in df.columns}
        missing = [c for c in required if c not in cols_map]
        if missing:
            raise ValueError(f"{name} missing required columns: {missing}")
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    if len(out) < 20:
        raise ValueError(f"{name} needs at least 20 rows, got {len(out)}")
    return out


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1 / period, adjust=False).mean()


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).fillna(0.0)

    atr = _wilder_smooth(tr, period).replace(0, np.nan)
    plus_di = 100 * _wilder_smooth(plus_dm, period) / atr
    minus_di = 100 * _wilder_smooth(minus_dm, period) / atr

    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan)
    adx = _wilder_smooth(dx.fillna(0.0), period).fillna(0.0)
    return adx


def _compute_atr_pct(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).fillna(0.0)
    atr = _wilder_smooth(tr, period)
    atr_pct = (atr / close.replace(0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return atr_pct


def _compute_volume_ratio(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    avg_vol = df["volume"].rolling(lookback, min_periods=max(5, lookback // 2)).mean()
    ratio = (df["volume"] / avg_vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    return ratio


def _compute_trend_bias(df: pd.DataFrame) -> pd.Series:
    fast = df["close"].ewm(span=10, adjust=False).mean()
    slow = df["close"].ewm(span=30, adjust=False).mean()
    raw = ((fast - slow) / df["close"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return raw.clip(-0.02, 0.02) / 0.02  # normalize roughly to [-1, 1]


def _latest_metrics(df: pd.DataFrame) -> TimeframeMetrics:
    adx = float(_compute_adx(df).iloc[-1])
    atr_pct = float(_compute_atr_pct(df).iloc[-1])
    volume_ratio = float(_compute_volume_ratio(df).iloc[-1])
    trend_bias = float(_compute_trend_bias(df).iloc[-1])
    return TimeframeMetrics(adx=adx, atr_pct=atr_pct, volume_ratio=volume_ratio, trend_bias=trend_bias)


def detect_market_state(
    data_1m: pd.DataFrame,
    data_5m: pd.DataFrame,
    data_15m: pd.DataFrame,
) -> MarketState:
    """
    Detect market regime using 1m, 5m, and 15m OHLCV.

    Parameters
    ----------
    data_1m, data_5m, data_15m : pd.DataFrame
        Must contain columns: open, high, low, close, volume

    Returns
    -------
    MarketState
    """
    df1 = _validate_ohlcv(data_1m, "data_1m")
    df5 = _validate_ohlcv(data_5m, "data_5m")
    df15 = _validate_ohlcv(data_15m, "data_15m")

    m1 = _latest_metrics(df1)
    m5 = _latest_metrics(df5)
    m15 = _latest_metrics(df15)

    w1, w5, w15 = 0.2, 0.3, 0.5
    adx_w = m1.adx * w1 + m5.adx * w5 + m15.adx * w15
    atr_w = m1.atr_pct * w1 + m5.atr_pct * w5 + m15.atr_pct * w15
    vol_w = m1.volume_ratio * w1 + m5.volume_ratio * w5 + m15.volume_ratio * w15
    trend_w = m1.trend_bias * w1 + m5.trend_bias * w5 + m15.trend_bias * w15

    low_vol_threshold = 0.18
    high_vol_threshold = 1.2
    adx_trend_threshold = 22.0

    if atr_w < low_vol_threshold:
        regime: Regime = "LOW_VOL"
    elif atr_w > high_vol_threshold:
        regime = "HIGH_VOL"
    elif adx_w >= adx_trend_threshold:
        regime = "TREND_UP" if trend_w >= 0 else "TREND_DOWN"
    else:
        regime = "RANGE"

    trend_component = np.clip((adx_w - 10.0) / 30.0, 0.0, 1.0) * 40.0
    volume_component = np.clip((vol_w - 0.7) / 1.0, 0.0, 1.0) * 25.0
    alignment_component = (1.0 - np.std([m1.trend_bias, m5.trend_bias, m15.trend_bias])) * 20.0
    alignment_component = float(np.clip(alignment_component, 0.0, 20.0))
    volatility_penalty = 0.0
    if regime == "LOW_VOL":
        volatility_penalty = 20.0
    elif regime == "HIGH_VOL":
        volatility_penalty = 10.0
    quality = float(np.clip(trend_component + volume_component + alignment_component - volatility_penalty, 0.0, 100.0))

    return MarketState(
        regime=regime,
        quality_score=quality,
        metrics_1m=m1,
        metrics_5m=m5,
        metrics_15m=m15,
        adx_weighted=float(adx_w),
        atr_pct_weighted=float(atr_w),
        volume_ratio_weighted=float(vol_w),
        trend_bias_weighted=float(trend_w),
    )


def is_tradable_regime(
    regime: Regime,
    quality_score: float,
    min_quality: float = 45.0,
) -> bool:
    """
    Return True when regime is tradable and quality is above threshold.
    """
    if quality_score < min_quality:
        return False
    return regime in {"TREND_UP", "TREND_DOWN", "RANGE"}


# ==========================
# Unit tests (in-file)
# ==========================
if __name__ == "__main__":
    import unittest

    def _make_df(
        n: int = 180,
        drift: float = 0.0,
        vol: float = 0.2,
        vol_mult: float = 1.0,
        seed: int = 7,
    ) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        rets = rng.normal(loc=drift, scale=vol, size=n)
        close = 100 + np.cumsum(rets)
        open_ = np.r_[close[0], close[:-1]]
        spread = np.abs(rng.normal(0.08, 0.03, size=n))
        high = np.maximum(open_, close) + spread
        low = np.minimum(open_, close) - spread
        volume = (rng.normal(1000, 120, size=n).clip(min=100) * vol_mult).astype(float)
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    class MarketStateTests(unittest.TestCase):
        def test_trend_up_regime(self) -> None:
            d1 = _make_df(drift=0.18, vol=0.12, seed=1)
            d5 = _make_df(drift=0.22, vol=0.10, seed=2)
            d15 = _make_df(drift=0.25, vol=0.09, seed=3)
            state = detect_market_state(d1, d5, d15)
            self.assertIn(state.regime, {"TREND_UP", "HIGH_VOL"})

        def test_trend_down_regime(self) -> None:
            d1 = _make_df(drift=-0.18, vol=0.12, seed=4)
            d5 = _make_df(drift=-0.20, vol=0.10, seed=5)
            d15 = _make_df(drift=-0.23, vol=0.09, seed=6)
            state = detect_market_state(d1, d5, d15)
            self.assertIn(state.regime, {"TREND_DOWN", "HIGH_VOL"})

        def test_low_vol_regime(self) -> None:
            d1 = _make_df(drift=0.0, vol=0.01, seed=10)
            d5 = _make_df(drift=0.0, vol=0.01, seed=11)
            d15 = _make_df(drift=0.0, vol=0.01, seed=12)
            state = detect_market_state(d1, d5, d15)
            self.assertEqual(state.regime, "LOW_VOL")
            self.assertLessEqual(state.quality_score, 80.0)

        def test_high_vol_regime(self) -> None:
            d1 = _make_df(drift=0.0, vol=1.8, seed=20)
            d5 = _make_df(drift=0.0, vol=1.6, seed=21)
            d15 = _make_df(drift=0.0, vol=1.4, seed=22)
            state = detect_market_state(d1, d5, d15)
            self.assertEqual(state.regime, "HIGH_VOL")

        def test_is_tradable_regime(self) -> None:
            self.assertTrue(is_tradable_regime("TREND_UP", 60))
            self.assertFalse(is_tradable_regime("LOW_VOL", 90))
            self.assertFalse(is_tradable_regime("RANGE", 20))

    unittest.main()
