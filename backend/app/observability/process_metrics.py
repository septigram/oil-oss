"""プロセスメトリクス（Windows を含むクロスプラットフォーム）。"""

from __future__ import annotations

import os
import sys

from prometheus_client import Gauge, REGISTRY


def _disable_default_process_collector() -> None:
    """Linux 上の prometheus_client 既定 ProcessCollector と重複しないよう解除する。"""
    try:
        from prometheus_client.process_collector import ProcessCollector

        for collector in tuple(REGISTRY._collector_to_names):
            if isinstance(collector, ProcessCollector):
                REGISTRY.unregister(collector)
    except ImportError:
        pass


_disable_default_process_collector()

PROCESS_RESIDENT_MEMORY_BYTES = Gauge(
    "process_resident_memory_bytes",
    "Resident memory size in bytes.",
)


def _read_rss_windows() -> int | None:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_ulonglong),
                ("WorkingSetSize", ctypes.c_ulonglong),
                ("QuotaPeakPagedPoolUsage", ctypes.c_ulonglong),
                ("QuotaPagedPoolUsage", ctypes.c_ulonglong),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_ulonglong),
                ("QuotaNonPagedPoolUsage", ctypes.c_ulonglong),
                ("PagefileUsage", ctypes.c_ulonglong),
                ("PeakPagefileUsage", ctypes.c_ulonglong),
            ]

        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        access = 0x0400 | 0x0010  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        handle = kernel32.OpenProcess(access, False, os.getpid())
        if not handle:
            return None
        try:
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, ValueError):
        return None
    return None


def _read_rss_unix() -> int | None:
    try:
        with open(f"/proc/{os.getpid()}/status", encoding="ascii") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = int(usage.ru_maxrss)
        if sys.platform == "darwin":
            return rss
        return rss * 1024
    except (OSError, ValueError):
        return None


def read_process_rss_bytes() -> int | None:
    if sys.platform == "win32":
        return _read_rss_windows()
    return _read_rss_unix()


def refresh_process_metrics() -> None:
    rss = read_process_rss_bytes()
    if rss is not None:
        PROCESS_RESIDENT_MEMORY_BYTES.set(rss)
