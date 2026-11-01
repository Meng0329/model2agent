import sys; sys.path.insert(0,"/home/test/.local/lib/python3.12/site-packages")
import json
rev=json.load(open('/data/mzb/paper2agent/results/experiments/S1/rice-R2-closed-loop/B3/rep0/revised2.json'))
top=[r['id'] for r in rev[:10]]
print("TOP-10 (posterior P>Q75 desc, then est desc, model-rank tie-break):")
for i,r in enumerate(rev[:10],1):
    print(f"{i:2d} {r['id']} est={r['est']:.2f} P={r['p']:.3f} measured={r['measured']}")
json.dump({"top_ids":top}, open('/data/mzb/paper2agent/results/experiments/S1/rice-R2-closed-loop/B3/rep0/final_selection.json','w'), indent=2)
print("\nfinal_selection.json:",top)
# sanity: all top-10 measured, min value
mins=min(r['est'] for r in rev[:10])
print("min top-10 est:",mins, " (Q75 upper CI 2.622)")
