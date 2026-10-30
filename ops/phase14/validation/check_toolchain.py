#!/usr/bin/env python3
"""Read-only local dependency readiness report; never claims infrastructure was tested."""
import json, shutil, socket, subprocess, sys

def probe(command):
    path = shutil.which(command)
    if not path:
        return {"available": False, "reason": "executable not installed"}
    try:
        result = subprocess.run([command, "--version"], text=True, capture_output=True, timeout=8)
        return {"available": result.returncode == 0, "version": (result.stdout or result.stderr).strip()[:160]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

report = {"node": probe("node"), "npm": probe("npm"), "docker": probe("docker"), "psql": probe("psql")}
try:
    socket.getaddrinfo("registry.npmjs.org", 443)
    report["npm_registry_dns"] = {"available": True}
except OSError as exc:
    report["npm_registry_dns"] = {"available": False, "reason": str(exc)}
print(json.dumps(report, indent=2))
sys.exit(0)
