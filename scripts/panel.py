#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workbuddy破甲 · 本地控制面板（纯标准库，只监听 127.0.0.1）

用法：
  python scripts/panel.py                # 自动选端口并打开浏览器
  python scripts/panel.py --port 8301
  python scripts/panel.py --no-open      # 不自动开浏览器（调试用）

面板按钮驱动 scripts/pojia.py 的全部子命令：
  doctor / status / check / apply --dry-run / apply / restart
  gate status / gate on / gate off / gate off --restart
  revert / persona
附加能力：执行历史（localStorage）、体检环境摘要、--cloudmem 选项、数字快捷键 1-9。
写入类操作前端有二次确认，执行后自动刷新状态徽章。
restart 会关闭 WorkBuddy 进程（正在进行的会话随进程终止，属预期）。
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
    "doctor":           ["doctor"],
    "status":           ["status"],
    "check":            ["check"],
    "dry":              ["apply", "--dry-run"],
    "apply":            ["apply"],
    "restart":          ["restart"],
    "revert":           ["revert"],
    "persona":          ["persona"],
    "gate-status":      ["gate", "status"],
    "gate-on":          ["gate", "on"],
    "gate-off":         ["gate", "off"],
    "gate-off-restart": ["gate", "off", "--restart"],
}

# --cloudmem 只对写盘类命令有意义
CLOUDMEM_APPLICABLE = {"apply", "restart"}


