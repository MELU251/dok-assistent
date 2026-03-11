# ---- Build-Stage: Python-Abhängigkeiten installieren ----
FROM python:3.11-slim AS builder

WORKDIR /app

# System-Dependencies für Unstructured (PDF, DOCX, XLSX) und OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten zuerst kopieren → Layer-Cache optimal nutzen
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ---- Finale Stage ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# System-Libraries für Laufzeit (libmagic, poppler, tesseract)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-deu \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installierte Python-Pakete aus Builder-Stage übernehmen
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Anwendungscode kopieren (.env wird NICHT kopiert – kommt als env_file zur Laufzeit)
COPY src/ ./src/
COPY app.py ingest_cli.py ./

# Docs-Verzeichnis anlegen (wird als Volume gemountet)
RUN mkdir -p /app/docs

EXPOSE 8000

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
