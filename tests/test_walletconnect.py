import pytest

from app.dex.walletconnect import WalletConnectAdapter
from app.exchange.walletconnect import WalletConnection, WalletConnectSession


def test_walletconnect_never_approves_without_connection():
    with pytest.raises(RuntimeError):
        WalletConnectSession("project").require_user_approval()


def test_walletconnect_exposes_only_qr_session_uri():
    session = WalletConnectSession("project")
    session.attach(WalletConnection("0xpublic", 56, "wc:session-uri"))
    assert session.qr_uri == "wc:session-uri"
    assert session.require_user_approval() is True
    assert session.is_approved is True


def test_dex_walletconnect_prepares_public_session_only():
    adapter = WalletConnectAdapter(project_id="demo-project", chain_id=8453, rpc_url="https://rpc.example")
    uri = adapter.prepare_session()
    assert uri.startswith("wc:placeholder-session@1?project_id=demo-project")
    with pytest.raises(NotImplementedError, match="implemented per chain and wallet"):
        adapter.sign_transaction({"to": "0xabc"})


def test_walletconnect_session_connect_and_disconnect_cycle():
    session = WalletConnectSession("project")
    connection = session.connect("0xpublic", 8453, "wc:session-uri")
    assert isinstance(connection, WalletConnection)
    assert session.qr_uri == "wc:session-uri"
    assert session.require_user_approval() is True
    session.disconnect()
    assert session.connection is None
    assert session.is_approved is False
    with pytest.raises(RuntimeError):
        session.require_user_approval()
