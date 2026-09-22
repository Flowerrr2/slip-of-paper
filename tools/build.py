"""Build an offline, folder-based Windows distribution with Qt's dynamic DLLs."""
import shutil
import os
import subprocess
import sys
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--output',default='release',help='Output folder relative to the workspace')
OUTPUT=(ROOT/parser.parse_args().output).resolve()
sys.path.insert(0,str(ROOT))
from stickies.app import create_application
from stickies.ui import icon

app=create_application()
assets=ROOT/'assets'
assets.mkdir(exist_ok=True)
icon_path=assets/'paper.ico'
if not icon().pixmap(64,64).save(str(icon_path),'ICO'):
    raise RuntimeError('Could not create application icon')
build_env=dict(os.environ)
# Do not let unrelated development tools (e.g. Poppler's ICU) contaminate Qt DLL resolution.
windows=Path(os.environ.get('SystemRoot',r'C:\Windows'))
build_env['PATH']=os.pathsep.join([str(Path(sys.executable).parent),sys.base_prefix,str(windows/'System32'),str(windows)])
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
                '--name','小纸片','--icon',str(icon_path),'--distpath',str(OUTPUT),
                '--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick',
                '--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets',
                str(ROOT/'main.py')],cwd=ROOT,env=build_env,check=True)
target=OUTPUT/'小纸片'
# Qt uses Windows' unversioned ICU API. It must not load an unrelated ICU build.
for library in (target/'_internal').glob('icu*.dll'):
    library.unlink()
for name in ('使用说明.md','THIRD_PARTY_NOTICES.md'):
    shutil.copy2(ROOT/name,target/name)
licenses=target/'licenses'
licenses.mkdir(exist_ok=True)
import importlib.metadata
for package in ('PySide6_Essentials','shiboken6'):
    dist=importlib.metadata.distribution(package)
    for entry in dist.files or []:
        if 'license' in str(entry).lower() and str(entry).lower().endswith(('.txt','.md')):
            path=dist.locate_file(entry)
            if path.is_file():
                shutil.copy2(path,licenses/(package+'_'+path.name))
for path in (assets/'licenses').glob('*'):
    shutil.copy2(path,licenses/path.name)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():
    shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
pyinstaller_license=importlib.metadata.distribution('pyinstaller').locate_file('pyinstaller-6.22.3.dist-info/licenses/COPYING.txt')
if pyinstaller_license.exists():
    shutil.copy2(pyinstaller_license,licenses/'PyInstaller-COPYING.txt')
shutil.make_archive(str(OUTPUT/'小纸片-Windows-x64'),'zip',OUTPUT,'小纸片')
print('Ready:',target/'小纸片.exe')
