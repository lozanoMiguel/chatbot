#!/bin/bash
echo "🚀 Ejecutando entrypoint..."
echo "📁 Directorio actual: $(pwd)"
echo "📂 Archivos: $(ls -la)"

echo "🧠 Ejecutando indexación..."
python3 indexar_documentos.py

echo "🚀 Iniciando servidor..."
uvicorn app.main:app --host 0.0.0.0 --port $PORT