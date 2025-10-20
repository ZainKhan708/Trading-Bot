"""Event-driven trading state machine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Mapping, Optional

from .regime import RegimeFilter


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class TradeIntent:
    """Represents an action requested by the state machine."""

    action: str  # "enter" or "exit"
    direction: Direction
    size: float
    reason: str
    stop_price: Optional[float] = None


@dataclass
class PositionState:
    direction: Optional[Direction] = None
    size: float = 0.0
    pyramids: int = 0
    entry_price: Optional[float] = None
    trailing_stop: Optional[float] = None

    def reset(self) -> None:
        self.direction = None
        self.size = 0.0
        self.pyramids = 0
        self.entry_price = None
        self.trailing_stop = None


@dataclass
class StrategySettings:
    entry_signal_key: str = "signal"
    price_key: str = "price"
    atr_key: str = "atr"
    high_key: str = "high"
    low_key: str = "low"
    close_key: str = "close"
    breadth_key: str = "breadth"
    entry_threshold: float = 1.0
    exit_threshold: float = 0.0
    base_position_size: float = 1.0
    max_pyramids: int = 0
    pyramid_scale: float = 0.5
    trailing_stop_pct: Optional[float] = None
    trailing_stop_atr_multiplier: Optional[float] = None

    def pyramid_trigger(self, level: int) -> float:
        return self.entry_threshold * (1 + level * self.pyramid_scale)


@dataclass
class TradingStateMachine:
    settings: StrategySettings
    regime_filter: Optional[RegimeFilter] = None
    state: PositionState = field(default_factory=PositionState)

    def on_features(self, features: Mapping[str, float]) -> List[TradeIntent]:
        intents: List[TradeIntent] = []
        price = self._require(features, self.settings.price_key)
        signal = self._require(features, self.settings.entry_signal_key)

        self._update_regime(features)

        if self.state.direction is None:
            intents.extend(self._evaluate_entries(signal, price, features))
        else:
            intents.extend(self._evaluate_exits(signal, price, features))
            intents.extend(self._evaluate_pyramids(signal, price, features))
        return intents

    # ------------------------------------------------------------------
    def _evaluate_entries(
        self, signal: float, price: float, features: Mapping[str, float]
    ) -> List[TradeIntent]:
        intents: List[TradeIntent] = []
        if not self._mean_reversion_allowed():
            return intents

        if signal >= self.settings.entry_threshold:
            size = self.settings.base_position_size
            self._open_position(Direction.LONG, size, price, features)
            intents.append(
                TradeIntent(
                    action="enter",
                    direction=Direction.LONG,
                    size=size,
                    reason="long entry threshold reached",
                    stop_price=self.state.trailing_stop,
                )
            )
        elif signal <= -self.settings.entry_threshold:
            size = self.settings.base_position_size
            self._open_position(Direction.SHORT, size, price, features)
            intents.append(
                TradeIntent(
                    action="enter",
                    direction=Direction.SHORT,
                    size=size,
                    reason="short entry threshold reached",
                    stop_price=self.state.trailing_stop,
                )
            )
        return intents

    def _evaluate_exits(
        self, signal: float, price: float, features: Mapping[str, float]
    ) -> List[TradeIntent]:
        intents: List[TradeIntent] = []

        # Exit if regime turns trending
        if self.regime_filter and not self.regime_filter.allow_mean_reversion():
            intents.append(self._exit_position("regime filter triggered"))
            return intents

        if self.state.direction == Direction.LONG and signal <= self.settings.exit_threshold:
            intents.append(self._exit_position("long exit threshold"))
        elif self.state.direction == Direction.SHORT and signal >= -self.settings.exit_threshold:
            intents.append(self._exit_position("short exit threshold"))
        else:
            self._refresh_trailing_stop(price, features)
            stop_hit = self._check_trailing_stop(price)
            if stop_hit:
                intents.append(self._exit_position("trailing stop"))
        return [intent for intent in intents if intent is not None]

    def _evaluate_pyramids(
        self, signal: float, price: float, features: Mapping[str, float]
    ) -> List[TradeIntent]:
        intents: List[TradeIntent] = []
        if not self._mean_reversion_allowed():
            return intents
        if self.state.direction is None:
            return intents
        if self.state.pyramids >= self.settings.max_pyramids:
            return intents

        trigger = self.settings.pyramid_trigger(self.state.pyramids + 1)
        direction = self.state.direction
        should_add = (
            direction == Direction.LONG and signal >= trigger
        ) or (direction == Direction.SHORT and signal <= -trigger)
        if not should_add:
            return intents

        addition_size = self.settings.base_position_size * (
            1 - self.settings.pyramid_scale * self.state.pyramids
        )
        addition_size = max(addition_size, 0.0)
        if addition_size == 0:
            return intents

        self.state.size += addition_size
        self.state.pyramids += 1
        self._refresh_trailing_stop(price, features)
        intents.append(
            TradeIntent(
                action="enter",
                direction=direction,
                size=addition_size,
                reason="pyramid add-on",
                stop_price=self.state.trailing_stop,
            )
        )
        return intents

    # ------------------------------------------------------------------
    def _open_position(
        self, direction: Direction, size: float, price: float, features: Mapping[str, float]
    ) -> None:
        self.state.direction = direction
        self.state.size = size
        self.state.pyramids = 0
        self.state.entry_price = price
        self._refresh_trailing_stop(price, features)

    def _exit_position(self, reason: str) -> TradeIntent:
        intent = TradeIntent(
            action="exit",
            direction=self.state.direction or Direction.LONG,
            size=self.state.size,
            reason=reason,
            stop_price=self.state.trailing_stop,
        )
        self.state.reset()
        return intent

    def _refresh_trailing_stop(
        self, price: float, features: Mapping[str, float]
    ) -> None:
        if self.state.direction is None:
            return
        distance = self._trailing_distance(price, features)
        if distance is None:
            self.state.trailing_stop = None
            return
        if self.state.direction == Direction.LONG:
            stop = price - distance
            if self.state.trailing_stop is None:
                self.state.trailing_stop = stop
            else:
                self.state.trailing_stop = max(self.state.trailing_stop, stop)
        else:
            stop = price + distance
            if self.state.trailing_stop is None:
                self.state.trailing_stop = stop
            else:
                self.state.trailing_stop = min(self.state.trailing_stop, stop)

    def _check_trailing_stop(self, price: float) -> bool:
        if self.state.direction is None or self.state.trailing_stop is None:
            return False
        if self.state.direction == Direction.LONG:
            if price <= self.state.trailing_stop:
                return True
        else:
            if price >= self.state.trailing_stop:
                return True
        return False

    def _trailing_distance(
        self, price: float, features: Mapping[str, float]
    ) -> Optional[float]:
        if self.settings.trailing_stop_pct is not None:
            return price * self.settings.trailing_stop_pct
        if self.settings.trailing_stop_atr_multiplier is not None:
            atr = features.get(self.settings.atr_key)
            if atr is None:
                return None
            return atr * self.settings.trailing_stop_atr_multiplier
        return None

    def _update_regime(self, features: Mapping[str, float]) -> None:
        if not self.regime_filter:
            return
        try:
            high = self._require(features, self.settings.high_key)
            low = self._require(features, self.settings.low_key)
            close = self._require(features, self.settings.close_key)
            breadth = self._require(features, self.settings.breadth_key)
        except KeyError:
            return
        self.regime_filter.update(high, low, close, breadth)

    def _mean_reversion_allowed(self) -> bool:
        if not self.regime_filter:
            return True
        return self.regime_filter.allow_mean_reversion()

    @staticmethod
    def _require(features: Mapping[str, float], key: str) -> float:
        if key not in features:
            raise KeyError(f"Feature '{key}' missing from feature vector")
        return float(features[key])
