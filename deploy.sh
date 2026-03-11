#!/bin/bash
# deploy.sh – Dok-Assistent auf dem VPS deployen
# Aufruf: chmod +x deploy.sh && ./deploy.sh

set -e  # Bei Fehler sofort abbrechen

echo "=== Dok-Assistent Deployment ==="
echo ""

# 1. Prüfen ob .env existiert
if [ ! -f ".env" ]; then
    echo "[FEHLER] .env nicht gefunden."
    echo "Bitte zuerst: cp .env.example .env && nano .env"
    exit 1
fi
echo "[OK] .env gefunden"

# 2. Prüfen ob CHAINLIT_AUTH_SECRET gesetzt ist
if ! grep -q "^CHAINLIT_AUTH_SECRET=.\+" .env; then
    echo "[FEHLER] CHAINLIT_AUTH_SECRET in .env ist leer."
    echo "Generieren mit: python -c \"import secrets; print(secrets.token_hex(32))\""
    exit 1
fi
echo "[OK] CHAINLIT_AUTH_SECRET gesetzt"

# 3. Docker-Image bauen
echo ""
echo "Baue Docker-Image..."
docker compose build chainlit

# 4. Container starten (oder neu starten falls bereits läuft)
echo ""
echo "Starte Chainlit-Container..."
docker compose up -d chainlit

# 5. Kurz warten und Status prüfen
sleep 3
echo ""
docker compose ps

echo ""
echo "========================================"
echo "[FERTIG] Chainlit läuft auf http://100.103.54.4:8000"
echo "Logs: docker compose logs -f chainlit"
echo "========================================"
