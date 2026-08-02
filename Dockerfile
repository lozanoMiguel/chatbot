FROM python:3.11-slim

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema necesarias para ChromaDB/SQLite
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar requirements.txt primero (para aprovechar caché de Docker)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto (Render usará $PORT)
EXPOSE 8000

# Comando para ejecutar la aplicación
# Usamos el puerto de Render ($PORT) y ejecutamos indexación antes
CMD sh -c "python indexar_documentos.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT"