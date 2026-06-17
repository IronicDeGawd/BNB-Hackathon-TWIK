# BNB AI Agent SDK (bnbagent-sdk) — Developer Reference

**Status**: Verified against repo main branch (June 2026).
**Source**: https://github.com/bnb-chain/bnbagent-sdk

---

## Overview

The BNBAgent SDK is a **Python library for building on-chain AI agents on BNB Smart Chain**. It implements two BNB Chain improvement proposals:

- **ERC-8004** — On-chain agent identity (NFT-based registration + discovery)
- **ERC-8183** — Trustless job-based commerce (create → fund → execute → settle → pay)

**Critical finding for this hackathon**: The SDK does NOT provide swap/DEX execution, market data, or trading helpers. It is an agent identity + job escrow framework. Swap execution belongs to **TWAK** (Trust Wallet Agent Kit); market data belongs to **CMC Agent Hub**. The three tools form a stack: CMC (data) → agent logic → TWAK (execution) → BNB SDK (on-chain identity/settlement).

---

## Language & Install

**Language**: Python 3.10, 3.11, 3.12 only. No TypeScript/JS SDK exists in this repo.

```bash
# Base install
pip install bnbagent

# With server (FastAPI/uvicorn for hosting an agent as a service)
pip install "bnbagent[server]"

# With IPFS storage support
pip install "bnbagent[server,ipfs]"

# Recommended: use uv
uv add bnbagent
uv add "bnbagent[server,ipfs]"
```

**Core dependencies** (auto-installed):
- `web3 >=6.15.0` — BSC RPC connectivity
- `eth-account >=0.10.0` — Transaction signing
- `python-dotenv >=1.0.0` — Env var management
- `requests >=2.31.0` — HTTP

**Optional dependencies**:
- `server` extra: `fastapi >=0.104.0`, `uvicorn >=0.24.0`
- `ipfs` extra: `httpx >=0.25.0`

---

## Quickstart

### Agent Identity Registration (ERC-8004)

```python
from bnbagent import ERC8004Agent, EVMWalletProvider

wallet = EVMWalletProvider(password="pwd", private_key="0xYOUR_KEY")
sdk = ERC8004Agent(network="bsc-mainnet", wallet_provider=wallet)

# Generate the on-chain URI
agent_uri = sdk.generate_agent_uri(
    name="my-trading-agent",
    description="AI trading agent for BNB Hack",
    endpoint="https://my-agent.example.com/erc8183"
)

# Register (check for existing first)
existing = sdk.get_local_agent_info("my-trading-agent")
if not existing:
    result = sdk.register_agent(agent_uri=agent_uri)
    print(f"Agent ID: {result['agentId']}")
    print(f"Tx: {result['transactionHash']}")
```

### Agent Server (ERC-8183 Job Processor)

```python
from bnbagent.erc8183.server import create_erc8183_app

def execute_job(job: dict) -> str:
    # Your trading logic here — receives a job description
    # Returns a string deliverable (markdown, JSON, etc.)
    return f"Executed strategy for: {job['description']}"

app = create_erc8183_app(on_job=execute_job)
# Run: uvicorn agent:app --host 0.0.0.0 --port 8003
```

---

## What the SDK Actually Provides

### Module 1: ERC-8004 (Agent Identity)

| Feature | Detail |
|---------|--------|
| On-chain registration | NFT-based agent identity on BSC |
| Gas sponsorship | Free on BSC Testnet via MegaFuel paymaster |
| Discovery | `get_all_agents()` — paginated indexer query |
| URI generation | `generate_agent_uri()` — EIP-8004 compliant base64 data URI |
| SSRF protection | Blocks private IPs, cloud metadata, DNS rebinding |
| Update support | `register_agent()` with `--force` to update existing URI |

### Module 2: ERC-8183 (Agentic Commerce / Job Escrow)

| Feature | Detail |
|---------|--------|
| Job lifecycle | OPEN → FUNDED → SUBMITTED → COMPLETED (or REJECTED/EXPIRED) |
| Background polling | Auto-polls for funded jobs via background task |
| Optimistic settlement | Silence past dispute window = approval |
| Permissionless settlement | Any caller can settle after dispute window |
| Dispute/rejection | Whitelisted voters can reject by quorum |
| Non-pausable refund | `claimRefund()` available past expiry — cannot be blocked |
| Server endpoints | `POST /erc8183/negotiate`, `GET /erc8183/job/{id}`, `GET /erc8183/status` |

### Core Infrastructure

