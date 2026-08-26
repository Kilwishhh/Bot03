import pytest
from decimal import Decimal
from app.exchange.hyperliquid import HyperliquidAdapter
from app.exchange.models import OrderRequest, OrderSide, OrderType


def test_hyperliquid_orders_require_wallet_approval():
    with pytest.raises(NotImplementedError, match="wallet approval"):
        HyperliquidAdapter().place_order(None)


def test_hyperliquid_preview_requires_wallet_and_explicit_approval():
    adapter = HyperliquidAdapter(wallet_address="0xabc")
    request = OrderRequest(
        symbol="BTCUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        price=Decimal("50000"),
        client_order_id="client-1",
    )
    preview = adapter.preview_order(request)
    assert preview.symbol == "BTCUSD"
    assert preview.requires_approval is True
    assert preview.status == "pending_approval"

    with pytest.raises(RuntimeError, match="explicit wallet approval"):
        adapter.place_order(request)

    adapter.approve_order(preview)
    result = adapter.place_order(request)
    assert result.symbol == "BTCUSD"
    assert result.status == "approved"
    assert result.executed_quantity == Decimal("0.01")