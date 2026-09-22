"""Smoke-test the packaged app, single-instance activation and restart persistence."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import argparse
from contextlib import closing,ExitStack

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--output',default='release')
exe=ROOT/parser.parse_args().output/'小纸片'/'小纸片.exe'

class Memory(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
              ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
              ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
              ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
              ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]

def snapshot(directory):
    with closing(sqlite3.connect(Path(directory)/'database.db')) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        notes=[json.loads(r[0]) for r in db.execute('SELECT data FROM notes')]
        clean=json.loads(db.execute("SELECT value FROM settings WHERE key='unclean'").fetchone()[0]) is False
        assert clean
        return notes

with tempfile.TemporaryDirectory(prefix='littlepaper-release-') as tmp, ExitStack() as processes:
    env=dict(os.environ,STICKY_DATA_DIR=tmp)
    def launch(*args):
        p=subprocess.Popen([str(exe),*args],env=env)
        def cleanup():
            if p.poll() is None:
                p.kill()
                p.wait(timeout=5)
        processes.callback(cleanup)
        return p
    start=time.perf_counter()
    process=launch('--smoke-exit')
    handle=wintypes.HANDLE(int(process._handle))
    ready=ctypes.windll.user32.WaitForInputIdle(handle,10000)
    assert ready==0, f'App was not ready: {ready}'
    startup=time.perf_counter()-start
    time.sleep(.35)
    memory=Memory()
    memory.cb=ctypes.sizeof(memory)
    ctypes.windll.psapi.GetProcessMemoryInfo(handle,ctypes.byref(memory),memory.cb)
    second=launch()
    assert second.wait(timeout=10)==0
    assert process.wait(timeout=15)==0
    original=snapshot(tmp)
    assert len(original)==1 and '嘿，这是一张便签' in original[0]['plain']
    restarted=launch('--smoke-exit')
    assert restarted.wait(timeout=15)==0
    restored=snapshot(tmp)
    assert restored[0]['id']==original[0]['id']
    assert restored[0]['plain']==original[0]['plain']
    log=Path(tmp)/'app.log'
    assert not log.exists() or not log.read_text(encoding='utf-8').strip()
    report=dict(packaged_launch='passed',single_instance='passed',restart_persistence='passed',
                database_integrity='ok',startup_to_input_idle_seconds=round(startup,3),
                working_set_mb=round(memory.WorkingSetSize/1024/1024,1),
                package_mb=round(sum(p.stat().st_size for p in exe.parent.rglob('*') if p.is_file())/1024/1024,1))
    (ROOT/'artifacts'/'release-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
