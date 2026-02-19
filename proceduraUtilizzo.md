# Procedura per Eseguire il Progetto

## 1. Creare un ambiente virtuale
```powershell
python -m venv venv
.\venv\Scripts\activate
```

## 2. Installare le dipendenze
```powershell
pip install -r requirements.txt
```

## 3. Avviare Elasticsearch
Con Docker:
```powershell
docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" -e "xpack.security.enabled=false" elasticsearch:8.12.1
```
Oppure scarica e installa manualmente da https://www.elastic.co/downloads/elasticsearch

## 4. Eseguire il progetto

### Opzione A: Pipeline Completa (Consigliato)

```powershell
python main.py
```
---

**Note**:
- Prima di iniziare, assicurati che Elasticsearch sia in esecuzione!
- La prima esecuzione richiederà più tempo (scraping e indicizzazione)
- Le esecuzioni successive possono riutilizzare i dati esistenti (opzione [3])