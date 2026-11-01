# R3 rediscovery — B3 rep0 (rice, GRWT100)

## Answer
**top-1 = IRIS_313.12254, measured GRWT100 = 5.0 g/100 grains** (highest of the 20 phenotyped lines; also model rank 1 with predicted 3.662 g).
Runner-up: IRIS_313.12349 = 4.7 g (model rank 14), then 12344 = 4.6, 12242 = 4.5.

## Loop
1. **H1 (falsifiable).** The measured argmax of GRWT100 over the 904 candidates lies in the top-20 lines of the rice_gs Ridge ranking; equivalently Spearman(pred, meas) > 0 and the rank-1 line holds the measured maximum.
   Refutation: Spearman <= 0 among queried lines, or the measured max not in the top-20 predicted.
2. **exp-1 (E1).** `rank_candidates` on all 904 ids (shipped `infer.py`, examples reproduced exactly; sanctioned `run_model` on the top-20 byte-identical). Pred 1.499-3.662 g, mean 2.480, sd 0.302. All 904 ids present in the genotype table.
3. **exp-2 (E3).** 20/20 oracle queries on the **top-20 predicted** lines — under a monotone-likelihood error model this set maximises P(the measured argmax is observed within the 20-query budget). Query set fixed before any measurement.
   Measured: 5.0 (12254), 4.7 (12349), 4.6 (12344), 4.5 (12242), then 3.8-2.8.
4. **Falsification test.** Spearman = +0.473 (p = 0.035), Pearson = 0.680; rank-1 predicted line holds the measured max => H1 not refuted, revised to H1' (specific line).
5. **exp-3 (E2).** meas = -8.10 + 3.489*pred (slope SE 0.886, p = 0.001), residual sd 0.442 g. Highest calibrated mean among the 884 unqueried lines is 2.96 g (pred 3.171), 2.04 g below 5.0. P(no unqueried line > 5.0 g): 0.999+ (Gaussian sd 0.44-0.55), 0.983 (sd 0.70), 0.72-0.90 (Student-t df 4-8, sd 0.6). Expected # exceedances 0.000-0.33. Highest-risk unqueried: 11705, 12251, 12049.

## Uncertainty & limitations (stated, not hidden)
- 884 of 904 lines were never phenotyped; the answer is the max of a 20-line sample.
- The calibration is extrapolated from a truncated top-of-pool sample (predictions only 3.17-3.66 g); the linear fit even gives negative means at the lowest predictions, so it is valid only near the sampled range. The exceedance probability is model-based (E2), not measured.
- E1 predictions are compressed (1.50-3.66 g) vs measurements (2.8-5.0 g); never read them as phenotypes.
- Single environment, no GxE; linear additive Ridge (no epistasis/dominance); held-out pool Spearman 0.454.
- One measurement per line, no replication; values rounded to 0.1 g, so the 0.3 g margin over the runner-up is ~0.7 residual sd.
- The model ordering at the top is partly non-monotonic in measurement (rank 14 = 4.7 > rank 2 = 4.5), so no finer ranking below the measured top-4 is trustworthy.

## Files
- `final_selection.json` — `{"top_ids": [...]}`, all 904 ids: the 20 measured lines in measured order, then the 884 unmeasured lines in predicted order.
- `evidence.jsonl` (ev-4 E1, ev-5 E3, ev-6 E2 for this run), `plans.jsonl` (exp-1), `oracle_access.jsonl` (20/20 queries).
- `analysis_b3/` — predict_all.py, e1_full.json, analyze.py, calib.json, sensitivity.py, finalize.py.
