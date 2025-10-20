"""Order request and state modeling utilities."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class OrderType(str, Enum):
    """Enumerated order types supported by the manager."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    """Enumerated time-in-force policies."""

    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTX = "GTX"  # Post-only


class TriggerType(str, Enum):
    """Trigger type for contingent orders."""

    NONE = "none"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    """Lifecycle states for an order."""

    NEW = "new"
    PENDING_ACK = "pending_ack"
    ACKED = "acked"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class OrderRequest:
    """Represents an order intent submitted to an exchange."""

    symbol: str
    side: str
    quantity: float
    order_type: OrderType
    price: Optional[float] = None
    client_order_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    time_in_force: TimeInForce = TimeInForce.GTC
    post_only: bool = False
    reduce_only: bool = False
    trigger_type: TriggerType = TriggerType.NONE
    trigger_price: Optional[float] = None
    parent_client_order_id: Optional[str] = None
    extra_params: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_payload(self) -> Dict[str, str | float | bool | None]:
        """Serialize the request into a payload suitable for REST APIs."""

        payload = {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "type": self.order_type.value,
            "time_in_force": self.time_in_force.value,
            "client_order_id": self.client_order_id,
            "post_only": self.post_only,
            "reduce_only": self.reduce_only,
            "trigger_type": None if self.trigger_type is TriggerType.NONE else self.trigger_type.value,
            "trigger_price": self.trigger_price,
        }
        if self.price is not None:
            payload["price"] = self.price
        payload.update(self.extra_params)
        # Remove ``None`` values to keep payload compact
        return {k: v for k, v in payload.items() if v is not None}


@dataclass(slots=True)
class OrderState:
    """Runtime state for a live order tracked by the manager."""

    request: OrderRequest
    exchange_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.NEW
    cumulative_filled: float = 0.0
    avg_fill_price: Optional[float] = None
    last_update_ts: float = field(default_factory=time.time)
    pending_cancel: bool = False
    acknowledged_at: Optional[float] = None
    first_fill_ts: Optional[float] = None

    def mark_acknowledged(self, exchange_order_id: str, timestamp: Optional[float] = None) -> None:
        self.exchange_order_id = exchange_order_id
        self.status = OrderStatus.ACKED
        self.acknowledged_at = timestamp or time.time()
        self.last_update_ts = self.acknowledged_at

    def apply_fill(self, fill_qty: float, fill_price: float, timestamp: Optional[float] = None) -> None:
        self.cumulative_filled += fill_qty
        self.avg_fill_price = fill_price if self.avg_fill_price is None else (
            (self.avg_fill_price * (self.cumulative_filled - fill_qty) + fill_price * fill_qty)
            / self.cumulative_filled
        )
        if self.cumulative_filled >= self.request.quantity:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
        now = timestamp or time.time()
        if self.first_fill_ts is None:
            self.first_fill_ts = now
        self.last_update_ts = now

    def mark_canceled(self, timestamp: Optional[float] = None) -> None:
        self.status = OrderStatus.CANCELED
        self.last_update_ts = timestamp or time.time()

    def mark_rejected(self, timestamp: Optional[float] = None) -> None:
        self.status = OrderStatus.REJECTED
        self.last_update_ts = timestamp or time.time()

    def latency_to_ack(self) -> Optional[float]:
        if self.acknowledged_at is None:
            return None
        return self.acknowledged_at - self.request.created_at

    def latency_to_fill(self) -> Optional[float]:
        if self.first_fill_ts is None:
            return None
        return self.first_fill_ts - self.request.created_at
