---
name: conviction-agent-findings
description: Conviction Agent research + experiment results — infra realities and a scoring design flaw
metadata: 
  node_type: memory
  type: project
  originSessionId: f0269527-0622-411a-a4c8-befb0543b5e4
---

Research (in `research/`) + live PoCs (in `experiment/`) for [[conviction-agent-scaffold]], done 2026-06-15.

**Infra realities (verified live):**
- TWAK = TypeScript CLI, NO Python SDK → execution layer is subprocess calls, not import.
- x402 has NO BSC support (USDT lacks EIP-3009) → pay on Base, trade on BSC = two-chain setup.
- BscScan V2 requires a PAID plan for BSC chain 56 (~$49/mo Lite); holder list = Standard+.
- Public `bsc-dataseed` RPC blocks `eth_getLogs`; `rpc.ankr.com/bsc` needs key. `bsc-rpc.publicnode.com` works keyless (dev RPC). web3.py 7.16 BSC needs `ExtraDataToPOAMiddleware` at layer 0.

**Design flaw the experiment exposed (must fix before Phase C):** the conviction scorer is a flat weighted sum that rewards social velocity — but the prime "accumulation" setup (whales in, retail asleep) has LOW social by definition, so it scored 50 and did NOT fire while the weaker confirmation setup fired at 74. Fix: make `brain/conviction.py` scoring SETUP-CONDITIONAL — low social is a bonus for accumulation, not a penalty.
