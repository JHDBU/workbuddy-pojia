#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workbuddy破甲 · 本地控制面板（纯标准库，只监听 127.0.0.1）

用法：
  python scripts/panel.py                # 自动选端口并打开浏览器
  python scripts/panel.py --port 8301
  python scripts/panel.py --no-open      # 不自动开浏览器（调试用）

面板按钮驱动 scripts/pojia.py 的全部子命令：
  doctor / status / apply --dry-run / apply / restart
  gate status / gate on / gate off
  revert / persona
写入类操作前端有二次确认。restart 会关闭 WorkBuddy 进程（正在进行的会话随进程终止，属预期）。
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
POJIA = SCRIPTS / "pojia.py"
ROOT = SCRIPTS.parent

# 面板按钮 → pojia.py 参数（白名单，未列出的命令不接受）
ACTIONS: dict[str, list[str]] = {
    "doctor":      ["doctor"],
    "status":      ["status"],
    "dry":         ["apply", "--dry-run"],
    "apply":       ["apply"],
    "restart":     ["restart"],
    "revert":      ["revert"],
    "persona":     ["persona"],
    "gate-status": ["gate", "status"],
    "gate-on":     ["gate", "on"],
    "gate-off":    ["gate", "off"],
}


def run_action(action: str, install: str, data: str) -> dict:
    """同步执行 pojia.py 子命令，捕获 stdout/stderr 返回 JSON。"""
    args = [sys.executable, str(POJIA), *ACTIONS[action]]
    if install:
        args += ["-i", install]
    if data:
        args += ["-d", data]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        p = subprocess.run(
            args, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=600, cwd=str(ROOT), env=env,
        )
        out = p.stdout or ""
        if p.stderr:
            out += "\n[stderr]\n" + p.stderr
        return {"ok": p.returncode == 0, "code": p.returncode, "output": out.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -1, "output": "命令超时（600 秒）"}


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>workbuddy破甲 · 控制面板</title>
<style>
  :root{--fg:#1f2328;--muted:#57606a;--line:#d0d7de;--bg:#fff;--soft:#f6f8fa;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;}
  header{padding:18px 24px 12px;border-bottom:1px solid var(--line);}
  h1{margin:0;font-size:18px;font-weight:600;}
  header p{margin:3px 0 0;color:var(--muted);font-size:12px;}
  main{padding:16px 24px 24px;max-width:920px;}
  .params{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 16px;}
  .params label{font-size:12px;color:var(--muted);}
  .params input{margin-top:4px;border:1px solid var(--line);border-radius:6px;
                padding:5px 8px;font:12px ui-monospace,Consolas,monospace;width:300px;}
  .group{margin:0 0 14px;}
  .group h2{font-size:12px;font-weight:600;color:var(--muted);margin:0 0 8px;}
  .row{display:flex;flex-wrap:wrap;gap:8px;}
  button{appearance:none;border:1px solid var(--line);background:var(--soft);
         color:var(--fg);padding:6px 14px;border-radius:6px;cursor:pointer;
         font:inherit;font-size:13px;}
  button:hover{background:#eef1f4;}
  button:disabled{opacity:.55;cursor:default;}
  button.primary{color:#1a7f37;border-color:#a3c9a8;}
  button.primary:hover{background:#f0f7f1;}
  button.danger{color:#cf222e;border-color:#d5a3a8;}
  button.danger:hover{background:#fff0f0;}
  #out{border:1px solid var(--line);border-radius:8px;background:var(--soft);
       padding:12px 14px;min-height:220px;max-height:62vh;overflow:auto;
       font:12px/1.55 ui-monospace,"Cascadia Mono",Consolas,monospace;
       white-space:pre-wrap;word-break:break-all;}
  .meta{color:var(--muted);}
</style>
</head>
<body>
<header>
  <h1>workbuddy破甲 · 控制面板</h1>
  <p>本机运行 · 仅监听 127.0.0.1 · 按钮直达 scripts/pojia.py（写入类有二次确认）</p>
</header>
<main>
  <div class="params">
    <div>
      <label>安装目录（留空自动探测）</label><br>
      <input id="install" placeholder="D:\\WorkBuddy" spellcheck="false">
    </div>
    <div>
      <label>数据目录（留空用默认）</label><br>
      <input id="data" placeholder="%USERPROFILE%\\.workbuddy" spellcheck="false">
    </div>
  </div>
  <div class="group">
    <h2>常规</h2>
    <div class="row">
      <button data-act="doctor">体检</button>
      <button data-act="status">状态</button>
      <button data-act="dry">演练（不写盘）</button>
      <button data-act="apply" class="primary">写入补丁</button>
      <button data-act="restart" class="primary">关进程 → 写入 → 重启</button>
    </div>
  </div>
  <div class="group">
    <h2>L3 命令闸门（全局，重启后生效）</h2>
    <div class="row">
      <button data-act="gate-status">闸门状态</button>
      <button data-act="gate-on" class="danger">gate on</button>
      <button data-act="gate-off">gate off</button>
    </div>
  </div>
  <div class="group">
    <h2>维护</h2>
    <div class="row">
      <button data-act="persona">人格文本</button>
      <button data-act="revert" class="danger">全部还原（.pojia.bak）</button>
    </div>
  </div>
  <div id="out"><span class="meta">就绪。点上面任一按钮执行，输出显示在这里。</span></div>
</main>
<script>
  var OUT = document.getElementById('out');
  var CONFIRM = {
    'apply':    '确认写入补丁？幂等，自动备份 .pojia.bak。',
    'restart':  '确认执行？会先关闭 WorkBuddy——正在客户端里的对话会随进程终止。',
    'revert':   '确认从 .pojia.bak 全部还原？',
    'gate-on':  '确认开启 L3 闸门？全局放行，需重启 WorkBuddy 生效。',
    'gate-off': '确认关闭 L3 闸门并还原 mjs 原版？'
  };
  function log(line){
    OUT.textContent += line + '\\n';
    OUT.scrollTop = OUT.scrollHeight;
  }
  document.querySelectorAll('button[data-act]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var act = btn.dataset.act;
      if (CONFIRM[act] && !confirm(CONFIRM[act])) return;
      var t = new Date().toLocaleTimeString();
      OUT.textContent = '';
      log('[' + t + '] $ pojia ' + act + '  …运行中');
      document.querySelectorAll('button').forEach(function(b){ b.disabled = true; });
      fetch('/api/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          action: act,
          install: document.getElementById('install').value,
          data: document.getElementById('data').value
        })
      }).then(function(r){ return r.json(); }).then(function(j){
        OUT.textContent = '';
        log('[' + t + '] $ pojia ' + act + '  → 退出码 ' + j.code + (j.ok ? '  ✓' : '  ✗'));
        log('──────────────────────────');
        log(j.output || '(无输出)');
      }).catch(function(e){
        OUT.textContent = '';
        log('请求失败：' + e);
      }).finally(function(){
        document.querySelectorAll('button').forEach(function(b){ b.disabled = false; });
      });
    });
  });
