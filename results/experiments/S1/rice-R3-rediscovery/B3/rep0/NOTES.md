# R3 rediscovery — B3 rep0 (rice, GRWT100)

## Answer
**top-1 = IRIS_313.12254, measured GRWT100 = 5.0 g/100 grains** (highest of the 20 phenotyped lines).
Runner-up: IRIS_313.12349 = 4.7 g.

## Loop
1. **H1 (falsifiable).** The true argmax of measured GRWT100 lies in the top-20 lines ranked by the Ridge model; equivalently, model rank agrees with measured rank > 0 and the model rank-1 line holds the measured maximum.
   Refutation: Spearman(pred, meas) <= 0 among queried lines, or the rank-1 line is not the measured max.
2. **exp-1 (E1).** `run_model(rank_candidates, all 904 ids)`. Predictions 1.499-3.662 g, mean 2.479, sd 0.302. (rank_candidates returned 902; IRIS_313.10791/10794 recovered by a second `predict_by_ids` call — 2.544 / 2.774 g.)
3. **exp-2 (E3).** 20/20 oracle queries spent on the **top-20 predicted** lines. Rationale: under a Gaussian error model the posterior argmax-probability is monotone in prediction, so the top-20 predicted set maximizes P(true argmax is measured within budget).
4. **Result.** Spearman(pred, meas) = 0.473, Pearson = 0.680 (both > 0); rank-1 line holds the measured max => H1 not refuted, revised to H1' (specific line).
5. **exp-3 (E2).** Calibration meas = -8.10 + 3.49*pred (slope t = 3.94), residual sd 0.465 g. Expected number of unqueried lines above 5.0 g = 0.00-0.08; P(no unqueried line exceeds 5.0 g) = 0.93-1.00 (stress tests on residual sd 0.47/0.60/0.80 g). Highest-risk unqueried: IRIS_313.11705, .12251, .12049.

## Uncertainty & limitations (stated, not hidden)
- 884 of 904 lines never phenotyped; the answer is the max of a *sample* of 20.
- Calibration is extrapolated from a truncated top-20 sample (predictions only 3.17-3.66 g); slope/residual-sd uncertainty is large, so the probability in exp-3 is itself model-based (E2), not measured.
- E1 predictions are heavily compressed (1.50-3.66 g) vs measured (2.8-5.0 g); **never** read predictions as phenotypes.
- Single environment, no GxE; linear additive model, no epistasis/dominance; held-out pool Spearman 0.4535.
- One measurement per line, no replication; values rounded to 0.1 g, so the 0.3 g margin is ~6 rounding steps but only ~0.6 residual sd.
- `rank_candidates` silently dropped 2 of 904 ids (tool-output limitation); both were rescored and are mid-pool.

## Files
- `final_selection.json` — `{"top_ids": [...]}`, 904 ids: 20 measured lines ordered by measured value, then unmeasured lines ordered by prediction.
- `evidence.jsonl` (ev-1 E1, ev-2 E3, ev-3 E2), `conclusions.jsonl` (C1-C4), `plans.jsonl`, `oracle_access.jsonl` (20/20).
- `analysis/` — e1_full.json, analyze.py, sensitivity.py, finalize.py.
