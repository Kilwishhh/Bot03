
The WalletConnect session boundary exposes only a public wallet address and QR session URI. A future dashboard can render that URI as a QR code; it must never request, transmit, or persist wallet recovery phrases or private keys.
# Modular Binance Crypto Trading Bot

A safety-first Python framework for paper and Binance Futures Testnet trading. Performance not yet validated.

## Phase 1

The initial foundation includes typed exchange-neutral models, an `ExchangeAdapter` contract, environment configuration, structured logging, and a CLI. Strategy, risk, execution, persistence, and dashboard layers will be added in later phases without changing the exchange contract.

```text
Market Data -> Strategy -> Signal -> Risk -> Execution -> Exchange Adapter
                                      |
                              Database / Monitoring
```

## Setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
python -m app.main status
pytest
```

The default mode is `paper`. Testnet credentials belong only in `.env`; never commit that file. Live mode requires all of `TRADING_MODE=live`, `ENABLE_LIVE_TRADING=true`, `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK`, and credentials. Phase 1 does not place orders yet.

Set `TRADING_MODE=testnet` to select the Binance Futures Testnet adapter, or `TRADING_MODE=live` to select the live Binance adapter after all live safety gates pass. DEX mode is separate: the application stores no seed phrase or private key, and a WalletConnect session must be connected with each transaction explicitly approved by the wallet owner. A chain-specific DEX router adapter is still required before DEX execution is enabled.

Testnet mode requires Binance credentials to be set in the environment variables.

Signals can be formatted and sent through the optional Telegram notifier. Binance Square publication is intentionally isolated and disabled until an official supported publishing API is configured; a social-posting failure must never stop or trigger a trade.

Risk defaults also include `MAX_EXPOSURE=1000` and `MAX_CONSECUTIVE_LOSSES=3`; both can be changed in `.env` before a trading mode is selected.

The registered `indicator` strategy can be configured with `EMA_FAST`, `EMA_SLOW`, `RSI_PERIOD`, `BB_PERIOD`, and `ADX_PERIOD`. New strategies should implement the `Strategy` interface and be registered explicitly; arbitrary class paths from environment variables are rejected.

Operational events and errors are stored in SQLite and shown in the dashboard for troubleshooting.

### Hyperliquid

Set `TRADING_MODE=dex`, `EXCHANGE_PROVIDER=hyperliquid`, and provide `WALLETCONNECT_PROJECT_ID` to select the Hyperliquid provider. Its public market-data adapter is available without a private key. Signed orders are intentionally disabled until wallet connection, transaction preview, and explicit wallet approval are implemented. Never place a seed phrase or private key in `.env`.

## CLI

```powershell
python -m app.main status
python -m app.main health
python scripts/check_app.py
python -m app.main start --mode paper
python -m app.main start --mode paper --cycles 5 --interval 10
python -m uvicorn app.api.server:app --reload
py scripts/run_paper_demo.py
py -m app.main paper-demo
py scripts/run_backtest.py
py scripts/scan_binance_futures.py
```

Mobile backend read-only endpoints: `GET /health`, `GET /status`, `GET /metrics`, `GET /orders?limit=20`, `GET /signals?limit=20`, `GET /trades?limit=20`, `GET /balances`, and `GET /positions`.

Remote control endpoints (POST /control/start and POST /control/stop) are available but disabled by default. To enable remote start/stop set `ENABLE_REMOTE_CONTROL=true` in your `.env`. Even when enabled the server enforces safety checks and will refuse to start Testnet/Live modes without the required credentials and confirmations.

Trading control endpoints will require authentication and explicit confirmations before being exposed to untrusted networks.

Phone-friendly dashboard: start the API and open `http://127.0.0.1:8000/mobile`.
The page includes a PWA manifest and can be added to a phone home screen when served over a suitable network/HTTPS setup.
It also includes a basic service worker for the dashboard shell; live data still requires network access.

Mobile/web clients may use the configured read-only CORS origins from `API_ALLOWED_ORIGINS`; only `GET` requests are allowed by default.

The paper demo uses synthetic candles and creates `paper_demo.sqlite3`; it never contacts Binance. Delete that local database when you want a fresh demo run.

The backtest demo also uses synthetic candles and is for verifying the pipeline only. It is not evidence of profitability.

Historical data can be split chronologically with `split_candles` into train, validation, and out-of-sample test periods. Do not optimize parameters on the test period.

`scan_binance_futures.py` uses Binance Futures public market-data endpoints to discover all active USDT perpetual symbols and scan them. It does not place orders and does not require Binance API credentials. Large scans can take time and may be affected by public API rate limits.

## Current Safety Boundary

Paper mode is runnable locally. Testnet and live Binance modes require credentials in `.env`; live additionally requires the explicit confirmation settings. Hyperliquid public market data is supported, but signed wallet orders remain disabled until transaction preview and official wallet approval integration are complete. Lighter, BNB Chain DEX routing, and Binance Square posting require their respective official APIs and provider-specific implementation. Performance not yet validated.

The optional dashboard can later be installed and started with:

```powershell
py -m pip install -e ".[dashboard]"
py -m streamlit run app/dashboard/streamlit_app.py
```

Docker defaults to a paper-mode status check. The optional dashboard profile is started with `docker compose --profile dashboard up --build`.

## Roadmap

Phase 2 adds order and position lifecycle management, followed by risk controls, strategies, database persistence, backtesting, monitoring, and deployment. New strategies will implement an exchange-independent strategy interface.