</script>
</body>
</html>
"""


class Panel(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):  # 安静模式，不刷控制台
        pass

    def _send(self, code: int, body, ctype: str):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE, "text/html")
        elif path == "/api/health":
            self._send(200, json.dumps({"ok": True}), "application/json")
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            self._send(404, "not found", "text/plain")
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            action = str(req.get("action", ""))
            if action not in ACTIONS:
                self._send(400, json.dumps({"ok": False, "code": -1, "output": "未知操作: " + action}), "application/json")
                return
            result = run_action(
                action,
                str(req.get("install", "")).strip(),
                str(req.get("data", "")).strip(),
            )
            self._send(200, json.dumps(result), "application/json")
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"ok": False, "code": -1, "output": "面板内部错误: " + str(e)}), "application/json")


def main() -> int:
    ap = argparse.ArgumentParser(prog="panel", description="workbuddy破甲 本地控制面板")
    ap.add_argument("--port", type=int, default=0, help="监听端口（0 = 自动选择，默认）")
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    a = ap.parse_args()

    if not POJIA.is_file():
        print("找不到 scripts/pojia.py，请在仓库根目录或 scripts/ 下运行")
        return 1

    server = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Panel)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"
    print(f"workbuddy破甲 控制面板已启动: {url}")
    print("Ctrl+C 停止。写入类命令有二次确认；restart 会关闭 WorkBuddy 进程。")
    if not a.no_open:
        threading_open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


def threading_open(url: str):
    import threading
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()


if __name__ == "__main__":
    sys.exit(main())
