#!/bin/bash
cd /c/Users/Avett/Documents/Projects/iosont560nu
for k in L A B; do
  SRC=kernel.development.sweet python tools/mkvar_gestalt.py kernel.v$k $k >/dev/null 2>&1
  RD=ufsroot0 EXTRA="sweetsample=SpringBoard ufsrw=1 rootrw=1 nointr_consio=1" bash tools/local_pack.sh kernel.v$k shim-boot-0110v$k.img >/dev/null 2>&1
  python tools/pyfastboot.py reboot-bootloader >/dev/null 2>&1; sleep 6
  bash tools/bootcycle.sh shim-boot-0110v$k.img console_log_0110v$k.txt 300 >/dev/null 2>&1
  echo "$k: nsnull $(grep -ac 'NSNull' console_log_0110v$k.txt) surfpix $(grep -ac SURFPIX console_log_0110v$k.txt) crashes $(grep -ac '^CRASH .*sig' console_log_0110v$k.txt)" >> bisect3.out
done
echo done >> bisect3.out
