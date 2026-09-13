"""Real HTTP services, independent databases and durable workflow recovery."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

import httpx
import pytest
from scripts.dev_config import ROOT, SERVICES, environment
from pg_cluster import Databases


@pytest.fixture(scope="module")
def cluster(tmp_path_factory):
    data = tmp_path_factory.mktemp("services")
    # Reserve distinct ephemeral ports, then close immediately before startup.
    holders=[]
    for _ in SERVICES:
        sock=socket.socket();sock.bind(("127.0.0.1",0));holders.append(sock)
    ports={s:sock.getsockname()[1] for s,sock in zip(SERVICES,holders)}
    import json
    urls={s:f"http://127.0.0.1:{p}" for s,p in ports.items()}
    children={}
    logs=[]
    envs={}
    databases = Databases(os.environ["UNUM_TEST_PG_DSN"]) if os.environ.get("UNUM_TEST_PG_DSN") else None
    try:
        for s,sock in zip(SERVICES,holders):
            env=environment(s,data) | {"UNUM_SERVICE_URLS":json.dumps(urls)}
            # Only the explicit qualification DSN may select PostgreSQL. An
            # inherited developer PGHOST must never point tests at real data.
            env = {k: v for k, v in env.items() if not k.startswith("PG")}
            owner_env = env
            if databases:
                owner, app = databases.create(s)
                owner_env, env = env | owner, env | app
            envs[s]=env
            subprocess.run([sys.executable,"manage.py","migrate","--noinput"],cwd=ROOT,env=owner_env,check=True,capture_output=True)
            if databases:
                databases.grant(owner_env, env)
            subprocess.run([sys.executable,"manage.py","seed_demo"],cwd=ROOT,env=env,check=True,capture_output=True)
            sock.close()
            log=open(data/(s+".log"),"w");logs.append(log)
            children[s]=subprocess.Popen([sys.executable,"manage.py","runserver",f"127.0.0.1:{ports[s]}","--noreload"],cwd=ROOT,env=env,stdout=log,stderr=log)
        for url in urls.values():
            for attempt in range(100):
                try:
                    if httpx.get(url+"/health").status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.05)
            else:raise RuntimeError("Service failed to start: "+url)
        yield urls,data,children,envs
    finally:
        for sock in holders:sock.close()
        for p in children.values():p.terminate()
        for p in children.values():
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill()
        for log in logs:log.close()
        if databases:
            databases.close()
