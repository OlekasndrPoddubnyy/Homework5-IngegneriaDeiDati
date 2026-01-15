"""
Pipeline principale del sistema di ricerca.
Ingegneria dei Dati 2025/2026 - Homework 5

Questo script esegue l'intero workflow:
1. Scraping articoli da arXiv e PubMed
2. Estrazione tabelle e figure
3. Indicizzazione in Elasticsearch
"""

import os
import sys
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importa moduli del progetto
from config import (
    DATA_DIR, PAPERS_DIR, ARXIV_KEYWORDS, PUBMED_KEYWORDS,
    ELASTICSEARCH_URL, ARXIV_DATA_DIR, PUBMED_DATA_DIR
)
from scrapers.arxiv_scraper import ArxivScraper
from scrapers.pubmed_scraper import PubMedScraper
from extractors.table_extractor import TableExtractor
from extractors.figure_extractor import FigureExtractor
from indexers.elasticsearch_setup import get_elasticsearch_client, create_indices
from indexers.paper_indexer import PaperIndexer
from indexers.table_indexer import TableIndexer
from indexers.figure_indexer import FigureIndexer


def check_existing_data():
    """
    Controlla se esistono dati precedenti e chiede all'utente come procedere.
    
    Returns:
        str: 'fresh' per ricominciare, 'continue' per continuare, 'skip' per saltare scraping
    """
    arxiv_metadata = DATA_DIR / "arxiv_metadata.json"
    pubmed_metadata = DATA_DIR / "pubmed_metadata.json"
    
    arxiv_exists = arxiv_metadata.exists()
    pubmed_exists = pubmed_metadata.exists()
    
    # Conta file HTML/XML esistenti
    arxiv_html_count = len(list(ARXIV_DATA_DIR.glob("*.html"))) if ARXIV_DATA_DIR.exists() else 0
    pubmed_html_count = len(list(PUBMED_DATA_DIR.glob("*.html"))) + len(list(PUBMED_DATA_DIR.glob("*.xml"))) if PUBMED_DATA_DIR.exists() else 0
    
    if not arxiv_exists and not pubmed_exists and arxiv_html_count == 0 and pubmed_html_count == 0:
        print("\n[INFO] Nessun dato esistente trovato. Avvio nuovo scraping...")
        return 'fresh'
    
    print("\n" + "=" * 60)
    print("DATI ESISTENTI TROVATI")
    print("=" * 60)
    
    if arxiv_exists:
        with open(arxiv_metadata, 'r', encoding='utf-8') as f:
            arxiv_data = json.load(f)
        print(f"   arXiv: {len(arxiv_data)} articoli in metadata, {arxiv_html_count} file HTML")
    else:
        print(f"   arXiv: nessun metadata, {arxiv_html_count} file HTML")
    
    if pubmed_exists:
        with open(pubmed_metadata, 'r', encoding='utf-8') as f:
            pubmed_data = json.load(f)
        print(f"   PubMed: {len(pubmed_data)} articoli in metadata, {pubmed_html_count} file HTML")
    else:
        print(f"   PubMed: nessun metadata, {pubmed_html_count} file HTML")
    
    print("=" * 60)
    print("\nCosa vuoi fare?")
    print("  [1] Cancella tutto e ricomincia da zero")
    print("  [2] Continua (salta articoli già scaricati)")
    print("  [3] Salta lo scraping e usa i dati esistenti")
    print("  [4] Esci")
    
    while True:
        try:
            choice = input("\nScelta (1-4): ").strip()
            
            if choice == '1':
                confirm = input("Sei sicuro? Tutti i dati saranno eliminati (s/n): ").strip().lower()
                if confirm == 's':
                    print("\n[INFO] Eliminazione dati esistenti...")
                    # Elimina metadata
                    if arxiv_metadata.exists():
                        arxiv_metadata.unlink()
                    if pubmed_metadata.exists():
                        pubmed_metadata.unlink()
                    # Elimina HTML files
                    if ARXIV_DATA_DIR.exists():
                        for f in ARXIV_DATA_DIR.glob("*.html"):
                            f.unlink()
                    if PUBMED_DATA_DIR.exists():
                        for f in PUBMED_DATA_DIR.glob("*.html"):
                            f.unlink()
                    # Elimina altri file json nella data dir
                    for f in DATA_DIR.glob("*.json"):
                        f.unlink()
                    print("[OK] Dati eliminati. Avvio nuovo scraping...")
                    return 'fresh'
                else:
                    continue
                    
            elif choice == '2':
                print("\n[INFO] Continuazione scraping (articoli esistenti saranno saltati)...")
                return 'continue'
                
            elif choice == '3':
                print("\n[INFO] Uso dati esistenti, scraping saltato...")
                return 'skip'
                
            elif choice == '4':
                print("\n[INFO] Uscita...")
                sys.exit(0)
                
            else:
                print("[WARN] Scelta non valida. Inserisci 1, 2, 3 o 4.")
                
        except KeyboardInterrupt:
            print("\n\n[INFO] Operazione annullata.")
            sys.exit(0)


