import win32com.client
import subprocess
import time
import xml.etree.ElementTree as ET

# Abrir OneNote desktop si no está abierto
subprocess.Popen(['cmd', '/c', 'start', 'onenote:'], shell=True)
time.sleep(3)

for dispatch_name in ['OneNote.Application', 'OneNote.Application.15']:
    try:
        on = win32com.client.GetActiveObject(dispatch_name)
        print(f'GetActiveObject OK: {dispatch_name}')

        import ctypes
        xml_out = ctypes.c_wchar_p('')
        result = on.GetHierarchy('', 1, '')
        print('GetHierarchy:', str(result)[:300])
        break
    except Exception as e:
        print(f'{dispatch_name} GetActiveObject: {e}')

    try:
        on = win32com.client.Dispatch(dispatch_name)
        result = on.GetHierarchy('', 1, '')
        print(f'Dispatch {dispatch_name} GetHierarchy:', str(result)[:300])
        break
    except Exception as e:
        print(f'{dispatch_name} Dispatch: {e}')
