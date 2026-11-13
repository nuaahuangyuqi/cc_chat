"""Manage the background service used by the macOS .command launchers."""

import argparse
import fcntl
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
PROJECT_KEY = hashlib.sha256(os.fsencode(ROOT)).hexdigest()[:16]
RUNTIME = Path(
    os.environ.get("CCASK_RUNTIME_DIR", f"~/Library/Caches/ccask/{PROJECT_KEY}")
).expanduser()
STATE = RUNTIME / "service.json"
LOG = RUNTIME / "service.log"


def signature(pid):
    """Include process start time so a recycled PID cannot match an old record."""
    if not isinstance(pid, int) or pid <= 1:
        return ""
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def running(state):
    expected = state.get("signature")
    return bool(expected and signature(state.get("pid")) == expected)


def read_state():
    try:
        state = json.loads(STATE.read_text())
        return state if isinstance(state, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def open_browser(url):
    if os.environ.get("CCASK_NO_BROWSER") != "1":
        subprocess.run(["/usr/bin/open", url], check=False)


def start():
    state = read_state()
    if running(state):
        url = f"http://127.0.0.1:{state['port']}"
        print(f"CC Ask 已在运行：{url}")
        open_browser(url)
        return
    STATE.unlink(missing_ok=True)
    port = int(os.environ.get("CCASK_PORT", "8765"))
    if not 1 <= port <= 65535:
        raise ValueError("CCASK_PORT 必须在 1 到 65535 之间。")
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(f"端口 {port} 已被占用，请关闭原服务，或设置 CCASK_PORT。") from None

    with LOG.open("a") as log:
        process = subprocess.Popen(
            [sys.executable, "-B", "-m", "ccask", "serve", "--port", str(port)],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    state = {"pid": process.pid, "port": port, "signature": signature(process.pid)}
    if not state["signature"]:
        process.wait(timeout=5)
        raise RuntimeError(f"服务启动失败，请查看日志：{LOG}")
    try:
        STATE.write_text(json.dumps(state))
        STATE.chmod(0o600)
        url = f"http://127.0.0.1:{port}"
        opener = build_opener(ProxyHandler({}))
        for _ in range(75):
            if process.poll() is not None:
                raise RuntimeError(f"服务启动失败，请查看日志：{LOG}")
            try:
                with opener.open(url + "/api/setup", timeout=0.5) as response:
                    ready = json.load(response).get("install_path") == str(ROOT)
                if ready and process.poll() is None:
                    print(f"CC Ask 已启动：{url}\n日志：{LOG}\n双击「关闭.command」停止服务。")
                    open_browser(url)
                    return
            except (URLError, TimeoutError, OSError, ValueError):
                pass
            time.sleep(0.2)
        raise RuntimeError(f"等待服务启动超时，请查看日志：{LOG}")
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        STATE.unlink(missing_ok=True)
        raise


def stop():
    state = read_state()
    if not running(state):
        STATE.unlink(missing_ok=True)
        print("CC Ask 已关闭。")
        return
    try:
        os.kill(state["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(75):
        if not running(state):
            STATE.unlink(missing_ok=True)
            print("CC Ask 已关闭。")
            return
        time.sleep(0.2)
    raise RuntimeError(f"服务仍在退出，请稍后再双击关闭脚本。日志：{LOG}")


def main():
    parser = argparse.ArgumentParser(description="CC Ask 后台服务管理")
    parser.add_argument("action", choices=["start", "stop"])
    args = parser.parse_args()
    try:
        RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (RUNTIME / "launcher.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            (start if args.action == "start" else stop)()
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
