"""
Zerodha Kite Connect client: orders, positions, Kill Switch (square off).
Uses kiteconnect library for Zerodha API.
"""
from __future__ import annotations

import os
import time
from typing import Any

try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    KiteConnect = None

# Cache for NSE instruments (symbol search). TTL 24 hours.
_instruments_cache: list[dict[str, Any]] = []
_instruments_cache_time: float = 0
INSTRUMENTS_CACHE_TTL_SEC = 24 * 3600

# Cache for NFO options (index option tradingsymbol resolution).
_nfo_options_cache: list[dict[str, Any]] = []
_nfo_options_cache_time: float = 0
NFO_CACHE_TTL_SEC = 3600

# Standard indices (F&O underlyings) - always searchable even if not in NSE dump (FINNIFTY removed)
_FNO_INDEX_LIST = [
    {"symbol": "NIFTY 50", "name": "Nifty 50 Index", "instrument_type": "INDEX", "exchange": "NSE"},
    {"symbol": "NIFTY BANK", "name": "Nifty Bank Index", "instrument_type": "INDEX", "exchange": "NSE"},
    {"symbol": "MIDCPNIFTY", "name": "Nifty Midcap Select", "instrument_type": "INDEX", "exchange": "NSE"},
]


def _get_kite() -> KiteConnect | None:
    """Initialize and return KiteConnect instance."""
    import logging
    logger = logging.getLogger(__name__)
    
    if not KITE_AVAILABLE:
        logger.warning("KiteConnect library not available")
        return None
    
    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
    
    logger.info(f"Attempting Kite auth: api_key={'present' if api_key else 'missing'}, access_token={'present' if access_token else 'missing'}")
    
    if not api_key or not access_token:
        logger.error("Zerodha credentials not found in environment")
        return None
    
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        logger.info("Kite client created successfully")
        return kite
    except Exception as e:
        logger.exception(f"Failed to create Kite client: {e}")
        return None


def _get_instrument_token(symbol: str) -> int | None:
    """Convert NSE symbol to instrument token. Format: NSE:SYMBOL"""
    kite = _get_kite()
    if not kite:
        return None
    
    try:
        instruments = kite.instruments("NSE")
        for inst in instruments:
            if inst["tradingsymbol"] == symbol.upper():
                return inst["instrument_token"]
        return None
    except Exception:
        return None


def _load_nfo_options_cache(force: bool = False) -> list[dict[str, Any]]:
    """Load NFO instruments (options) for index option tradingsymbol resolution."""
    global _nfo_options_cache, _nfo_options_cache_time
    now = time.time()
    if not force and _nfo_options_cache and (now - _nfo_options_cache_time) < NFO_CACHE_TTL_SEC:
        return _nfo_options_cache
    kite = _get_kite()
    if not kite:
        return _nfo_options_cache
    try:
        import socket
        socket.setdefaulttimeout(60)
        raw = kite.instruments("NFO")
        out = [inst for inst in raw if (inst.get("instrument_type") or "").upper() in ("CE", "PE")]
        _nfo_options_cache = out
        _nfo_options_cache_time = now
        return out
    except Exception:
        return _nfo_options_cache


def get_nfo_option_tradingsymbol(
    index_name: str,
    strike: int,
    option_type: str,
) -> str | None:
    """
    Return Zerodha NFO tradingsymbol for index option (e.g. NIFTY24SEP2622500CE).
    Used for LIVE index option execution. Returns None if not found.
    """
    index_name = (index_name or "").upper().replace(" ", "")
    if index_name == "BANKNIFTY":
        underlying = "BANKNIFTY"
    else:
        underlying = "NIFTY"
    opt = (option_type or "CE").upper()
    if opt not in ("CE", "PE"):
        opt = "CE"
    instruments = _load_nfo_options_cache()
    strike_str = str(strike)
    for inst in instruments:
        ts = (inst.get("tradingsymbol") or "").strip()
        if not ts.startswith(underlying):
            continue
        if not ts.endswith(opt):
            continue
        if strike_str not in ts:
            continue
        return ts
    return None


