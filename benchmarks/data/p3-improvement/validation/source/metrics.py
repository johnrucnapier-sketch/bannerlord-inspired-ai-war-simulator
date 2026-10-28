"""Read peak memory from this actual Python process, not the Windows venv launcher."""
import sys

def peak_memory_mib():
    try:
        if sys.platform=='win32':
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetCurrentProcess.restype=wintypes.HANDLE
            psapi=ctypes.WinDLL('psapi',use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
            counters=Counters();counters.cb=ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
                return None
            return round(counters.PeakWorkingSetSize/(1024*1024),2)
        import resource
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak/(1024*1024 if sys.platform=='darwin' else 1024),2)
    except (OSError,ImportError,AttributeError):return None
