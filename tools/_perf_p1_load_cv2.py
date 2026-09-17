"""Timed OpenCV DLL/pyd load probe for PERF P1 (ARM64)."""
from __future__ import annotations

import ctypes
import os
import time

BIN = r"C:\Users\S8633\.arm64-build\build\bin\Release"
PYD = r"C:\Users\S8633\.arm64-build\build\lib\python3\Release\cv2.cp314-win_arm64.pyd"

os.add_dll_directory(BIN)
os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")

t0 = time.time()
for name in (
    "opencv_core500.dll",
    "opencv_geometry500.dll",
    "opencv_imgproc500.dll",
    "opencv_imgcodecs500.dll",
    "opencv_highgui500.dll",
):
    print(f"loading {name}", flush=True)
    ctypes.WinDLL(os.path.join(BIN, name))
    print(f"ok {name} {time.time() - t0:.2f}s", flush=True)

print("loading pyd", flush=True)
ctypes.WinDLL(PYD)
print(f"ok pyd {time.time() - t0:.2f}s", flush=True)
