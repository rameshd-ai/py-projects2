"""
Robust order state machine for broker order lifecycle management.

This module provides:
- OrderState enum
- Pydantic dataclasses for order payloads
- BrokerInterface protocol
- OrderManager with safe state transitions and reconciliation
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import field
from decimal import Decimal, InvalidOperation
from enum import Enum
from threading import RLock
from typing import Any, Protocol

from pydantic.dataclasses import dataclass

logger = logging.getLogger(__name__)


class OrderState(str, Enum):
    """Supported order lifecycle states."""

    NEW = "NEW"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES: set[OrderState] = {
    OrderState.FILLED,
    OrderState.REJECTED,
    OrderState.CANCELLED,
}


ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.NEW: {OrderState.SENT, OrderState.REJECTED, OrderState.CANCELLED},
    OrderState.SENT: {
        OrderState.ACKNOWLEDGED,
        OrderState.PARTIAL_FILLED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.CANCELLED,
    },
    OrderState.ACKNOWLEDGED: {
        OrderState.PARTIAL_FILLED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.CANCELLED,
    },
    OrderState.PARTIAL_FILLED: {
        OrderState.PARTIAL_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
    },
    OrderState.FILLED: set(),
    OrderState.REJECTED: set(),
    OrderState.CANCELLED: set(),
}


@dataclass
class OrderRequest:
    """Client-side order request."""

    symbol: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    price: float | None = None
    exchange: str = "NSE"
    client_order_id: str = field(default_factory=lambda: f"cli_{uuid.uuid4().hex}")
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FillEvent:
    """Represents one fill event from broker/orderbook."""

    quantity: int
    price: float
    ts_epoch_ms: int


@dataclass
class OrderSnapshot:
    """Broker status snapshot for reconciliation."""

    broker_order_id: str
    status: str
    filled_quantity: int = 0
    avg_fill_price: float | None = None
    reject_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    fills: list[FillEvent] = field(default_factory=list)


@dataclass
class ManagedOrder:
    """Internal managed order model tracked by OrderManager."""

    request: OrderRequest
    state: OrderState = OrderState.NEW
    broker_order_id: str | None = None
    sent_at: float | None = None
    updated_at: float = field(default_factory=lambda: time.time())
    filled_quantity: int = 0
    remaining_quantity: int = 0
    avg_fill_price: float | None = None
    reject_reason: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.remaining_quantity = max(0, int(self.request.quantity) - int(self.filled_quantity))


class BrokerInterface(Protocol):
    """Minimal broker adapter protocol required by OrderManager."""

    def place_order(self, request: OrderRequest) -> dict[str, Any]:
        """Send order to broker.

        Expected return (minimum):
            {"success": bool, "order_id": str | None, "error": str | None}
        """

    def get_order_status(self, broker_order_id: str) -> dict[str, Any]:
        """Fetch order status from broker.

        Recommended keys:
            status, filled_quantity, avg_fill_price, reject_reason, fills
        """

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        """Cancel order at broker.

        Expected return:
            {"success": bool, "cancelled": bool, "error": str | None}
        """


class OrderManager:
    """Stateful order lifecycle manager with safe transitions."""

    def __init__(self, broker: BrokerInterface) -> None:
        self._broker = broker
        self._orders: dict[str, ManagedOrder] = {}
        self._lock = RLock()

    def send_order(self, request: OrderRequest) -> ManagedOrder:
        """Accept an order request and send to broker.

        Returns the managed order object (always tracked in manager).
        """
        with self._lock:
            if request.client_order_id in self._orders:
                raise ValueError(f"Duplicate client_order_id: {request.client_order_id}")

            order = ManagedOrder(request=request)
            self._orders[request.client_order_id] = order
            self._transition(order, OrderState.SENT, reason="Order submitted to broker")
            order.sent_at = time.time()

        try:
            result = self._broker.place_order(request)
            success = bool(result.get("success"))
            broker_order_id = result.get("order_id")

            with self._lock:
                if success and broker_order_id:
                    order.broker_order_id = str(broker_order_id)
                    self._transition(order, OrderState.ACKNOWLEDGED, reason="Broker acknowledged order")
                else:
                    err = str(result.get("error") or "Broker rejected order")
                    order.reject_reason = err
                    self._transition(order, OrderState.REJECTED, reason=err)
                    logger.error("Order rejected client_order_id=%s error=%s", request.client_order_id, err)
        except Exception as exc:
            with self._lock:
                order.reject_reason = str(exc)
                self._transition(order, OrderState.REJECTED, reason=f"Exception while placing order: {exc}")
            logger.exception("send_order failed client_order_id=%s", request.client_order_id)

        return order

    def poll_status(self, client_order_id: str) -> ManagedOrder:
        """Poll broker order status and apply safe state transitions."""
        with self._lock:
            order = self._get_order_or_raise(client_order_id)
            if order.state in TERMINAL_STATES:
                return order
            if not order.broker_order_id:
                self._transition(order, OrderState.REJECTED, reason="Missing broker_order_id")
                return order
            broker_order_id = order.broker_order_id

        try:
            status_payload = self._broker.get_order_status(broker_order_id)
            snapshot = self._to_snapshot(broker_order_id, status_payload)
        except Exception as exc:
            logger.exception("poll_status failed client_order_id=%s", client_order_id)
            return order

        with self._lock:
            order = self._get_order_or_raise(client_order_id)
            if order.state in TERMINAL_STATES:
                return order

            mapped = self._map_broker_status(snapshot.status)
            if mapped is None:
                logger.warning(
                    "Unknown broker status client_order_id=%s broker_status=%s",
                    client_order_id,
                    snapshot.status,
                )
                return order

            if mapped == OrderState.REJECTED:
                order.reject_reason = snapshot.reject_reason or order.reject_reason
                self._transition(order, OrderState.REJECTED, reason=order.reject_reason or "Rejected by broker")
                return order

            if mapped in (OrderState.PARTIAL_FILLED, OrderState.FILLED):
                self.reconcile_fill(client_order_id, snapshot)
                return self._get_order_or_raise(client_order_id)

            self._transition(order, mapped, reason=f"Broker status={snapshot.status}")
            return order

    def reconcile_fill(self, client_order_id: str, snapshot: OrderSnapshot) -> ManagedOrder:
        """Reconcile fill quantities/price and derive partial/filled state."""
        with self._lock:
            order = self._get_order_or_raise(client_order_id)
            if order.state in TERMINAL_STATES:
                return order

            total_filled = max(0, int(snapshot.filled_quantity))
            requested_qty = max(0, int(order.request.quantity))
            total_filled = min(total_filled, requested_qty)

            prev_filled = order.filled_quantity
            order.filled_quantity = total_filled
            order.remaining_quantity = max(0, requested_qty - total_filled)

            avg_price = self._compute_avg_fill(snapshot, fallback=snapshot.avg_fill_price)
            if avg_price is not None:
                order.avg_fill_price = avg_price

            if order.filled_quantity >= requested_qty:
                self._transition(order, OrderState.FILLED, reason="Order fully filled")
            elif order.filled_quantity > 0:
                self._transition(
                    order,
                    OrderState.PARTIAL_FILLED,
                    reason=f"Partial fill {order.filled_quantity}/{requested_qty} (+{order.filled_quantity - prev_filled})",
                )
            else:
                # Broker may still be acknowledged/open without fills.
                if order.state == OrderState.SENT:
                    self._transition(order, OrderState.ACKNOWLEDGED, reason="No fills yet")

            return order

    def cancel_order(self, client_order_id: str) -> ManagedOrder:
        """Cancel an order if it is not terminal."""
        with self._lock:
            order = self._get_order_or_raise(client_order_id)
            if order.state in TERMINAL_STATES:
                return order
            if not order.broker_order_id:
                self._transition(order, OrderState.CANCELLED, reason="Local cancel before broker ack")
                return order
            broker_order_id = order.broker_order_id

        try:
            result = self._broker.cancel_order(broker_order_id)
            cancelled = bool(result.get("success")) and bool(result.get("cancelled", True))
            err = result.get("error")
        except Exception as exc:
            cancelled = False
            err = str(exc)
            logger.exception("cancel_order failed client_order_id=%s", client_order_id)

        with self._lock:
            order = self._get_order_or_raise(client_order_id)
            if order.state in TERMINAL_STATES:
                return order
            if cancelled:
                self._transition(order, OrderState.CANCELLED, reason="Cancelled at broker")
            else:
                logger.error("Cancel rejected client_order_id=%s error=%s", client_order_id, err)
            return order

    async def poll_until_terminal(
        self,
        client_order_id: str,
        interval_seconds: float = 0.5,
        timeout_seconds: float = 30.0,
    ) -> ManagedOrder:
        """Async helper to poll an order until terminal or timeout."""
        deadline = time.time() + max(0.0, timeout_seconds)
        while time.time() < deadline:
            order = self.poll_status(client_order_id)
            if order.state in TERMINAL_STATES:
                return order
            await asyncio.sleep(max(0.05, interval_seconds))
        logger.warning("poll_until_terminal timeout client_order_id=%s", client_order_id)
        return self.get_order(client_order_id)

    def get_order(self, client_order_id: str) -> ManagedOrder:
        """Return current managed order snapshot."""
        with self._lock:
            return self._get_order_or_raise(client_order_id)

    def _get_order_or_raise(self, client_order_id: str) -> ManagedOrder:
        order = self._orders.get(client_order_id)
        if not order:
            raise KeyError(f"Unknown client_order_id: {client_order_id}")
        return order

    def _transition(self, order: ManagedOrder, new_state: OrderState, reason: str = "") -> None:
        old_state = order.state
        if old_state == new_state:
            order.updated_at = time.time()
            order.history.append(
                {"from": old_state.value, "to": new_state.value, "ts": order.updated_at, "reason": reason}
            )
            return

        allowed = ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            logger.error(
                "Invalid transition client_order_id=%s %s->%s reason=%s",
                order.request.client_order_id,
                old_state.value,
                new_state.value,
                reason,
            )
            raise ValueError(f"Invalid transition: {old_state.value} -> {new_state.value}")

        order.state = new_state
        order.updated_at = time.time()
        order.history.append(
            {"from": old_state.value, "to": new_state.value, "ts": order.updated_at, "reason": reason}
        )
        logger.info(
            "Order transition client_order_id=%s broker_order_id=%s %s->%s reason=%s",
            order.request.client_order_id,
            order.broker_order_id,
            old_state.value,
            new_state.value,
            reason,
        )

    @staticmethod
    def _map_broker_status(status: str | None) -> OrderState | None:
        if not status:
            return None
        s = status.strip().upper().replace("-", "_").replace(" ", "_")
        mapping = {
            "NEW": OrderState.NEW,
            "OPEN": OrderState.ACKNOWLEDGED,
            "TRIGGER_PENDING": OrderState.ACKNOWLEDGED,
            "SENT": OrderState.SENT,
            "ACKNOWLEDGED": OrderState.ACKNOWLEDGED,
            "PARTIAL": OrderState.PARTIAL_FILLED,
            "PARTIALLY_FILLED": OrderState.PARTIAL_FILLED,
            "PARTIAL_FILLED": OrderState.PARTIAL_FILLED,
            "COMPLETE": OrderState.FILLED,
            "FILLED": OrderState.FILLED,
            "REJECTED": OrderState.REJECTED,
            "CANCELLED": OrderState.CANCELLED,
            "CANCELED": OrderState.CANCELLED,
        }
        return mapping.get(s)

    @staticmethod
    def _to_snapshot(broker_order_id: str, payload: dict[str, Any]) -> OrderSnapshot:
        fills_payload = payload.get("fills") or []
        fills: list[FillEvent] = []
        for f in fills_payload:
            try:
                fills.append(
                    FillEvent(
                        quantity=int(f.get("quantity", 0)),
                        price=float(f.get("price", 0.0)),
                        ts_epoch_ms=int(f.get("ts_epoch_ms", int(time.time() * 1000))),
                    )
                )
            except Exception:
                continue

        return OrderSnapshot(
            broker_order_id=broker_order_id,
            status=str(payload.get("status") or ""),
            filled_quantity=int(payload.get("filled_quantity") or 0),
            avg_fill_price=float(payload["avg_fill_price"]) if payload.get("avg_fill_price") is not None else None,
            reject_reason=(str(payload.get("reject_reason")) if payload.get("reject_reason") else None),
            raw=payload,
            fills=fills,
        )

    @staticmethod
    def _compute_avg_fill(snapshot: OrderSnapshot, fallback: float | None = None) -> float | None:
        if snapshot.fills:
            total_qty = 0
            weighted = Decimal("0")
            for fill in snapshot.fills:
                qty = max(0, int(fill.quantity))
                if qty <= 0:
                    continue
                try:
                    px = Decimal(str(fill.price))
                except (InvalidOperation, ValueError):
                    continue
                total_qty += qty
                weighted += px * qty
            if total_qty > 0:
                return float((weighted / Decimal(total_qty)).quantize(Decimal("0.0001")))
        return fallback