def _load_instruments_cache(force: bool = False) -> list[dict[str, Any]]:
    """Load NSE instruments from Zerodha and cache. Returns EQ (equity) + INDEX (Nifty, Bank Nifty, etc.) for search/F&O."""
    global _instruments_cache, _instruments_cache_time
    now = time.time()
    if not force and _instruments_cache and (now - _instruments_cache_time) < INSTRUMENTS_CACHE_TTL_SEC:
        return _instruments_cache
    kite = _get_kite()
    if not kite:
        return _instruments_cache
    try:
        import socket
        socket.setdefaulttimeout(30)
        raw = kite.instruments("NSE")
        out = []
        seen = set()
        for i in _FNO_INDEX_LIST:
            s = (i.get("symbol") or "").strip()
            if s and s not in seen:
                seen.add(s)
                out.append({**i, "symbol": s})
        for inst in raw:
            seg = inst.get("segment") or ""
            itype = (inst.get("instrument_type") or "").upper()
            if seg == "NSE" and (itype == "EQ" or itype == "INDEX"):
                s = (inst.get("tradingsymbol") or "").strip()
                if s and s not in seen:
                    seen.add(s)
                    out.append({
                        "symbol": s,
                        "name": (inst.get("name") or "").strip(),
                        "instrument_type": itype,
                        "exchange": "NSE",
                    })
        # Load NFO (F&O) futures for main indices so "nifty" shows Nifty futures
        try:
            nfo_raw = kite.instruments("NFO")
            fno_keywords = ("NIFTY", "BANKNIFTY", "MIDCPNIFTY")
            nfo_count = 0
            for inst in nfo_raw:
                if nfo_count >= 40:
                    break
                itype = (inst.get("instrument_type") or "").upper()
                if itype != "FUT":
                    continue
                s = (inst.get("tradingsymbol") or "").strip()
                if not s or s in seen:
                    continue
                if any(kw in s for kw in fno_keywords):
                    seen.add(s)
                    out.append({
                        "symbol": s,
                        "name": (inst.get("name") or "").strip() or s,
                        "instrument_type": "FUT",
                        "exchange": "NFO",
                    })
                    nfo_count += 1
        except Exception:
            pass
        _instruments_cache = out
        _instruments_cache_time = now
        return out
    except Exception:
        return _instruments_cache


