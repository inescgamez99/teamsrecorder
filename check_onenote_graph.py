"""
Prueba de autenticacion y acceso a OneNote via Microsoft Graph API.
Usa el cliente publico de Microsoft (no necesita registro de app).
"""
import msal
import requests

# Client ID de Microsoft Graph Explorer (publico, no necesita secreto)
CLIENT_ID = '14d82eec-204b-4c2f-b7e8-296a70dab67e'  # Microsoft Graph Explorer app
SCOPES = ['Notes.ReadWrite', 'Notes.Read']
AUTHORITY = 'https://login.microsoftonline.com/common'

app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

# Device flow: el usuario se autentica en el navegador
flow = app.initiate_device_flow(scopes=SCOPES)
print(f"\n{'='*50}")
print("Para autenticarte en OneNote:")
print(f"1. Ve a: {flow['verification_uri']}")
print(f"2. Introduce el codigo: {flow['user_code']}")
print(f"{'='*50}\n")

result = app.acquire_token_by_device_flow(flow)

if 'access_token' in result:
    print("Autenticacion OK!")
    headers = {'Authorization': f"Bearer {result['access_token']}"}
    r = requests.get('https://graph.microsoft.com/v1.0/me/onenote/notebooks', headers=headers)
    if r.status_code == 200:
        notebooks = r.json().get('value', [])
        print(f"\nCuadernos encontrados ({len(notebooks)}):")
        for nb in notebooks:
            print(f"  - {nb['displayName']}  (ID: {nb['id'][:20]}...)")
    else:
        print(f"Error listando cuadernos: {r.status_code} {r.text[:200]}")
else:
    print(f"Error de autenticacion: {result.get('error_description', result)}")
