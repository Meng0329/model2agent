import json
E=json.load(open("analysis_b3/e1_full.json"))
pred={r["id"]:r["predicted"] for r in E["predictions"]}
meas=json.load(open("analysis_b3/calib.json"))["measured"]
measured_sorted=sorted(meas, key=lambda i:(-meas[i], -pred[i]))
unqueried=sorted([i for i in pred if i not in meas], key=lambda i:-pred[i])
top=measured_sorted+unqueried
assert len(top)==904 and len(set(top))==904
json.dump({"top_ids":top}, open("final_selection.json","w"), indent=1)
print("top10:",[(i,meas.get(i),round(pred[i],3)) for i in top[:10]])
print("n",len(top),"total_unique",len(set(top)))
