import json
E1={r['id']:r['predicted'] for r in json.load(open('analysis/e1_full.json'))}
E3={"IRIS_313.12254":5.0,"IRIS_313.12349":4.7,"IRIS_313.12344":4.6,"IRIS_313.12242":4.5,"IRIS_313.12228":3.8,"IRIS_313.12129":3.8,"IRIS_313.11094":3.6,"IRIS_313.10679":3.6,"IRIS_313.12262":3.4,"IRIS_313.10653":3.4,"IRIS_313.10660":3.4,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,"IRIS_313.12321":3.3,"IRIS_313.12227":3.3,"IRIS_313.11845":3.3,"IRIS_313.12352":3.1,"IRIS_313.12342":3.1,"IRIS_313.12134":2.9,"IRIS_313.12330":2.8}
# measured first: by measured desc, ties by prediction desc
measured=sorted(E3, key=lambda i:(-E3[i], -E1[i]))
unmeasured=sorted([i for i in E1 if i not in E3], key=lambda i:-E1[i])
final=measured+unmeasured
json.dump({"top_ids":final}, open('final_selection.json','w'))
print(len(final))
for k,i in enumerate(final[:30],1):
    print(k,i, ('measured %s'%E3[i]) if i in E3 else ('E1 pred %.3f'%E1[i]))
