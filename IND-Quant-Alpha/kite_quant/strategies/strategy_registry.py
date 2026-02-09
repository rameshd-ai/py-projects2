"""
Strategy registry: map strategy names (from algo/recommendation) to strategy classes.
"""
from __future__ import annotations

from typing import Any

from strategies.base_strategy import BaseStrategy
from strategies.momentum_breakout import MomentumBreakout
from strategies.vwap_trend import VWAPTrend
from strategies.rsi_reversal import RSIReversal
from strategies.orb_breakout import OpeningRangeBreakout
from strategies.pullback_continuation import PullbackContinuation
from strategies.bollinger_mean_reversion import BollingerMeanReversion
from strategies.vwap_mean_reversion import VWAPMeanReversion
from strategies.liquidity_sweep_reversal import LiquiditySweepReversal
from strategies.inside_bar_breakout import InsideBarBreakout
from strategies.news_volatility_burst import NewsVolatilityBurst
from strategies.time_based_volatility_play import TimeBasedVolatilityPlay
from strategies.gamma_scalping_lite import GammaScalpingLite
from strategies.sector_rotation_momentum import SectorRotationMomentum
from strategies.relative_strength_breakout import RelativeStrengthBreakout
from strategies.volume_climax_reversal import VolumeClimaxReversal
from strategies.trend_day_vwap_hold import TrendDayVWAPHold
from strategies.ema_ribbon_trend_alignment import EMARibbonTrendAlignment
from strategies.range_compression_breakout import RangeCompressionBreakout
from strategies.failed_breakdown_trap import FailedBreakdownTrap
from strategies.vwap_reclaim import VWAPReclaim
from strategies.volume_dry_up_breakout import VolumeDryUpBreakout
from strategies.daily_breakout_continuation import DailyBreakoutContinuation
from strategies.pullback_20_50_dma import Pullback2050DMA
from strategies.swing_rsi_compression_breakout import SwingRSICompressionBreakout
from strategies.swing_volume_accumulation import SwingVolumeAccumulation
from strategies.multi_timeframe_alignment import MultiTimeframeAlignment
from strategies.liquidity_zone_reaction import LiquidityZoneReaction
from strategies.order_flow_imbalance_proxy import OrderFlowImbalanceProxy
from strategies.volatility_contraction_expansion import VolatilityContractionExpansion
from strategies.time_of_day_behavior import TimeOfDayBehavior
from strategies.smart_money_trap_detection import SmartMoneyTrapDetection

STRATEGY_MAP: dict[str, type[BaseStrategy]] = {
    "Momentum Breakout": MomentumBreakout,
    "momentum_breakout": MomentumBreakout,
    "VWAP Trend Ride": VWAPTrend,
    "vwap_trend_ride": VWAPTrend,
    "RSI Reversal Fade": RSIReversal,
    "rsi_reversal_fade": RSIReversal,
    "Opening Range Breakout": OpeningRangeBreakout,
    "orb_opening_range_breakout": OpeningRangeBreakout,
    "orb": OpeningRangeBreakout,
    "Index Momentum": MomentumBreakout,
    "index_lead_stock_lag": MomentumBreakout,
    "Pullback Continuation": PullbackContinuation,
    "pullback_continuation": PullbackContinuation,
    "Bollinger Mean Reversion": BollingerMeanReversion,
    "bollinger_mean_reversion": BollingerMeanReversion,
    "VWAP Mean Reversion": VWAPMeanReversion,
    "vwap_mean_reversion": VWAPMeanReversion,
    "Liquidity Sweep Reversal": LiquiditySweepReversal,
    "liquidity_sweep_reversal": LiquiditySweepReversal,
    "Inside Bar Breakout": InsideBarBreakout,
    "inside_bar_breakout": InsideBarBreakout,
    "News Volatility Burst": NewsVolatilityBurst,
    "news_volatility_burst": NewsVolatilityBurst,
    "Time-Based Volatility Play": TimeBasedVolatilityPlay,
    "time_based_volatility_play": TimeBasedVolatilityPlay,
    "Gamma Scalping Lite": GammaScalpingLite,
    "gamma_scalping_lite": GammaScalpingLite,
    "Sector Rotation Momentum": SectorRotationMomentum,
    "sector_rotation_momentum": SectorRotationMomentum,
    "Relative Strength Breakout": RelativeStrengthBreakout,
    "relative_strength_breakout": RelativeStrengthBreakout,
    "Volume Climax Reversal": VolumeClimaxReversal,
    "volume_climax_reversal": VolumeClimaxReversal,
    "Trend Day VWAP Hold": TrendDayVWAPHold,
    "trend_day_vwap_hold": TrendDayVWAPHold,
    "EMA Ribbon Trend Alignment": EMARibbonTrendAlignment,
    "ema_ribbon_trend_alignment": EMARibbonTrendAlignment,
    "Range Compression Breakout": RangeCompressionBreakout,
    "range_compression_breakout": RangeCompressionBreakout,
    "Failed Breakdown / Breakdown Trap": FailedBreakdownTrap,
    "failed_breakdown_trap": FailedBreakdownTrap,
    "VWAP Reclaim": VWAPReclaim,
    "vwap_reclaim": VWAPReclaim,
    "Volume Dry-Up Breakout": VolumeDryUpBreakout,
    "volume_dry_up_breakout": VolumeDryUpBreakout,
    "Daily Breakout Continuation": DailyBreakoutContinuation,
    "daily_breakout_continuation": DailyBreakoutContinuation,
    "Pullback to 20/50 DMA": Pullback2050DMA,
    "pullback_20_50_dma": Pullback2050DMA,
    "Swing RSI Compression Breakout": SwingRSICompressionBreakout,
    "swing_rsi_compression_breakout": SwingRSICompressionBreakout,
    "Swing Volume Accumulation": SwingVolumeAccumulation,
    "swing_volume_accumulation": SwingVolumeAccumulation,
    "Multi-Timeframe Alignment": MultiTimeframeAlignment,
    "multi_timeframe_alignment": MultiTimeframeAlignment,
    "Liquidity Zone Reaction": LiquidityZoneReaction,
    "liquidity_zone_reaction": LiquidityZoneReaction,
    "Order Flow Imbalance Proxy": OrderFlowImbalanceProxy,
    "order_flow_imbalance_proxy": OrderFlowImbalanceProxy,
    "Volatility Contraction → Expansion Model": VolatilityContractionExpansion,
    "volatility_contraction_expansion": VolatilityContractionExpansion,
    "Time-of-Day Behavior Model": TimeOfDayBehavior,
    "time_of_day_behavior": TimeOfDayBehavior,
    "Smart Money Trap Detection": SmartMoneyTrapDetection,
    "smart_money_trap_detection": SmartMoneyTrapDetection,
}


def get_strategy_for_session(
    session: dict,
    data_provider: Any,
    strategy_name_override: str | None = None,
) -> BaseStrategy | None:
    """Return strategy instance. Uses strategy_name_override if given (for engine re-scan), else session recommendation."""
    rec = session.get("recommendation") or {}
    name = strategy_name_override or rec.get("strategyName") or rec.get("selectedAlgoName") or rec.get("strategy") or ""
    strategy_id = rec.get("strategyId") or ""
    StrategyClass = STRATEGY_MAP.get(name) or STRATEGY_MAP.get(strategy_id)
    if not StrategyClass:
        StrategyClass = MomentumBreakout
    instrument = session.get("instrument", "")
    return StrategyClass(instrument, data_provider)