def load_existing_articles():
    """Carica articoli esistenti dai file metadata."""
    arxiv_articles = []
    pubmed_articles = []
    
    arxiv_metadata = DATA_DIR / "arxiv_metadata.json"
    pubmed_metadata = DATA_DIR / "pubmed_metadata.json"
    
    if arxiv_metadata.exists():
        with open(arxiv_metadata, 'r', encoding='utf-8') as f:
            arxiv_articles = json.load(f)
        print(f"[INFO] Caricati {len(arxiv_articles)} articoli arXiv esistenti")
    
    if pubmed_metadata.exists():
        with open(pubmed_metadata, 'r', encoding='utf-8') as f:
            pubmed_articles = json.load(f)
        print(f"[INFO] Caricati {len(pubmed_articles)} articoli PubMed esistenti")
    
    return arxiv_articles, pubmed_articles


def run_scraping(continue_mode=False):
    """
    Esegue lo scraping di articoli da arXiv e PubMed.
    
    Args:
        continue_mode: Se True, salta articoli già scaricati
    """
    logger.info("=" * 60)
    logger.info("FASE 1: SCRAPING ARTICOLI")
    logger.info("=" * 60)
    
    # Carica articoli esistenti se in modalità continue
    existing_arxiv_ids = set()
    existing_pubmed_ids = set()
    arxiv_articles = []
    pubmed_articles = []
    
    if continue_mode:
        arxiv_metadata = DATA_DIR / "arxiv_metadata.json"
        pubmed_metadata = DATA_DIR / "pubmed_metadata.json"
        
        if arxiv_metadata.exists():
            with open(arxiv_metadata, 'r', encoding='utf-8') as f:
                arxiv_articles = json.load(f)
            existing_arxiv_ids = {a.get('arxiv_id') for a in arxiv_articles}
            logger.info(f"[INFO] Trovati {len(existing_arxiv_ids)} articoli arXiv esistenti")
        
        if pubmed_metadata.exists():
            with open(pubmed_metadata, 'r', encoding='utf-8') as f:
                pubmed_articles = json.load(f)
            existing_pubmed_ids = {a.get('pmc_id') or a.get('pmid') for a in pubmed_articles}
            logger.info(f"[INFO] Trovati {len(existing_pubmed_ids)} articoli PubMed esistenti")
    
    # Scraping arXiv
    logger.info(f"\n[ARXIV] Scraping arXiv con keywords: {ARXIV_KEYWORDS}")
    arxiv_scraper = ArxivScraper()
    new_arxiv_articles = []
    
    for keyword in ARXIV_KEYWORDS:
        logger.info(f"  Cercando: {keyword}")
        articles = arxiv_scraper.search_articles(keyword, max_results=50)
        logger.info(f"  Trovati {len(articles)} articoli")
        
        # Filtra articoli già esistenti
        for article in articles:
            if continue_mode and article.get('arxiv_id') in existing_arxiv_ids:
                continue  # Già scaricato
            new_arxiv_articles.append(article)
    
    # Download parallelo degli articoli arXiv
    if new_arxiv_articles:
        logger.info(f"\n[ARXIV] Download parallelo di {len(new_arxiv_articles)} articoli...")
        new_arxiv_articles = arxiv_scraper.download_articles_parallel(new_arxiv_articles)
        arxiv_articles.extend(new_arxiv_articles)
    
    # Rimuovi duplicati per arxiv_id
    seen_ids = set()
    unique_arxiv = []
    for a in arxiv_articles:
        aid = a.get('arxiv_id')
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            unique_arxiv.append(a)
    arxiv_articles = unique_arxiv
    
    logger.info(f"[OK] arXiv: totale {len(arxiv_articles)} articoli")
    
    # Salva metadata arXiv
    arxiv_meta_path = DATA_DIR / "arxiv_metadata.json"
    with open(arxiv_meta_path, 'w', encoding='utf-8') as f:
        json.dump(arxiv_articles, f, ensure_ascii=False, indent=2)
    
    # Scraping PubMed
    logger.info(f"\n[PUBMED] Scraping PubMed con keywords: {PUBMED_KEYWORDS}")
    pubmed_scraper = PubMedScraper()
    new_pubmed_articles = []
    
    for keyword in PUBMED_KEYWORDS:
        logger.info(f"  Cercando: {keyword}")
        articles = pubmed_scraper.search_via_api(keyword, max_results=500)
        logger.info(f"  Trovati {len(articles)} articoli open access")
        
        # Filtra articoli già esistenti
        for article in articles:
            article_id = article.get('pmc_id') or article.get('pmid')
            if continue_mode and article_id in existing_pubmed_ids:
                continue  # Già scaricato
            new_pubmed_articles.append(article)
    
    # Download parallelo degli articoli PubMed
    if new_pubmed_articles:
        logger.info(f"\n[PUBMED] Download parallelo di {len(new_pubmed_articles)} articoli...")
        new_pubmed_articles = pubmed_scraper.download_articles_parallel(new_pubmed_articles)
        pubmed_articles.extend(new_pubmed_articles)
    
    # Rimuovi duplicati
    seen_ids = set()
    unique_pubmed = []
    for a in pubmed_articles:
        pid = a.get('pmc_id') or a.get('pmid')
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_pubmed.append(a)
    pubmed_articles = unique_pubmed
    
    logger.info(f"[OK] PubMed: totale {len(pubmed_articles)} articoli")
    
    # Salva metadata PubMed
    pubmed_meta_path = DATA_DIR / "pubmed_metadata.json"
    with open(pubmed_meta_path, 'w', encoding='utf-8') as f:
        json.dump(pubmed_articles, f, ensure_ascii=False, indent=2)
    
    return arxiv_articles, pubmed_articles


