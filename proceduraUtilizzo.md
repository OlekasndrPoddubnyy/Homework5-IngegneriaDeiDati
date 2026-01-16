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

Il sistema presenterà un menu interattivo se trova dati esistenti:

```
DATI ESISTENTI TROVATI
================================
   arXiv: X articoli in metadata, Y file HTML
   PubMed: X articoli in metadata, Y file HTML
================================

Cosa vuoi fare?
  [1] Cancella tutto e ricomincia da zero
  [2] Continua (salta articoli già scaricati)
  [3] Salta lo scraping e usa i dati esistenti
  [4] Esci
```

**Scelta consigliata**:
- **[1]** se vuoi ricominciare completamente
- **[2]** se la precedente esecuzione si è interrotta
- **[3]** se vuoi solo re-indicizzare i dati esistenti

### Opzione B: Esecuzione Modulare

Puoi anche eseguire le singole fasi separatamente:

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

**Web Interface** (Consigliata - più funzionalità):
```powershell
python web/app.py
```
Poi apri il browser su http://localhost:5000

**Funzionalità Web UI**:
- Ricerca full-text e booleana (AND, OR, NOT)
- Filtro per fonte: Tutte / Solo arXiv / Solo PubMed
- Ricerca in: Articoli / Tabelle / Figure
- Visualizzazione dettagli articolo con tabelle e figure
- Highlighting dei termini cercati

**CLI** (Interfaccia linea di comando):
```powershell
python cli/search_cli.py
```

---

**Note**:
- Prima di iniziare, assicurati che Elasticsearch sia in esecuzione!
- La prima esecuzione richiederà più tempo (scraping e indicizzazione)
- Le esecuzioni successive possono riutilizzare i dati esistenti (opzione [3])