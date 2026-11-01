# ESM-2 650M — zero-shot variant-effect scoring

- **Model**: `facebook/esm2_t33_650M_UR50D`, pinned revision
  `08e4846e537177426273712802403f7ba8261b6c` (MIT). Loaded via transformers 4.57.
- **Method**: masked-marginal delta log-likelihood. For each mutated position, the
  residue is masked and the log-probability of the mutant vs wild-type residue is
  compared; the per-mutation deltas are summed.
- **Inputs**: wild-type protein sequence and mutation(s) in `A16C` form (colon-
  separated for multiple mutations).
- **Outputs**: a scalar delta log-likelihood (higher = more tolerated by the model);
  and a mean per-residue log-likelihood for a sequence.
- **Interpretation**: these are MODEL PREDICTIONS (E1). They are **not**
  experimental measurements and must not be reported as such.
- **Limitations**: no experimental validation; zero-shot ranking quality varies by
  protein and assay; does not model stability/function separately; sequence-only.
- **Hardware**: GPU0, ~2.7 GB VRAM.
