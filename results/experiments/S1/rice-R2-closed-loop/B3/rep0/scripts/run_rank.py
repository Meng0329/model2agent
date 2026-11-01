import json, sys, importlib.util, os
os.environ.setdefault("PYTHONNOUSERSITE","")
sys.path.insert(0,"/home/test/.local/lib/python3.12/site-packages")
ASSET="/data/mzb/paper2agent/model_assets/rice_gs"
spec=importlib.util.spec_from_file_location("m2a_infer", ASSET+"/infer.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ids=json.load(open(sys.argv[1]))
rank=m.rank_candidates(ids)
json.dump(rank, open(sys.argv[2],"w"))
print("total",len(rank),"trait",m.trait())
for r in rank[:55]:
    print(f"{r['predicted']:.4f} {r['id']}")
