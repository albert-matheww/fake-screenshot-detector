import sys, numpy as np
B="/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend"
sys.path.insert(0,B); sys.path.insert(0,B+"/tools/forge")
import train_text_model as T
from sklearn.metrics import roc_auc_score
D="/Users/albertmathew/Desktop/projects/fake-screenshot-detector/data/forge_v6"
tr,va,te=[T.load(D,s) for s in("train","val","test")]
isc=lambda r: r["label"]==1 and r["meta"].get("op")=="chrome_patch"
isp=lambda r: r["label"]==1 and r["meta"].get("op")!="chrome_patch"
auth_te=[r for r in te if r["label"]==0]
def run(name,keep):
    sub=[r for r in tr if r["label"]==0 or keep(r)]
    X,y,w=T.word_table_w(sub); m=T.fit(X,y,sample_weight=w)
    out=[]
    for tname,tk in (("Pillow edits",isp),("Chrome edits",isc)):
        rs=auth_te+[r for r in te if tk(r)]
        s=T.image_scores(m,rs); y_=T.edit_labels(rs)
        out.append(f"{tname}: AUC {roc_auc_score(y_,s):.3f}")
    print(f"trained on {name:14s} -> test on  "+"  |  ".join(out),flush=True)
run("Pillow only",isp); run("Chrome only",isc); run("both engines",lambda r:True)
