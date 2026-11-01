import json, importlib.util, sys
from pathlib import Path
ASSET = Path("/data/mzb/paper2agent/model_assets/rice_gs/infer.py")
spec = importlib.util.spec_from_file_location("rice_infer", ASSET)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
cands = json.load(open("/data/mzb/paper2agent/m2a_data/research/inputs/rice_candidates.json"))["candidates"]
res = mod.predict_by_ids(cands)
print("n:", len(res))
# sanity: no missing
assert all("predicted" in r for r in res)
preds = {r["id"]: r["predicted"] for r in res}
json.dump(preds, open("predictions.json","w"))
# ranked
ranked = sorted(preds.items(), key=lambda kv: -kv[1])
json.dump([{"id":i,"predicted":v} for i,v in ranked], open("ranked_e1.json","w"), indent=0)
print("top 20 by model:")
for i,v in ranked[:20]:
    print(f"  {i}  {v:.4f}")
print("bottom 5:")
for i,v in ranked[-5:]:
    print(f"  {i}  {v:.4f}")
print("pred min/max:", min(preds.values()), max(preds.values()))
print("mean:", sum(preds.values())/len(preds))
