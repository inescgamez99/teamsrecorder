import psutil
import win32gui
import win32process

pids = {p.pid: p.name() for p in psutil.process_iter(['name', 'pid'])
        if 'team' in (p.info['name'] or '').lower()}

print("Procesos Teams encontrados:")
for pid, name in pids.items():
    print(f"  PID {pid}: {name}")

print("\nVentanas de esos procesos:")
def cb(hwnd, _):
    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid in pids and title:
        print(f"  [{pid}] {title}")

win32gui.EnumWindows(cb, None)
