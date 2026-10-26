import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import wave

from lyrics_editor.store import Store, encoded
from lyrics_studio.processing import Cancelled, make_document
from lyrics_studio.resolve_export import export_package, lua_string, title_plan


class ResolveExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / 'synthetic.wav'
        with wave.open(str(self.audio), 'wb') as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b'\0' * 64000 * 8)
        doc = make_document(self.audio, [(0.2, 2.0, 'One'), (1.5, 3.0, 'Two'), (3, 4, 'Three')])
        data = self.root / 'source.json'
        data.write_bytes(encoded(doc))
        store = Store(data, self.root / 'state')
        for row in store.rows:
            store.act(dict(action='confirm', id=row['id'], revision=store.revision,
                           reviewer='Synthetic test', acknowledge=True, allow_overlap=True))
        self.document = store.document()

    def test_timing_offset_target_fps_and_overlap_lanes(self):
        plan = title_plan(self.document, 'Test', fps=25, offset=10)
        self.assertEqual([(r['start_frame'], r['end_frame'], r['track']) for r in plan['rows']],
                         [(255, 300, 1), (287, 325, 2), (325, 350, 1)])
        self.assertEqual(plan['audio_start_frame'], 250)
        self.assertEqual(plan['carrier_frames'], 46)

    def test_empty_unconfirmed_and_invalid_parameters_are_rejected(self):
        doc = copy.deepcopy(self.document)
        doc['confirmed_occurrences'] = []
        with self.assertRaises(ValueError):
            title_plan(doc, 'Test')
        for values in [{'fps':23.976}, {'offset':float('nan')}, {'offset':-1}, {'width':16,'height':16}]:
            with self.assertRaises(ValueError):
                title_plan(self.document, 'Test', **values)
        doc = copy.deepcopy(self.document)
        doc['confirmed_occurrences'][0]['timing']['display_enabled'] = False
        with self.assertRaises(ValueError):
            title_plan(doc, 'Test')

    def test_portable_package_contains_only_confirmed_passages_and_audio(self):
        before = copy.deepcopy(self.document)
        output = export_package(self.document, 'Song / Test', self.audio, self.root)
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['rows']), 3)
        self.assertEqual((output / 'song.wav').read_bytes(), self.audio.read_bytes())
        self.assertEqual(len(list((output / 'carrier').glob('*.png'))), manifest['carrier_frames'])
        self.assertTrue((output / 'comps').is_dir())
        self.assertIn('*', (output / '.gitignore').read_text())
        self.assertIn('dofile(', (output / 'IMPORT-ANLEITUNG.txt').read_text(encoding='utf-8'))
        self.assertIn('Lyrics_Text', (output / 'Import_in_DaVinci.lua').read_text(encoding='utf-8'))
        self.assertIn('GetSelectedClips', (output / 'Titelstil_in_Resolve.lua').read_text(encoding='utf-8'))
        self.assertIn('GhostlyMistDissolve', (output / 'Ghostly Mist Dissolve.setting').read_text(encoding='utf-8'))
        self.assertTrue((output / 'Lyrics_Stile.lua').is_file())
        self.assertIn('Titelstil_in_Resolve.lua', (output / 'IMPORT-ANLEITUNG.txt').read_text(encoding='utf-8'))
        self.assertEqual(self.document, before)
        self.assertNotIn(str(self.audio), (output / 'Titel_Daten.lua').read_text(encoding='utf-8'))

    def test_no_audio_option_and_second_export_do_not_overwrite(self):
        first = export_package(self.document, 'Test', self.audio, self.root, include_audio=False)
        second = export_package(self.document, 'Test', self.audio, self.root, include_audio=False)
        self.assertNotEqual(first, second)
        self.assertFalse((first / 'song.wav').exists())
        self.assertIsNone(json.loads((first/'manifest.json').read_text(encoding='utf-8'))['audio'])

    def test_cancellation_cleans_only_its_temporary_files(self):
        cancel = threading.Event()
        cancel.set()
        marker = self.root / 'keep.txt'
        marker.write_text('keep')
        with self.assertRaises(Cancelled):
            export_package(self.document, 'Test', self.audio, self.root, cancel=cancel)
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual(list(self.root.glob('.lyrics-export-*')), [])

    def test_audio_change_aborts_without_publishing_package(self):
        self.audio.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            export_package(self.document, 'Test', self.audio, self.root)
        self.assertEqual(list(self.root.glob('*-DaVinci-*')), [])

    def test_lua_quoting_preserves_unicode_and_escapes_code_characters(self):
        quoted = lua_string('Grüße "Welt"\nC:\\Song\x00')
        self.assertEqual(quoted, '"Grüße \\"Welt\\"\\010C:\\\\Song\\000"')


if __name__ == '__main__':
    unittest.main()
