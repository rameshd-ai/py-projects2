"""
Indian F&O Brokerage & Tax Calculator
Realistic charges for Zerodha-like discount brokers
"""
import logging

logger = logging.getLogger(__name__)


def calculate_fo_charges(
    entry_price: float,
    exit_price: float,
    qty: int,
    lot_size: int = 50,
) -> dict:
    """
    Calculate total brokerage and taxes for F&O intraday trade.
    
    Indian F&O Charges (Discount Broker like Zerodha):
    - Brokerage: ₹20 per order (flat for intraday)
    - STT (Securities Transaction Tax): 0.0625% on SELL side only
    - Exchange charges (NSE): 0.00173% of turnover
    - SEBI charges: ₹10 per crore (negligible)
    - GST: 18% on (brokerage + exchange charges)
    - Stamp duty: 0.003% on BUY side
    
    Args:
        entry_price: Entry price per contract
        exit_price: Exit price per contract
        qty: Total quantity (contracts)
        lot_size: Lot size for the instrument
    
    Returns:
        dict with breakdown of charges
    """
    # Calculate turnover
    buy_value = entry_price * qty
    sell_value = exit_price * qty
    turnover = buy_value + sell_value
    
    # 1. Brokerage (₹20 per order, 2 orders = entry + exit)
    brokerage = 20 + 20  # ₹40 total
    
    # 2. STT (0.0625% on sell side only for F&O)
    stt = sell_value * 0.000625
    
    # 3. Exchange charges (NSE F&O: 0.00173%)
    exchange_charges = turnover * 0.0000173
    
    # 4. SEBI charges (₹10 per crore, usually negligible)
    sebi_charges = (turnover / 10000000) * 10 if turnover > 0 else 0
    
    # 5. Stamp duty (0.003% on buy side)
    stamp_duty = buy_value * 0.00003
    
    # 6. GST (18% on brokerage + exchange charges)
    gst_base = brokerage + exchange_charges
    gst = gst_base * 0.18
    
    # Total charges
    total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
    
    breakdown = {
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(exchange_charges, 2),
        "sebi_charges": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "gst": round(gst, 2),
        "total_charges": round(total_charges, 2),
        "turnover": round(turnover, 2),
    }
    
    logger.debug(
        f"[BROKERAGE] Turnover: ₹{turnover:.2f} | "
        f"Brokerage: ₹{brokerage:.2f} | STT: ₹{stt:.2f} | "
        f"GST: ₹{gst:.2f} | Total: ₹{total_charges:.2f}"
    )
    
    return breakdown


def calculate_net_pnl(gross_pnl: float, charges: dict) -> float:
    """
    Calculate net P&L after deducting all charges.
    
    Args:
        gross_pnl: Gross P&L before charges
        charges: Dict from calculate_fo_charges()
    
    Returns:
        Net P&L after charges
    """
    total_charges = charges.get("total_charges", 0)
    net_pnl = gross_pnl - total_charges
    return round(net_pnl, 2)


def get_charges_summary(all_trades: list) -> dict:
    """
    Calculate total charges across all trades.
    
    Args:
        all_trades: List of trade dicts with 'charges' field
    
    Returns:
        Summary dict with total charges breakdown
    """
    total_brokerage = 0
    total_stt = 0
    total_exchange = 0
    total_gst = 0
    total_stamp = 0
    total_charges = 0
    
    for trade in all_trades:
        charges = trade.get("charges", {})
        total_brokerage += charges.get("brokerage", 0)
        total_stt += charges.get("stt", 0)
        total_exchange += charges.get("exchange_charges", 0)
        total_gst += charges.get("gst", 0)
        total_stamp += charges.get("stamp_duty", 0)
        total_charges += charges.get("total_charges", 0)
    
    return {
        "total_brokerage": round(total_brokerage, 2),
        "total_stt": round(total_stt, 2),
        "total_exchange_charges": round(total_exchange, 2),
        "total_gst": round(total_gst, 2),
        "total_stamp_duty": round(total_stamp, 2),
        "total_charges": round(total_charges, 2),
    }
