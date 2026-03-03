#!/usr/bin/env python3
"""
Run backend (FastAPI) and frontend (Vite React) together.
Usage: python run.py
Backend: http://127.0.0.1:8000
Frontend: http://localhost:5173 (proxies /api to backend)
Press Ctrl+C to stop both.
"""

import os
import signal
import subprocess
import sys
import time

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root, "frontend")

    if not os.path.isdir(frontend_dir):
        print("Error: frontend/ not found. Run from project root.")
        sys.exit(1)

    backend_cmd = [sys.executable, "app.py"]
    # Frontend: npm run dev (cross-platform)
    if sys.platform == "win32":
        frontend_cmd = "npm run dev"
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=root,
            stdout=sys.stdout,
            stderr=sys.stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
        )
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            shell=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
        )
    else:
        frontend_cmd = ["npm", "run", "dev"]
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=root,
            stdout=sys.stdout,
            stderr=sys.stderr,
            start_new_session=True,
        )
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            stdout=sys.stdout,
            stderr=sys.stderr,
            start_new_session=True,
        )

    print("Backend (FastAPI): http://127.0.0.1:8000")
    print("Frontend (React):  http://localhost:5173")
    print("Press Ctrl+C to stop both.\n")

    def shutdown(sig=None, frame=None):
        for proc in (backend_proc, frontend_proc):
            if proc.poll() is None:
                proc.terminate()
        time.sleep(0.5)
        for proc in (backend_proc, frontend_proc):
            if proc.poll() is None:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    main()
