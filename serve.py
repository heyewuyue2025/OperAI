"""OperAI 品牌首页 & Agent 页面静态服务。

用法: python serve.py  →  http://127.0.0.1:8080
"""
from __future__ import annotations

import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
PORT = 8080

WORKBENCH = "http://127.0.0.1:8501"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/app", "/app/"):
            self.send_response(302)
            self.send_header("Location", WORKBENCH)
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main() -> None:
    if not FRONTEND.is_dir():
        raise SystemExit(f"缺少 frontend 目录: {FRONTEND}")
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"OperAI: http://127.0.0.1:{PORT}/")
        print(f"  总览   → /")
        print(f"  数据   → /d-agent.html")
        print(f"  内容   → /c-agent.html")
        print(f"  工作台 → {WORKBENCH}  (/app)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
