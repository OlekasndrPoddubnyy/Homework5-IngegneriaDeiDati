# Procedura per Eseguire il Progetto

## 1. Creare un ambiente virtuale
```powershell
python -m venv venv
.\venv\Scripts\activate
```

## 2. Installare le dipendenze
```powershell
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m nltk.downloader punkt stopwords
```

## 3. Avviare Elasticsearch
Con Docker:
```powershell
docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" -e "xpack.security.enabled=false" elasticsearch:8.12.1
```
Oppure scarica e installa manualmente da https://www.elastic.co/downloads/elasticsearch

## 4. Eseguire il progetto

Puoi scegliere tra:

**Pipeline completa** (scraping, estrazione, indicizzazione):
```powershell
python main.py
```

**Oppure eseguire le singole fasi**:
```powershell
# Scraping
python scrapers/arxiv_scraper.py
python scrapers/pubmed_scraper.py

# Estrazione
python extractors/table_extractor.py
python extractors/figure_extractor.py

# Indicizzazione
python indexers/paper_indexer.py
python indexers/table_indexer.py
python indexers/figure_indexer.py
```

## 5. Utilizzare l'interfaccia di ricerca

**CLI**:
```powershell
python cli/search_cli.py
```

**Web** (apri http://localhost:5000):
```powershell
python web/app.py
```

---

**Nota**: Prima di iniziare, assicurati che Elasticsearch sia in esecuzione!