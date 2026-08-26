"""DEX provider skeletons and adapters.

This module contains lightweight skeletons for DEX adapters (WalletConnect skeleton).
Implementations must be added per-chain and per-DEX; these are intentionally non-functional placeholders
until a production WalletConnect signing flow is provided.
"""
from .walletconnect import WalletConnectAdapter
