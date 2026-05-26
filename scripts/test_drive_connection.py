"""
Prueba mínima de conexión con Google Drive.
Lista los primeros 5 archivos del Drive para confirmar que la autenticación funciona.
"""

from __future__ import annotations

import sys
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.extraction.drive_client import get_drive_service, listar_archivos


def main() -> None:
    print("=" * 55)
    print("  PRUEBA DE CONEXIÓN — Google Drive")
    print("=" * 55)
    print()

    # Autenticar
    print("Paso 1: Autenticando con Google Drive...")
    service = get_drive_service()
    print("  ✓ Autenticación exitosa")
    print()

    # Listar los primeros 5 archivos (cualquier tipo)
    print("Paso 2: Listando los 5 archivos más recientes del Drive...")
    archivos = listar_archivos(service, max_results=5)

    if not archivos:
        print("  ⚠️  No se encontraron archivos en el Drive.")
        return

    print(f"  ✓ {len(archivos)} archivos encontrados:\n")
    for i, archivo in enumerate(archivos, 1):
        nombre = archivo.get("name", "(sin nombre)")
        tipo = archivo.get("mimeType", "")
        modificado = archivo.get("modifiedTime", "")[:10]  # solo la fecha

        # Nombre amigable del tipo
        tipo_corto = (
            tipo.replace("application/vnd.google-apps.", "Google ")
                .replace("application/", "")
                .replace("text/", "texto/")
        )

        print(f"  {i}. {nombre}")
        print(f"     Tipo: {tipo_corto}")
        print(f"     Última modificación: {modificado}")
        print()

    print("=" * 55)
    print("  ✅ Conexión con Google Drive funcionando correctamente")
    print("=" * 55)


if __name__ == "__main__":
    main()