| Component | Detail |
|-----------|--------|
| `EVMWalletProvider` | Keystore V3 encryption, MetaMask-compatible, persisted to `~/.bnbagent/wallets/` |
| `MPCWalletProvider` | HSM/MPC extension point via subclassing |
| `LocalStorageProvider` | Stores job deliverables in `.agent-data/` |
| `IPFSStorageProvider` | Pins to Pinata, returns `ipfs://CID` |
| `ModuleRegistry` | Plugin system — discovers modules via built-ins + entry points |
| Nonce manager | Per-account singletons, exponential backoff on 429, re-sync on conflicts |
| EIP-712 signing policy | Strict default: blocks ERC-2612 Permit, allows EIP-3009 TransferWithAuthorization |

---

## Network Configuration

### Built-in Network Presets

| Setting | BSC Mainnet (`bsc-mainnet`) | BSC Testnet (`bsc-testnet`) |
|---------|----------------------------|----------------------------|
| Chain ID | **56** | 97 |
| RPC URL | `https://bsc-dataseed.binance.org` | `https://data-seed-prebsc-2-s2.binance.org:8545` |
| Paymaster | `https://bsc-megafuel.nodereal.io/` | `https://bsc-megafuel-testnet.nodereal.io` |
| Identity Registry | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` | `0x8004A818BFB912233c491871b3d84c89A494BD9e` |
| Commerce Proxy | `0xea4daa3100a767e86fded867729ae7446476eba6` | `0xa206c0517b6371c6638cd9e4a42cc9f02a33b0de` |
| Router Proxy | `0x51895229e12f9876011789b04f8698af06ccd6da` | `0xd7d36d66d2f1b608a0f943f722d27e3744f66f25` |
| Policy | `0x9c01845705b3078aa2e8cff7520a6376fd766de5` | `0x4f4678d4439fec812ac7674bb3efb4c8f5fb78a6` |
| Payment Token | `0xcE24439F2D9C6a2289F741120FE202248B666666` | `0xc70B8741B8B07A6d61E54fd4B20f22Fa648E5565` |

To override RPC: set `RPC_URL` env var. To use mainnet: set `NETWORK=bsc-mainnet`.

---

## Environment Variables

```bash
# Required
WALLET_PASSWORD=<keystore encryption password>
PRIVATE_KEY=0x<raw private key>  # Only on first run; SDK encrypts and removes after

# Network
NETWORK=bsc-mainnet              # or bsc-testnet
RPC_URL=https://...              # Optional override

# ERC-8183 agent server
ERC8183_AGENT_URL=https://my-agent.example.com/erc8183
ERC8183_SERVICE_PRICE=1000000000000000000  # Minimum budget (raw wei units)
ERC8183_FUNDED_POLL_INTERVAL=30            # Seconds between job polls
ERC8183_NEGOTIATE_RATE_LIMIT=120
ERC8183_NEGOTIATE_RATE_WINDOW=60
ERC8183_MAX_RESPONSE_BYTES=5242880         # 5 MB
ERC8183_MAX_METADATA_BYTES=262144          # 256 KB

# Storage
STORAGE_PROVIDER=local           # or ipfs
STORAGE_LOCAL_PATH=.agent-data/
STORAGE_API_KEY=<Pinata JWT>     # Required for IPFS
STORAGE_GATEWAY_URL=https://...  # Optional custom IPFS gateway

# Optional
ERC8004_REGISTRY_ADDRESS=<override>
ERC8183_COMMERCE_ADDRESS=<override>
ERC8183_ROUTER_ADDRESS=<override>
ERC8183_POLICY_ADDRESS=<override>
DEBUG=true
```

---

## Relationship to TWAK and CMC

### The Three-Layer Stack

```
Layer 1: CMC Agent Hub (Market Data)
  └─ 12 MCP tools: quotes, technicals, on-chain, derivatives, sentiment, news
  └─ Pre-computed signals: MACD, RSI, EMA, Fear & Greed, market regime
  └─ Keyless x402 pay-per-request access
  └─ MCP endpoint — works with Claude Code, Cursor, VS Code, Codex

Layer 2: Agent Logic (your code)
  └─ Reads CMC data → decides strategy → submits to TWAK

Layer 3: TWAK — Trust Wallet Agent Kit (Execution)
  └─ CLI: `twak swap 100 USDC ETH`
  └─ Cross-chain swaps across 25+ blockchains (including BSC)
  └─ DCA, limit orders, price alerts
  └─ MCP protocol: plug into Claude, Cursor, Windsurf
  └─ Self-custody signing (WalletConnect or agent wallet)
  └─ Install: curl -fsSL https://agent-kit.trustwallet.com/install.sh | bash
