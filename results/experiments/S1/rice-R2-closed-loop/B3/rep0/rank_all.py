import json, sys
import importlib.util

ASSET = "/data/mzb/paper2agent/model_assets/rice_gs"
spec = importlib.util.spec_from_file_location("m2a_infer", ASSET + "/infer.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

cands = json.load(open("/data/mzb/paper2agent/m2a_data/research/inputs/rice_candidates.json"))["candidates"]
rank = m.rank_candidates(cands)
json.dump(rank, open("full_rank.json", "w"))
print("total", len(rank))
print("trait:", m.trait())
for r in rank[:60]:
    print(f"{r['predicted']:.4f} {r['id']}")
