import copy
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

from lyrics_editor.store import Store, Conflict, digest, encoded
from lyrics_studio.processing import make_document
from lyrics_editor.timebase import frame_interval, frames_to_seconds, seconds_to_frame, validate_interval
from lyrics_editor.server import make_server

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / 'editor-test-artifacts'


class Fixture(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='unit-', dir=TEST_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        assert self.directory.is_relative_to(TEST_ROOT.resolve())
        self.addCleanup(self.temporary.cleanup)
        audio = self.directory / 'fixture.wav'
        with wave.open(str(audio), 'wb') as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b'\x00\x10\x00\xf0' * 160000)
        data = make_document(audio, [(1, 2, 'Synthetic one'), (3, 4, 'Synthetic two'), (5, 6, 'Synthetic three')])
        data['audio'] = dict(path=str(audio), sha256=digest(audio), duration_seconds=10)
        data['recognized_occurrences'] = data['recognized_occurrences'][:3]
        for index, item in enumerate(data['recognized_occurrences']):
            item['asr_segment_timing'].update(start_time=1 + index*2, end_time=2 + index*2,
                                             start_frame=24 + index*48, end_frame=48 + index*48)
            item['hypothesis_repeat_of'] = None
        ids = {r['id'] for r in data['recognized_occurrences']}
        data['alignment_attempts'] = [r for r in data.get('alignment_attempts', []) if r.get('occurrence_id') in ids]
        data['confirmed_occurrences'] = []
        self.data = self.directory / 'source.json'
        self.data.write_bytes(encoded(data))
        self.original = self.data.read_bytes()
        self.store = Store(self.data, self.directory / 'state')

    def action(self, action, index=0, **values):
        return self.store.act(dict(action=action, revision=self.store.revision,
                                   id=self.store.rows[index]['id'], **values))

    def confirm(self, index=0, **values):
        return self.action('confirm', index, acknowledge=True,
                           reviewer='AUTOMATED TEST ONLY - no real lyric review', **values)


class FrameTests(unittest.TestCase):
    def test_round_trip(self):
        for frame in list(range(1000)) + [9771, 9772, 86400]:
            seconds = frames_to_seconds(frame)
            self.assertEqual(seconds_to_frame(seconds, rounding='floor'), frame)
            self.assertEqual(seconds_to_frame(seconds, rounding='ceil'), frame)

    def test_exact_fraction(self):
        self.assertEqual(frame_interval(1/24, 2/24), (1, 2))

    def test_outward(self):
        self.assertEqual(frame_interval(.1, .2), (2, 5))
        self.assertEqual(frame_interval(0, 407.16), (0, 9772))

    def test_real_fraction_not_snapped(self):
        self.assertEqual(seconds_to_frame(1/24+.00001, rounding='ceil'), 2)

    def test_adjacent_unsnapped(self):
        self.assertEqual(frame_interval(1, 1.1), (24, 27))
        self.assertEqual(frame_interval(1.1, 1.2), (26, 29))

    def test_invalid(self):
        for a,b in [(-1,1),(2,1),(1,1),(float('nan'),2),(1,float('inf')),(False,1)]:
            with self.subTest(a=a,b=b), self.assertRaises(ValueError):
                frame_interval(a,b)
        with self.assertRaises(ValueError):
            validate_interval(0,11,10)


