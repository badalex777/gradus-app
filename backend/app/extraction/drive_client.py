"""
Cliente de Google Drive para Gradus.

Maneja la autenticación OAuth2 y las operaciones básicas con la API de Drive.
El token de autenticación se guarda en token.json (ignorado por Git).
"""

from __future__ import annotations

import os
import warnings
import warnings
from pathlib import Path
from typing import List, Optional, Dict, Any

# Silenciar advertencias de versión de Python de las librerías de Google
warnings.filterwarnings("ignore", category=FutureWarning, module="google")
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"

# Permiso de solo lectura — suficiente para listar y descargar documentos
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def get_drive_service():
    """
    Autentica con Google Drive y devuelve el servicio listo para usar.

    - Si ya existe token.json válido: lo reutiliza sin abrir el navegador.
    - Si el token venció: lo renueva automáticamente.
    - Si no hay token: abre el navegador para que el usuario autorice.
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales en: {CREDENTIALS_PATH}\n"
            "Descargá las credenciales de Google Cloud Console y ponelas en la "
            "raíz del proyecto como 'credentials.json'."
        )

    creds = None

    # Intentar reutilizar token guardado
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Si no hay credenciales válidas, iniciar el flujo de autenticación
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("  Token vencido — renovando automáticamente...")
            creds.refresh(Request())
        else:
            print("  Iniciando autenticación con Google Drive...")
            print("  ⚠️  Se abrirá tu navegador. Autorizá el acceso y volvé aquí.")
            print()
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0, open_browser=True)

        # Guardar token para la próxima vez
        TOKEN_PATH.write_text(creds.to_json())
        print(f"  ✓ Token guardado en: {TOKEN_PATH}")

    service = build("drive", "v3", credentials=creds)
    return service


# ---------------------------------------------------------------------------
# Operaciones con Drive
# ---------------------------------------------------------------------------

def listar_archivos(
    service,
    max_results: int = 10,
    query: Optional[str] = None,
    campos: str = "files(id, name, mimeType, modifiedTime, size)",
) -> List[Dict[str, Any]]:
    """
    Lista archivos del Drive.

    Args:
        service: servicio de Drive autenticado
        max_results: cuántos archivos devolver
        query: filtro en sintaxis de Drive API (ej: "mimeType='application/vnd.google-apps.document'")
        campos: qué campos incluir en la respuesta

    Returns:
        Lista de diccionarios con la información de cada archivo.
    """
    params: Dict[str, Any] = {
        "pageSize": max_results,
        "fields": f"nextPageToken, {campos}",
        "orderBy": "modifiedTime desc",
    }
    if query:
        params["q"] = query

    resultado = service.files().list(**params).execute()
    return resultado.get("files", [])


def obtener_contenido_documento(service, file_id: str) -> str:
    """
    Descarga el contenido de un Google Doc como texto plano.
    Solo funciona con Google Docs (no con PDFs ni otros formatos).
    """
    request = service.files().export_media(
        fileId=file_id,
        mimeType="text/plain"
    )
    contenido = request.execute()
    if isinstance(contenido, bytes):
        return contenido.decode("utf-8", errors="replace")
    return contenido


def obtener_metadatos(service, file_id: str) -> Dict[str, Any]:
    """Devuelve los metadatos de un archivo por su ID."""
    return service.files().get(
        fileId=file_id,
        fields="id, name, mimeType, modifiedTime, size, parents"
    ).execute()
