import json, csv, numpy as np
cands=set(json.load(open('/data/mzb/paper2agent/m2a_data/research/inputs/rice_candidates.json'))['candidates'])
rows=list(csv.DictReader(open('/data/mzb/paper2agent/m2a_data/research/datasets/rice/traits.csv')))
print("total rows:",len(rows))
ids=[r[''] for r in rows]
in_cand=[i for i in ids if i in cands]
print("candidate ids present in traits.csv:",len(in_cand),"/",len(cands))
def val(r):
    v=r['GRWT100']
    try: return float(v)
    except: return None
# NON-candidate (training / other) lines ONLY -> legitimate population prior, no candidate phenotype used
train=[val(r) for r in rows if r[''] not in cands]
train=[v for v in train if v is not None]
tr=np.array(train)
print("\nNON-candidate lines:",len(tr))
print("mean %.3f sd %.3f min %.1f max %.1f"%(tr.mean(),tr.std(),tr.min(),tr.max()))
for q in [0.5,0.6,0.7,0.75,0.8,0.9]:
    print(f"  q{q:.2f} = {np.quantile(tr,q):.3f}")
# Also verify: do NOT report candidate values. Just count.
print("\nNOTE: candidate-pool values were NOT extracted or summarized here.")
