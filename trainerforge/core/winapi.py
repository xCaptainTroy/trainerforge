"""Thin, dependency-free Win32 bindings used by TrainerForge.

Only the APIs needed for process discovery, memory access, module lookup and
global hotkeys are declared here. Everything is read-only with respect to the
operating system; TrainerForge never installs a driver or a service.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

if os.name != "nt":  # pragma: no cover - the whole project is Windows-first
    raise RuntimeError("TrainerForge requires Windows")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
HANDLE = wintypes.HANDLE
LPVOID = wintypes.LPVOID
LPCVOID = ctypes.c_void_p
SIZE_T = ctypes.c_size_t
LPCWSTR = wintypes.LPCWSTR
LPWSTR = wintypes.LPWSTR

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# ---------------------------------------------------------------------------
# Process access rights
# ---------------------------------------------------------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_ALL_ACCESS = 0x1F0FFF

SYNCHRONIZE = 0x00100000

# ---------------------------------------------------------------------------
# Memory constants
# ---------------------------------------------------------------------------
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE = 0x10000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100
PAGE_NOCACHE = 0x200
PAGE_WRITECOMBINE = 0x400

MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000

READABLE_PROTECTIONS = (
    PAGE_READONLY
    | PAGE_READWRITE
    | PAGE_WRITECOPY
    | PAGE_EXECUTE_READ
    | PAGE_EXECUTE_READWRITE
    | PAGE_EXECUTE_WRITECOPY
)

WRITABLE_PROTECTIONS = (
    PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY
)

LIST_MODULES_ALL = 0x03

# Hotkey constants
WM_HOTKEY = 0x0312
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HWND_MESSAGE = ctypes.c_void_p(-3)

# Token constants
TOKEN_QUERY = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020
SE_PRIVILEGE_ENABLED = 0x00000002
ERROR_NOT_ALL_ASSIGNED = 1300
TokenElevation = 20
TokenElevationType = 18

# Error codes
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87
ERROR_PARTIAL_COPY = 299

IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------
class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", DWORD),
        ("__alignment1", DWORD),
        ("RegionSize", ctypes.c_uint64),
        ("State", DWORD),
        ("Protect", DWORD),
        ("Type", DWORD),
        ("__alignment2", DWORD),
    ]


class MEMORY_BASIC_INFORMATION32(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint32),
        ("AllocationBase", ctypes.c_uint32),
        ("AllocationProtect", DWORD),
        ("RegionSize", ctypes.c_uint32),
        ("State", DWORD),
        ("Protect", DWORD),
        ("Type", DWORD),
    ]


MEMORY_BASIC_INFORMATION = (
    MEMORY_BASIC_INFORMATION64 if ctypes.sizeof(ctypes.c_void_p) == 8 else MEMORY_BASIC_INFORMATION32
)


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", LPVOID),
        ("SizeOfImage", DWORD),
        ("EntryPoint", LPVOID),
    ]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", DWORD)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", DWORD),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


# ---------------------------------------------------------------------------
# Function prototypes
# ---------------------------------------------------------------------------
kernel32.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
kernel32.OpenProcess.restype = HANDLE

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = HANDLE

kernel32.ReadProcessMemory.argtypes = [HANDLE, LPCVOID, LPVOID, SIZE_T, ctypes.POINTER(SIZE_T)]
kernel32.ReadProcessMemory.restype = BOOL

kernel32.WriteProcessMemory.argtypes = [HANDLE, LPCVOID, LPCVOID, SIZE_T, ctypes.POINTER(SIZE_T)]
kernel32.WriteProcessMemory.restype = BOOL

kernel32.VirtualQueryEx.argtypes = [
    HANDLE,
    LPCVOID,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    SIZE_T,
]
kernel32.VirtualQueryEx.restype = SIZE_T

kernel32.QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, ctypes.POINTER(DWORD)]
kernel32.QueryFullProcessImageNameW.restype = BOOL

if hasattr(kernel32, "IsWow64Process2"):
    kernel32.IsWow64Process2.argtypes = [
        HANDLE,
        ctypes.POINTER(wintypes.USHORT),
        ctypes.POINTER(wintypes.USHORT),
    ]
    kernel32.IsWow64Process2.restype = BOOL

kernel32.IsWow64Process.argtypes = [HANDLE, ctypes.POINTER(BOOL)]
kernel32.IsWow64Process.restype = BOOL

kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
kernel32.WaitForSingleObject.restype = DWORD

kernel32.GetModuleHandleW.argtypes = [LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

psapi.EnumProcesses.argtypes = [ctypes.POINTER(DWORD), DWORD, ctypes.POINTER(DWORD)]
psapi.EnumProcesses.restype = BOOL

psapi.EnumProcessModulesEx.argtypes = [
    HANDLE,
    ctypes.POINTER(wintypes.HMODULE),
    DWORD,
    ctypes.POINTER(DWORD),
    DWORD,
]
psapi.EnumProcessModulesEx.restype = BOOL

psapi.GetModuleBaseNameW.argtypes = [HANDLE, wintypes.HMODULE, LPWSTR, DWORD]
psapi.GetModuleBaseNameW.restype = DWORD

psapi.GetModuleFileNameExW.argtypes = [HANDLE, wintypes.HMODULE, LPWSTR, DWORD]
psapi.GetModuleFileNameExW.restype = DWORD

psapi.GetModuleInformation.argtypes = [
    HANDLE,
    wintypes.HMODULE,
    ctypes.POINTER(MODULEINFO),
    DWORD,
]
psapi.GetModuleInformation.restype = BOOL

advapi32.OpenProcessToken.argtypes = [HANDLE, DWORD, ctypes.POINTER(HANDLE)]
advapi32.OpenProcessToken.restype = BOOL

advapi32.LookupPrivilegeValueW.argtypes = [LPCWSTR, LPCWSTR, ctypes.POINTER(LUID)]
advapi32.LookupPrivilegeValueW.restype = BOOL

advapi32.AdjustTokenPrivileges.argtypes = [
    HANDLE,
    BOOL,
    ctypes.POINTER(TOKEN_PRIVILEGES),
    DWORD,
    ctypes.POINTER(TOKEN_PRIVILEGES),
    ctypes.POINTER(DWORD),
]
advapi32.AdjustTokenPrivileges.restype = BOOL

advapi32.GetTokenInformation.argtypes = [HANDLE, DWORD, LPVOID, DWORD, ctypes.POINTER(DWORD)]
advapi32.GetTokenInformation.restype = BOOL

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = BOOL

user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = BOOL

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = BOOL

user32.CreateWindowExW.argtypes = [
    DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = BOOL

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = BOOL

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t


def last_error() -> int:
    return ctypes.get_last_error()


def error_text(code: int | None = None) -> str:
    code = last_error() if code is None else code
    try:
        return ctypes.FormatError(code).strip() or f"Windows error {code}"
    except Exception:  # pragma: no cover - defensive
        return f"Windows error {code}"


def open_process(pid: int, rights: int) -> HANDLE | None:
    return kernel32.OpenProcess(rights, False, int(pid))


def close_handle(handle: int | None) -> None:
    if handle:
        kernel32.CloseHandle(handle)


def is_process_alive(handle: int) -> bool:
    if not handle:
        return False
    # WAIT_TIMEOUT (258) means the process is still running.
    return kernel32.WaitForSingleObject(handle, 0) == 258


def process_image_path(pid: int) -> str:
    """Return the full image path for a PID, or an empty string if denied."""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def query_architecture(handle: int) -> tuple[int, str]:
    """Return ``(pointer_size, label)`` for a process handle.

    ``IsWow64Process2`` distinguishes a 32-bit process on 64-bit Windows from
    a native 64-bit process. If it is unavailable we fall back to the older
    WOW64 API, which is sufficient for the x86/x64 targets TrainerForge
    supports.
    """
    if hasattr(kernel32, "IsWow64Process2"):
        process_machine = wintypes.USHORT(0)
        native_machine = wintypes.USHORT(0)
        if kernel32.IsWow64Process2(handle, ctypes.byref(process_machine), ctypes.byref(native_machine)):
            machine = process_machine.value
            if machine == 0:
                machine = native_machine.value
            if machine == IMAGE_FILE_MACHINE_I386:
                return 4, "x86"
            if machine == IMAGE_FILE_MACHINE_AMD64:
                return 8, "x64"
            if machine == IMAGE_FILE_MACHINE_ARM64:
                return 8, "ARM64"
            return (8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 4), "unknown"

    wow64 = BOOL(0)
    if kernel32.IsWow64Process(handle, ctypes.byref(wow64)):
        if wow64.value:
            return 4, "x86"
        return (8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 4), "x64"
    return (8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 4), "unknown"


def is_admin() -> bool:
    token = HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        return False
    try:
        elevation = TOKEN_ELEVATION()
        returned = DWORD(0)
        if advapi32.GetTokenInformation(
            token,
            TokenElevation,
            ctypes.byref(elevation),
            ctypes.sizeof(elevation),
            ctypes.byref(returned),
        ):
            return bool(elevation.TokenIsElevated)
        return False
    finally:
        kernel32.CloseHandle(token)


def enable_debug_privilege() -> tuple[bool, str]:
    """Enable SeDebugPrivilege for the current process.

    This requires the process token to belong to an elevated administrator.
    It never bypasses Windows security: the API call simply enables a privilege
    the user already holds.
    """
    token = HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(token),
    ):
        return False, error_text()

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
            return False, error_text()

        privileges = TOKEN_PRIVILEGES()
        privileges.PrivilegeCount = 1
        privileges.Privileges[0].Luid = luid
        privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        if not advapi32.AdjustTokenPrivileges(
            token, False, ctypes.byref(privileges), 0, None, None
        ):
            return False, error_text()

        if ctypes.get_last_error() == ERROR_NOT_ALL_ASSIGNED:
            return False, "SeDebugPrivilege is not held by this token (run as administrator)."
        return True, ""
    finally:
        kernel32.CloseHandle(token)


def enum_process_ids() -> list[int]:
    """Return all process IDs visible to the current user."""
    capacity = 4096
    while True:
        array = (DWORD * capacity)()
        needed = DWORD(0)
        if not psapi.EnumProcesses(array, ctypes.sizeof(array), ctypes.byref(needed)):
            raise OSError(last_error(), "EnumProcesses failed: " + error_text())
        count = needed.value // ctypes.sizeof(DWORD)
        if count < capacity:
            return [int(array[i]) for i in range(count)]
        capacity = max(capacity * 2, count + 1024)


def enum_modules(handle: int) -> list[tuple[int, int, str, str]]:
    """Return ``(base, size, name, path)`` tuples for a process."""
    capacity = 1024
    while True:
        array = (wintypes.HMODULE * capacity)()
        needed = DWORD(0)
        if not psapi.EnumProcessModulesEx(
            handle,
            array,
            ctypes.sizeof(array),
            ctypes.byref(needed),
            LIST_MODULES_ALL,
        ):
            raise OSError(last_error(), "EnumProcessModulesEx failed: " + error_text())
        count = needed.value // ctypes.sizeof(wintypes.HMODULE)
        if count <= capacity:
            break
        capacity = max(capacity * 2, count + 256)

    result: list[tuple[int, int, str, str]] = []
    for index in range(count):
        module = array[index]
        if not module:
            continue
        name_buffer = ctypes.create_unicode_buffer(1024)
        path_buffer = ctypes.create_unicode_buffer(32768)
        name_len = psapi.GetModuleBaseNameW(handle, module, name_buffer, len(name_buffer))
        path_len = psapi.GetModuleFileNameExW(handle, module, path_buffer, len(path_buffer))
        info = MODULEINFO()
        if not psapi.GetModuleInformation(handle, module, ctypes.byref(info), ctypes.sizeof(info)):
            continue
        base = int(info.lpBaseOfDll or 0)
        size = int(info.SizeOfImage)
        name = name_buffer.value if name_len else ""
        path = path_buffer.value if path_len else ""
        if not name and path:
            name = os.path.basename(path)
        result.append((base, size, name, path))
    result.sort(key=lambda item: item[0])
    return result