def search_instruments(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search NSE equity and index symbols. INDEX (Nifty, Bank Nifty, F&O underlyings) always first, then EQ."""
    q = (query or "").strip().upper()
    if not q or len(q) < 2:
        return []
    instruments = _load_instruments_cache()
    q_lower = query.strip().lower()
    index_results = []
    fut_results = []
    eq_results = []
    for inst in instruments:
        sym = inst.get("symbol") or ""
        name = inst.get("name") or ""
        if not (q in sym or q_lower in name.lower() or sym.startswith(q) or q in (name or "").upper()):
            continue
        itype = (inst.get("instrument_type") or "").upper()
        if itype == "INDEX":
            index_results.append(inst)
        elif itype == "FUT":
            fut_results.append(inst)
        else:
            eq_results.append(inst)
    # Order: INDEX (F&O underlyings) first, then FUT (futures), then EQ
    def prefix_sort_key(x):
        s = x.get("symbol") or ""
        return (0 if s.startswith(q) else 1, s)
    index_results.sort(key=prefix_sort_key)
    fut_results.sort(key=prefix_sort_key)
    eq_results.sort(key=prefix_sort_key)
    combined = index_results + fut_results + eq_results
    return combined[:limit]


def place_order(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "MARKET",
    price: float | None = None,
    trigger_price: float | None = None,
    sl: float | None = None,
    tp: float | None = None,
    exchange: str | None = None,
    tradingsymbol: str | None = None,
) -> dict[str, Any]:
    """
    Place order via Zerodha Kite. side: BUY | SELL.
    For NFO index options pass exchange="NFO" and tradingsymbol (e.g. NIFTY24SEP2622500CE).
    For NSE equity pass symbol only (exchange defaults NSE).
    """
    kite = _get_kite()
    if not kite:
        return {"error": "Kite Connect not initialized. Check API credentials.", "success": False}
    use_exchange = (exchange or "NSE").upper()
    use_tradingsymbol = (tradingsymbol or symbol or "").strip().upper()
    if not use_tradingsymbol:
        return {"error": "Missing symbol or tradingsymbol", "success": False}
    try:
        order_type_upper = order_type.upper()
        if order_type_upper in ("MARKET", "LIMIT", "SL", "SL-M"):
            kite_order_type = order_type_upper
        else:
            kite_order_type = "MARKET"
        transaction_type = "BUY" if side.upper() == "BUY" else "SELL"
        product_type = "MIS"
        order_params = {
            "exchange": use_exchange,
            "tradingsymbol": use_tradingsymbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": kite_order_type,
            "product": product_type,
            "validity": "DAY",
        }
        if price is not None and kite_order_type in ("LIMIT", "SL"):
            order_params["price"] = price
        if trigger_price is not None and kite_order_type in ("SL", "SL-M"):
            order_params["trigger_price"] = trigger_price
        order_id = kite.place_order(**order_params)
        result = {"order_id": order_id, "success": True, "symbol": use_tradingsymbol}
        if sl is not None or tp is not None:
            result["stop_loss"] = sl
            result["target"] = tp
            result["note"] = "Place SL/TP orders separately or use GTT"
        return result
    except Exception as e:
        return {"error": str(e), "success": False}


def get_order_status(order_id: str) -> dict[str, Any]:
    """Fetch latest broker order status and fill details for an order_id."""
    kite = _get_kite()
    if not kite:
        return {"success": False, "error": "Kite Connect not initialized"}
    if not order_id:
        return {"success": False, "error": "Missing order_id"}
    try:
        import socket

        socket.setdefaulttimeout(10)
        history = kite.order_history(order_id)
        if not history:
            return {"success": False, "error": f"No order history found for {order_id}"}

        latest = history[-1] if isinstance(history, list) else history
        status = str(latest.get("status") or "").upper()
        filled_quantity = int(latest.get("filled_quantity") or 0)
        avg_fill_price = latest.get("average_price")
        try:
            avg_fill_price = float(avg_fill_price) if avg_fill_price is not None else None
        except (TypeError, ValueError):
            avg_fill_price = None
        reject_reason = latest.get("status_message") or latest.get("status_message_raw")

        return {
            "success": True,
            "order_id": order_id,
            "status": status,
            "filled_quantity": filled_quantity,
            "avg_fill_price": avg_fill_price,
            "reject_reason": reject_reason,
            "raw": latest,
            "fills": [],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancel_order(order_id: str, variety: str = "regular") -> dict[str, Any]:
    """Cancel an order at broker and return normalized result."""
    kite = _get_kite()
    if not kite:
        return {"success": False, "cancelled": False, "error": "Kite Connect not initialized"}
    if not order_id:
        return {"success": False, "cancelled": False, "error": "Missing order_id"}
    try:
        kite.cancel_order(variety=variety, order_id=order_id)
        return {"success": True, "cancelled": True, "order_id": order_id}
    except Exception as e:
        return {"success": False, "cancelled": False, "error": str(e), "order_id": order_id}


def get_open_orders() -> list[dict[str, Any]]:
    """Return broker open/pending orders with normalized keys."""
    kite = _get_kite()
    if not kite:
        return []
    try:
        import socket

        socket.setdefaulttimeout(10)
        orders = kite.orders()
        out: list[dict[str, Any]] = []
        for o in orders or []:
            status = str(o.get("status") or "").upper()
            if status not in ("OPEN", "TRIGGER PENDING", "AMO REQ RECEIVED", "PUT ORDER REQ RECEIVED"):
                continue
            out.append(
                {
                    "order_id": o.get("order_id"),
                    "status": status,
                    "symbol": o.get("tradingsymbol"),
                    "exchange": o.get("exchange"),
                    "side": o.get("transaction_type"),
                    "quantity": int(o.get("quantity") or 0),
                    "filled_quantity": int(o.get("filled_quantity") or 0),
                    "pending_quantity": int(o.get("pending_quantity") or 0),
                    "order_type": o.get("order_type"),
                    "price": float(o.get("price") or 0.0),
                    "trigger_price": float(o.get("trigger_price") or 0.0),
                }
            )
        return out
    except Exception:
        return []


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


def get_balance() -> tuple[float, bool]:
    """Fetch available trading balance from Zerodha (equity segment). Returns (balance, success). Use success to show — when disconnected."""
    kite = _get_kite()
    if not kite:
        return (0.0, False)
    
    try:
        import socket
        socket.setdefaulttimeout(8)
        margins = kite.margins("equity")
        avail = margins.get("available") if isinstance(margins.get("available"), dict) else {}
        raw = avail.get("live_balance") or avail.get("cash") or 0
        try:
            return (float(raw), True)
        except (TypeError, ValueError):
            return (0.0, True)
    except Exception:
        return (0.0, False)


def get_zerodha_profile_info() -> dict[str, Any]:
    """
    Fetch all important Zerodha profile and account info for trading:
    profile (user, email, broker), equity margins (available, utilised, net), positions summary.
    """
    kite = _get_kite()
    if not kite:
        return {"connected": False, "error": "Zerodha not connected"}

    try:
        import socket
        socket.setdefaulttimeout(5)
        out: dict[str, Any] = {"connected": True, "profile": {}, "margins": {}, "positions_summary": {}}

        # Profile
        try:
            profile = kite.profile()
            out["profile"] = {
                "user_name": profile.get("user_name", ""),
                "user_id": profile.get("user_id", ""),
                "user_type": profile.get("user_type", ""),
                "email": profile.get("email", ""),
                "broker": profile.get("broker", "Zerodha"),
                "exchanges": profile.get("exchanges", []),
                "products": profile.get("products", []),
                "order_types": profile.get("order_types", []),
            }
        except Exception as e:
            out["profile"] = {"error": str(e)}

        # Equity margins (available, utilised, net)
        try:
            margins = kite.margins("equity")
            if not isinstance(margins, dict):
                margins = {}
            avail = margins.get("available")
            utilised = margins.get("utilised")
            if not isinstance(avail, dict):
                avail = {}
            if not isinstance(utilised, dict):
                utilised = {}
            net_val = margins.get("net")
            if net_val is not None and not isinstance(net_val, (int, float)):
                net_val = 0
            elif net_val is None:
                net_val = 0
            # Normalise to numbers for JSON
            def _float(v, default=0):
                try:
                    return float(v) if v is not None else default
                except (TypeError, ValueError):
                    return default
            out["margins"] = {
                "available": {
                    "cash": _float(avail.get("cash")),
                    "live_balance": _float(avail.get("live_balance")),
                    "opening_balance": _float(avail.get("opening_balance")),
                    "collateral": _float(avail.get("collateral")),
                    "adhoc_margin": _float(avail.get("adhoc_margin")),
                    "intraday_payin": _float(avail.get("intraday_payin")),
                },
                "utilised": {
                    "debits": _float(utilised.get("debits")),
                    "span": _float(utilised.get("span")),
                    "exposure": _float(utilised.get("exposure")),
                    "option_premium": _float(utilised.get("option_premium")),
                    "m2m_unrealised": _float(utilised.get("m2m_unrealised")),
                    "m2m_realised": _float(utilised.get("m2m_realised")),
                    "delivery": _float(utilised.get("delivery")),
                },
                "net": float(net_val),
            }
        except Exception as e:
            out["margins"] = {"error": str(e)}

        # Positions summary
        try:
            positions = get_positions()
            total_pnl = sum(float(p.get("pnl", 0)) for p in positions)
            out["positions_summary"] = {
                "count": len(positions),
                "total_pnl": total_pnl,
                "positions": positions,
            }
        except Exception as e:
            out["positions_summary"] = {"error": str(e), "count": 0, "total_pnl": 0, "positions": []}

        return out
    except Exception as e:
        return {"connected": False, "error": str(e)}


def get_quote(symbol: str, exchange: str = "NSE") -> dict[str, Any]:
    """Get current quote. For NFO options pass exchange='NFO' and symbol as tradingsymbol (e.g. NIFTY24SEP2622500CE)."""
    kite = _get_kite()
    if not kite:
        return {"symbol": symbol, "last": 0.0, "open": 0.0, "high": 0.0, "low": 0.0}
    key = f"{(exchange or 'NSE').upper()}:{(symbol or '').strip().upper()}"
    try:
        quote = kite.quote(key)
        ltp_data = quote.get(key, {})
        depth = ltp_data.get("depth", {})
        buy_qty = sum(item.get("quantity", 0) for item in (depth.get("buy") or []) if item.get("quantity"))
        sell_qty = sum(item.get("quantity", 0) for item in (depth.get("sell") or []) if item.get("quantity"))
        if not buy_qty and not sell_qty:
            buy_qty = int(ltp_data.get("buy_quantity", 0))
            sell_qty = int(ltp_data.get("sell_quantity", 0))
        return {
            "symbol": symbol,
            "last": float(ltp_data.get("last_price", 0)),
            "last_price": float(ltp_data.get("last_price", 0)),
            "open": float(ltp_data.get("ohlc", {}).get("open", 0)),
            "high": float(ltp_data.get("ohlc", {}).get("high", 0)),
            "low": float(ltp_data.get("ohlc", {}).get("low", 0)),
            "buy_quantity": buy_qty,
            "sell_quantity": sell_qty,
        }
    except Exception:
        return {"symbol": symbol, "last": 0.0, "open": 0.0, "high": 0.0, "low": 0.0}


def get_quotes_bulk(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Get quotes for multiple NSE symbols in one call. Returns dict keyed by symbol with last, open, high, low, change, change_pct."""
    kite = _get_kite()
    if not kite or not symbols:
        return {}
    instruments = [f"NSE:{s.upper()}" for s in symbols if s and isinstance(s, str)]
    if not instruments:
        return {}
    try:
        import socket
        socket.setdefaulttimeout(10)
        raw = kite.quote(instruments)
        out = {}
        for sym in symbols:
            sym = (sym or "").strip().upper()
            if not sym:
                continue
            key = f"NSE:{sym}"
            ltp_data = raw.get(key, {})
            last = float(ltp_data.get("last_price", 0))
            ohlc = ltp_data.get("ohlc") or {}
            open_p = float(ohlc.get("open", 0))
            high = float(ohlc.get("high", 0))
            low = float(ohlc.get("low", 0))
            change = last - open_p if open_p else 0
            change_pct = (change / open_p * 100) if open_p else 0
            out[sym] = {
                "symbol": sym,
                "last": last,
                "open": open_p,
                "high": high,
                "low": low,
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            }
        return out
    except Exception:
        return {}


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
