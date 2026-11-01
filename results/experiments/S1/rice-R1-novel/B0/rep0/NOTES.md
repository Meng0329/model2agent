# Method B0 — Rice GRWT100 genomic prediction (rep0)

## Task
- Model: `rice_gs`; trait: GRWT100 (100-grain weight).
- Goal: within <=20 real phenotyping queries, identify the 10 candidates most likely in the high-grain-weight quartile.
- Method under evaluation: **B0** (no-information / no-model baseline).

## Input available
- `rice_candidates.json`: a single JSON list of ~1000 candidate accession IDs (`IRIS_313.NNNNN`).
- **No** genotype matrix, **no** marker data, **no** trained model artifact, **no** training phenotypes,
  **no** historical measurements, **no** oracle/measurement tool exposed to the agent.

## What was executed
- The genomic prediction model could **not** be executed (no model artifact / no execution capability).
- **0** of 20 oracle queries were used (no oracle/measurement tool is available; measurements are UNOBSERVABLE).

## Evidence
- E1 (model predictions): **none** — model could not be run.
- E3 (historical measurements): **none** — no measured values were returned by any oracle; no value was invented or proxied.

## Scientific conclusion
- With no genotype, passport, or phenotype information, all candidates are **exchangeable** with respect to GRWT100.
- There is no scientific basis to rank one candidate above another; any ranking has expected top-10 precision equal to the
  population frequency of the top quartile (~25%, i.e. ~2.5/10 hits by chance).

## Selection rule (deterministic, auditable, unbiased)
- To avoid any systematic coupling with administrative accession-number order, 10 evenly spaced target positions
  were taken across the accession-number span of the candidate set (7685–12354):
  targets = 7685 + (k + 0.5) * (12354 - 7685) / 10, for k = 0..9.
- For each target, the listed candidate ID with the nearest accession number was selected.
- Resulting IDs (all verified present in the candidate list):
  7933, 8382, 8854, 9314, 9783, 10258, 10719, 11189, 11656, 12129.
- Within-rank order is arbitrary (ascending accession number) and carries no information.

## Limitations
1. No features => genomic prediction is impossible; this baseline is equivalent to random selection.
2. Accession number is an administrative identifier (Genesys / IRRI genebank) with no established relationship to grain weight.
3. Expected performance of any B0 selection is chance-level; the result should be interpreted as a no-information control.
4. Measurements for the selected lines remain unobserved; no phenotype value is claimed or fabricated.
