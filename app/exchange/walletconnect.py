"""WalletConnect boundary for future user-approved DEX transactions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WalletConnection:
    address: str
    chain_id: int
    session_uri: str


class WalletConnectSession:
    """Stores only public session information, never private wallet material."""

    def __init__(self, project_id: str) -> None:
        if not project_id:
            raise ValueError("WalletConnect project ID is required")
        self.project_id = project_id
        self.connection: WalletConnection | None = None
        self.is_approved = False

    def attach(self, connection: WalletConnection) -> None:
        if not connection.address or not connection.session_uri:
            raise ValueError("wallet address and session URI are required")
        self.connection = connection
        self.is_approved = False

    def connect(self, address: str, chain_id: int, session_uri: str) -> WalletConnection:
        if not address or not session_uri:
            raise ValueError("wallet address and session URI are required")
        connection = WalletConnection(address=address, chain_id=chain_id, session_uri=session_uri)
        self.attach(connection)
        return connection

    def disconnect(self) -> None:
        self.connection = None
        self.is_approved = False

    @property
    def qr_uri(self) -> str | None:
        """Return the session URI that a UI may render as a QR code."""
        return self.connection.session_uri if self.connection else None

    def require_user_approval(self) -> bool:
        if self.connection is None:
            raise RuntimeError("connect a wallet before requesting user approval")
        self.is_approved = True
        return True