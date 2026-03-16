# BOTmarket Research Program

> Adapted from Karpathy's autoresearch: constrain scope, define metric, iterate, keep/discard.
> "Autonomy scales when you constrain scope, clarify success, mechanize verification."

## Goal

Exhaustively analyze the BOTmarket concept (AI agent service exchange) before writing any code.
Produce a research corpus that answers every critical question a founder/investor would ask.

## Research Metric

Each research dimension is scored 1-10 on **completeness** (all sub-questions answered)
and **actionability** (findings lead to concrete decisions). Combined score tracked in
`research/results.tsv`.

Target: All 12 dimensions score ≥ 7/10 before proceeding to architecture/code.

## Research Dimensions

| # | Dimension | Key Questions |
|---|-----------|--------------|
| 1 | **Market Size & Timing** | TAM/SAM/SOM, growth rate, why now, adoption curve |
| 2 | **Competitive Landscape** | Direct/indirect competitors, moats, white space |
| 3 | **User Personas** | Who are the agents? Who deploys them? Who pays? |
| 4 | **Value Proposition** | Why exchange > direct integration? What's the 10x? |
| 5 | **Business Model** | Revenue streams, unit economics, pricing strategy |
| 6 | **Token Economics** | Token design, incentive alignment, regulatory risk |
| 7 | **Technical Architecture** | Order book vs AMM, matching engine, settlement |
| 8 | **Protocol Design** | Agent identity, service discovery, SLA, reputation |
| 9 | **Legal & Regulatory** | Securities law, money transmission, GDPR, liability |
| 10 | **Go-to-Market** | First agents, cold start problem, growth loops |
| 11 | **Risk Assessment** | Technical, market, regulatory, competitive risks |
| 12 | **MVP Definition** | Smallest thing that proves the thesis, success metric |

## Iteration Protocol

```
LOOP:
  1. Pick the lowest-scoring dimension
  2. Research it deeply (web, papers, competitors, first principles)
  3. Write findings to research/{dimension}.md
  4. Score completeness + actionability
  5. Log to research/results.tsv
  6. If all dimensions ≥ 7 → STOP, produce synthesis
  7. Repeat
```

## Scope Constraints

- **DO NOT** write any application code
- **DO NOT** make technology choices yet
- **DO** challenge assumptions ruthlessly
- **DO** identify what we don't know (known unknowns)
- **DO** find real data points over opinions
- **DO** map the decision tree (what depends on what)

## Output

Final deliverable: `research/SYNTHESIS.md` — a single document that:
1. States the thesis clearly
2. Summarizes each dimension's findings
3. Lists the top 5 risks and mitigations
4. Defines the MVP scope with success criteria
5. Provides the decision framework for architecture choices
