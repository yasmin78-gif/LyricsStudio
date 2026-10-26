"""Read-only history audit. Prints finding locations, never matched credentials."""
import json
import re
import subprocess
from pathlib import Path


def audit():
    def git(*args):
        return subprocess.check_output(['git', *args])
    patterns = {
        'credential': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9]{32,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',
        'personal-path': rb'(?:[A-Z]:[\\/](?:Users|Resolve)[\\/][^\s"\x27<>]+)',
    }
    findings = []
    objects = git('rev-list', '--objects', '--all').decode().splitlines()
    seen = {line.split(' ',1)[0] for line in objects}
    for line in git('ls-files','--stage').decode().splitlines():
        metadata, path = line.split('\t',1)
        oid = metadata.split()[1]
        if oid not in seen:
            objects.append(oid+' '+path)
            seen.add(oid)
    blobs = 0
    for line in objects:
        oid, _, path = line.partition(' ')
        if git('cat-file', '-t', oid).strip() != b'blob':
            continue
        blobs += 1
        data = git('cat-file', 'blob', oid)
        if re.search(r'(?i)(?:\.(?:wav|mp3|flac|m4a|mp4|mov|pem|key)|(?:^|/)\.env)$', path):
            findings.append({'kind': 'private-file', 'path': path, 'object': oid})
        if len(data) < 10_000_000 and b'\0' not in data:
            for kind, pattern in patterns.items():
                if re.search(pattern, data):
                    findings.append({'kind': kind, 'path': path, 'object': oid})
    return {'commits': int(git('rev-list','--count','HEAD')), 'blobs_checked': blobs, 'findings': findings}


if __name__ == '__main__':
    report = audit()
    target = Path('editor-test-artifacts/release-audit.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
