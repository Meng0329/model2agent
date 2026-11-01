import json, sys, hashlib, importlib.util
from pathlib import Path
ASSET = Path("/data/mzb/paper2agent/model_assets/rice_gs")
INP = Path("/data/mzb/paper2agent/m2a_data/research/inputs/rice_candidates.json")
spec = importlib.util.spec_from_file_location("rice_infer", ASSET/"infer.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

# 1) verify the model entry reproduces its declared examples exactly
ex = json.loads((ASSET/"examples.json").read_text())
checks=[]
for case in ex["predict_by_ids"]:
    got = mod.predict_by_ids(case["args"]["ids"])
    ok = all(abs(g["predicted"]-o["predicted"])<1e-9 and g["id"]==o["id"] for g,o in zip(got,case["output"]))
    checks.append({"cap":"predict_by_ids","match":ok})
for case in ex["rank_candidates"]:
    got = mod.rank_candidates(case["args"]["ids"])
    ok = all(g["id"]==o["id"] and abs(g["predicted"]-o["predicted"])<1e-9 for g,o in zip(got,case["output"]))
    checks.append({"cap":"rank_candidates","match":ok})
print("example_checks", checks)

ids = json.loads(INP.read_text())["candidates"]
index, X = mod._genotypes()
missing = [i for i in ids if i not in index]
print("n_candidates", len(ids), "n_missing_genotype", len(missing), missing[:10])
have = [i for i in ids if i in index]
rows = mod.predict_by_ids(have)
rows.sort(key=lambda r: -r["predicted"])
sha = hashlib.sha256((ASSET/"infer.py").read_bytes()).hexdigest()
out = {"capability":"rank_candidates","n_requested":len(ids),"n_scored":len(rows),
       "missing":missing,"infer_py_sha256":sha,"example_checks":checks,
       "predictions":[{"rank":k+1,"id":r["id"],"predicted":r["predicted"]} for k,r in enumerate(rows)]}
Path("/data/mzb/paper2agent/results/experiments/S1/rice-R3-rediscovery/B3/rep0/analysis_b3/e1_full.json").write_text(json.dumps(out,indent=1))
import statistics as st
p=[r["predicted"] for r in rows]
print("pred min %.4f max %.4f mean %.4f sd %.4f"%(min(p),max(p),st.mean(p),st.pstdev(p)))
print("top25:")
for r in rows[:25]: print("  %2d %s %.4f"%(rows.index(r)+1,r["id"],r["predicted"]))
print("bottom3:", [(r["id"],round(r["predicted"],3)) for r in rows[-3:]])
