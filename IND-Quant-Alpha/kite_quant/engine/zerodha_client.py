"""
Zerodha Kite Connect client: orders, positions, Kill Switch (square off).
Uses kiteconnect library for Zerodha API.
"""
from __future__ import annotations

import os
from typing import Any

try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    KiteConnect = None


def _get_kite() -> KiteConnect | None:
    """Initialize and return KiteConnect instance."""
    if not KITE_AVAILABLE:
        return None
    
    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
    
    if not api_key or not access_token:
        return None
    
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        return kite
    except Exception:
        return None


def _get_instrument_token(symbol: str) -> int | None:
    """Convert NSE symbol to instrument token. Format: NSE:SYMBOL"""
    kite = _get_kite()
    if not kite:
        return None
    
    try:
        # Try NSE format first
        nse_symbol = f"NSE:{symbol}"
        instruments = kite.instruments("NSE")
        for inst in instruments:
            if inst["tradingsymbol"] == symbol.upper():
                return inst["instrument_token"]
        return None
    except Exception:
        return None


def place_order(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "MARKET",
    price: float | None = None,
    sl: float | None = None,
    tp: float | None = None,
) -> dict[str, Any]:
    """
    Place order via Zerodha Kite. side: BUY | SELL.
    sl/tp as absolute price or None.
    """
    kite = _get_kite()
    if not kite:
        return {"error": "Kite Connect not initialized. Check API credentials.", "success": False}
    
    try:
        instrument_token = _get_instrument_token(symbol)
        if not instrument_token:
            return {"error": f"Instrument token not found for {symbol}", "success": False}
        
        # Map order types
        kite_order_type = "MARKET" if order_type.upper() == "MARKET" else "LIMIT"
        transaction_type = "BUY" if side.upper() == "BUY" else "SELL"
        product_type = "MIS"  # Intraday
        
        order_params = {
            "exchange": "NSE",
            "tradingsymbol": symbol.upper(),
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": kite_order_type,
            "product": product_type,
            "validity": "DAY",
        }
        
        if price is not None and kite_order_type == "LIMIT":
            order_params["price"] = price
        
        # Place order
        order_id = kite.place_order(**order_params)
        
        # If SL/TP provided, place bracket orders (Zerodha supports GTT or separate orders)
        result = {"order_id": order_id, "success": True, "symbol": symbol}
        
        if sl is not None or tp is not None:
            # Note: Zerodha bracket orders require different approach
            # For now, we'll place the main order and note SL/TP in response
            result["stop_loss"] = sl
            result["target"] = tp
            result["note"] = "Place SL/TP orders separately or use GTT"
        
        return result
    except Exception as e:
        return {"error": str(e), "success": False}


def get_positions() -> list[dict[str, Any]]:
    """Fetch open positions from Zerodha."""
    kite = _get_kite()
    if not kite:
        return []
    
    try:
        positions = kite.positions()
        # Zerodha returns {'net': [...], 'day': [...]}
        net_positions = positions.get("net", [])
        
        result = []
        for pos in net_positions:
            if int(pos.get("quantity", 0)) != 0:  # Only non-zero positions
                result.append({
                    "symbol": pos.get("tradingsymbol", ""),
                    "quantity": int(pos.get("quantity", 0)),
                    "pnl": float(pos.get("pnl", 0)),
                    "unrealized": float(pos.get("unrealized", 0)),
                    "average_price": float(pos.get("average_price", 0)),
                    "last_price": float(pos.get("last_price", 0)),
                })
        return result
    except Exception:
        return []


def get_quote(symbol: str) -> dict[str, Any]:
    """Get current quote for symbol."""
    kite = _get_kite()
    if not kite:
        return {"symbol": symbol, "last": 0.0, "open": 0.0, "high": 0.0, "low": 0.0}
    
    try:
        nse_symbol = f"NSE:{symbol.upper()}"
        quote = kite.quote(nse_symbol)
        ltp_data = quote.get(nse_symbol, {})
        
        return {
            "symbol": symbol,
            "last": float(ltp_data.get("last_price", 0)),
            "open": float(ltp_data.get("ohlc", {}).get("open", 0)),
            "high": float(ltp_data.get("ohlc", {}).get("high", 0)),
            "low": float(ltp_data.get("ohlc", {}).get("low", 0)),
        }
    except Exception:
        return {"symbol": symbol, "last": 0.0, "open": 0.0, "high": 0.0, "low": 0.0}


def close_position(symbol: str, quantity: int | None = None) -> dict[str, Any]:
    """Square off one position (SELL for long, BUY for short)."""
    positions = get_positions()
    for p in positions:
        if p.get("symbol", "").upper() == symbol.upper():
            qty = abs(quantity or int(p.get("quantity", 0)))
            side = "SELL" if int(p.get("quantity", 0)) > 0 else "BUY"
            return place_order(symbol, side, qty)
    return {"error": "Position not found", "success": False}


def kill_switch() -> list[dict[str, Any]]:
    """Close all open positions immediately."""
    positions = get_positions()
    results = []
    for p in positions:
        sym = p.get("symbol", "")
        qty = abs(int(p.get("quantity", 0)))
        if sym and qty:
            side = "SELL" if int(p.get("quantity", 0)) > 0 else "BUY"
            results.append(place_order(sym, side, qty))
    return results
