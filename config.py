"""
Configurazione del sistema di ricerca articoli scientifici.
Ingegneria dei Dati 2025/2026 - Homework 5
Studente Lavoratore - Keywords: "Query processing" / "Query optimization"
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============== ELASTICSEARCH CONFIG ==============
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ELASTICSEARCH_PORT = int(os.getenv("ELASTICSEARCH_PORT", 9200))
ELASTICSEARCH_URL = f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"

# Indici Elasticsearch
INDEX_PAPERS = "scientific_papers"
INDEX_TABLES = "paper_tables"
INDEX_FIGURES = "paper_figures"

# ============== ARXIV CONFIG ==============
ARXIV_BASE_URL = "https://arxiv.org"
ARXIV_SEARCH_URL = "https://arxiv.org/search/"

# Keywords per studenti lavoratori
ARXIV_KEYWORDS = [
    "Query processing",
    "Query optimization"
]

# ============== PUBMED CONFIG ==============
PUBMED_BASE_URL = "https://pmc.ncbi.nlm.nih.gov"
PUBMED_SEARCH_URL = "https://pmc.ncbi.nlm.nih.gov/search/"
PUBMED_OPEN_ACCESS_FILTER = "filter=collections.open_access"

# Scegli uno dei gruppi per PubMed (decommentare quello scelto)
# Gruppo 1:
PUBMED_KEYWORDS = ["cancer risk AND coffee consumption"]
# Gruppo 2:
# PUBMED_KEYWORDS = ["glyphosate AND cancer risk"]
# Gruppo 3:
# PUBMED_KEYWORDS = ["air pollution AND cognitive decline"]
# Gruppo 4:
# PUBMED_KEYWORDS = ["ultra-processed foods AND cardiovascular risk"]

# Numero minimo di articoli da recuperare da PubMed
PUBMED_MIN_ARTICLES = 500

# ============== SCRAPING CONFIG ==============
REQUEST_DELAY = 1.5  # Delay tra richieste (secondi) per rispettare rate limits
REQUEST_TIMEOUT = 15  # Timeout per richieste HTTP (ridotto per evitare blocchi)
MAX_RETRIES = 3  # Numero massimo di tentativi per richiesta

# Headers per le richieste HTTP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ============== DATA DIRECTORIES ==============
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PAPERS_DIR = DATA_DIR / "papers"
ARXIV_DATA_DIR = DATA_DIR / "arxiv"
PUBMED_DATA_DIR = DATA_DIR / "pubmed"
TABLES_DIR = DATA_DIR / "tables"
FIGURES_DIR = DATA_DIR / "figures"

# Crea le directory se non esistono
for directory in [DATA_DIR, PAPERS_DIR, ARXIV_DATA_DIR, PUBMED_DATA_DIR, TABLES_DIR, FIGURES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============== STOPWORDS (termini non informativi) ==============
STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", 
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "e", "o", "ma", "se", "che", "come", "dove", "quando",
    "questo", "quello", "quale", "chi", "cosa", "sono", "essere"
}

STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "this", "that", "these",
    "those", "it", "its", "they", "them", "their", "we", "our", "you", "your",
    "he", "she", "him", "her", "his", "hers", "who", "which", "what", "where",
    "when", "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "so", "than", "too",
    "very", "just", "also", "now", "here", "there", "then", "if", "about",
    "into", "through", "during", "before", "after", "above", "below", "between"
}

STOPWORDS = STOPWORDS_IT.union(STOPWORDS_EN)

# ============== FLASK CONFIG ==============
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
