import socket, time, subprocess
t=time.time(); ai=socket.getaddrinfo("nosbazar.com",443); print("dns",round(time.time()-t,1),sorted({(a[0].name,a[4][0]) for a in ai}),flush=True)
for fam in (socket.AF_INET, socket.AF_INET6):
    for a in {x[4] for x in ai if x[0]==fam}:
        s=socket.socket(fam); s.settimeout(30); t=time.time()
        try: s.connect(a); print("connect",fam.name,a[0],round(time.time()-t,2),"s",flush=True)
        except Exception as e: print("connect",fam.name,a[0],"ERR",round(time.time()-t,1),e,flush=True)
        s.close()
for flag in ("-4","-6"):
    print(subprocess.run(["curl",flag,"-s","-o","/dev/null","-w",flag+" dns %{time_namelookup} conn %{time_connect} tls %{time_appconnect} first %{time_starttransfer} tot %{time_total} code %{http_code}\n","--max-time","40","https://nosbazar.com/api/servers"],capture_output=True,text=True).stdout,flush=True)
for i in range(3):
    print(subprocess.run(["curl","-4","-s","-o","/dev/null","-w","again tot %{time_total} first %{time_starttransfer}\n","--max-time","40","https://nosbazar.com/api/servers"],capture_output=True,text=True).stdout,flush=True)
