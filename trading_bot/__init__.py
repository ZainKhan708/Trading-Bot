"""Core package for the Trading-Bot event pipeline."""

from .events import L2Update, QuoteSnapshot, TradeEvent
from .feeds.kucoin import KuCoinFeedHandler
from .pubsub import EventBus

__all__ = [
    "EventBus",
    "KuCoinFeedHandler",
    "L2Update",
    "QuoteSnapshot",
    "TradeEvent",
]
