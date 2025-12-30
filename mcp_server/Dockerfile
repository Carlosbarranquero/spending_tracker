FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./server.py

# Lo mejor es montarlo por volumen, pero si quieres lo puedes copiar:
COPY service-account.json ./service-account.json

CMD ["python", "/app/server.py"]
