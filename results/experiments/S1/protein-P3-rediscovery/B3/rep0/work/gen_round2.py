import json
from blosum62 import bscore
d=json.load(open('/data/mzb/paper2agent/m2a_data/research/inputs/protein_candidates.json'))
seq=d['sequence']; cands=d['candidates']
from collections import defaultdict
bypos=defaultdict(list)
for c in cands:
    pos=int(c[1:-1]); bypos[pos].append(c)
for p in bypos:
    bypos[p].sort(key=lambda c: -bscore(c[0], c[-1]))  # desc BLOSUM
# top positions by probe delta
top_pos=[19,22,2,23,14,12,35,44,24,40,42,41]
# For top 8 positions take ranks 2-6 (indices1-5), for next 4 take ranks 2-4 (indices1-3)
sel=[]
for i,p in enumerate(top_pos):
    rl=bypos[p]
    if i<8:
        take=rl[1:6]
    else:
        take=rl[1:4]
    for c in take:
        sel.append((p,c))
print("n selected", len(sel))
for p,c in sel:
    print(c, "blosum", bscore(c[0],c[-1]))
json.dump([c for _,c in sel], open('round2_ids.json','w'))
