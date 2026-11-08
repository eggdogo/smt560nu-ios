#!/usr/bin/env python3
"""
Download the newest shim-boot-hfs CI artifact from eggdogo/smt560nu-ios and
unpack shim-boot.img + slim_ramdisk.dmg into the project root.

Auth comes from the GitHub sign-in Git Credential Manager already stores
(`git credential fill`), so no token lives in this repo.

Usage: python tools/fetch_build.py [--sha <commit>] [--boot]
"""
import argparse, io, json, os, subprocess, sys, urllib.request, zipfile

REPO = 'eggdogo/smt560nu-ios'
ARTIFACT = 'shim-boot-hfs'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def github_token():
    env = dict(os.environ, GCM_INTERACTIVE='never', GIT_TERMINAL_PROMPT='0')
    out = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                         capture_output=True, text=True, env=env, timeout=30).stdout
    for line in out.splitlines():
        if line.startswith('password='):
            return line[len('password='):]
    sys.exit('no stored GitHub credential; push once from a terminal to sign in')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def api(token, url):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}',
                                               'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 307):
            raise
        # Artifact zips redirect to signed blob storage, which rejects the GitHub token
        with urllib.request.urlopen(e.headers['Location']) as r:
            return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sha', help='only accept a build of this commit (prefix ok)')
    ap.add_argument('--boot', action='store_true', help='fastboot boot the image afterwards')
    args = ap.parse_args()

    token = github_token()
    arts = json.loads(api(token, f'https://api.github.com/repos/{REPO}/actions/artifacts?name={ARTIFACT}&per_page=10'))
    arts = [a for a in arts['artifacts'] if not a['expired']]
    if args.sha:
        arts = [a for a in arts if a['workflow_run']['head_sha'].startswith(args.sha)]
    if not arts:
        sys.exit('no matching artifact yet (CI still running?)')
    a = arts[0]
    print(f"artifact {a['id']} from {a['workflow_run']['head_sha'][:7]}, {a['created_at']}, {a['size_in_bytes']:,} bytes")

    blob = api(token, a['archive_download_url'])
    with open(os.path.join(ROOT, f'{ARTIFACT}.zip'), 'wb') as f:
        f.write(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            z.extract(name, ROOT)
            print(f'  {name}')

    if args.boot:
        subprocess.check_call([sys.executable, os.path.join(ROOT, 'tools', 'pyfastboot.py'),
                               'boot', os.path.join(ROOT, 'shim-boot.img')])


if __name__ == '__main__':
    main()
