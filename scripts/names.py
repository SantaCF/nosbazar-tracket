import json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
def one(v):
    t=time.time(); b={"server":1,"filters":{"index":0,"category":0,"sub_category":0,"level":0,"rare":0,"upgrade":0,"order":0,"vnum":[v]},"lang":"IT","name":""}
    try: urllib.request.urlopen(urllib.request.Request("https://nosbazar.com/api/search",data=json.dumps(b).encode(),headers={"User-Agent":UA,"Content-Type":"application/json"}),timeout=60).read(); return round(time.time()-t,1)
    except Exception as e: return "ERR %s %.0f"%(e,time.time()-t)
V=[1013,1014,1028,1029,1030,1012,1092,2282,1242,2196,1016,1027]
for n in (1,4,8,12):
    t=time.time()
    with ThreadPoolExecutor(n) as ex: r=list(ex.map(one,V[:max(n,4)]))
    print("workers",n,"richieste",len(r),"tempi",r,"totale",round(time.time()-t,1),flush=True)
