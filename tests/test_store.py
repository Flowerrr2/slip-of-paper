import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime,timedelta
from pathlib import Path

from stickies.store import Store,pending,title


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_roundtrip_unicode_and_geometry(self):
        n=self.store.new('天气系统 ☁\n☐ 风雨效果')
        n.update(x=-1200,y=55,width=420,height=350,color='丁香紫',pinned=True,tags=['工作','游戏'])
        self.store.save(n)
        self.assertEqual(self.store.get(n['id']),n)
        self.assertEqual(pending(n),1)
        self.assertEqual(title(n),'天气系统 ☁')

    def test_snapshot_survives_metadata_saves(self):
        n=self.store.new('原文','<p>原文</p>')
        n.update(plain='新文',content='<p>新文</p>')
        self.store.save(n)
        self.assertEqual(len(self.store.history(n['id'])),1)
        n['x']=42
        self.store.save(n)
        self.assertEqual(self.store.history(n['id'])[0]['plain'],'原文')

    def test_backup_integrity_and_export_merge(self):
        n=self.store.new('绝不覆盖')
        backup=self.store.backup()
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT count(*) FROM notes').fetchone()[0],1)
        path=Path(self.temp.name)/'export.stickybackup'
        self.store.export_all(path)
        self.assertEqual(self.store.import_all(path),1)
        self.assertEqual(len(self.store.all()),2)
        self.assertEqual(self.store.get(n['id'])['plain'],'绝不覆盖')

    def test_invalid_import_is_atomic(self):
        n=self.store.new('留下')
        path=Path(self.temp.name)/'bad.json'
        path.write_text(json.dumps(dict(format='littlepaper',version=1,notes=[n,{'id':'broken'}])),encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.import_all(path)
        self.assertEqual(len(self.store.all()),1)

    def test_trash_retention_and_cascade(self):
        old=self.store.new('旧纸片','<p>旧纸片</p>')
        old.update(content='<p>更新</p>',plain='更新',deleted_at=(datetime.now()-timedelta(days=31)).isoformat())
        self.store.save(old)
        new=self.store.new('刚扔掉')
        new['deleted_at']=datetime.now().isoformat()
        self.store.save(new)
        self.store.prune_trash()
        self.assertIsNone(self.store.get(old['id']))
        self.assertIsNotNone(self.store.get(new['id']))
        self.assertEqual(self.store.history(old['id']),[])

    def test_settings_and_clean_shutdown_persist(self):
        self.store.save_settings({'font_size':19,'startup':'全部隐藏'})
        self.store.close()
        self.store=Store(self.temp.name)
        self.assertEqual(self.store.settings['font_size'],19)
        self.assertFalse(self.store.was_unclean)

    def test_unclean_marker(self):
        self.store.db.close()
        self.store=Store(self.temp.name)
        self.assertTrue(self.store.was_unclean)


if __name__=='__main__':
    unittest.main()
