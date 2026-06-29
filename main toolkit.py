"""
SAINT BEV DEV TOOLKIT
======================
3 tools in one menu:
1. Archive Auditor  - scan & unpack zip files
2. Execution Profiler - track how code runs
3. Debug Proxy - intercept HTTP requests
"""

import os
import sys
import time
import uuid
import zipfile
import socket
import threading
import functools
import inspect
import logging
import pprint
from datetime import datetime


# ─────────────────────────────────────────────
# TOOL 1: ARCHIVE AUDITOR
# ─────────────────────────────────────────────

ARCHIVE_EXTS = [".zip"]
WORKSPACE = "./workspace_temp"

def setup_workspace():
    os.makedirs(WORKSPACE, exist_ok=True)

def clear_workspace():
    for dirpath, dirs, files in os.walk(WORKSPACE, topdown=False):
        for f in files:
            try:
                os.remove(os.path.join(dirpath, f))
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(dirpath, d))
            except OSError:
                pass

def audit_archives(scan_dir="."):
    setup_workspace()
    results = {}
    for f in os.listdir(scan_dir):
        if any(f.endswith(ext) for ext in ARCHIVE_EXTS):
            path = os.path.join(scan_dir, f)
            results[f] = {"files": [], "errors": []}
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    for member in z.namelist():
                        if ".." not in member:
                            z.extract(member, WORKSPACE)
                            results[f]["files"].append(member)
                            print(f"  [+] Unpacked: {member}")
                        else:
                            results[f]["errors"].append(f"Skipped unsafe path: {member}")
            except zipfile.BadZipFile:
                results[f]["errors"].append("Bad zip file")
    return results

def run_archive_auditor():
    print("\n--- ARCHIVE AUDITOR ---")
    scan_dir = input("Enter directory to scan (press Enter for current): ").strip() or "."
    if not os.path.isdir(scan_dir):
        print("Directory not found.")
        return
    results = audit_archives(scan_dir)
    if not results:
        print("No zip files found.")
    else:
        print(f"\nScanned {len(results)} archive(s):")
        for archive, data in results.items():
            print(f"\n{archive}:")
            print(f"  Files: {len(data['files'])}")
            if data['errors']:
                print(f"  Errors: {data['errors']}")
    clear_workspace()


# ─────────────────────────────────────────────
# TOOL 2: EXECUTION PROFILER
# ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("profiler")

class TraceEvent:
    def __init__(self, fn_name, args, kwargs, result=None, duration=0, error=None):
        self.id = str(uuid.uuid4())[:8]
        self.fn_name = fn_name
        self.args = args
        self.kwargs = kwargs
        self.result = result
        self.duration = duration
        self.error = error
        self.timestamp = datetime.now().isoformat()

    def __repr__(self):
        status = "ERROR" if self.error else "OK"
        return f"[{self.timestamp}] {self.fn_name} ({self.duration:.4f}s) [{status}]"

def profile(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        error = None
        result = None
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            error = e
        finally:
            duration = time.perf_counter() - start
            event = TraceEvent(fn.__name__, args, kwargs, result, duration, error)
            log.info(event)
            if error:
                raise error
        return result
    return wrapper

# Example functions to profile
@profile
def example_fast():
    return sum(range(1000))

@profile
def example_slow():
    time.sleep(0.3)
    return "done"

@profile
def example_error():
    raise ValueError("test error")

def run_profiler():
    print("\n--- EXECUTION PROFILER ---")
    print("Running profiled functions...\n")
    example_fast()
    example_slow()
    try:
        example_error()
    except ValueError:
        pass
    print("\nProfiling complete. Check logs above.")


# ─────────────────────────────────────────────
# TOOL 3: DEBUG PROXY
# ─────────────────────────────────────────────

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8888
LOG_FILE = "proxy_trace.log"

def log_request(data, direction=">>"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {direction} {len(data)} bytes"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
        try:
            f.write(data.decode("utf-8", errors="replace")[:500] + "\n---\n")
        except Exception:
            pass

def handle_client(client_sock):
    try:
        data = client_sock.recv(4096)
        if not data:
            return
        log_request(data, ">> CLIENT")

        # Parse host from HTTP CONNECT or GET
        first_line = data.split(b"\n")[0].decode("utf-8", errors="replace")
        host = "example.com"
        port = 80

        if "CONNECT" in first_line:
            parts = first_line.split(" ")[1].split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 443
            client_sock.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            data = client_sock.recv(4096)
        elif "Host:" in data.decode("utf-8", errors="replace"):
            for line in data.decode("utf-8", errors="replace").split("\r\n"):
                if line.startswith("Host:"):
                    host = line.split(":")[1].strip()
                    break

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.connect((host, port))
        server_sock.send(data)
        log_request(data, f">> {host}:{port}")

        response = server_sock.recv(4096)
        log_request(response, "<< RESPONSE")
        client_sock.send(response)

        server_sock.close()
    except Exception as e:
        print(f"  [proxy error] {e}")
    finally:
        client_sock.close()

def run_proxy():
    print(f"\n--- DEBUG PROXY ---")
    print(f"Listening on {PROXY_HOST}:{PROXY_PORT}")
    print(f"Logging to {LOG_FILE}")
    print("Press Ctrl+C to stop.\n")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((PROXY_HOST, PROXY_PORT))
        server.listen(5)
        while True:
            client, addr = server.accept()
            print(f"  [+] Connection from {addr}")
            t = threading.Thread(target=handle_client, args=(client,))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
    finally:
        server.close()


# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────

def main():
    while True:
        print("\n" + "="*40)
        print("  SAINT BEV DEV TOOLKIT")
        print("="*40)
        print("  1. Archive Auditor")
        print("  2. Execution Profiler")
        print("  3. Debug Proxy")
        print("  Q. Quit")
        print("="*40)
        choice = input("Select: ").strip().lower()

        if choice == "1":
            run_archive_auditor()
        elif choice == "2":
            run_profiler()
        elif choice == "3":
            run_proxy()
        elif choice == "q":
            print("Later.")
            sys.exit(0)
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
