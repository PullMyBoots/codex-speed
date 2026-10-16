#!/usr/bin/env python3
"""Exercise the real TUI and renderer using a loopback-only synthetic Responses server."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import signal
import struct
import subprocess
import tempfile
import termios
import threading
import time

base = Path(__file__).resolve().parent
import sys
import pyte

work = Path(tempfile.mkdtemp(prefix='codex-statusline-smoke-', dir='/tmp'))
profile = work / 'home'
profile.mkdir()
requests = []
tool_sent = False
main_count = 0
request_times = []
tool_lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        data = b'{"data":[]}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        global tool_sent, main_count
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        with (work / "requests.jsonl").open("a") as f: f.write(json.dumps(body) + "\n")
        requests.append(self.path)
        request_times.append({'at':time.monotonic(),'main':bool(body.get('tools'))})
        if not self.path.endswith('/responses'):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        def send(event):
            self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
            self.wfile.flush()
        send({'type':'response.created','response':{'id':'smoke-response'}})
        with tool_lock:
            if body.get('tools'):
                main_count += 1
            buffered_only = bool(body.get('tools')) and main_count >= 3
            call_tool = bool(body.get('tools')) and not tool_sent
            if call_tool:
                tool_sent = True
        if buffered_only:
            # This request has no timed deltas. A prior valid rate must survive.
            item={'id':'buffered-message','type':'message','role':'assistant','content':[{'type':'output_text','text':'OK'}]}
            send({'type':'response.output_item.added','item':item})
            send({'type':'response.output_item.done','item':item})
            send({'type':'response.completed','response':{'id':'buffered-response','usage':{
                'input_tokens':1000,'output_tokens':1,'total_tokens':1001,
                'output_tokens_details':{'reasoning_tokens':0}}}})
            return
        if call_tool:
            time.sleep(1.5)
            reasoning={'id':'smoke-reasoning','type':'reasoning','summary':[], 'content':[]}
            send({'type':'response.output_item.added','item':reasoning})
            for _ in range(40):
                send({'type':'response.reasoning_text.delta','item_id':reasoning['id'],'content_index':0,'delta':' x'})
                time.sleep(0.025)
            # Summary is deliberately different speed, and is never decode usage.
            time.sleep(0.6)
            for _ in range(20):
                send({'type':'response.reasoning_summary_text.delta','item_id':reasoning['id'],'summary_index':0,'delta':' x'})
                time.sleep(0.05)
            reasoning['content']=[{'type':'reasoning_text','text':' x'*40}]
            reasoning['summary']=[{'type':'summary_text','text':' x'*20}]
            send({'type':'response.output_item.done','item':reasoning})
            time.sleep(0.6)
            args=json.dumps({'cmd':'sleep 2','yield_time_ms':3000})
            item = {'id':'smoke-tool','type':'function_call','call_id':'call_smoke_sleep',
                    'name':'exec_command','arguments':''}
            send({'type':'response.output_item.added','item':item})
            for char in args:
                send({'type':'response.function_call_arguments.delta','item_id':item['id'],'call_id':item['call_id'],'delta':char})
                time.sleep(0.03)
            item['arguments']=args
            time.sleep(1.5)
            send({'type':'response.output_item.done','item':item})
            send({'type':'response.completed','response':{'id':'smoke-tool-response','usage':{
                'input_tokens':1000,'output_tokens':120,'total_tokens':1120,
                'output_tokens_details':{'reasoning_tokens':40}}}})
            return
        send({'type':'response.output_item.added','item':{'id':'smoke-message','type':'message','role':'assistant','content':[]}})
        time.sleep(1.5)  # TTFT/hidden reasoning: excluded
        for _ in range(40):
            send({'type':'response.output_text.delta','delta':' x'})
            time.sleep(0.025)
        time.sleep(1.5)  # final usage lag: excluded
        send({'type':'response.output_item.done','item':{'id':'smoke-message','type':'message','role':'assistant','content':[{'type':'output_text','text':' x'*40}]}})
        send({'type':'response.completed','response':{'id':'smoke-response','usage':{'input_tokens':1000,'output_tokens':1040,'total_tokens':2040,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':1000}}}})

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
config = f'''model = "gpt-5.4"
model_provider = "smoke"
approval_policy = "never"
check_for_update_on_startup = false
[model_providers.smoke]
name = "Smoke local endpoint"
base_url = "http://127.0.0.1:{server.server_port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
[projects."{work}"]
trust_level = "trusted"
[tui]
animations = false
status_line = ["model-with-reasoning", "current-dir", "used-tokens"]
'''
(profile / 'config.toml').write_text(config)
renderer = work / 'renderer.py'
artifact = base.parent / 'staged-generation.txt'
expected_version = '0.163.0'
python = sys.executable
cx = base.parent / 'render.py'
renderer.write_text(f'''import json, os, sys
raw=sys.stdin.buffer.read()
with open({str(work/'payloads.jsonl')!r},'ab') as f: f.write(raw+b'\\n')
with open({str(work/'render-widths.jsonl')!r},'a') as f: f.write(os.environ.get('CXSTATUSLINE_WIDTH','')+'\\n')
import time
with open({str(work/'sample-times.jsonl')!r},'a') as f: f.write(str(time.monotonic())+'\\n')
r,w=os.pipe()
os.write(w,raw)
os.close(w)
os.dup2(r,0)
os.close(r)
os.execv({python!r},[{python!r},{str(cx)!r}])
''')
binary = Path(os.environ['CODEX_STATUSLINE_SMOKE_BINARY'])
baseline = os.environ.get('CODEX_STATUSLINE_SMOKE_BASELINE') == '1'
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 120, 0, 0))
env = os.environ.copy()
env.update(CODEX_HOME=str(profile), TERM='xterm-256color', OPENAI_API_KEY='synthetic-local-only',
           CXSTATUSLINE_COMMAND='python3 ' + str(renderer), XDG_CACHE_HOME=str(work/'cache'))
for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy','CXSTATUSLINE_WIDTH','CCSTATUSLINE_WIDTH'):
    env.pop(key, None)
backend_args = []
process = subprocess.Popen([str(binary),*backend_args,'--no-alt-screen','-C',str(work)],
                           stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True)
os.close(slave)
output = bytearray()
screen = pyte.Screen(120, 35)
terminal_stream = pyte.ByteStream(screen)
frames = []
layout_checks = {}
started = time.monotonic()
typed = False
submitted = False
resized = False
second_typed = False
second_submitted = False
try:
    while time.monotonic() - started < 50 and process.poll() is None:
        if select.select([master],[],[],0.2)[0]:
            try:
                data = os.read(master, 262144)
            except OSError:
                break
            output.extend(data)
            terminal_stream.feed(data)
            lines = list(screen.display)
            if any("Decode" in line or "Summary" in line for line in lines):
                frames.append({"at":time.monotonic()-started,"width":screen.columns,"lines":lines})
                speed_rows=[i for i,line in enumerate(lines) if ("Decode" in line or "Summary" in line) and ("t/s" in line or "—" in line)]
                native_rows=[i for i,line in enumerate(lines) if "gpt-5.4" in line and "codex-statusline-smoke-" in line]
                if speed_rows and native_rows and speed_rows[0] != native_rows[0]:
                    layout_checks[screen.columns]=True
            if b'\x1b[6n' in data:
                os.write(master,b'\x1b[1;1R')
            if b'\x1b[c' in data:
                os.write(master,b'\x1b[?1;2c')
            if b'\x1b]11;?' in data:
                os.write(master,b'\x1b]11;rgb:0000/0000/0000\x07')
        elapsed = time.monotonic() - started
        if elapsed > 6 and not typed:
            os.write(master,b'local smoke check')
            typed = True
        if elapsed > 7 and not submitted:
            os.write(master,b'\r')
            submitted = True
        if not baseline and elapsed > 18 and not resized:
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 83, 0, 0))
            os.kill(process.pid, signal.SIGWINCH)
            screen.resize(35, 83)
            resized = True
        if not baseline and elapsed > 22 and not second_typed:
            os.write(master,b'second local smoke check')
            second_typed = True
        if not baseline and elapsed > 23 and not second_submitted:
            os.write(master,b'\r')
            second_submitted = True
        if baseline and requests and elapsed > 12:
            break
        payload_file = work / 'payloads.jsonl'
        if payload_file.exists():
            records = [json.loads(line) for line in payload_file.read_text().splitlines() if line]
            if any(p.get('usage',{}).get('output_tokens') == 1161 for p in records) and elapsed > 30:
                break
finally:
    os.write(master,b'\x03')
    time.sleep(0.3)
    if process.poll() is None:
        os.write(master,b'\x03')
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
    os.close(master)
    server.shutdown()
(work / 'terminal.bin').write_bytes(output)
(work / 'frames.json').write_text(json.dumps(frames,indent=2))
records = []
if (work / 'payloads.jsonl').exists():
    records = [json.loads(line) for line in (work / 'payloads.jsonl').read_text().splitlines() if line]
plain_output = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', bytes(output))
# Ratatui emits screen diffs: a changed number may arrive without its unchanged "Out:" prefix.
speed_values = sorted({float(value) for value in re.findall(rb'([0-9]+(?:\.[0-9]+)?)\s*t/s', plain_output) if float(value) > 0})
widths = sorted({int(line) for line in (work/'render-widths.jsonl').read_text().splitlines() if line.isdigit()}) if (work/'render-widths.jsonl').exists() else []
result = {'renderer_widths':widths,'work':str(work),'requests':requests,'payload_count':len(records),
          'expected_output_tokens':1161,
          'exact_output_tokens':any(p.get('usage',{}).get('output_tokens') == 1161 for p in records),
          'codex_versions':sorted({p.get('session',{}).get('codex_version','') for p in records}),
          'speed_unit_visible':b't/s' in output,'positive_output_speeds':speed_values,'version_preserved':all(p.get('session',{}).get('codex_version') == expected_version for p in records)}
result['native_and_plugin_separate_rows'] = layout_checks
completed=[p['stream_metrics'] for p in records if (p.get('stream_metrics') or {}).get('phase')=='complete' and p['stream_metrics'].get('output_tps') is not None]
unique={ (m['generation_ms'],m['output_tps']) : m for m in completed }
result['completed_metrics'] = list(unique.values())
result['known_server_tps'] = 40
text_completed=[m for m in completed if m.get('reported_output_tokens')==1040]
result['throughput_matches_known_stream'] = bool(text_completed) and all(abs(m['output_tps']-40)<4 and 900<=m['generation_ms']<=1150 for m in text_completed)
phases={p['stream_metrics'].get('stream_kind') for p in records if (p.get('stream_metrics') or {}).get('phase')=='streaming' and p['stream_metrics'].get('output_tps',0) is not None}
result['positive_live_stream_kinds']=sorted(phases)
result['all_decode_phases_observed']=set(('text','tool','reasoning','summary')).issubset(phases)
result['summary_visible']=any('Summary:' in line and 't/s' in line for frame in frames for line in frame['lines'])
result['thinking_visible']=any('Decode (think):' in line and 't/s' in line for frame in frames for line in frame['lines'])
result['tool_speed_visible']=any('Decode (tool):' in line and 't/s' in line for frame in frames for line in frame['lines'])
last_records=[p for p in records if p.get('usage',{}).get('output_tokens')==1161]
result['last_survives_buffered_request']=bool(last_records) and all((p.get('stream_metrics') or {}).get('output_tps') is not None and p['stream_metrics']['phase']!='streaming' and p['stream_metrics']['reported_output_tokens']==1040 for p in last_records)
first_completed=[m for m in completed if m.get('reported_output_tokens')==120]
result['decode_excludes_summary_and_gaps']=bool(first_completed) and all(1900<=m['generation_ms']<=2600 for m in first_completed)

result['live_sample_count'] = len([p for p in records if (p.get('stream_metrics') or {}).get('phase')=='streaming' and p['stream_metrics'].get('output_tps') is not None])
result['live_sampling_100ms'] = all(p['stream_metrics']['sample_interval_ms']==100 for p in records if p.get('stream_metrics'))
main_times = [r['at'] for r in request_times if r['main']]
result['actual_tool_call_completed'] = len(main_times)>=3 and main_times[1]-main_times[0]>=2
result['first_tool_roundtrip_seconds'] = main_times[1]-main_times[0] if len(main_times)>1 else None
Path(os.environ.get('CODEX_SPEED_SMOKE_RESULT',str(work/'result.json'))).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if not (bool(requests) if baseline else (result['actual_tool_call_completed'] and result['throughput_matches_known_stream'] and result['all_decode_phases_observed'] and result['last_survives_buffered_request'] and result['decode_excludes_summary_and_gaps'] and result['summary_visible'] and result['thinking_visible'] and result['tool_speed_visible'] and layout_checks.get(83) and layout_checks.get(120) and result['live_sample_count'] >= 6 and result['exact_output_tokens'] and bool(speed_values) and result['version_preserved'] and widths == [83,120])):
    raise SystemExit(1)