def run_action(action: str, install: str, data: str, cloudmem: bool = False) -> dict:
    """同步执行 pojia.py 子命令，捕获 stdout/stderr 返回 JSON。"""
    args = [sys.executable, str(POJIA), *ACTIONS[action]]
    if install:
        args += ["-i", install]
    if data:
        args += ["-d", data]
    if cloudmem and action in CLOUDMEM_APPLICABLE:
        args += ["--cloudmem"]
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
  :root{
    --bg:#f6f8fa; --panel:#ffffff; --line:#d8dee4; --line2:#c3cbd4;
    --fg:#1f2328; --muted:#6e7781;
    --green:#1a7f37; --green-bg:#dafbe1; --green-line:#a3d9b0;
    --red:#cf222e; --red-line:#f0b8bf; --red-bg:#fff0f0;
    --gray-bg:#eef1f4;
    --term:#0d1117; --term-fg:#e6edf3; --term-head:#161b22; --term-green:#7ee787; --term-dim:#8b949e;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
       -webkit-font-smoothing:antialiased;}
  .wrap{max-width:880px;margin:28px auto 44px;padding:0 20px;}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;
         box-shadow:0 1px 2px rgba(31,35,40,.06),0 10px 30px rgba(31,35,40,.05);}
  header{padding:20px 24px 16px;border-bottom:1px solid var(--line);}
  .brand{display:flex;align-items:center;gap:12px;}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--green);
       box-shadow:0 0 0 4px var(--green-bg);flex:none;}
  h1{margin:0;font-size:17px;font-weight:650;letter-spacing:.2px;}
  .brand p{margin:1px 0 0;font-size:12px;color:var(--muted);}
  .badges{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0;align-items:center;}
  .badge{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:500;
         padding:3px 11px;border-radius:999px;border:1px solid var(--line);
         background:var(--gray-bg);color:#444c56;font-variant-numeric:tabular-nums;}
  .badge.ok{background:var(--green-bg);border-color:var(--green-line);color:#116329;}
  .badge.off{background:var(--panel);color:var(--muted);}
  .badge.warn{background:var(--red-bg);border-color:var(--red-line);color:var(--red);}
  .envline{margin-top:9px;font-size:12px;color:var(--muted);display:none;
           font-variant-numeric:tabular-nums;}
  .refresh{appearance:none;border:1px solid var(--line);background:var(--panel);color:var(--muted);
           width:27px;height:27px;border-radius:7px;cursor:pointer;font-size:14px;line-height:1;}
  .refresh:hover{border-color:var(--line2);color:var(--fg);background:#f3f4f6;}
  .refresh.busy{animation:spin 1s linear infinite;}
  @keyframes spin{to{transform:rotate(360deg);}}
  main{padding:16px 24px 24px;}
  .params{display:flex;gap:14px;flex-wrap:wrap;padding:2px 0 14px;border-bottom:1px solid var(--line);}
  .field{flex:1;min-width:230px;}
  .field label{font-size:12px;color:var(--muted);}
  .field input{margin-top:5px;width:100%;border:1px solid var(--line);border-radius:7px;
               padding:6px 10px;font:12px ui-monospace,Consolas,"Cascadia Mono",monospace;
               background:var(--panel);color:var(--fg);}
  .field input:focus{outline:2px solid rgba(9,105,218,.25);border-color:#0969da;}
  .check{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted);
         cursor:pointer;user-select:none;padding-top:22px;flex:none;}
  .check input{accent-color:var(--green);width:14px;height:14px;cursor:pointer;margin:0;}
  .groups{padding:16px 0 4px;display:grid;gap:13px;}
  .group{display:grid;grid-template-columns:66px 1fr;gap:10px;align-items:start;}
  .group h2{margin:7px 0 0;font-size:12px;font-weight:600;color:var(--muted);}
  .row{display:flex;flex-wrap:wrap;gap:8px;}
  button.act{appearance:none;border:1px solid var(--line);background:var(--panel);color:var(--fg);
             padding:0 14px;height:32px;border-radius:7px;cursor:pointer;font:500 13px/1 inherit;
             transition:background .15s,border-color .15s;position:relative;}
  button.act:hover{background:#f3f4f6;border-color:var(--line2);}
  button.act:active{background:#ebeeef;}
  button.act:disabled{opacity:.45;cursor:default;}
  button.act.primary{color:var(--green);border-color:#a3d9b0;}
  button.act.primary:hover{background:#f2fff4;}
  button.act.danger{color:var(--red);border-color:var(--red-line);}
  button.act.danger:hover{background:var(--red-bg);}
  button.act .k{position:absolute;top:-7px;right:-6px;font:600 9px/1 ui-monospace,monospace;
                color:var(--muted);background:var(--panel);border:1px solid var(--line);
                border-radius:4px;padding:1px 3px;display:none;}
  .term{margin-top:16px;border:1px solid #2a3138;border-radius:10px;overflow:hidden;
        box-shadow:0 6px 24px rgba(1,4,9,.20);}
  .term-head{display:flex;align-items:center;gap:8px;
             background:var(--term-head);padding:7px 12px;}
  .term-head>span{font:11px ui-monospace,Consolas,monospace;color:var(--term-dim);
                  letter-spacing:.5px;flex:none;}
  #hist{display:flex;gap:6px;flex-wrap:wrap;flex:1;justify-content:flex-end;min-height:0;}
  .hpill{appearance:none;border:1px solid #30363d;background:#21262d;color:var(--term-dim);
         font:11px ui-monospace,Consolas,monospace;padding:2px 9px;border-radius:999px;cursor:pointer;}
  .hpill:hover{color:var(--term-fg);border-color:#8b949e;}
  .term-clear{appearance:none;border:0;background:none;color:var(--term-dim);cursor:pointer;
              font-size:11px;padding:3px 8px;border-radius:5px;flex:none;}
  .term-clear:hover{color:var(--term-fg);background:#21262d;}
  #out{background:var(--term);color:var(--term-fg);min-height:240px;max-height:58vh;overflow:auto;
       padding:12px 14px;margin:0;
       font:12.5px/1.62 ui-monospace,"Cascadia Mono",Consolas,monospace;
       white-space:pre-wrap;word-break:break-all;}
  #out .cmd{color:var(--term-green);}
  #out .dim{color:var(--term-dim);}
  #out .ok{color:var(--term-green);}
  #out .fail{color:#ffa198;}
  #out .sep{color:#30363d;}
  footer{padding:11px 24px 16px;border-top:1px solid var(--line);
         font-size:11.5px;color:var(--muted);}
  kbd{font:10px ui-monospace,monospace;border:1px solid var(--line);border-radius:4px;
      padding:0 4px;background:var(--gray-bg);}
</style>
</head>
<body>
<div class="wrap">
  <div class="panel">
    <header>
      <div class="brand">
        <div class="dot"></div>
        <div>
          <h1>workbuddy破甲 · 控制面板</h1>
          <p>本机运行 · 仅监听 127.0.0.1 · 按钮直达 scripts/pojia.py</p>
        </div>
      </div>
      <div class="badges">
        <span class="badge" id="b-L1">L1 模板 …</span>
        <span class="badge" id="b-L2">L2 产品 …</span>
        <span class="badge" id="b-L3">L3 闸门 …</span>
        <span class="badge" id="b-L6">L6 记忆 …</span>
        <button class="refresh" id="refresh" title="刷新状态">↻</button>
      </div>
      <div class="envline" id="envline"></div>
    </header>
    <main>
      <div class="params">
        <div class="field">
          <label>安装目录（留空自动探测）</label>
          <input id="install" placeholder="D:\\WorkBuddy" spellcheck="false">
        </div>
        <div class="field">
          <label>数据目录（留空用默认）</label>
          <input id="data" placeholder="%USERPROFILE%\\.workbuddy" spellcheck="false">
        </div>
        <label class="check" title="对应 --cloudmem">
          <input type="checkbox" id="cloudmem"> 写入时同步云记忆（L6）
        </label>
      </div>
      <div class="groups">
        <div class="group">
          <h2>常规</h2>
          <div class="row">
            <button class="act" data-act="doctor">体检</button>
            <button class="act" data-act="status">状态</button>
            <button class="act" data-act="check">复查</button>
            <button class="act" data-act="dry">演练（不写盘）</button>
            <button class="act primary" data-act="apply">写入补丁</button>
            <button class="act primary" data-act="restart">关进程 → 写入 → 重启</button>
          </div>
        </div>
        <div class="group">
          <h2>L3 闸门</h2>
          <div class="row">
            <button class="act" data-act="gate-status">闸门状态</button>
            <button class="act danger" data-act="gate-on">gate on（全局）</button>
            <button class="act" data-act="gate-off">gate off</button>
            <button class="act danger" data-act="gate-off-restart">gate off + 重启</button>
          </div>
        </div>
        <div class="group">
          <h2>维护</h2>
          <div class="row">
            <button class="act" data-act="persona">人格文本</button>
            <button class="act danger" data-act="revert">全部还原</button>
          </div>
        </div>
      </div>
      <div class="term">
        <div class="term-head">
          <span>pojia.py · stdout</span>
          <div id="hist"></div>
          <button class="term-clear" id="clear">清空</button>
        </div>
        <pre id="out"><span class="dim">就绪。正在体检…</span></pre>
      </div>
    </main>
    <footer>写入类操作有二次确认 · restart / gate 会重启 WorkBuddy 进程（正在进行的会话随进程终止） · 幂等写入，自动备份 .pojia.bak · 快捷键 <kbd>1</kbd>–<kbd>9</kbd> 执行前九个按钮 · 点终端头部胶囊回看历史输出</footer>
  </div>
</div>
<script>
  var OUT = document.getElementById('out');
  var CONFIRM = {
    'apply':            '确认写入补丁？幂等，自动备份 .pojia.bak。',
    'restart':          '确认执行？会先关闭 WorkBuddy——正在客户端里的对话会随进程终止。',
    'revert':           '确认从 .pojia.bak 全部还原？',
    'gate-on':          '确认开启 L3 闸门？全局放行，需重启 WorkBuddy 生效。',
    'gate-off':         '确认关闭 L3 闸门并还原 mjs 原版？',
    'gate-off-restart': '确认关闭 L3 闸门并立刻重启 WorkBuddy？'
  };
  var WRITE_ACTS = ['apply', 'restart', 'revert', 'gate-on', 'gate-off', 'gate-off-restart'];

  function esc(s){
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
  function scrollDown(){ OUT.scrollTop = OUT.scrollHeight; }
  function setBusy(b){
    document.querySelectorAll('button.act').forEach(function(x){ x.disabled = b; });
    document.getElementById('refresh').classList.toggle('busy', b);
  }
  function setBadge(id, text, cls){
    var el = document.getElementById(id);
    el.textContent = text;
    el.className = 'badge' + (cls ? ' ' + cls : '');
  }

  /* ---------- 执行历史（localStorage，最近 8 条） ---------- */
  var HIST = [];
  try { HIST = JSON.parse(localStorage.getItem('pojia-hist') || '[]'); } catch (e) { HIST = []; }
  function saveHist(){
    try { localStorage.setItem('pojia-hist', JSON.stringify(HIST)); } catch (e) {}
  }
  function renderHist(){
    var el = document.getElementById('hist');
    el.innerHTML = HIST.map(function(h, i){
      return '<button class="hpill" data-i="' + i + '" title="' + esc(h.t) + ' 回看输出">'
           + esc(h.act) + (h.ok ? ' ✓' : ' ✗') + '</button>';
    }).join('');
  }
  document.getElementById('hist').addEventListener('click', function(e){
    var b = e.target.closest ? e.target.closest('.hpill') : null;
    if (!b) return;
    var h = HIST[+b.getAttribute('data-i')];
    if (!h) return;
    OUT.innerHTML = '<span class="dim">[' + h.t + ']（历史回放）</span> '
                   + '<span class="cmd">$ pojia ' + esc(h.act) + '</span> '
                   + '<span class="' + (h.ok ? 'ok' : 'fail') + '">→ 退出码 ' + h.code + '</span>\\n'
                   + '<span class="sep">──────────────────────────────</span>\\n'
                   + esc(h.output || '(无输出)') + '\\n';
    scrollDown();
  });

  /* ---------- status → 徽章 ---------- */
  function grabNum(line){
    var i = line.indexOf(':');
    if (i < 0) return '';
    var s = line.slice(i + 1).trim();
    var sp = s.indexOf(' ');
    return sp > 0 ? s.slice(0, sp) : s;
  }
  function parseStatus(text){
    var lines = text.split('\\n');
    for (var i = 0; i < lines.length; i++){
      var L = lines[i];
      if (L.indexOf('L1') === 0){
        var v = grabNum(L), p = v.split('/');
        setBadge('b-L1', 'L1 模板 ' + v, (p.length === 2 && p[0] === p[1] && p[1] !== '0') ? 'ok' : '');
      } else if (L.indexOf('L2') === 0){
        var v = grabNum(L), p = v.split('/');
        setBadge('b-L2', 'L2 产品 ' + v, (p.length === 2 && p[0] === p[1] && p[1] !== '0') ? 'ok' : '');
      } else if (L.indexOf('L3') === 0){
        var on = L.indexOf('开启') >= 0;
        setBadge('b-L3', 'L3 闸门 ' + (on ? '开启' : '关闭'), on ? 'warn' : 'off');
      } else if (L.indexOf('L6') === 0){
        setBadge('b-L6', 'L6 记忆 ' + grabNum(L), 'off');
      }
    }
  }

  /* ---------- doctor → 环境摘要行 ---------- */
  function parseDoctor(text){
    var info = [];
    var lines = text.split('\\n');
    for (var i = 0; i < lines.length; i++){
      var L = lines[i];
      if (L.indexOf('Python') === 0){
        info.push('Python ' + L.slice(L.indexOf(':') + 1).trim());
      } else if (L.indexOf('node') === 0){
        var nv = L.slice(L.indexOf(':') + 1).trim();
        if (nv.indexOf('缺失') < 0) info.push('node ' + nv);
      } else if (L.indexOf('写入权限') === 0){
        info.push('写入' + (L.indexOf('OK') >= 0 ? '✓' : '✗'));
      } else if (L.indexOf('进程') === 0){
        info.push('WorkBuddy ' + (L.indexOf('运行中') >= 0 ? '运行中' : '未运行'));
      }
    }
    var el = document.getElementById('envline');
    el.textContent = info.join(' · ');
    el.style.display = info.length ? '' : 'none';
  }

  function post(action){
    return fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        action: action,
        install: document.getElementById('install').value,
        data: document.getElementById('data').value,
        cloudmem: document.getElementById('cloudmem').checked
      })
    }).then(function(r){ return r.json(); });
  }

  function refreshBadges(){
    var btn = document.getElementById('refresh');
    btn.classList.add('busy');
    return post('status').then(function(j){
      parseStatus(j.output || '');
      btn.classList.remove('busy');
    }).catch(function(){ btn.classList.remove('busy'); });
  }

  function run(act){
    if (CONFIRM[act] && !confirm(CONFIRM[act])) return;
    var t = new Date().toLocaleTimeString();
    OUT.innerHTML = '';
    OUT.innerHTML += '<span class="dim">[' + t + ']</span> <span class="cmd">$ pojia ' + esc(act) + '</span> <span class="dim">…运行中</span>\\n';
    scrollDown();
    setBusy(true);
    post(act).then(function(j){
      OUT.innerHTML = '';
      OUT.innerHTML += '<span class="dim">[' + t + ']</span> <span class="cmd">$ pojia ' + esc(act) + '</span>'
                     + ' <span class="' + (j.ok ? 'ok' : 'fail') + '">→ 退出码 ' + j.code + (j.ok ? '  ✓' : '  ✗') + '</span>\\n';
      OUT.innerHTML += '<span class="sep">──────────────────────────────</span>\\n';
      OUT.innerHTML += esc(j.output || '(无输出)') + '\\n';
      scrollDown();
      HIST.unshift({t: t, act: act, code: j.code, ok: j.ok, output: (j.output || '').slice(0, 6000)});
      if (HIST.length > 8) HIST.length = 8;
      saveHist();
      renderHist();
      if (act === 'doctor') parseDoctor(j.output || '');
    }).catch(function(e){
      OUT.innerHTML = '';
      OUT.innerHTML += '<span class="fail">请求失败：' + esc(String(e)) + '</span>\\n';
    }).finally(function(){
      setBusy(false);
      if (WRITE_ACTS.indexOf(act) >= 0) setTimeout(refreshBadges, 600);
    });
  }

  document.querySelectorAll('button.act').forEach(function(btn){
    btn.addEventListener('click', function(){ run(btn.dataset.act); });
  });
  document.getElementById('refresh').addEventListener('click', refreshBadges);
  document.getElementById('clear').addEventListener('click', function(){
    OUT.innerHTML = '<span class="dim">（已清空）</span>\\n';
  });

  /* 数字快捷键 1-9：按 DOM 顺序执行前九个按钮 */
  document.addEventListener('keydown', function(e){
    if (e.target.tagName === 'INPUT') return;
    var n = parseInt(e.key, 10);
    if (isNaN(n) || n < 1 || n > 9) return;
    var btns = document.querySelectorAll('button.act');
    if (btns[n - 1] && !btns[n - 1].disabled) run(btns[n - 1].dataset.act);
  });

  renderHist();
  window.addEventListener('load', function(){
    refreshBadges().then(function(){
      OUT.innerHTML = '<span class="dim">就绪。状态徽章已刷新，点上面任一按钮执行，快捷键 1-9。</span>\\n';
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
                bool(req.get("cloudmem", False)),
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
        open_later(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


def open_later(url: str):
    import threading
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()


if __name__ == "__main__":
    sys.exit(main())
