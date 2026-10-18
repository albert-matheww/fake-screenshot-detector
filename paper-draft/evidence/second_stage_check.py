import sys, numpy as np, pickle, time
B="/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend"
sys.path.insert(0,B); sys.path.insert(0,B+"/tools/forge")
import train_text_model as T
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
D="/Users/albertmathew/Desktop/projects/fake-screenshot-detector/data/forge_v1"
tr,va,te=[T.load(D,s) for s in("train","val","test")]
X,y=T.word_table(tr,0)
t=time.time()
m=HistGradientBoostingClassifier(max_iter=900,learning_rate=0.07,max_leaf_nodes=48,min_samples_leaf=25,l2_regularization=1.0,random_state=0,early_stopping=True,validation_fraction=0.1,n_iter_no_change=40).fit(X,y)
print("iters",m.n_iter_,"%.0fs"%(time.time()-t))
def probs(recs): return [ (m.predict_proba(r["X"])[:,1] if len(r["y"]) and r["X"].shape[0]==len(r["y"]) else np.zeros(0)) for r in recs]
pv,pt=probs(va),probs(te)
yv=np.array([r["label"] for r in va]); yt=np.array([r["label"] for r in te])
def topk(p,k): 
    s=np.sort(p)[::-1]; return s[k-1] if len(s)>=k else 0.0
def feats(p,r):
    s=np.sort(p)[::-1] if len(p) else np.zeros(1)
    g=lambda k: s[k-1] if len(s)>=k else 0.0
    lg=lambda v: np.log(np.clip(v,1e-6,1-1e-6)/(1-np.clip(v,1e-6,1-1e-6)))
    return [lg(g(1)),lg(g(2)),lg(g(3)),lg(g(1))-lg(g(2)),np.log1p(len(p)),float((p>0.5).sum()),lg(np.median(p)) if len(p) else -14]
aggs={"max":lambda p:topk(p,1),"top2mean":lambda p:(topk(p,1)+topk(p,2))/2}
for n,f in aggs.items():
    print(n,"val AUC %.3f test AUC %.3f"%(roc_auc_score(yv,[f(p) for p in pv]),roc_auc_score(yt,[f(p) for p in pt])))
Fv=np.array([feats(p,r) for p,r in zip(pv,va)]); Ft=np.array([feats(p,r) for p,r in zip(pt,te)])
lr=LogisticRegression(C=1.0,max_iter=500).fit(Fv,yv); print("stage2 LR (fit on val)  test AUC %.3f"%roc_auc_score(yt,lr.decision_function(Ft)))
# measurable fraction
ed=[r for r in te if r["label"]==1]
has=np.array([bool((r["y"]==1).any()) and r["X"].shape[0]==len(r["y"]) for r in ed])
print("edited word measurable: %.3f"%has.mean(), {d:round(float(np.mean([h for r,h in zip(ed,has) if r["meta"]["degrade"]==d])),2) for d in ("png","jpeg","resize_png","resize_jpeg")})
# AUC restricted to images where the edit is measurable
tm=np.array([ (r["label"]==0) or (bool((r["y"]==1).any()) and r["X"].shape[0]==len(r["y"])) for r in te])
print("AUC on measurable subset (max agg): %.3f"%roc_auc_score(yt[tm],[topk(p,1) for p,k in zip(pt,tm) if k]))
pickle.dump({"pv":pv,"pt":pt},open("/tmp/exp2_probs.pkl","wb"))
