import psutil
from pycaw.pycaw import AudioUtilities

pids = {p.pid: p.name() for p in psutil.process_iter(['name', 'pid'])
        if 'team' in (p.info['name'] or '').lower()}

print("PIDs Teams:", pids)
print("\nSesiones de audio:")
for s in AudioUtilities.GetAllSessions():
    name = s.Process.name() if s.Process else '(sistema)'
    pid  = s.Process.pid if s.Process else 0
    print(f"  [{s.State}] PID {pid}: {name}  {'<-- TEAMS ACTIVO' if pid in pids and s.State == 1 else ''}")
