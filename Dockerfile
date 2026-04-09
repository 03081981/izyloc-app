FROM python:3.11-slim

# Instalar FFmpeg e dependencias do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Diretorio de trabalho
WORKDIR /app

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo da aplicacao
COPY . .

# Expor porta
EXPOSE 8000

# Comando de inicializacao
CMD ["python", "server.py"]
