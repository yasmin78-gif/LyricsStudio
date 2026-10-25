import io
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from lyrics_studio import __version__
from lyrics_studio.app import Window
from lyrics_studio.updates import API_URL, RELEASES_URL, UpdateResult, check_for_updates, version_tuple


class UpdateTests(unittest.TestCase):
    def response(self, **values):
        return io.BytesIO(json.dumps(dict(tag_name='v0.2.0', draft=False, prerelease=False, **values)).encode())

    def test_numeric_versions_and_no_arbitrary_release_links(self):
        payload = io.BytesIO(json.dumps(dict(tag_name='v0.10.0', html_url='https://example.com/untrusted')).encode())
        with patch('lyrics_studio.updates.urllib.request.urlopen', return_value=payload):
            result = check_for_updates('0.2.0')
        self.assertEqual(result.status, 'available')
        self.assertEqual(result.url, RELEASES_URL + '/tag/v0.10.0')
        self.assertGreater(version_tuple('0.10.0'), version_tuple('0.2.0'))

    def test_current_and_older_versions(self):
        for tag in ('v0.2.0', 'v0.1.0'):
            with patch('lyrics_studio.updates.urllib.request.urlopen', return_value=io.BytesIO(json.dumps({'tag_name':tag}).encode())):
                self.assertEqual(check_for_updates('0.2.0').status, 'current')

    def test_drafts_prereleases_invalid_and_oversized_are_not_updates(self):
        for release in [{'tag_name':'v1.0.0','draft':True}, {'tag_name':'v1.0.0','prerelease':True},
                        {'tag_name':'v1.0.0-beta'}, {'tag_name':123}, [], {}]:
            with patch('lyrics_studio.updates.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(release).encode())):
                self.assertEqual(check_for_updates().status, 'unavailable')
        with patch('lyrics_studio.updates.urllib.request.urlopen', return_value=io.BytesIO(b'x'*1_000_001)):
            self.assertEqual(check_for_updates().status, 'unavailable')

    def test_private_repo_offline_and_rate_limit_have_clear_status(self):
        for code in (401, 403, 404, 500):
            with patch('lyrics_studio.updates.urllib.request.urlopen', side_effect=HTTPError(API_URL,code,'error',{},None)):
                result=check_for_updates()
                self.assertEqual(result.status,'unavailable')
                if code==404:self.assertIn('privat',result.message)
        with patch('lyrics_studio.updates.urllib.request.urlopen',side_effect=URLError('offline')):
            self.assertEqual(check_for_updates().status,'unavailable')

    def test_private_access_token_is_only_sent_to_fixed_api(self):
        with patch.dict(os.environ,{'LYRICS_STUDIO_UPDATE_TOKEN':'synthetic-secret'}), \
             patch('lyrics_studio.updates.urllib.request.urlopen',return_value=self.response()) as request:
            result=check_for_updates()
        args=request.call_args
        self.assertEqual(args.args[0].full_url,API_URL)
        self.assertEqual(args.args[0].get_header('Authorization'),'Bearer synthetic-secret')
        self.assertEqual(args.kwargs['timeout'],6)
        self.assertNotIn('synthetic-secret',repr(result))


class UpdateWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.settings=QSettings(str(self.root/'settings.ini'),QSettings.Format.IniFormat)

    def test_startup_check_runs_in_background_and_shows_update_action(self):
        result=UpdateResult('available','Neue Version verfügbar','9.0.0',RELEASES_URL+'/tag/v9.0.0')
        with patch('lyrics_studio.app.check_for_updates',return_value=result) as check:
            window=Window(self.root/'projects',self.settings,start_updates=True)
            window.show()
            self.addCleanup(window.close)
            for _ in range(30):
                QTest.qWait(50)
                if window.update_check.isEnabled() and window.update_url:break
            check.assert_called_once()
            self.assertEqual(window.update_url,result.url)
            self.assertFalse(window.update_open.isHidden())
            self.assertIn(__version__,window.windowTitle())
            with patch('lyrics_studio.app.QDesktopServices.openUrl') as open_url:
                window.open_update()
                self.assertEqual(open_url.call_args.args[0].toString(),result.url)

    def test_disabled_automatic_check_makes_no_request(self):
        self.settings.setValue('check_updates_startup',False)
        with patch('lyrics_studio.app.check_for_updates') as check:
            window=Window(self.root/'projects',self.settings,start_updates=True)
            self.addCleanup(window.close)
            QTest.qWait(400)
            check.assert_not_called()
            self.assertIn('deaktiviert',window.update_status.text())


if __name__=='__main__':
    unittest.main()
