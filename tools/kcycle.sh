#!/bin/bash
# Fast kernel test cycle after pushing an xnu/patches change:
#   wait for the xnu CI build of <sha> -> fetch the kernel -> pack the boot
#   image locally (tools/local_pack.sh, no pack CI) -> fastboot boot it.
# The kernel is also committed and pushed so the repo stays in sync; that
# pack CI run is not waited for.
# Usage: bash tools/kcycle.sh <sha> [string that must be in the kernel]
set -e
PROJ=/c/Users/Avett/Documents/Projects/iosont560nu
REPO_DIR=/c/Users/Avett/Documents/GitHub/smt560nu-ios
SHA=$(git -C "$REPO_DIR" rev-parse "$1")
MUST=$2
cd "$PROJ"

T=$(printf "protocol=https\nhost=github.com\n\n" | GCM_INTERACTIVE=never git credential fill 2>/dev/null | sed -n 's/^password=//p')

echo "waiting for xnu build of ${SHA:0:7}"
for i in $(seq 1 60); do
  R=$(curl -s -H "Authorization: Bearer $T" "https://api.github.com/repos/eggdogo/smt560nu-ios/actions/workflows/xnu.yml/runs?head_sha=$SHA&per_page=1" \
      | python -c "import json,sys;r=json.load(sys.stdin)['workflow_runs'];print(r[0]['status'],r[0]['conclusion'],r[0]['id']) if r else print('none')")
  case "$R" in completed*) break;; esac
  sleep 20
done
echo "xnu: $R"
case "$R" in "completed success"*) ;; *) echo "XNU BUILD FAILED"; exit 1;; esac

rm -rf xnu_build && mkdir -p xnu_build
python tools/fetch_build.py --artifact xnu-kernel --sha "${SHA:0:7}" --out xnu_build
cat xnu_build/*.lse.txt
if [ -n "$MUST" ]; then grep -q "$MUST" xnu_build/kernel.development.sweet || { echo "kernel lacks '$MUST'"; exit 1; }; fi
cp xnu_build/kernel.development.sweet kernel.development.sweet

bash tools/local_pack.sh kernel.development.sweet shim-boot.img | tail -1
if timeout 10 python tools/pyfastboot.py getvar product 2>/dev/null | grep -q lk2nd; then
  python tools/pyfastboot.py boot shim-boot.img
else
  echo "tablet not in lk2nd fastboot; boot it later with: python tools/pyfastboot.py boot shim-boot.img"
fi

cp kernel.development.sweet "$REPO_DIR/"
cd "$REPO_DIR"
git add kernel.development.sweet
git commit -q -m "Kernel: CI build of ${SHA:0:7}"
GCM_INTERACTIVE=never GIT_TERMINAL_PROMPT=0 timeout 120 git push origin main 2>&1 | tail -1
