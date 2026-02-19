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

**Opzionale**: Impostare variabile ambiente per Flask:
```bash
# Windows PowerShell
$env:FLASK_SECRET_KEY="tua-chiave-sicura-qui"

# Linux/Mac
export FLASK_SECRET_KEY="tua-chiave-sicura-qui"
```

Se non impostata, verrà generata automaticamente ad ogni avvio.

## Utilizzo

### Esecuzione Completa (Consigliato)

**Pipeline automatica** che gestisce scraping, estrazione e indicizzazione:

```bash
python main.py
```

Il sistema chiederà interattivamente come procedere:
- **[1] Cancella tutto e ricomincia** - Reset completo
- **[2] Continua** - Salta articoli già scaricati
- **[3] Salta scraping** - Usa dati esistenti e re-indicizza
- **[4] Esci** - Annulla operazione

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