class StoreTests(Fixture):
    def test_initial(self):
        self.assertEqual(len(self.store.rows), 3)
        self.assertTrue(all(r['status'] == 'unreviewed' for r in self.store.rows))
        self.assertEqual(self.store.document()['confirmed_occurrences'], [])

    def test_edit_save_restart(self):
        self.action('update', text='Edited', start=1.1, end=1.9)
        self.store.save(self.store.revision)
        loaded = Store(self.data, self.store.directory)
        self.assertEqual(loaded.rows[0]['text'], 'Edited')
        self.assertEqual(loaded.rows[0]['status'], 'editing')
        self.assertEqual(self.data.read_bytes(), self.original)

    def test_explicit_confirmation(self):
        with self.assertRaises(ValueError):
            self.action('confirm', reviewer='Test')
        self.confirm()
        doc = self.store.document()
        self.assertEqual(len(doc['confirmed_occurrences']), 1)
        self.assertTrue(doc['confirmed_occurrences'][0]['manual_text_confirmation'])
        self.assertEqual(doc['recognized_occurrences'], self.store.base['recognized_occurrences'])
        self.assertTrue(self.store.path.exists())

    def test_edit_revokes(self):
        self.confirm()
        self.action('update', text='Changed again', start=1,end=2)
        self.assertEqual(self.store.document()['confirmed_occurrences'], [])

    def test_failed_action_preserves_undo(self):
        before = copy.deepcopy(self.store.state())
        with self.assertRaises(ValueError):
            self.action('confirm', reviewer='Test')
        self.assertEqual(self.store.state(), before)

    def test_duplicate(self):
        self.action('duplicate')
        last = self.store.rows[-1]
        self.assertNotEqual(last['id'], self.store.rows[0]['id'])
        self.assertEqual(last['repeat_of'], self.store.rows[0]['id'])
        self.assertEqual(last['status'], 'editing')

    def test_delete_undo(self):
        self.action('delete')
        self.assertTrue(self.store.rows[0]['deleted'])
        self.action('undo')
        self.assertFalse(self.store.rows[0]['deleted'])
        self.assertEqual(self.data.read_bytes(), self.original)

    def test_insert(self):
        self.action('insert', start=7)
        self.assertEqual(self.store.rows[-1]['source_ids'], [])

    def test_stale_revision(self):
        with self.assertRaises(Conflict):
            self.store.save('stale')

    def test_changed_source(self):
        self.data.write_bytes(self.original+b' ')
        with self.assertRaises(Conflict):
            self.store.save(self.store.revision)

    def test_changed_draft(self):
        self.store.save(self.store.revision)
        self.store.path.write_bytes(self.store.path.read_bytes()+b' ')
        with self.assertRaises(Conflict):
            self.store.save(self.store.revision)

    def test_failed_atomic_save(self):
        self.store.save(self.store.revision)
        before = self.store.path.read_bytes()
        self.action('update', text='Still only in memory',start=1,end=2)
        with patch('lyrics_editor.store.os.replace', side_effect=OSError('test failure')):
            with self.assertRaises(OSError):
                self.store.save(self.store.revision)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertTrue(self.store.state()['dirty'])

    def test_invalid_edit(self):
        before = copy.deepcopy(self.store.rows)
        with self.assertRaises(ValueError):
            self.action('update',text='Invalid',start=3,end=2)
        self.assertEqual(self.store.rows,before)

    def test_adjacent_confirmation(self):
        self.action('update',text='One',start=1/24,end=2/24)
        self.action('update',1,text='Two',start=2/24,end=3/24)
        self.confirm()
        self.confirm(1)
        self.assertEqual(len(self.store.document()['confirmed_occurrences']),2)

    def test_overlap_requires_acknowledgement(self):
        self.action('duplicate')
        self.confirm()
        with self.assertRaises(ValueError):
            self.confirm(3)

    def test_export_reopen(self):
        self.confirm()
        result = self.store.export(self.store.revision)
        loaded = Store(result['path'],self.directory/'reopened')
        self.assertEqual(len(loaded.document()['confirmed_occurrences']),1)

    def test_repeated_confirmed_export_reopen(self):
        self.action('duplicate')
        self.confirm()
        self.confirm(3,allow_overlap=True)
        result=self.store.export(self.store.revision)
        loaded=Store(result['path'],self.directory/'repeated-reopened')
        confirmed=loaded.document()['confirmed_occurrences']
        self.assertEqual(len(confirmed),2)
        self.assertEqual(confirmed[1]['repeat_of'],confirmed[0]['id'])

    def test_revision_backup(self):
        self.store.save(self.store.revision)
        previous=self.store.path.read_bytes()
        self.action('update',text='Revision two',start=1,end=2)
        self.store.save(self.store.revision)
        self.assertIn(previous,[p.read_bytes() for p in self.store.history.glob('*.json')])

    def test_inconsistent_reload_preserves_memory(self):
        self.store.save(self.store.revision)
        saved=json.loads(self.store.path.read_text(encoding='utf-8'))
        saved['reviewed_document']['workflow_status']='different'
        self.store.path.write_bytes(encoded(saved))
        before=copy.deepcopy(self.store.rows)
        with self.assertRaises(ValueError):
            self.store.reload(self.store.revision)
        self.assertEqual(self.store.rows,before)


class HTTPTests(Fixture):
    def setUp(self):
        super().setUp()
        self.server = make_server(self.data,self.directory/'http',0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self,path,method='GET',body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        conn.request(method,path,body=body,headers=headers or {})
        response=conn.getresponse()
        result=response.status,dict(response.getheaders()),response.read()
        conn.close()
        return result

    def test_state_and_peaks(self):
        self.assertEqual(json.loads(self.request('/api/state')[2])['source_count'],3)
        self.assertEqual(json.loads(self.request('/api/peaks')[2])['channels'],2)

    def test_windowed_app_without_console(self):
        with patch('sys.stderr', None):
            self.assertEqual(self.request('/api/state')[0], 200)

    def test_audio_range_and_head(self):
        status,headers,body=self.request('/api/audio',headers={'Range':'bytes=0-11'})
        self.assertEqual(status,206)
        self.assertEqual(body[:4],b'RIFF')
        self.assertTrue(headers['Content-Range'].startswith('bytes 0-11/'))
        self.assertEqual(self.request('/api/audio','HEAD')[2],b'')

    def test_invalid_range(self):
        self.assertEqual(self.request('/api/audio',headers={'Range':'bytes=999999999-'})[0],416)

    def test_segment(self):
        status,_,body=self.request('/api/segment?start=1&end=2')
        self.assertEqual(status,200)
        with wave.open(io.BytesIO(body)) as audio:
            self.assertEqual(audio.getnframes(),16000)
            self.assertEqual(audio.getnchannels(),2)

    def test_invalid_segment(self):
        self.assertEqual(self.request('/api/segment?start=2&end=1')[0],400)

    def test_paths_and_host(self):
        self.assertEqual(self.request('/../lyrics_timing.json')[0],404)
        self.assertEqual(self.request('/api/state',headers={'Host':'example.com'})[0],403)

    def test_csrf(self):
        self.assertEqual(self.request('/api/save','POST',b'{}')[0],403)

    def test_single_process_per_state_directory(self):
        with self.assertRaises(OSError):
            make_server(self.data,self.directory/'http',0)

    def test_save_and_conflict(self):
        state=json.loads(self.request('/api/state')[2])
        headers={'X-Editor-Token':state['token'],'Content-Type':'application/json'}
        self.assertEqual(self.request('/api/save','POST',encoded({'revision':state['revision']}),headers)[0],200)
        self.assertEqual(self.request('/api/save','POST',encoded({'revision':'stale'}),headers)[0],409)


if __name__ == '__main__':
    unittest.main()
