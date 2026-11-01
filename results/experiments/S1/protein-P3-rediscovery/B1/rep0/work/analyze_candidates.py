import json, sys
from collections import defaultdict

path = sys.argv[1]
d = json.load(open(path))
seq = d["sequence"]
cands = d["candidates"]
AA = "ACDEFGHIKLMNPQRSTVWY"
by_pos = defaultdict(list)
for c in cands:
    wt, pos, mut = c[0], int(c[1:-1]), c[-1]
    by_pos[pos].append(mut)
print("sequence:", seq, "len", len(seq))
print("n candidates:", len(cands), "n positions:", len(by_pos))
total = 0
for p in sorted(by_pos):
    muts = sorted(set(by_pos[p]), key=lambda a: AA.index(a))
    total += len(muts)
    print(f"pos {p:2d} wt={seq[p-1]} n={len(muts):2d} {''.join(muts)}")
print("total listed:", total)
# consistency: must be single mutants matching WT
bad = [c for c in cands if seq[int(c[1:-1])-1] != c[0]]
print("wt-mismatch candidates:", bad[:10], "count", len(bad))
# positions present
print("missing positions:", [p for p in range(1,len(seq)+1) if p not in by_pos])
