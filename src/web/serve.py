"""本地预览 Web 情报流（先构建 JSON，再启动静态服务）。"""

import http.server
import socketserver
import webbrowser
from functools import partial
from pathlib import Path

from src.web.build import main as build_main


def main(port: int = 8080) -> None:
    build_main()
    web_dir = Path(__file__).resolve().parents[2] / "web"

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            if str(args[1]).startswith("4") or str(args[1]).startswith("5"):
                super().log_message(format, *args)

    handler = partial(QuietHandler, directory=str(web_dir))

    httpd = None
    for candidate in range(port, port + 10):
        try:
            httpd = socketserver.TCPServer(("", candidate), handler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        raise OSError(f"无法在 {port}–{port + 9} 端口启动预览服务")

    with httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"Scout Brief 预览: {url}")
        print("Ctrl+C 结束")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
