"""Native macOS shell. The backend shares this process and cannot be orphaned."""

import contextlib
import fcntl
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from ccask.config import Settings

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
LOG_DIR = Path.home() / "Library/Logs/CC Ask"


class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Third party exceptions can contain request bodies or credentials.
        event = record.getMessage() if record.name == "ccask.desktop" else "runtime event"
        return f"{self.formatTime(record)} {record.levelname} {record.name}: {event}"


def configure_logs():
    LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = LOG_DIR / "desktop.log"
    handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3)
    path.chmod(0o600)
    handler.setFormatter(SafeFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "pywebview"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def alert(message):
    from AppKit import NSAlert, NSApplication

    application = NSApplication.sharedApplication()
    application.setActivationPolicy_(0)
    application.finishLaunching()
    application.activateIgnoringOtherApps_(True)
    box = NSAlert.alloc().init()
    box.setMessageText_("CC Ask")
    box.setInformativeText_(message + f"\n\n日志：{LOG_DIR}/desktop.log")
    box.addButtonWithTitle_("好")
    box.addButtonWithTitle_("查看日志")
    box.window().makeKeyAndOrderFront_(None)
    if box.runModal() == 1001:
        subprocess.run(["/usr/bin/open", str(LOG_DIR)], check=False)


def activate(pid):
    from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if app:
        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)


class Instance:
    def __init__(self, data_dir):
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (data_dir / "desktop.lock").open("a+")
        self.listener = None
        self.stopped = threading.Event()

    def acquire(self):
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.seek(0)
            try:
                state = json.loads(self.lock.read())
                with socket.create_connection(("127.0.0.1", state["port"]), timeout=2) as client:
                    client.sendall(state["token"].encode())
                activate(state["pid"])
            except (OSError, ValueError, KeyError):
                alert("CC Ask 正在启动，请稍候再打开。")
            return False
        import secrets

        self.token = secrets.token_hex(32)
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(4)
        self.listener.settimeout(0.5)
        self.lock.seek(0)
        self.lock.truncate()
        json.dump(
            {"pid": os.getpid(), "port": self.listener.getsockname()[1], "token": self.token},
            self.lock,
        )
        self.lock.flush()
        os.fchmod(self.lock.fileno(), 0o600)
        return True

    def listen(self, window):
        while not self.stopped.is_set():
            try:
                client, _ = self.listener.accept()
                with client:
                    client.settimeout(1)
                    token = client.recv(256).decode()
                    if token == self.token:
                        window.restore()
                        window.show()
                        activate(os.getpid())
            except (OSError, UnicodeError):
                continue

    def close(self):
        self.stopped.set()
        if self.listener:
            self.listener.close()
        self.lock.close()


class Backend:
    def __init__(self, settings):
        self.settings = settings
        self.lock = None
        self.sock = None
        self.server = None
        self.thread = None
        self.app = None
        self.active = 0
        self.active_lock = threading.Lock()

    def start(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("127.0.0.1", PORT))
        except OSError:
            self.sock.close()
            self.sock = None
            try:
                with build_opener(ProxyHandler({})).open(URL + "/api/health", timeout=1) as r:
                    existing = json.load(r).get("status") == "ok"
            except (OSError, ValueError):
                existing = False
            if existing:
                raise RuntimeError(
                    "127.0.0.1:8765 已有 CLI 或其他 CC Ask 服务。请先用原来的关闭方式停止它，再打开 App。"
                ) from None
            raise RuntimeError(
                "127.0.0.1:8765 被其他程序占用。请退出占用端口的程序，再打开 CC Ask。"
            ) from None
        self.sock.listen(128)
        self.lock = (self.settings.data_dir / "service.lock").open("a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("此数据目录已有 CLI 服务运行，请先停止原服务。") from None
        import uvicorn

        from ccask.web import create_app

        self.app = create_app(self.settings)

        @self.app.middleware("http")
        async def count_calls(request, call_next):
            tracked = request.method == "POST" and request.url.path.endswith(("/ask", "/test"))
            if tracked:
                with self.active_lock:
                    self.active += 1
            try:
                return await call_next(request)
            finally:
                if tracked:
                    with self.active_lock:
                        self.active -= 1

        self.server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                host="127.0.0.1",
                port=PORT,
                access_log=False,
                log_config=None,
                loop="asyncio",
                http="h11",
                ws="none",
                timeout_graceful_shutdown=1,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.sock]}, daemon=True
        )
        self.thread.start()
        opener = build_opener(ProxyHandler({}))
        for _ in range(150):
            if not self.thread.is_alive():
                raise RuntimeError("本地服务启动失败，请查看日志。")
            try:
                with opener.open(URL + "/api/health", timeout=0.3) as r:
                    if json.load(r).get("status") == "ok":
                        logging.getLogger("ccask.desktop").info("backend_ready")
                        return
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise RuntimeError("本地服务启动超时，请查看日志。")

    def stop(self):
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=4)
        if self.sock:
            self.sock.close()
            self.sock = None
        if self.lock:
            self.lock.close()
            self.lock = None


