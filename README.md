# Sistema di Ricerca Articoli Scientifici

**Ingegneria dei Dati 2025/2026 - Homework 5**
**Studente Lavoratore**

## Descrizione

Sistema avanzato di search su articoli scientifici dove le tabelle e le figure sono trattate come oggetti di prima classe e completamente indicizzabili.

## Requisiti

- Python 3.10+
- Elasticsearch 8.x
- Docker (opzionale, per Elasticsearch)

## Installazione

### 1. Creare ambiente virtuale

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### 2. Installare dipendenze

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m nltk.downloader punkt stopwords
```

### 3. Avviare Elasticsearch

Con Docker:
```bash
docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" -e "xpack.security.enabled=false" elasticsearch:8.12.1
```

Oppure installare manualmente da: https://www.elastic.co/downloads/elasticsearch

### 4. Configurazione

Modificare `config.py` per:
- Selezionare le keyword PubMed (gruppi 1-4)
- Configurare host Elasticsearch

## Utilizzo

### Fase 1: Scraping articoli

```bash
# Scraping da arXiv (Query processing/optimization)
python scrapers/arxiv_scraper.py

# Scraping da PubMed (almeno 500 articoli)
python scrapers/pubmed_scraper.py
```

### Fase 2: Estrazione tabelle e figure

```bash
python extractors/table_extractor.py
python extractors/figure_extractor.py
```

### Fase 3: Indicizzazione

```bash
python indexers/paper_indexer.py
python indexers/table_indexer.py
python indexers/figure_indexer.py
```

### Fase 4: Ricerca

**CLI (Command Line Interface):**
```bash
python cli/search_cli.py
```

**Web Interface:**
```bash
python web/app.py
# Apri http://localhost:5000
```

## Struttura Progetto

```
Homework 5/
├── config.py                 # Configurazione globale
├── requirements.txt          # Dipendenze Python
├── README.md                 # Documentazione
│
├── scrapers/                 # Script di scraping
│   ├── arxiv_scraper.py      # Scraper arXiv
│   └── pubmed_scraper.py     # Scraper PubMed
│
├── extractors/               # Estrazione tabelle/figure
│   ├── table_extractor.py    # Estrazione tabelle
│   └── figure_extractor.py   # Estrazione figure
│
├── indexers/                 # Indicizzazione Elasticsearch
│   ├── elasticsearch_setup.py # Setup indici
│   ├── paper_indexer.py      # Indicizzazione papers
│   ├── table_indexer.py      # Indicizzazione tabelle
│   └── figure_indexer.py     # Indicizzazione figure
│
├── cli/                      # Interfaccia riga di comando
│   └── search_cli.py         # CLI ricerca
│
├── web/                      # Interfaccia web
│   ├── app.py                # Flask application
│   └── templates/            # Template HTML
│       └── index.html        # Pagina principale
│
├── data/                     # Dati scaricati
│   ├── arxiv/                # Articoli arXiv
│   ├── pubmed/               # Articoli PubMed
│   ├── tables/               # Tabelle estratte
│   └── figures/              # Figure estratte
│
└── tests/                    # Test unitari
    └── test_search.py        # Test ricerca
```

## Keywords Assegnate

### arXiv (Studenti Lavoratori)
- "Query processing"
- "Query optimization"

### PubMed (scegliere un gruppo)
- Gruppo 1: "cancer risk AND coffee consumption"
- Gruppo 2: "glyphosate AND cancer risk"
- Gruppo 3: "air pollution AND cognitive decline"
- Gruppo 4: "ultra-processed foods AND cardiovascular risk"


