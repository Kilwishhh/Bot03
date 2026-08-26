from dataclasses import dataclass
from typing import Optional


@dataclass
class WalletConnectAdapter:
    project_id: str
    chain_id: Optional[int] = None
    rpc_url: Optional[str] = None

    def prepare_session(self) -> str:
        """Return a WalletConnect session URI that can be rendered as a QR code.
        This method does not store any private keys and only returns a public session string.
        """
        if not self.project_id:
            raise ValueError("WalletConnect project ID is required")
        return f"wc:placeholder-session@1?project_id={self.project_id}"

    def sign_transaction(self, unsigned_tx: dict) -> str:
        """Placeholder: in production this should send the unsigned_tx to the connected wallet
        and return the signed transaction hex/serialized payload after user approval.
        """
        raise NotImplementedError("WalletConnect signing must be implemented per chain and wallet")
