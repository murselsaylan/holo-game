"""How much memory the game uses right now, in MB (for the crash breadcrumbs in session.json).

iOS ends an app that grows past its memory limit without any error the app could catch (jetsam), so the last
breadcrumb's number is the best clue there is. iOS / macOS: the "physical footprint" the system itself judges the app
by (task_info TASK_VM_INFO); Android: resident memory (/proc/self/status); elsewhere psutil if it is installed.
Every reader is optional - footprint() returns None rather than ever raising.
"""
import sys

_reader = None


def _darwin_reader():
    import ctypes

    class _VmInfo(ctypes.Structure):          # task_vm_info_data_t up to phys_footprint (TASK_VM_INFO_REV1)
        _fields_ = [("virtual_size", ctypes.c_uint64), ("region_count", ctypes.c_int32), ("page_size", ctypes.c_int32),
                    ("resident_size", ctypes.c_uint64), ("resident_size_peak", ctypes.c_uint64),
                    ("device", ctypes.c_uint64), ("device_peak", ctypes.c_uint64),
                    ("internal", ctypes.c_uint64), ("internal_peak", ctypes.c_uint64),
                    ("external", ctypes.c_uint64), ("external_peak", ctypes.c_uint64),
                    ("reusable", ctypes.c_uint64), ("reusable_peak", ctypes.c_uint64),
                    ("purgeable_volatile_pmap", ctypes.c_uint64), ("purgeable_volatile_resident", ctypes.c_uint64),
                    ("purgeable_volatile_virtual", ctypes.c_uint64),
                    ("compressed", ctypes.c_uint64), ("compressed_peak", ctypes.c_uint64),
                    ("compressed_lifetime", ctypes.c_uint64), ("phys_footprint", ctypes.c_uint64)]

    libc = ctypes.CDLL(None)
    task = ctypes.c_uint32.in_dll(libc, "mach_task_self_").value
    task_info = libc.task_info
    task_info.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]

    def read():
        info = _VmInfo()
        count = ctypes.c_uint32(ctypes.sizeof(_VmInfo) // 4)
        if task_info(task, 22, ctypes.byref(info), ctypes.byref(count)) != 0:      # 22 = TASK_VM_INFO
            return None
        return (info.phys_footprint or info.resident_size) / 1048576.0
    return read


def _linux_reader():
    def read():
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
        return None
    return read


def _psutil_reader():
    import psutil
    proc = psutil.Process()
    return lambda: proc.memory_info().rss / 1048576.0


def footprint():
    """Memory in MB, or None."""
    global _reader
    if _reader is None:
        _reader = False
        for make in ((_darwin_reader,) if sys.platform in ("ios", "darwin") else
                     (_linux_reader,) if sys.platform.startswith("linux") else ()) + (_psutil_reader,):
            try:
                r = make()
                if r() is not None:
                    _reader = r
                    break
            except Exception:
                continue
    if not _reader:
        return None
    try:
        v = _reader()
        return None if v is None else round(v, 1)
    except Exception:
        return None