def run_extraction(arxiv_articles, pubmed_articles):
    """Estrae tabelle e figure dagli articoli scaricati."""
    logger.info("\n" + "=" * 60)
    logger.info("FASE 2: ESTRAZIONE TABELLE E FIGURE")
    logger.info("=" * 60)
    
    table_extractor = TableExtractor()
    figure_extractor = FigureExtractor()
    
    all_tables = []
    all_figures = []
    
    # Processa articoli arXiv
    logger.info("\n[EXTRACT] Estrazione da articoli arXiv...")
    for article in arxiv_articles:
        if 'html_path' not in article:
            continue
        
        html_path = Path(article['html_path'])
        if not html_path.exists():
            continue
        
        paper_id = article.get('arxiv_id', html_path.stem)
        base_url = f"https://arxiv.org/html/{paper_id}/"
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Estrai tabelle
            tables = table_extractor.extract_from_html(html_content, paper_id, 'arxiv')
            all_tables.extend(tables)
            
            # Estrai figure
            figures = figure_extractor.extract_from_html(html_content, paper_id, 'arxiv', base_url)
            all_figures.extend(figures)
            
        except Exception as e:
            logger.warning(f"  Errore con {paper_id}: {e}")
    
    logger.info(f"  Estratte {len(all_tables)} tabelle e {len(all_figures)} figure da arXiv")
    
    # Processa articoli PubMed
    logger.info("\n[EXTRACT] Estrazione da articoli PubMed...")
    for article in pubmed_articles:
        if 'html_path' not in article:
            continue
        
        html_path = Path(article['html_path'])
        if not html_path.exists():
            continue
        
        paper_id = article.get('pmc_id', article.get('pmid', html_path.stem))
        base_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{paper_id}/"
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Estrai tabelle
            tables = table_extractor.extract_from_html(html_content, paper_id, 'pubmed')
            all_tables.extend(tables)
            
            # Estrai figure  
            figures = figure_extractor.extract_from_html(html_content, paper_id, 'pubmed', base_url)
            all_figures.extend(figures)
            
        except Exception as e:
            logger.warning(f"  Errore con {paper_id}: {e}")
    
    logger.info(f"[OK] Totale: {len(all_tables)} tabelle e {len(all_figures)} figure estratte")
    
    # Salva dati estratti
    tables_path = DATA_DIR / "extracted_tables.json"
    with open(tables_path, 'w', encoding='utf-8') as f:
        json.dump(all_tables, f, ensure_ascii=False, indent=2)
    
    figures_path = DATA_DIR / "extracted_figures.json"
    with open(figures_path, 'w', encoding='utf-8') as f:
        json.dump(all_figures, f, ensure_ascii=False, indent=2)
    
    return all_tables, all_figures


