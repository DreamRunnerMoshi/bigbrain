# Findings

Answers to the experiment hypotheses in spec section 9, each with numbers, plots, and a
recommendation. Nothing has run yet: this file holds the structure and stays empty of
results until the experiment harness lands (M6).

Conventions: each experiment section states the hypothesis, the config used
(`experiments/configs/<id>.yaml`), and the run it reports on
(`results/<exp>/<run_id>/report.md`). Every result must be reproducible from its config,
seed, and cassettes. Invariant violations are reported as failures, never as a metric to
trade off.

| Experiment | Hypothesis (one line) | Status |
| --- | --- | --- |
| E1 - privacy and leakage audit | no plaintext recoveries, no competitor-term leakage, workers share no offer-bearing state | not run |
| E2 - does negotiation create value? | multi-attribute rounds create surplus for claimed merchants in the synthetic market | not run |
| E3 - scale and latency | broadcast to channels scales to 1k+ merchants per channel with usable p95 latency | not run |
| E4 - offline buyer device | sealed offers reach an offline buyer and the session completes on reconnect | not run |
| E5 - prompt injection | defense layers D0-D3 keep I1/I10 violations at zero under >=20 attack templates | not run |
| E6 - power asymmetry | negotiation outcomes and welfare depend on buyer/merchant power balance | not run |
| E7 - rule-based vs LLM agents | LLM agents beat rule-based quality at a measurable token cost | not run |
| E8 - human-final under stress | zero carts or checkout URLs without a valid approval of the exact terms | not run |
| E9 - shop taxonomy profiling | the profiler picks the right channels with high precision without reading the full catalog | not run |
| E10 - real-shop offer quality | channel-routed offers meet hard constraints and stay accurate at checkout | not run |
| E11 - outbound leakage to Shopify | outbound queries carry only derived keywords and allowed filters | not run |

## Open problems carried forward

Spec section 12 (broker governance, merchant consent and claiming, legal exposure,
operator trust, prompt injection, power asymmetry, liability, metadata leakage, store
discovery) stays stubbed until the experiments that inform them are run.