def codex_guard():
    """Forward stdio; the parent's EOF also terminates Codex after a crash/SIGKILL."""
    from ccask.runtime import executable_env

    executable, codex_dir = sys.argv[2:4]
    proc = subprocess.Popen(
        [executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=sys.stdout.buffer,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={**executable_env(executable), "CODEX_HOME": codex_dir},
    )
    try:
        for line in sys.stdin.buffer:
            proc.stdin.write(line)
            proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--codex-guard":
        codex_guard()
        return
    configure_logs()
    instance = None
    backend = None
    menu_bar = None
    try:
        settings = Settings.from_env()
        instance = Instance(settings.data_dir)
        if not instance.acquire():
            return
        backend = Backend(settings)
        backend.start()
        import webview
        from webview.menu import Menu, MenuAction

        window = webview.create_window(
            "CC Ask",
            URL,
            width=1380,
            height=900,
            min_size=(1000, 680),
            frameless=True,
            easy_drag=False,
        )

        def native_chrome():
            nonlocal menu_bar
            from AppKit import (
                NSFullSizeContentViewWindowMask,
                NSWindowCloseButton,
                NSWindowMiniaturizeButton,
                NSWindowTitleHidden,
                NSWindowZoomButton,
            )

            native = window.native
            native.setStyleMask_(native.styleMask() | NSFullSizeContentViewWindowMask)
            native.setTitleVisibility_(NSWindowTitleHidden)
            native.setTitlebarAppearsTransparent_(True)
            native.setMovableByWindowBackground_(True)
            for button in (NSWindowCloseButton, NSWindowMiniaturizeButton, NSWindowZoomButton):
                native.standardWindowButton_(button).setHidden_(False)
            from .desktop_menu import MenuBarController

            menu_bar = MenuBarController.alloc().initWithContext_(
                (window, settings, backend.app.state.service.db, backend.app.state.usage)
            )

        window.events.before_show += native_chrome

        def closing():
            if backend.active:
                # Already on Cocoa's main thread: dispatching a pywebview dialog
                # to that same thread would deadlock Command+Q and window close.
                from AppKit import NSAlert, NSAlertFirstButtonReturn

                prompt = NSAlert.alloc().init()
                prompt.setMessageText_("退出 CC Ask？")
                prompt.setInformativeText_("有正在进行的调用，退出会中断请求。确定退出吗？")
                prompt.addButtonWithTitle_("继续使用")
                prompt.addButtonWithTitle_("退出并中断")
                if prompt.runModal() == NSAlertFirstButtonReturn:
                    return False
            # Cocoa's Command+Q terminates immediately after this callback.
            backend.stop()
            if menu_bar:
                menu_bar.stop()
            logging.getLogger("ccask.desktop").info("app_closed")
            return True

        window.events.closing += closing
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: window.destroy())

        def show_monitor():
            from PyObjCTools import AppHelper

            if menu_bar:
                AppHelper.callAfter(menu_bar.item.button().performClick_, None)

        def monitor_preferences():
            from PyObjCTools import AppHelper

            if menu_bar:
                AppHelper.callAfter(menu_bar.showSettings_, None)

        menus = [
            Menu(
                "__app__",
                [
                    MenuAction("菜单栏用量", show_monitor),
                    MenuAction("监控设置…", monitor_preferences),
                    MenuAction(
                        "查看日志…",
                        lambda: subprocess.run(["/usr/bin/open", str(LOG_DIR)], check=False),
                    ),
                    MenuAction("退出", window.destroy),
                ],
            )
        ]
        threading.Thread(target=instance.listen, args=(window,), daemon=True).start()
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.start(
            gui="cocoa",
            menu=menus,
            private_mode=True,
            localization={
                "global.quit": "退出",
                "global.cancel": "取消",
                "global.ok": "好",
                "cocoa.menu.quit": "退出",
                "cocoa.menu.about": "关于",
            },
        )
    except Exception as exc:  # noqa: BLE001 - final native error boundary
        logging.getLogger("ccask.desktop").error("startup_failed_%s", type(exc).__name__)
        message = (
            str(exc) if isinstance(exc, RuntimeError) else "启动失败，请查看日志后重新打开 App。"
        )
        alert(message)
    finally:
        if backend:
            backend.stop()
        if instance:
            instance.close()


if __name__ == "__main__":
    main()
