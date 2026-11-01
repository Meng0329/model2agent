# Rice genomic-selection model (Ridge on pruned SNP dosages)

- **Model**: Ridge regression (alpha=1000) on the top-2000 variance SNPs (variance
  computed on the training split only). Standardized features.
- **Trait target**: `GRWT100` — 100-grain weight (g), a real measured agronomic trait.
- **Data**: 2259 rice lines from Orhobor et al. 2018, doi:10.17632/sr8zzsrpcs.1
  (CC-BY-SA-4.0); 12,486 SNPs; 2000 selected by train-only variance.
- **Split**: deterministic seed 20261029; 60% training (1356 lines) / 40% held-out
  candidate pool (903 lines). The pool was never used to prune, scale, or tune.
- **Metrics (real, held-out pool)**: CV Spearman 0.467 (train); held-out pool
  Spearman 0.454; held-out top-20 quartile hit 1.00.
- **Interpretation**: predictions are MODEL PREDICTIONS (E1), not measured
  phenotypes (E3). Genomic prediction is not a substitute for phenotyping.
- **Limitations**: single environment; linear marker model; imputed markers.
