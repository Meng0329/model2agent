import json

rank = json.load(open("full_rank.json"))
pred = {r["id"]: r["predicted"] for r in rank}

meas = {
 "IRIS_313.12254":5.0,"IRIS_313.12344":4.6,"IRIS_313.12242":4.5,"IRIS_313.12228":3.8,
 "IRIS_313.11094":3.6,"IRIS_313.12262":3.4,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,
 "IRIS_313.12352":3.1,"IRIS_313.12342":3.1,"IRIS_313.11086":3.1,"IRIS_313.12330":2.8,
 "IRIS_313.10883":2.7,"IRIS_313.12015":2.6,"IRIS_313.10001":2.6,"IRIS_313.9461":2.2,
 "IRIS_313.11905":2.0,"IRIS_313.11218":1.2,
 "IRIS_313.10679":3.6,"IRIS_313.12321":3.3,"IRIS_313.12134":2.9,"IRIS_313.12349":4.7,
 "IRIS_313.12129":3.8,"IRIS_313.10653":3.4,"IRIS_313.12227":3.3,"IRIS_313.10660":3.4,
 "IRIS_313.11845":3.3,"IRIS_313.11705":2.9,"IRIS_313.12251":2.5,"IRIS_313.12049":2.0,
}
# sort by measured desc, tie by model pred desc
order = sorted(meas, key=lambda c: (-meas[c], -pred[c]))
print("All 30 measured, ranked:")
for i, c in enumerate(order, 1):
    print(f"{i:2d} {c} meas={meas[c]:.1f} pred={pred[c]:.3f}")
top10 = order[:10]
print("\nFINAL TOP-10:")
for i, c in enumerate(top10, 1):
    print(f"{i:2d} {c} meas={meas[c]:.1f}")
json.dump({"top_ids": top10}, open("final_selection.json", "w"), indent=2)
print("\nwritten final_selection.json")
