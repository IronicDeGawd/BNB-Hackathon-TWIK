# Trust Wallet Agent Kit (TWAK) — Developer Reference

> Last updated: 2026-06-14  
> Confidence: HIGH for CLI/MCP/auth/swap/x402 (direct from official docs). MEDIUM for competition on-chain registration details (inferred from press releases + skills registry; no `twak compete` command syntax confirmed from official docs).

---

## Overview

TWAK (Trust Wallet Agent Kit) is a **TypeScript/Node.js CLI + MCP server + REST API** that lets AI agents execute real crypto transactions with self-custody signing — keys never leave the device. It supports 25+ chains including **BNB Smart Chain (BSC)**.

Core primitives:
- Wallet & identity (agent wallet or WalletConnect)
- Swaps and cross-chain swaps
- DCA automations and limit orders
- Market data (prices, risk scores, trending)
- x402 pay-per-request micropayments
- ERC-8004 agent identity registration
- ERC-8183 agentic commerce (job escrows)

**Language / SDK:** TypeScript/Node.js (`@trustwallet/cli` npm package). No official Python SDK found — CLI is the primary interface; REST API available for polyglot use.

---

## Install / Setup

### One-liner installer (recommended)
```bash
curl -fsSL https://agent-kit.trustwallet.com/install.sh | bash
```
Installs CLI, prompts for credentials, auto-wires Claude Code / Cursor / Codex harness.

### Manual npm install
```bash
npm install -g @trustwallet/cli
# Verify:
npx @trustwallet/cli --version
```

### Agent Skills (gives your AI coding agent TWAK domain knowledge)
```bash
# Auto-detect coding agent:
npx skills add trustwallet/tw-agent-skills

# Target specific agent:
npx skills add trustwallet/tw-agent-skills -a claude-code
npx skills add trustwallet/tw-agent-skills -a cursor
# Also: codex, windsurf, github-copilot, cline, opencode, roo
```

---

## Auth / Keys

### Get credentials
1. Sign in at https://portal.trustwallet.com
2. Create an app → generate API key
3. Copy **Access ID** and **HMAC Secret** (shown once only)

### Configure CLI
```bash
twak init --api-key <ACCESS_ID> --api-secret <HMAC_SECRET>
# Stored in ~/.twak/credentials.json with restricted permissions
```

### CI/CD — environment variables
```bash
export TWAK_ACCESS_ID=your_access_id
export TWAK_HMAC_SECRET=your_hmac_secret
```

### Verify auth
```bash
twak auth status
twak auth status --json
```

### HMAC-SHA256 request signing (for direct REST API calls)
Every request signs: `METHOD + PATH + QUERY + ACCESS_ID + NONCE + DATE`

Required headers:
- `X-TW-Credential`: your Access ID
- `X-TW-Nonce`: unique random string per request
- `X-TW-Date`: ISO 8601 timestamp (±5 min window)
- `Authorization`: Base64-encoded HMAC-SHA256 signature

> The CLI and TypeScript SDK handle signing automatically — you only need the raw headers if hitting the REST API directly.

---

## Wallet Setup

### Create an agent wallet (keys stored locally, AES-256-GCM encrypted)
```bash
twak wallet create --password <pw>
# Mnemonic encrypted with PBKDF2-derived key → ~/.twak/wallet.json
# Keys NEVER leave the device

# Opt into OS keychain (macOS Keychain / Linux Secret Service):
twak wallet keychain save --password <pw>
```

### Get wallet addresses
```bash
twak wallet address --chain bsc --json
twak wallet addresses --json   # all supported chains
twak wallet status --json
```

### Re-register wallet with Trust Wallet backend (enables portfolio tracking)
```bash
twak wallet register
```

### Password resolution order
1. `--password <pw>` flag
2. `TWAK_WALLET_PASSWORD` environment variable  ← use this for autonomous/unattended mode
3. OS keychain

---

## Competition Registration (BNB Hack)

> **CONFIDENCE: MEDIUM** — The `twak compete` subcommand is listed in the TWAK skills registry but exact syntax and flags are not publicly documented in official docs as of 2026-06-14. The on-chain registration mechanism is confirmed via press releases but the smart contract address is not publicly disclosed.

### Context
Track 1 (Autonomous Trading Agents, $24K pool) requires **on-chain registration via a BSC smart contract** that records the agent wallet address. Registration deadline: before trading window opens June 22, 2026.

