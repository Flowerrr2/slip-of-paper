from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path


COLORS = {
    '奶油黄': '#F7E7A6', '樱花粉': '#F2D4D7', '雾蓝': '#D3E5F0',
    '鼠尾草': '#DFE8CE', '丁香紫': '#E5DDF1', '白纸': '#F8F6EF', '夜色': '#394443',
}
DEFAULTS = dict(color='奶油黄', width=320, height=280, font_size=14,
                opacity=100, snap=True, hover_toolbar=True, startup='保持上次状态',
                skin='横线纸', doodle=True, backup_days=14,
                hotkeys={'new': 'Ctrl+Alt+N', 'capture': 'Ctrl+Alt+Space',
                         'search': 'Ctrl+Alt+F', 'hide': 'Ctrl+Alt+H', 'paste': 'Ctrl+Alt+V'})


def now():
    return datetime.now().isoformat(timespec='seconds')


def data_directory():
    return Path(os.environ.get('STICKY_DATA_DIR') or
                str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'LittlePaper'))


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else data_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'backups').mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.directory / 'database.db')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY, note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                saved_at TEXT NOT NULL, content TEXT NOT NULL, plain TEXT NOT NULL
            );
        ''')
        self.db.commit()
        self.settings = json.loads(json.dumps(DEFAULTS))
        for row in self.db.execute('SELECT * FROM settings'):
            if row['key'] in self.settings:
                self.settings[row['key']] = json.loads(row['value'])
        self.was_unclean = self.get_meta('unclean', False)
        self.set_meta('unclean', True)
        self.prune_trash()
        self.daily_backup()

    def get_meta(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, json.dumps(value)))

    def save_settings(self, values):
        with self.db:
            for key, value in values.items():
                if key in DEFAULTS:
                    self.db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                                    (key, json.dumps(value, ensure_ascii=False)))
        self.settings.update(values)

    def all(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT data FROM notes')]

    def get(self, note_id):
        row = self.db.execute('SELECT data FROM notes WHERE id=?', (note_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def new(self, plain='', content=''):
        s = self.settings
        note = dict(id=uuid.uuid4().hex, title='', content=content, plain=plain,
                    created_at=now(), updated_at=now(), x=None, y=None, width=s['width'],
                    height=s['height'], screen_id='', color=s['color'], opacity=s['opacity'],
                    font_size=s['font_size'], pinned=False, favorite=False, archived=False,
                    deleted_at=None, hidden=False, collapsed=False, tags=[])
        self.save(note)
        return note

    def save(self, note):
        old = self.get(note['id'])
        with self.db:
            self.db.execute('INSERT INTO notes (id,data) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                            (note['id'], json.dumps(note, ensure_ascii=False)))
            if old and old['content'] != note['content'] and old['plain'].strip():
                recent = self.db.execute('SELECT saved_at FROM versions WHERE note_id=? ORDER BY id DESC LIMIT 1',
                                         (note['id'],)).fetchone()
                if not recent or now() > (datetime.fromisoformat(recent[0]) + timedelta(minutes=1)).isoformat():
                    self.db.execute('INSERT INTO versions(note_id,saved_at,content,plain) VALUES(?,?,?,?)',
                                    (note['id'], now(), old['content'], old['plain']))
                    self.db.execute('DELETE FROM versions WHERE note_id=? AND id NOT IN '
                                    '(SELECT id FROM versions WHERE note_id=? ORDER BY id DESC LIMIT 30)',
                                    (note['id'], note['id']))

    def history(self, note_id):
        return [dict(r) for r in self.db.execute('SELECT * FROM versions WHERE note_id=? ORDER BY id DESC', (note_id,))]

    def delete_forever(self, note_id):
        with self.db:
            self.db.execute('DELETE FROM notes WHERE id=?', (note_id,))

    def prune_trash(self):
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        for note in self.all():
            if note['deleted_at'] and note['deleted_at'] < cutoff:
                self.delete_forever(note['id'])

    def backup(self, path=None):
        path = Path(path) if path else self.directory / 'backups' / f'backup_{datetime.now():%Y%m%d_%H%M%S}.db'
        with closing(sqlite3.connect(path)) as target:
            self.db.backup(target)
        return path

    def daily_backup(self, force=False):
        path = self.directory / 'backups' / f'daily_{datetime.now():%Y_%m_%d}.db'
        if force or not path.exists():
            self.backup(path)
        cutoff = datetime.now().timestamp() - self.settings['backup_days'] * 86400
        for backup in (self.directory / 'backups').glob('daily_*.db'):
            if backup.stat().st_mtime < cutoff:
                backup.unlink()

    def export_all(self, path):
        payload = dict(format='littlepaper', version=1, notes=self.all(), settings=self.settings)
        path = Path(path)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def import_all(self, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(payload, dict) or payload.get('format') != 'littlepaper' or payload.get('version') != 1:
            raise ValueError('这不是小纸片的数据备份文件。')
        notes = payload.get('notes')
        if not isinstance(notes, list) or len(notes) > 10000:
            raise ValueError('备份内容无效或超过 10000 张便签。')
        required = {'id','content','plain','created_at','updated_at','color','width','height','tags'}
        for n in notes:
            if not isinstance(n, dict) or not required.issubset(n):
                raise ValueError('备份中的便签字段不完整。')
            for key in ('id','content','plain','created_at','updated_at','color'):
                if not isinstance(n[key], str):
                    raise ValueError('备份字段类型无效。')
            if n['color'] not in COLORS or not isinstance(n['tags'], list) or not all(isinstance(t,str) for t in n['tags']):
                raise ValueError('备份颜色或标签无效。')
            for key in ('width','height','opacity','font_size'):
                if not isinstance(n.get(key), (int,float)) or isinstance(n.get(key),bool):
                    raise ValueError('备份尺寸或外观字段无效。')
            for key in ('x','y'):
                if n.get(key) is not None and not isinstance(n[key], int):
                    raise ValueError('备份位置无效。')
            for key in ('created_at','updated_at'):
                datetime.fromisoformat(n[key])
            if n.get('deleted_at'):
                datetime.fromisoformat(n['deleted_at'])
        self.backup()
        # Merge as new notes: importing never overwrites existing work.
        with self.db:
            for raw in notes:
                n = dict(raw, id=uuid.uuid4().hex, hidden=True, collapsed=False)
                for key, value in dict(title='', screen_id='', pinned=False, favorite=False,
                                       archived=False, deleted_at=None).items():
                    n.setdefault(key, value)
                n['width'] = max(220, min(3000, int(n['width'])))
                n['height'] = max(120, min(3000, int(n['height'])))
                n['opacity'] = max(60, min(100, int(n['opacity'])))
                n['font_size'] = max(10, min(32, int(n['font_size'])))
                self.db.execute('INSERT INTO notes VALUES (?,?)', (n['id'], json.dumps(n, ensure_ascii=False)))
        return len(notes)

    def close(self):
        self.set_meta('unclean', False)
        self.db.close()


def title(note):
    return note.get('title') or next((line.lstrip('☐☑# •').strip()[:36]
                                    for line in note['plain'].splitlines() if line.strip()), '一张新的小纸片')


def pending(note):
    return sum(line.strip().startswith(('☐', '[] ', '[ ] ')) for line in note['plain'].splitlines())
