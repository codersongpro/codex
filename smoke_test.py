#!/usr/bin/env python3
"""End-to-end smoke test for Jian English Exploration Studio."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = int(os.getenv("TEST_PORT", "4181"))
BASE = f"http://127.0.0.1:{PORT}"


def request(path, method="GET", body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", method=method, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.status, json.loads(res.read().decode("utf-8"))


def wait_for_health(timeout=8):
    start = time.time()
    while time.time() - start < timeout:
        try:
            status, payload = request("/health")
            if status == 200 and payload.get("ok"):
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("server health check failed")


def main():
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    proc = subprocess.Popen([sys.executable, "server.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        wait_for_health()

        # 1) Model info
        status, models = request("/api/models")
        assert status == 200 and "models" in models, "models endpoint failed"

        # 2) Login
        status, login = request("/api/login", method="POST", body={"name": "지안이테스트"})
        assert status == 200 and login.get("token"), "login failed"
        token = login["token"]

        # 3) Generate task
        payload = {"topic": "math_science", "mode": "Depth", "live_mode": "Talk with me"}
        status, task = request("/api/generate-task", method="POST", body=payload, token=token)
        assert status == 200, "generate task failed"
        assert task.get("reading", {}).get("text"), "task missing reading text"

        # 4) History
        status, history = request("/api/history", token=token)
        assert status == 200 and len(history.get("items", [])) >= 1, "history endpoint failed"

        print("SMOKE TEST PASS")
        print(f"provider={models.get('provider')} model={','.join(models.get('models', []))}")
        print(f"generated_topic={task.get('topic')} reading_title={task.get('reading', {}).get('title')}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
