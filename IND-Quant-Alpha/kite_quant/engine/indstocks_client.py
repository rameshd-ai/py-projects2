"""
INDstocks REST client: orders, positions, Kill Switch (square off).
Adjust endpoints to match https://api-docs.indstocks.com
"""
from __future__ import annotations

import os
from typing import Any

import requests


def _headers() -> dict[str, str]:
    api_key = os.getenv("IND_API_KEY")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _base_url() -> str:
    return (os.getenv("IND_BASE_URL", "https://api.indstocks.com")).rstrip("/")


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
    Place order via INDstocks. side: BUY | SELL.
    sl/tp as absolute price or None.
    """
    url = f"{_base_url()}/v1/order/place"
    payload = {
        "symbol": symbol,
        "side": side.upper(),
        "quantity": quantity,
        "order_type": order_type.upper(),
    }
    if price is not None:
        payload["price"] = price
    if sl is not None:
        payload["stop_loss"] = sl
    if tp is not None:
        payload["target"] = tp
    try:
        r = requests.post(url, json=payload, headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e), "success": False}


def get_positions() -> list[dict[str, Any]]:
    """Fetch open positions."""
    url = f"{_base_url()}/v1/positions"
    try:
        r = requests.get(url, headers=_headers(), timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("positions", data.get("data", []))
    except Exception:
        return []


def close_position(symbol: str, quantity: int | None = None) -> dict[str, Any]:
    """Square off one position (SELL for long)."""
    positions = get_positions()
    for p in positions:
        if p.get("symbol", "").upper() == symbol.upper():
            qty = quantity or int(p.get("quantity", p.get("qty", 0)))
            return place_order(symbol, "SELL", qty)
    return {"error": "Position not found", "success": False}


def kill_switch() -> list[dict[str, Any]]:
    """Close all open positions immediately."""
    positions = get_positions()
    results = []
    for p in positions:
        sym = p.get("symbol", "")
        qty = int(p.get("quantity", p.get("qty", 0)))
        if sym and qty:
            results.append(close_position(sym, qty))
    return results