```

### BNBAgent SDK's Role

The BNBAgent SDK sits **beside** this stack as an on-chain identity and job-commerce layer, not on top of it. Think of it as:
- **TWAK** = the hands that execute trades
- **CMC** = the eyes that read markets
- **BNBAgent SDK** = the on-chain identity card + payment escrow for agent-to-agent work

The SDK does NOT wrap TWAK or CMC. There are no TWAK imports, CMC API calls, or DEX/PancakeSwap helpers anywhere in the SDK source.

For this hackathon, BNBAgent SDK is useful if you want your agent to:
1. Have an on-chain identity (ERC-8004 registration)
2. Accept and deliver paid jobs from other agents/users (ERC-8183 escrow)

If you only need swap execution + market data, TWAK + CMC Agent Hub is sufficient without the BNBAgent SDK.

---

## Competition Registration

### What the BNBAgent SDK Does NOT Handle

The competition contract at `0x212c61b9b72c95d95bf29cf032f5e5635629aed5` is **not referenced anywhere in the SDK source**. The SDK has no built-in `compete`, `register_competition`, or hackathon-specific functionality.

### How Competition Registration Actually Works

Registration is via **TWAK CLI** or **TWAK MCP action**:

```bash
# CLI method (TWAK must be installed)
twak compete register

# MCP method (when TWAK is connected as an MCP server)
# MCP action: competition_register
```

This sends a transaction to `0x212c61b9b72c95d95bf29cf032f5e5635629aed5` on BSC mainnet (chain ID 56).

**Note**: The exact ABI and parameters for `competition_register` are not publicly documented in the sources reviewed. Check:
- TWAK developer docs: https://developer.trustwallet.com/developer/agent-sdk
- Trust Wallet Builders portal: https://portal.trustwallet.com/
- DoraHacks hackathon page: https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail

**[UNVERIFIED]** The MCP action name `competition_register` is referenced in the hackathon brief but not confirmed in TWAK public docs at time of writing.

---

## Swap / Trade Execution

The BNBAgent SDK has **no swap, DEX, or trade execution code**. This is handled entirely by TWAK.

### TWAK Swap API

```bash
# CLI usage
twak swap 100 USDC ETH            # Execute swap
twak swap 100 USDC ETH --quote-only  # Preview only
twak price ETH                    # Get price
twak wallet portfolio             # Portfolio view
twak alert create --token BTC --above 75000  # Price alert
```

The CMC hackathon page confirms: "BNB AI Agent SDK provides agent-native primitives for BSC mainnet execution, PancakeSwap routing, and derivatives trading" — but this refers to the broader BNB ecosystem / future SDK scope, not to swap functions present in the current `bnbagent` Python package. **[UNVERIFIED — not found in current repo]**

For actual PancakeSwap swaps today, use TWAK or call PancakeSwap contracts directly via web3.py.

---

## Agent Loop / Strategy Interface

The SDK does not define an agent loop or strategy interface. The "loop" is the ERC-8183 job polling loop — a background task that polls for funded jobs and calls your `on_job` handler.

```python
# The only "agent loop" the SDK provides:
app = create_erc8183_app(on_job=your_handler)
# Internally: polls ERC8183_FUNDED_POLL_INTERVAL seconds for FUNDED jobs
# Calls your_handler(job_dict) → returns str deliverable
# Submits deliverable to chain → enters SUBMITTED state
```

For an autonomous trading loop that runs strategy logic independently, you build that yourself. The SDK's polling loop is job-driven (reactive), not proactive.

---

## Market Data

The BNBAgent SDK does **not** access market data. No CMC API integration, no price feeds, no OHLCV.

Market data comes from **CMC Agent Hub**:
- MCP endpoint with 12 tools: quotes, technicals, on-chain, derivatives, sentiment, news
- Signals: MACD, RSI, EMA, Fear & Greed Index, market regime, ETF demand, cross-asset pressure
- x402 keyless pay-per-request model
- LLM-friendly Markdown/YAML output format

Connect via MCP in Claude Code:
```json
{
  "mcpServers": {
    "cmc-agent-hub": {
      "url": "https://mcp.coinmarketcap.com/sse"
    }
  }
}
```
(Exact MCP URL — verify at https://coinmarketcap.com/api/agent)

---

## Code Examples (from repo)

### Example: Register an agent and check for duplicates

From `examples/agent-server/scripts/register.py`:
```python
from bnbagent import ERC8004Agent, EVMWalletProvider

wallet = EVMWalletProvider(password=WALLET_PASSWORD, private_key=PRIVATE_KEY)
sdk = ERC8004Agent(network="bsc-mainnet", wallet_provider=wallet)

agent_uri = sdk.generate_agent_uri(
    name=AGENT_NAME,
    description=AGENT_DESCRIPTION,
    endpoint=f"http://{AGENT_HOST}/erc8183"
)

