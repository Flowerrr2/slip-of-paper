import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter


HOTKEY_NAMES = {'new': '新建便签', 'capture': '快速记录', 'search': '搜索便签',
                'hide': '显示 / 隐藏全部', 'paste': '剪贴板转便签'}


def parse_hotkey(sequence):
    parts = sequence.upper().replace(' ', '').split('+')
    mods = 0x4000  # MOD_NOREPEAT
    for part in parts[:-1]:
        if part not in {'CTRL','ALT','SHIFT','META','WIN'}:
            raise ValueError('快捷键包含不支持的修饰键。')
        mods |= {'CTRL':2,'ALT':1,'SHIFT':4,'META':8,'WIN':8}[part]
    key = parts[-1]
    if mods == 0x4000:
        raise ValueError('全局快捷键需要 Ctrl、Alt 或 Shift 等修饰键。')
    if len(key) == 1 and key.isascii() and key.isalnum():
        return mods, ord(key)
    if key == 'SPACE':
        return mods, 0x20
    if key.startswith('F') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return mods, 0x70 + int(key[1:]) - 1
    raise ValueError('请使用字母、数字、空格或 F1–F24 作为主键。')


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, callbacks):
        super().__init__()
        self.callbacks = callbacks
        self.registered = {}
        self.sequences = {}

    def clear(self):
        if os.name == 'nt':
            for ident in self.registered:
                ctypes.windll.user32.UnregisterHotKey(None, ident)
        self.registered.clear()

    def apply(self, sequences):
        parsed = {key: parse_hotkey(seq) for key, seq in sequences.items()}
        if len(set(parsed.values())) != len(parsed):
            raise ValueError('不同操作不能使用相同的快捷键。')
        previous = dict(self.sequences)
        self.clear()
        failed = []
        for index, (key, (mods, vk)) in enumerate(parsed.items(), 1700):
            if os.name == 'nt' and not ctypes.windll.user32.RegisterHotKey(None, index, mods, vk):
                failed.append(HOTKEY_NAMES[key] + '：' + sequences[key])
            else:
                self.registered[index] = key
        if failed:
            self.clear()
            # Restore the old working configuration on a rejected rebind.
            for index, (key, seq) in enumerate(previous.items(), 1700):
                mods, vk = parse_hotkey(seq)
                if os.name != 'nt' or ctypes.windll.user32.RegisterHotKey(None,index,mods,vk):
                    self.registered[index] = key
            raise ValueError('快捷键被其他程序占用：\n' + '\n'.join(failed))
        self.sequences = dict(sequences)

    def nativeEventFilter(self, event_type, message):
        if os.name == 'nt':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and int(msg.wParam) in self.registered:
                self.callbacks[self.registered[int(msg.wParam)]]()
                return True, 0
        return False, 0


def autostart_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            return bool(winreg.QueryValueEx(key, 'LittlePaper')[0])
    except OSError:
        return False


def set_autostart(enabled):
    if os.name != 'nt':
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            if getattr(sys, 'frozen', False):
                command = f'"{sys.executable}" --background'
            else:
                executable = sys.executable.replace('python.exe', 'pythonw.exe')
                script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main.py'))
                command = f'"{executable}" "{script}" --background'
            winreg.SetValueEx(key, 'LittlePaper', 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, 'LittlePaper')
            except FileNotFoundError:
                pass