### What is confirmed (from skills registry listing)
The `trust-wallet-cli` skill listing on tessl.io confirms TWAK CLI includes:
- "BNB Hack Competition: Registration, status tracking for AI trading agent edition"

### Likely command pattern [UNVERIFIED — inferred]
```bash
# These are UNVERIFIED — check official docs or Telegram community:
twak compete register --chain bsc --password <pw>
twak compete status --json
```

### Confirmed registration path
- Register on DoraHacks: https://dorahacks.io/hackathon/bnbhack-twt-cmc/
- Join Telegram for builder support: https://t.me/+MhiOLT0YUnlmNWFk
- The BSC contract address and exact CLI syntax should be confirmed via the DoraHacks buidl page or Telegram — they are NOT in publicly scraped docs.

---

## Balance / Holdings

```bash
# Native token balance on BSC:
twak wallet balance --chain bsc --json

# All tokens on BSC (includes ERC-20/BEP-20):
twak wallet balance --chain bsc --all --json

# Portfolio across all chains:
twak wallet portfolio --json

# Portfolio filtered to specific chains:
twak wallet portfolio --chains bsc,ethereum --json

# Check a specific address's balance (no wallet required):
twak balance --address <address> --coin <coinId> --json
```

### Chain key for BSC
Use `bsc` as the `--chain` value throughout.

---

## Swap / Sign / Broadcast on BSC

All signing happens **client-side** (in the CLI process on your machine). Private keys never leave `~/.twak/wallet.json`.

### Step 1 — Always quote first (no signing, no wallet needed)
```bash
# Quote by token amount:
twak swap 0.1 BNB USDC --chain bsc --quote-only --json

# Quote by USD value:
twak swap BNB USDC --chain bsc --usd 50 --quote-only --json

# Quote with explicit slippage:
twak swap 100 USDC BNB --chain bsc --slippage 2 --quote-only --json
```

### Step 2 — Execute (locally signs + broadcasts)
```bash
# Same-chain BSC swap:
twak swap 0.1 BNB USDC --chain bsc --password <pw> --json

# With slippage tolerance (default 1%, max 50%):
twak swap 0.1 BNB USDC --chain bsc --slippage 0.5 --password <pw> --json

# By USD amount:
twak swap BNB USDC --chain bsc --usd 50 --slippage 1 --password <pw> --json

# Cross-chain (BSC → Ethereum):
twak swap 100 USDC USDC --chain bsc --to-chain ethereum --password <pw> --json
```

### Slippage reference
| Flag | Value | Notes |
|------|-------|-------|
| `--slippage` omitted | 1% | Default |
| `--slippage 0.5` | 0.5% | Conservative |
| `--slippage 5` | 5% | High volatility |
| `--slippage 50` | 50% | Maximum allowed |

### Token resolution
You can use symbols (`BNB`, `USDC`), contract addresses, or Universal Asset IDs (`c20000714` for BNB, `c20000714_t0x...` for BEP-20 tokens).

### Error codes
| Code | Meaning |
|------|---------|
| `SLIPPAGE_EXCEEDED` | Slippage above 50% |
| `INSUFFICIENT_BALANCE` | Not enough funds |
| `NO_ROUTES` | No swap path for this pair |
| `TX_FAILED` | Transaction failed or unconfirmed |

> ERC-20/BEP-20 approvals are handled automatically — no manual approve step.

### Supported chains (confirmed in swap docs)
Ethereum, Arbitrum, Optimism, Polygon, **BSC**, Avalanche, Base, Fantom, Linea, Scroll, zkSync, Blast, Sonic, Celo, Aurora, Solana.

---

## Autonomous Mode

TWAK supports two trust models:

| Mode | Description |
|------|-------------|
| **Agent Wallet (Mode A)** | Agent has its own wallet. Developer configures rules upfront. Agent signs/executes with no per-transaction approval. For autonomous strategies: DCA, limit orders, scheduled execution. |
| **WalletConnect (Mode B)** | User retains custody. Agent proposes transactions. User approves each one. |

### Running unattended (autonomous)

**Option 1 — MCP server with `--watch` flag (background automation)**
```bash
# Start MCP server + background automation watcher:
twak serve --watch --watch-interval 60s --password <pw>

# Or load password from env (recommended for daemons):
export TWAK_WALLET_PASSWORD=your_wallet_password
twak serve --watch --watch-interval 30s
```
The `--watch` flag enables background polling for DCA executions and limit order triggers. Default interval: 60 seconds; minimum: 5 seconds.