existing = sdk.get_local_agent_info(AGENT_NAME)
if existing:
    # Update if --force flag provided
    result = sdk.register_agent(agent_uri=agent_uri, agent_id=existing["agentId"])
else:
    result = sdk.register_agent(agent_uri=agent_uri)

print(f"Agent ID: {result['agentId']}")
print(f"Tx: https://testnet.bscscan.com/tx/{result['transactionHash']}")
```

### Example: Job processing agent (full service)

From `examples/agent-server/src/service.py` pattern:
```python
from bnbagent.erc8183.server import create_erc8183_app

def process_task(job: dict) -> str:
    query = job.get("description", "")
    # Your logic: call CMC, run strategy, return result
    result = run_trading_strategy(query)
    return f"## Result\n\n{result}"

app = create_erc8183_app(on_job=process_task)
```

### Example: ERC-8183 job lifecycle (client side)

From `examples/client/happy.py` pattern:
```python
from bnbagent.erc8183 import ERC8183Client

client = ERC8183Client(network="bsc-mainnet", wallet_provider=wallet)

# Create + fund a job
job_id = client.create_job(description="Run TWAK ETH/USDC strategy")
client.set_budget(job_id, amount=1_000_000_000_000_000_000)  # 1 token
client.fund(job_id)

# After agent delivers: settle
client.settle(job_id)
```

---

## Architecture (Module Dependency Graph)

```
BNBAgent (facade, from_env())
├── ERC8004Module  ──────────────── ERC8004Agent
│   └── IdentityRegistry contract
└── ERC8183Module  ──────────────── ERC8183Client (facade)
    ├── CommerceClient (job CRUD)
    ├── RouterClient (settlement routing)
    └── PolicyClient (optimistic approval)

Core (shared, no upward deps):
├── EVMWalletProvider / MPCWalletProvider
├── NonceManager (per-account singleton)
├── ModuleRegistry (plugin discovery)
└── PaymasterClient (gas sponsorship)

Storage (pluggable):
├── LocalStorageProvider
└── IPFSStorageProvider (Pinata)
```

---

## Gotchas

1. **No swap execution in this SDK** — The press release mentions "PancakeSwap routing" as a BNB AI Agent SDK capability. This is NOT in the current Python package. Use TWAK for swaps.

2. **Alpha status** — Package metadata says Development Status 3 (Alpha). APIs may change.

3. **Private key handling** — SDK encrypts the private key to `~/.bnbagent/wallets/` on first run. Remove `PRIVATE_KEY` from `.env` after first startup. Do not commit it.

4. **Wrong-chain protection** — SDK verifies chain ID at connection time. If `NETWORK=bsc-mainnet`, RPC must return chain ID 56 or initialization fails.

5. **EIP-712 strict signing** — Default policy blocks ERC-2612 Permit signatures (common on some DEXes). If TWAK or a contract requires Permit, you need `SigningPolicy.extend()`.

6. **Paymaster = free gas (testnet only)** — MegaFuel paymaster sponsors gas on BSC Testnet. On mainnet, your wallet pays gas normally.

7. **Competition contract is TWAK's domain** — `0x212c61b9b72c95d95bf29cf032f5e5635629aed5` is not referenced in BNBAgent SDK. Use `twak compete register` or the `competition_register` MCP action via TWAK.

8. **uv is preferred** — The repo uses `uv` as the package manager (not pip directly). `uv run python scripts/register.py` is the documented invocation.

9. **SSRF protection in URI parsing** — If your agent URI includes an HTTP endpoint for the agent card, the SDK enforces a 1 MB response cap, 10s timeout, and blocks RFC-1918 IPs.

10. **Module initialization order** — ERC-8183 declares ERC-8004 as a dependency. If using both, initialize together via `BNBAgent.from_env()` rather than individually.

---

## Sources

- GitHub repo: https://github.com/bnb-chain/bnbagent-sdk
- BNB Chain blog: https://www.bnbchain.org/en/blog/bnbagent-sdk-the-first-live-erc-8183-implementation-for-onchain-ai-agents
- Hackathon announcement: https://chainwire.org/2026/06/03/bnb-chain-coinmarketcap-and-trust-wallet-launch-36000-bnb-hack-ai-trading-agent-edition/
- DoraHacks page: https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail
- CMC Agent Hub: https://coinmarketcap.com/api/agent
- TWAK announcement: https://trustwallet.com/blog/announcements/introducing-the-trust-wallet-agent-kit-twak-your-ai-agent-can-now-act-on-crypto
- TWAK builders portal: https://portal.trustwallet.com/
- TWAK developer docs: https://developer.trustwallet.com/developer/agent-sdk
