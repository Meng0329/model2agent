# Evidence record — B0 protein-P1-novel rep0

## What was actually executed
- Read candidate file `/data/mzb/paper2agent/m2a_data/research/inputs/protein_candidates.json`.
- 44-residue wild-type sequence: MRKLSDELLIESYFKATEMNLNRDFIELIENEIKRRSLGHIISV.
- Candidate set: 19 single substitutions at each of positions 1-44 (positions 21 and 22 lack one substitution each; 836 candidates total).

## What could NOT be executed
- No oracle/measurement tool and no ESM-2 inference tool were available in this environment (only file Read/Write).
- Therefore: zero ESM-2 zero-shot scores were computed, and zero experimental measurements were obtained.
- Every fitness statement below is E1 reasoning (a qualitative prior), NOT a model prediction and NOT an E3 measurement.
- Oracle measurements: UNOBSERVABLE.

## Ranking rationale (heuristic, substitution-conservatism prior)
The peptide is short (44 aa), highly charged/polar (many E/D/K/R/N/S), with interspersed hydrophobic residues
(L/I/F/Y/V) consistent with a helical/soluble peptide. Under a zero-shot variant-effect framework the
highest-scoring single mutants are generally those that preserve charge, volume, and secondary-structure
propensity. Ranked picks:

1. E27D — acid-to-acid, one methylene shorter; surface-exposed in most helical contexts; classic near-neutral swap.
2. E11D — acid-to-acid, same reasoning; position in a polar/helical stretch (LLIESY).
3. D24E — acid-to-acid, reverse direction; conservative isosteric charge-preserving change.
4. K34R — base-to-base, charge- and size-conservative; lies in a basic cluster (KRR) where charge preservation matters.
5. N31Q — amide-to-amide, similar size/H-bonding; conservative polar surface substitution.

## Limitations
- ESM-2 scores were not actually computed; the ranking above is a qualitative conservatism prior, not model output.
- No structure, homolog alignment, or conservation profile was available; buried vs exposed positions are inferred only from sequence composition.
- Functionally critical sites (possible nucleic-acid/partner-binding basic patch 34-36; possible turn motif 39-40)
  may not tolerate even conservative swaps.
- Measured fitness for this assay is UNOBSERVABLE here; no E3 evidence exists for any candidate.
