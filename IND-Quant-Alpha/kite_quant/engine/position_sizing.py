"""
Centralized Position Sizing Logic for F&O and Stock Trading
Used by Live, Paper, and Backtest modes
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Configuration constants
FO_POSITION_SIZE_PERCENT = 0.95  # Use 95% of capital for F&O positions (max utilization)
STOCK_RISK_PERCENT = 2.0  # Use 2% risk per trade for stocks
MIN_PREMIUM_FLOOR = 50.0  # Minimum realistic premium for options (Rs.)


def calculate_fo_position_size(
    capital: float,
    premium: float,
    lot_size: int,
) -> Tuple[int, float, bool]:
    """
    Calculate F&O position size based on capital.
    
    Args:
        capital: Available capital
        premium: Option premium per contract
        lot_size: Standard lot size for the instrument
    
    Returns:
        (lots, total_cost, can_afford)
        - lots: Number of lots that can be traded
        - total_cost: Total cost for the position
        - can_afford: Whether we can afford at least 1 lot
    """
    # Use configured percentage of capital for position
    max_position_value = capital * FO_POSITION_SIZE_PERCENT
    
    # Ensure premium is realistic
    effective_premium = max(premium, MIN_PREMIUM_FLOOR)
    
    # Calculate cost per lot
    cost_per_lot = effective_premium * lot_size
    
    if cost_per_lot <= 0:
        return 0, 0.0, False
    
    # Calculate affordable lots
    affordable_lots = int(max_position_value / cost_per_lot)
    
    if affordable_lots < 1:
        logger.info(
            f"[POSITION SIZING] Insufficient capital for F&O. "
            f"Need Rs.{cost_per_lot:.2f}/lot, have Rs.{max_position_value:.2f} available "
            f"({FO_POSITION_SIZE_PERCENT*100:.0f}% of Rs.{capital:.2f} capital)"
        )
        return 0, 0.0, False
    
    total_cost = affordable_lots * cost_per_lot
    
    logger.info(
        f"[POSITION SIZING] F&O: Capital=Rs.{capital:.2f}, "
        f"Premium=Rs.{effective_premium:.2f}, Lot size={lot_size}, "
        f"Affordable lots={affordable_lots}, Total cost=Rs.{total_cost:.2f}"
    )
    
    return affordable_lots, total_cost, True


def calculate_stock_position_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
    risk_percent: Optional[float] = None,
) -> Tuple[int, float]:
    """
    Calculate stock position size based on risk management.
    
    Args:
        capital: Available capital
        entry_price: Entry price per share
        stop_loss: Stop loss price per share
        risk_percent: Risk percentage (default: STOCK_RISK_PERCENT)
    
    Returns:
        (quantity, risk_amount)
        - quantity: Number of shares to trade
        - risk_amount: Total risk amount
    """
    if risk_percent is None:
        risk_percent = STOCK_RISK_PERCENT
    
    # Calculate risk amount
    risk_amount = capital * (risk_percent / 100.0)
    
    # Calculate risk per share
    risk_per_share = abs(entry_price - stop_loss)
    
    if risk_per_share <= 0:
        logger.warning(
            f"[POSITION SIZING] Invalid stop loss. "
            f"Entry: Rs.{entry_price:.2f}, Stop: Rs.{stop_loss:.2f}"
        )
        return 0, 0.0
    
    # Calculate quantity
    quantity = int(risk_amount / risk_per_share)
    
    logger.info(
        f"[POSITION SIZING] Stock: Capital=Rs.{capital:.2f}, "
        f"Entry=Rs.{entry_price:.2f}, Stop=Rs.{stop_loss:.2f}, "
        f"Risk={risk_percent:.1f}%, Quantity={quantity}"
    )
    
    return quantity, risk_amount


def calculate_position_size_auto(
    capital: float,
    entry_price: float,
    lot_size: int = 1,
    stop_loss: Optional[float] = None,
    premium: Optional[float] = None,
    risk_percent: Optional[float] = None,
) -> Tuple[int, float, bool]:
    """
    Automatically detect F&O vs Stock and calculate position size.
    
    Args:
        capital: Available capital
        entry_price: Entry price (premium for F&O, stock price for stocks)
        lot_size: Lot size (>1 for F&O, 1 for stocks)
        stop_loss: Stop loss price (required for stocks)
        premium: Option premium (for F&O, overrides entry_price if provided)
        risk_percent: Risk percentage for stocks
    
    Returns:
        (lots_or_quantity, total_cost_or_risk, can_afford)
    """
    # Detect if this is F&O (lot_size > 1) or Stock (lot_size = 1)
    is_fo = lot_size > 1
    
    if is_fo:
        # F&O position sizing
        effective_premium = premium if premium is not None else entry_price
        return calculate_fo_position_size(capital, effective_premium, lot_size)
    else:
        # Stock position sizing
        if stop_loss is None:
            # Default stop loss if not provided (1.5% below entry)
            stop_loss = entry_price * 0.985
        
        quantity, risk_amount = calculate_stock_position_size(
            capital, entry_price, stop_loss, risk_percent
        )
        can_afford = quantity > 0
        return quantity, risk_amount, can_afford


def get_min_capital_for_fo(premium: float, lot_size: int) -> float:
    """
    Calculate minimum capital required to trade F&O.
    
    Args:
        premium: Option premium per contract
        lot_size: Standard lot size
    
    Returns:
        Minimum capital required
    """
    effective_premium = max(premium, MIN_PREMIUM_FLOOR)
    cost_per_lot = effective_premium * lot_size
    min_capital = cost_per_lot / FO_POSITION_SIZE_PERCENT
    return min_capital


def can_afford_fo_position(capital: float, premium: float, lot_size: int) -> bool:
    """
    Quick check if capital is sufficient for F&O trading.
    
    Args:
        capital: Available capital
        premium: Option premium per contract
        lot_size: Standard lot size
    
    Returns:
        True if can afford at least 1 lot
    """
    _, _, can_afford = calculate_fo_position_size(capital, premium, lot_size)
    return can_afford
