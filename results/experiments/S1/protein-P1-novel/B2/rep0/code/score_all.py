"""Score all single mutants in the candidate file with the pinned ESM-2 650M
masked-marginal delta log-likelihood, using the asset's own infer module.

Writes scores.json  (E1 model predictions, NOT measurements).
"""
import importlib.util
import json
import sys

import torch

ASSET = "/data/mzb/paper2agent/model_assets/esm2_variant/infer.py"
CAND = "/data/mzb/paper2agent/m2a_data/research/inputs/protein_candidates.json"
OUT = sys.argv[1] if len(sys.argv) > 1 else "scores.json"

spec = importlib.util.spec_from_file_location("esm2_infer", ASSET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

data = json.load(open(CAND))
seq = data["sequence"]
cands = data["candidates"]
AA = "ACDEFGHIKLMNPQRSTVWY"

# Parse mutants, group by position
by_pos = {}
for c in cands:
    wt, pos, mut = c[0], int(c[1:-1]) - 1, c[-1]
    assert seq[pos] == wt, (c, seq[pos])
    by_pos.setdefault(pos, []).append((c, wt, mut))

tok, model = mod._load()

results = {}
for pos in sorted(by_pos):
    logps = mod._residue_logprobs(seq, [pos])[0]
    for c, wt, mut in by_pos[pos]:
        results[c] = float(logps[mut] - logps[wt])

# sanity check against shipped examples
ex = json.load(open("/data/mzb/paper2agent/model_assets/esm2_variant/examples.json"))
checks = []
for e in ex["score_variant"]:
    m = e["args"]["mutations"]
    checks.append((m, e["output"], results.get(m)))

json.dump({"sequence": seq, "scores": results}, open(OUT, "w"), indent=1)
print("n_scored", len(results))
for m, ref, got in checks:
    print(f"check {m}: entry={ref:.6f} mine={got:.6f} diff={abs(ref-got):.2e}")
print("top10", sorted(results.items(), key=lambda kv: -kv[1])[:10])
print("bottom5", sorted(results.items(), key=lambda kv: kv[1])[:5])
