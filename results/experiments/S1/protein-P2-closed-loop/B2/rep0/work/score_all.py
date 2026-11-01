import json
SEQ = "MRKLSDELLIESYFKATEMNLNRDFIELIENEIKRRSLGHIISV"
LP = json.load(open("work/logp_positions.json"))
CAND = json.load(open("/data/mzb/paper2agent/m2a_data/research/inputs/protein_candidates.json"))
cands = CAND["candidates"]

# validate wt residues match sequence
for p, d in LP.items():
    i = int(p) - 1
    assert SEQ[i] == d["wt"], (p, SEQ[i], d["wt"])

# sanity-check against the two reference score_variant outputs
def delta(pos1, wt, mut):
    d = LP[str(pos1)]
    return d[mut] - d[wt]

assert abs(delta(16, "A", "C") - (-6.815322548151016)) < 1e-5, delta(16,"A","C")
assert abs(delta(16, "A", "D") - (-9.651920467615128)) < 1e-5, delta(16,"A","D")

scores = {}
for c in cands:
    wt, pos, mut = c[0], int(c[1:-1]), c[-1]
    assert SEQ[pos-1] == wt, (c, SEQ[pos-1])
    scores[c] = delta(pos, wt, mut)

ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
json.dump(scores, open("work/e1_scores.json","w"), indent=1)
print("n candidates:", len(scores))
print("validated 2 reference score_variant values exactly")
print("\nTop 40 by ESM-2 delta log-likelihood (E1):")
for r,(c,v) in enumerate(ranked[:40],1):
    print(f"{r:2d}. {c:6s} {v:+.4f}")
print("\nBottom 10:")
for c,v in ranked[-10:]:
    print(f"   {c:6s} {v:+.4f}")