def run_indexing(arxiv_articles, pubmed_articles, all_tables, all_figures):
    """Indicizza tutti i dati in Elasticsearch."""
    logger.info("\n" + "=" * 60)
    logger.info("FASE 3: INDICIZZAZIONE ELASTICSEARCH")
    logger.info("=" * 60)
    
    # Setup Elasticsearch
    logger.info("\n[ES] Configurazione indici Elasticsearch...")
    es = get_elasticsearch_client()
    create_indices(es)
    
    # Indicizza articoli
    logger.info("\n[INDEX] Indicizzazione articoli...")
    paper_indexer = PaperIndexer()
    
    # Indicizza arXiv
    arxiv_count = paper_indexer.index_articles(arxiv_articles, "arxiv")
    logger.info(f"  Indicizzati {arxiv_count} articoli arXiv")
    
    # Indicizza PubMed
    pubmed_count = paper_indexer.index_articles(pubmed_articles, "pubmed")
    logger.info(f"  Indicizzati {pubmed_count} articoli PubMed")
    
    # Indicizza tabelle
    logger.info("\n[INDEX] Indicizzazione tabelle...")
    table_indexer = TableIndexer()
    table_count = table_indexer.index_tables(all_tables)
    logger.info(f"  Indicizzate {table_count} tabelle")
    
    # Indicizza figure
    logger.info("\n[INDEX] Indicizzazione figure...")
    figure_indexer = FigureIndexer()
    figure_count = figure_indexer.index_figures(all_figures)
    logger.info(f"  Indicizzate {figure_count} figure")
    
    # Statistiche finali
    logger.info("\n" + "=" * 60)
    logger.info("[STATS] STATISTICHE FINALI")
    logger.info("=" * 60)
    
    from indexers.elasticsearch_setup import get_index_stats
    get_index_stats(es)


def main():
    """Esegue la pipeline completa."""
    start_time = datetime.now()
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║   Sistema di Ricerca Articoli Scientifici                        ║
║   Ingegneria dei Dati 2025/2026 - Homework 5                     ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Crea directory
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PAPERS_DIR.mkdir(parents=True, exist_ok=True)
        (PAPERS_DIR / "arxiv").mkdir(exist_ok=True)
        (PAPERS_DIR / "pubmed").mkdir(exist_ok=True)
        
        # Controlla dati esistenti
        action = check_existing_data()
        
        if action == 'skip':
            # Usa dati esistenti
            arxiv_articles, pubmed_articles = load_existing_articles()
        else:
            # Esegui scraping (fresh o continue)
            arxiv_articles, pubmed_articles = run_scraping(continue_mode=(action == 'continue'))
        
        # Estrazione e indicizzazione
        all_tables, all_figures = run_extraction(arxiv_articles, pubmed_articles)
        run_indexing(arxiv_articles, pubmed_articles, all_tables, all_figures)
        
        # Riepilogo
        elapsed = datetime.now() - start_time
        logger.info(f"\n[OK] Pipeline completata in {elapsed}")
        
        print("""
+------------------------------------------------------------------+
|   PIPELINE COMPLETATA CON SUCCESSO                               |
|                                                                  |
|   Per avviare l'interfaccia:                                    |
|   - CLI: python cli/search_cli.py                               |
|   - Web: python web/app.py                                      |
+------------------------------------------------------------------+
        """)
        
    except KeyboardInterrupt:
        logger.info("\n[WARN] Pipeline interrotta dall'utente")
    except Exception as e:
        logger.error(f"\n[ERROR] Errore nella pipeline: {e}")
        raise


if __name__ == "__main__":
    main()