**Option 2 — REST server for custom agent loops**
```bash
twak serve --rest --port 3000 --watch --password <pw>
# Agent calls http://localhost:3000 endpoints to trigger swaps
```

**Option 3 — Direct CLI in scripts/cron**
```bash
export TWAK_WALLET_PASSWORD=your_wallet_password
twak swap 0.01 BNB USDC --chain bsc --slippage 1 --json
```

### DCA automation (autonomous recurring buys)
```bash
# Buy $10 of USDC every hour on BSC:
twak automate add --from BNB --to USDC --amount 10 \
  --chain bsc --interval 1h --max-runs 24 --password <pw> --json

# Limit order: buy BNB when price drops below $300:
twak automate add --from USDC --to BNB --amount 50 \
  --chain bsc --price 300 --condition below --password <pw> --json

# List active automations:
twak automate list --json

# Pause/resume/delete:
twak automate pause <id> --json
twak automate resume <id> --json
twak automate delete <id> --json
```

---

## MCP Server Setup

The MCP server lets Claude Code (or any MCP-compatible AI) call TWAK actions as tools.

### For Claude Code
```json
// In .claude/settings.json or mcp config:
{
  "mcpServers": {
    "twak": {
      "command": "twak",
      "args": ["serve"]
    }
  }
}
```

Or via CLI:
```bash
claude mcp add twak -- twak serve
```

### For Cursor / Windsurf
```json
{
  "mcpServers": {
    "twak": {
      "command": "twak",
      "args": ["serve"]
    }
  }
}
```

### Trust Wallet Docs MCP (for AI coding agents, no credentials needed)
```bash
claude mcp add --transport http trust-wallet-docs \
  https://developer.trustwallet.com/developer/~gitbook/mcp
```

---

## x402 Pay-Per-Request

x402 is the HTTP 402 Payment Required protocol — the server requests payment, the client signs an on-chain authorization and retries. TWAK natively supports this for both consuming paid APIs and serving your own.

### Consuming a paid API endpoint
```bash
# Preview payment options (no signing):
twak x402 quote <url> --json

# Make a paid request (interactive confirmation):
twak x402 request <url> --max-payment <atomic_amount> \
  --prefer-network bsc \
  --prefer-asset USDC \
  --password <pw> --json

# Non-interactive (autonomous mode):
twak x402 request <url> --max-payment 1000000 \
  --yes --auto-approve \
  --prefer-network base --prefer-method eip3009 \
  --prefer-asset USDC \
  --password <pw> --json
```

### Serving your own x402-gated API
```bash
# Expose your agent/API with per-request payment gating:
twak serve --rest --x402 --port 3000 --password <pw>
```

### Payment flow
1. Client requests endpoint → gets `402 Payment Required`
2. Server returns accepted payment options (chain, token, amount)
3. Client signs authorization (`EIP-3009` or `Permit2`) and retries with `X-PAYMENT` header
4. Server verifies on-chain → returns resource

**Recommended route:** USDC on Base via EIP-3009 (gasless, fast finality, low fees).

### x402 info
```bash
twak x402 info   # Show supported chains and methods
```

---

## Code Examples

### Example 1 — Minimal BSC swap script (shell)
```bash
#!/bin/bash
set -e

export TWAK_ACCESS_ID="your_access_id"
export TWAK_HMAC_SECRET="your_hmac_secret"
export TWAK_WALLET_PASSWORD="your_wallet_password"

# Check balance
echo "=== Balance ==="
twak wallet balance --chain bsc --all --json

# Quote first
echo "=== Quote: 0.01 BNB → USDC ==="
twak swap 0.01 BNB USDC --chain bsc --slippage 1 --quote-only --json

# Execute swap
echo "=== Executing swap ==="
twak swap 0.01 BNB USDC --chain bsc --slippage 1 --json
```

### Example 2 — Autonomous agent daemon (shell)
```bash
#!/bin/bash
# daemon.sh — run as background process or systemd service

export TWAK_ACCESS_ID="your_access_id"
export TWAK_HMAC_SECRET="your_hmac_secret"
export TWAK_WALLET_PASSWORD="your_wallet_password"

# Start MCP + background automation watcher
# Unlocks wallet via env var — no human prompt needed
twak serve --watch --watch-interval 30s --auto-lock 0
```

