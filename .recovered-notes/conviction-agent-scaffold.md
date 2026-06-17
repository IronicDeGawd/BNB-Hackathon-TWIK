---
name: conviction-agent-scaffold
description: "BNB-Hackathon-TWIK is Conviction Agent — autonomous BSC trading agent, Track 1"
metadata: 
  node_type: memory
  type: project
  originSessionId: f0269527-0622-411a-a4c8-befb0543b5e4
---

`/project/BNB-Hackathon-TWIK` = **Conviction Agent**, BNB Hack AI Trading Agent Edition (Track 1). Python. Thesis: trade divergence between social hype (Twitter+Reddit) and on-chain smart-money flow, CMC structural veto, TWAK as sole signer. Full spec in `docs/BUILD_SPEC.md`.

Scaffolded 2026-06-14: full repo tree, config/settings.py done, stubs for signals/brain/risk/execution by phase (A–E). git init, no commit yet.

**Locked decisions:** scorer = rules-based core + LLM only for rationale_text; spot-only to start.

**Blocker:** official 149 eligible-token list not yet provided — `config/tokens.py` addresses all `None`. Must resolve+verify (CMC+BscScan) before live trade. Build window closes June 21, live June 22–28.
