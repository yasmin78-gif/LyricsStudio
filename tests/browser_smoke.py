"""Browser regression check with synthetic data: title, status colors and editing.

Run from the repository root: python -B tests/browser_smoke.py
"""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-gpu --log-level=3'
import json, tempfile, time, wave
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl, QEventLoop, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWebEngineWidgets import QWebEngineView
from lyrics_studio import __version__
from lyrics_studio.projects import Library
from lyrics_studio.processing import make_document
from lyrics_studio.sessions import Sessions
from lyrics_editor.store import encoded
app=QApplication([])
for name in ['segoeui.ttf','segoeuib.ttf','seguisym.ttf']:
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)
def js(page, expression):
    loop=QEventLoop()
    value=[]
    page.runJavaScript(expression, lambda result:(value.append(result),loop.quit()))
    QTimer.singleShot(4000,loop.quit)
    loop.exec()
    if not value:raise AssertionError('JavaScript callback timed out')
    return value[0]
def until(page, expression):
    for _ in range(60):
        if js(page,expression):return
        QTest.qWait(100)
    raise AssertionError('UI condition not reached: '+expression)
with tempfile.TemporaryDirectory(prefix='lyrics-browser-test-') as tmp:
    root=Path(tmp);audio=root/'synthetic.wav'
    with wave.open(str(audio),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0'*64000*9)
    project=Library(root/'projects').create('Mein Song · Testprojekt',audio)
    target=project.path('audio.wav');target.write_bytes(audio.read_bytes())
    doc=make_document(target,[(0.2,1.8,'Erste Testpassage'),(2,3.8,'Zweite Testpassage'),(4,6,'Dritte Testpassage')])
    doc['audio']['path']='audio.wav';project.data.write_bytes(encoded(doc));project.update(status='ready')
    sessions=Sessions();server=sessions.open(project);store=server.store
    store.act(dict(action='update',revision=store.revision,id=store.rows[0]['id'],text='Bearbeitete Testpassage',start=0.3,end=1.8))
    store.act(dict(action='confirm',revision=store.revision,id=store.rows[2]['id'],reviewer='Synthetic QA',acknowledge=True))
    view=QWebEngineView();view.resize(1440,1150);view.show()
    view.load(QUrl(f'http://127.0.0.1:{server.server_port}'))
    page=view.page()
    until(page,"document.querySelectorAll('.lyric-row').length === 3 && document.getElementById('waveLoading').hidden")
    state=json.loads(js(page,"JSON.stringify({title:document.getElementById('songTitle').textContent,tab:document.title,rows:[...document.querySelectorAll('.lyric-row')].map(r=>({status:r.className,color:getComputedStyle(r.querySelector('.dot')).backgroundColor,border:getComputedStyle(r).borderLeftColor}))})"))
    assert state['title']==project.info['name'],state
    assert state['tab']==project.info['name']+' · Lyrics Studio '+__version__,state
    assert js(page,"document.getElementById('appVersion').textContent")=='v'+__version__
    for row in state['rows']:
        status=next(s for s in ('unreviewed','editing','confirmed') if s in row['status'])
        legend=js(page,f"getComputedStyle(document.querySelector('.legend .dot.{status}')).backgroundColor")
        assert row['color']==legend==row['border'],(row,legend)
    js(page,"document.querySelectorAll('.lyric-row')[1].click()")
    until(page,"document.querySelectorAll('.lyric-row')[1].classList.contains('selected')")
    assert js(page,"getComputedStyle(document.querySelector('.lyric-row.selected .dot')).backgroundColor")=='rgb(145, 163, 186)'
    QTest.qWait(100)
    preview=Path('editor-test-artifacts/browser-qa/statuses.png').resolve()
    preview.parent.mkdir(parents=True,exist_ok=True)
    view.grab().save(str(preview))
    js(page,"document.querySelectorAll('.lyric-row')[2].click()")
    until(page,"document.querySelectorAll('.lyric-row')[2].classList.contains('selected')")
    js(page,"document.getElementById('text').value='Geänderte bestätigte Passage';document.getElementById('text').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('apply').click()")
    until(page,"document.querySelectorAll('.lyric-row')[2].classList.contains('editing')")
    assert store.rows[2]['status']=='editing'
    assert js(page,"getComputedStyle(document.querySelectorAll('.lyric-row')[2].querySelector('.dot')).backgroundColor")=='rgb(242, 192, 120)'
    print('Browser QA passed: project title, tab title, all status colors, selection, confirmation revoked after edit.')
    view.close();view.setPage(None);app.processEvents();sessions.close()
