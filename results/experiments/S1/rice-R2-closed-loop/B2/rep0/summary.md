# Rice GRWT100 closed-loop selection — summary

Trait: GRWT100 (100-grain weight, g). Method: B2. Candidate pool: 904 lines.
Budget used: 30/30 oracle queries, model predictions for all 904.

## Loop
- Round 0 (E1): Ridge model scored all 904 candidates (predict min 1.50, max 3.66, mean 2.48).
- Round 1 (E3, 20 queries): top-12 model-ranked lines + 8 stratified controls
  (model ranks 100,200,300,400,500,600,700,800).
  Top-12 mean = 3.72 g vs controls mean = 2.64 g -> model ranking is enriched.
- Calibration revision: measured = -0.52 + 1.23*E1 (resid sd 0.54). Quartile boundary
  estimated at ~2.8-3.0 g (calibration sim 2.95 g; non-candidate panel q75 = 2.80 g).
- Round 2 (E3, 10 queries): 10 highest-posterior unmeasured lines; added 12349 (4.7), 12129 (3.8).

## Final ranked top-10 (by measured GRWT100)
| rank | id | measured g | E1 prediction |
|---|---|---|---|
| 1 | IRIS_313.12254 | 5.0 | 3.662 |
| 2 | IRIS_313.12349 | 4.7 | 3.302 |
| 3 | IRIS_313.12344 | 4.6 | 3.444 |
| 4 | IRIS_313.12242 | 4.5 | 3.599 |
| 5 | IRIS_313.12228 | 3.8 | 3.421 |
| 6 | IRIS_313.12129 | 3.8 | 3.301 |
| 7 | IRIS_313.11094 | 3.6 | 3.414 |
| 8 | IRIS_313.10679 | 3.6 | 3.340 |
| 9 | IRIS_313.10089 | 3.5 | 2.683 |
| 10 | IRIS_313.12262 | 3.4 | 3.346 |

All 10 measured >= 3.4 g, i.e. above the ~2.8-3.0 g high-quartile boundary.
Caveats: only 30/904 phenotyped; E1 is not a measurement; single environment;
linear additive model ignores GxE/epistasis/dominance.