### Example 3 — MCP server for Claude-driven autonomous agent
```bash
# Start REST server; your agent code calls localhost:3000
export TWAK_WALLET_PASSWORD="your_wallet_password"
twak serve --rest --port 3000 --watch
```

Then in your agent:
```typescript
// Agent calls TWAK REST endpoints
const quoteRes = await fetch('http://localhost:3000/swap/quote', {
  method: 'POST',
  body: JSON.stringify({ from: 'BNB', to: 'USDC', amount: 0.01, chain: 'bsc' })
});
const quote = await quoteRes.json();
// Evaluate quote, then execute:
const execRes = await fetch('http://localhost:3000/swap/execute', {
  method: 'POST',
  body: JSON.stringify({ ...quote, slippage: 1 })
});
```
> Note: REST API endpoint paths are UNVERIFIED — exact routes depend on TWAK REST server implementation. Consult `developer.trustwallet.com/developer/agent-sdk` for official REST spec.

### Example 4 — Price alert + conditional swap
```bash
# Watch BNB price; buy if it drops below $300
twak automate add \
  --from USDC --to BNB \
  --amount 100 \
  --chain bsc \
  --price 300 --condition below \
  --max-runs 1 \
  --password <pw> --json

# Start watcher so condition is evaluated automatically:
twak serve --watch --watch-interval 60s --password <pw>
```

---

## ERC-8004 Agent Identity Registration

TWAK supports on-chain agent identity registration (ERC-8004 standard). BSC is one of the 15 supported chains with 44,020+ indexed agents.

```bash
# Register this agent's on-chain identity (mints NFT on BSC):
# [UNVERIFIED exact syntax — from skills registry listing only]
twak wallet agent-identity register --chain bsc --password <pw> --json

# Manage agent metadata URI:
twak wallet agent-identity set-uri --uri <ipfs-or-https-uri> --chain bsc --password <pw> --json
```

---

## Rate Limits / Gotchas

| Item | Details |
|------|---------|
| Rate limit (free tier) | 1 request/second |
| HMAC timestamp window | ±5 minutes — keep system clock synced |
| Max slippage | 50% — `SLIPPAGE_EXCEEDED` thrown if exceeded |
| Min `--watch-interval` | 5 seconds |
| x402 URL security | Only HTTPS; private/loopback IPs rejected |
| Key storage | `~/.twak/wallet.json` (AES-256-GCM encrypted) — never commit |
| HMAC Secret | Shown once at portal.trustwallet.com — save immediately |
| BSC chain key | Use `bsc` (not `bnb`, not `binance`, not `smartchain`) |
| ERC-20 approvals | Handled automatically on swap execute — no manual step |
| Wallet password security | Use `TWAK_WALLET_PASSWORD` env var; never pass in shell history |
| `twak serve` default host | `127.0.0.1` — loopback only; use `--host 0.0.0.0` only if needed |

---

## Source URLs

| Resource | URL |
|----------|-----|
| Official blog announcement | https://trustwallet.com/blog/announcements/introducing-the-trust-wallet-agent-kit-twak-your-ai-agent-can-now-act-on-crypto |
| Developer portal | https://portal.trustwallet.com/ |
| Developer docs (Agent SDK) | https://developer.trustwallet.com/developer/agent-sdk |
| CLI Reference | https://developer.trustwallet.com/developer/agent-sdk/cli-reference |
| Authentication docs | https://developer.trustwallet.com/developer/agent-sdk/authentication |
| MCP servers docs | https://developer.trustwallet.com/developer/mcp |
| Agent Skills (Claude Code) | https://developer.trustwallet.com/developer/claude-code-skills |
| Agent Skills GitHub | https://github.com/trustwallet/tw-agent-skills |
| BNB Hack hackathon | https://dorahacks.io/hackathon/bnbhack-twt-cmc/ |
| BNB Hack announcement | https://chainwire.org/2026/06/03/bnb-chain-launches-36000-hackathon-to-advance-on-chain-ai-trading-agents/ |
| ERC-8004 standard | https://eips.ethereum.org/EIPS/eip-8004 |
| DCA + Limit orders blog | https://trustwallet.com/blog/announcements/your-ai-agent-can-now-run-your-crypto-strategy-introducing-dca-automation-and-limit-orders-in-trust-wallet-agent-kit |
| Tessl skills registry (CLI skill listing) | https://tessl.io/registry/skills/github/trustwallet/tw-agent-skills/trust-wallet-cli |
