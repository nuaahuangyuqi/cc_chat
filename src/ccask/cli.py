import argparse
import fcntl
import json
import os
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(prog="ccask", description="CC Switch 项目调用与用量面板")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="启动本地网页和调用服务")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="启动后打开网页")
    serve.add_argument("--data-dir", help="CC Ask 数据目录")
    serve.add_argument("--cc-dir", help="CC Switch 数据目录")
    serve.add_argument("--codex-dir", help="Codex 配置目录")
    sub.add_parser("doctor", help="检查 CC Switch 连接")
    args = parser.parse_args()
    if args.command == "serve":
        for arg, env in [
            ("data_dir", "CCASK_DATA_DIR"),
            ("cc_dir", "CCASK_CC_DIR"),
            ("codex_dir", "CCASK_CODEX_DIR"),
        ]:
            value = getattr(args, arg)
            if value:
                os.environ[env] = value
        import uvicorn

        from .config import Settings
        from .web import create_app

        data_dir = Settings.from_env().data_dir
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = (data_dir / "service.lock").open("a+")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "该数据目录已经有 CC Ask 服务运行，请使用现有服务。\n")
        if args.open:
            threading.Timer(1.0, webbrowser.open, args=(f"http://127.0.0.1:{args.port}",)).start()
        try:
            uvicorn.run(create_app(), host="127.0.0.1", port=args.port, workers=1, access_log=False)
        finally:
            lock.close()
    else:
        import asyncio

        from .ccswitch import CCSwitch
        from .config import Settings

        print(
            json.dumps(
                asyncio.run(CCSwitch(Settings.from_env()).status()), ensure_ascii=False, indent=2
            )
        )


if __name__ == "__main__":
    main()
