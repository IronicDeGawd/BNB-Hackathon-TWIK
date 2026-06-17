---
name: read-spec-before-asking
description: "When user provides a detailed spec, do not ask questions it already answers"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0269527-0622-411a-a4c8-befb0543b5e4
---

User rejected a round of broad stack questions (Next.js? Hardhat? Foundry?) right before pasting a full build spec that already named the stack (Python, no frontend).

**Why:** Asking what the spec already states wastes a turn and signals not reading the provided material.

**How to apply:** When the user hands over a spec/PRD, read it fully first. Ask only genuinely-open decisions (scope of "setup", §-level open choices), batched in one round. See [[conviction-agent-scaffold]].
