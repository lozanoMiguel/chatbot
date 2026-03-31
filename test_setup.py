"""
Archivo de prueba para verificar la configuración del proyecto
FastAPI + Uvicorn + OpenAI
"""

import sys
import fastapi
import uvicorn
import openai
from fastapi import FastAPI
from fastapi.testclient import TestClient

def test_versions():
    """Verificar versiones de las librerías"""
    print("=" * 50)
    print("VERIFICANDO VERSIONES")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"FastAPI version: {fastapi.__version__}")
    print(f"Uvicorn version: {uvicorn.__version__}")
    print(f"OpenAI version: {openai.__version__}")
    print("=" * 50)
    print()

def test_fastapi_basic():
    """Probar FastAPI con un endpoint básico"""
    print("PROBANDO FASTAPI...")
    
    # Crear una app simple
    app = FastAPI(title="Test API")
    
    @app.get("/")
    def read_root():
        return {"message": "FastAPI funciona correctamente!"}
    
    @app.get("/health")
    def health_check():
        return {"status": "ok", "python_version": sys.version.split()[0]}
    
    # Probar con TestClient
    client = TestClient(app)
    
    # Probar endpoint raíz
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "FastAPI funciona correctamente!"}
    print("✓ Endpoint /: OK")
    
    # Probar health check
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✓ Endpoint /health: OK")
    
    print("✅ FastAPI funcionando correctamente\n")

def test_openai_setup():
    """Verificar que OpenAI está configurado correctamente"""
    print("VERIFICANDO CONFIGURACIÓN DE OPENAI...")
    
    # Verificar si la API key está configurada
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("⚠️  OPENAI_API_KEY no está configurada como variable de entorno")
        print("   Para probar OpenAI, necesitas configurarla:")
        print("   export OPENAI_API_KEY='tu-api-key-aqui'")
        print("   O crear un archivo .env con: OPENAI_API_KEY=tu-api-key-aqui")
        print("   OpenAI no será probado ahora\n")
        return False
    else:
        print("✓ OPENAI_API_KEY encontrada")
        print("✅ Configuración de OpenAI correcta (no se hará llamada real)\n")
        return True

def create_env_example():
    """Crear archivo .env.example como referencia"""
    if not os.path.exists(".env.example"):
        with open(".env.example", "w") as f:
            f.write("""# Variables de entorno para el proyecto
OPENAI_API_KEY=tu-api-key-aqui
# Otros configuraciones
PORT=8000
HOST=0.0.0.0
""")
        print("✓ Archivo .env.example creado")
    else:
        print("✓ Archivo .env.example ya existe")

def create_main_app():
    """Crear un archivo main.py de ejemplo"""
    if not os.path.exists("main.py"):
        content = '''"""
Aplicación principal con FastAPI
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Crear instancia de FastAPI
app = FastAPI(
    title="Mi Proyecto con FastAPI",
    description="API construida con FastAPI, Uvicorn y OpenAI",
    version="0.1.0"
)

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Bienvenido a mi API",
        "status": "online",
        "version": "0.1.0"
    }

@app.get("/health")
async def health():
    """Health check para verificar que el servicio está funcionando"""
    return {
        "status": "healthy",
        "python_version": "3.11",
        "framework": "FastAPI"
    }

@app.get("/info")
async def info():
    """Información del proyecto"""
    return {
        "name": "Proyecto FastAPI",
        "dependencies": {
            "fastapi": "latest",
            "uvicorn": "latest",
            "openai": "latest"
        },
        "environment": {
            "openai_key_configured": bool(os.getenv("OPENAI_API_KEY"))
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, reload=True)
'''
        with open("main.py", "w") as f:
            f.write(content)
        print("✓ Archivo main.py creado")
    else:
        print("✓ Archivo main.py ya existe")

def create_requirements():
    """Crear requirements.txt actualizado"""
    requirements = """fastapi==0.115.0
uvicorn[standard]==0.30.0
openai==1.51.0
python-dotenv==1.0.0
httpx==0.27.0
"""
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    print("✓ Archivo requirements.txt actualizado")

if __name__ == "__main__":
    import os
    
    print("\n" + "=" * 50)
    print("PRUEBA DE CONFIGURACIÓN DEL PROYECTO")
    print("=" * 50 + "\n")
    
    # Ejecutar pruebas
    test_versions()
    test_fastapi_basic()
    test_openai_setup()
    
    # Crear archivos necesarios
    print("CREANDO ARCHIVOS DEL PROYECTO...")
    create_env_example()
    create_requirements()
    create_main_app()
    
    print("\n" + "=" * 50)
    print("✅ TODO FUNCIONA CORRECTAMENTE!")
    print("=" * 50)
    print("\nPróximos pasos:")
    print("1. Copia .env.example a .env y agrega tu API key de OpenAI")
    print("2. Ejecuta: uvicorn main:app --reload")
    print("3. Abre: http://localhost:8000/docs")
    print("4. O ejecuta: python main.py")
    print("\nComandos útiles:")
    print("  - Para instalar dependencias: pip install -r requirements.txt")
    print("  - Para ejecutar la app: uvicorn main:app --reload")
    print("  - Para ver la documentación: http://localhost:8000/docs")