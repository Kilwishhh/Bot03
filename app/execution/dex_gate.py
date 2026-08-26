"""Wallet-approval gate for DEX adapters that require explicit transaction
preview and wallet owner approval before signing.

The gate is a small wrapper around any adapter that exposes:
  - preview_order(request) -> OrderPreview
  - approve_order(preview) -> None
  - place_order(request)    -> OrderResult

Adapters without these methods pass through unchanged.
"""

from __future__ import annotations

from app.exchange.base import ExchangeAdapter
from app.exchange.models import OrderRequest, OrderResult


class DexOrderGate:
    """Enforce preview + explicit approval before any DEX signed order."""

    def __init__(self, exchange: ExchangeAdapter) -> None:
        self._exchange = exchange

    def supports_preview(self) -> bool:
        return hasattr(self._exchange, "preview_order") and hasattr(self._exchange, "approve_order")

    def submit(self, request: OrderRequest) -> OrderResult:
        """Submit an order through the wallet-approval gate.

        If the adapter does not support preview, fall through to a direct
        place_order call (used by paper/Binance adapters).
        """
        if not self.supports_preview():
            return self._exchange.place_order(request)

        preview = self._exchange.preview_order(request)
        if not preview.requires_approval:
            return self._exchange.place_order(request)
        if preview.status != "pending_approval":
            raise RuntimeError(f"unexpected preview status: {preview.status}")
        # Approval must come from the wallet owner; only the owner (or an
        # admin tool) can flip a preview into a real order. The OrderManager
        # does NOT auto-approve — it queues the preview and waits.
        raise RuntimeError(
            "DEX order requires explicit wallet approval; "
            "approve the preview via the admin/dex endpoint before placing"
        )

    def approve_and_place(self, request: OrderRequest) -> OrderResult:
        """Preview, mark approved by the wallet owner, then place.

        Only call this from an authenticated, audited admin path — never from
        the trading loop. The caller is responsible for having received real
        wallet-owner consent (WalletConnect session approval).
        """
        if not self.supports_preview():
            raise RuntimeError("adapter does not support preview/approval flow")
        preview = self._exchange.preview_order(request)
        self._exchange.approve_order(preview)
        return self._exchange.place_order(request)
