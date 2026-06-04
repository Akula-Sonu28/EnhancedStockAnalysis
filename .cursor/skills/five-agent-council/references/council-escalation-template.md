# Council Escalation — shared template

Use when a **research desk** (india-markets-*) or **PM** surfaces a code/config
change. Do not patch from the desk session — hand to main session for `COUNCIL`.

```markdown
## Council Escalation — [from: Fundamental | Technical | Macro | Portfolio | Regulatory | Product]

**Goal:** [one sentence]
**India context:** [NSE live | backtest-only | regulatory | none]
**Investor-facing:** YES / NO
**Product surface:** [analyzer | dashboard | backtest | scripts | CI]
**Evidence:** [report path, cache, history row, module output]
**Proposed change:** [file/function — no patch here]
**Council agents:** [ARCH | QUANT | RISK | AUDIT | SKEPTIC — likely reviewers]
**Trigger:** COUNCIL <goal>
```

After gate + user confirm → `software-product-orchestrator` (`BUILD`) implements.
