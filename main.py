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
    ELASTICSEARCH_URL
)
from scrapers.arxiv_scraper import ArxivScraper
from scrapers.pubmed_scraper import PubMedScraper
from extractors.table_extractor import TableExtractor
from extractors.figure_extractor import FigureExtractor
from indexers.elasticsearch_setup import ElasticsearchSetup
from indexers.paper_indexer import PaperIndexer
from indexers.table_indexer import TableIndexer
from indexers.figure_indexer import FigureIndexer


def run_scraping():
    """Esegue lo scraping di articoli da arXiv e PubMed."""
    logger.info("=" * 60)
    logger.info("FASE 1: SCRAPING ARTICOLI")
    logger.info("=" * 60)
    
    # Scraping arXiv
    logger.info(f"\n[ARXIV] Scraping arXiv con keywords: {ARXIV_KEYWORDS}")
    arxiv_scraper = ArxivScraper()
    arxiv_articles = []
    
    for keyword in ARXIV_KEYWORDS:
        logger.info(f"  Cercando: {keyword}")
        articles = arxiv_scraper.search_articles(keyword, max_results=50)
        logger.info(f"  Trovati {len(articles)} articoli")
        
        # Download HTML
        for article in articles:
            html_path = arxiv_scraper.download_html_article(article)
            if html_path:
                article['html_path'] = str(html_path)
                arxiv_articles.append(article)
    
    logger.info(f"[OK] arXiv: scaricati {len(arxiv_articles)} articoli con HTML")
    
    # Salva metadata arXiv
    arxiv_meta_path = DATA_DIR / "arxiv_metadata.json"
    with open(arxiv_meta_path, 'w', encoding='utf-8') as f:
        json.dump(arxiv_articles, f, ensure_ascii=False, indent=2)
    
    # Scraping PubMed
    logger.info(f"\n[PUBMED] Scraping PubMed con keywords: {PUBMED_KEYWORDS}")
    pubmed_scraper = PubMedScraper()
    pubmed_articles = []
    
    for keyword in PUBMED_KEYWORDS:
        logger.info(f"  Cercando: {keyword}")
        articles = pubmed_scraper.search_via_api(keyword, max_results=500)
        logger.info(f"  Trovati {len(articles)} articoli open access")
        
        # Download articoli
        for article in articles:
            html_path = pubmed_scraper.download_article(article)
            if html_path:
                article['html_path'] = str(html_path)
                pubmed_articles.append(article)
    
    logger.info(f"[OK] PubMed: scaricati {len(pubmed_articles)} articoli")
    
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
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Estrai tabelle
            tables = table_extractor.extract_from_html(html_content, paper_id)
            all_tables.extend(tables)
            
            # Estrai figure
            figures = figure_extractor.extract_from_html(html_content, paper_id)
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
        
        paper_id = article.get('pmid', html_path.stem)
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Estrai tabelle
            tables = table_extractor.extract_from_html(html_content, paper_id)
            all_tables.extend(tables)
            
            # Estrai figure  
            figures = figure_extractor.extract_from_html(html_content, paper_id)
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
    es_setup = ElasticsearchSetup()
    es_setup.create_all_indices()
    
    # Indicizza articoli
    logger.info("\n[INDEX] Indicizzazione articoli...")
    paper_indexer = PaperIndexer()
    
    # Prepara documenti arXiv
    arxiv_docs = []
    for article in arxiv_articles:
        doc = {
            'paper_id': article.get('arxiv_id', ''),
            'title': article.get('title', ''),
            'abstract': article.get('abstract', ''),
            'authors': article.get('authors', ''),
            'url': article.get('url', ''),
            'full_text': article.get('full_text', ''),
            'source': 'arxiv'
        }
        arxiv_docs.append(doc)
    
    # Prepara documenti PubMed
    pubmed_docs = []
    for article in pubmed_articles:
        doc = {
            'paper_id': article.get('pmid', ''),
            'title': article.get('title', ''),
            'abstract': article.get('abstract', ''),
            'authors': article.get('authors', ''),
            'url': article.get('url', ''),
            'full_text': article.get('full_text', ''),
            'source': 'pubmed'
        }
        pubmed_docs.append(doc)
    
    # Indicizza
    all_papers = arxiv_docs + pubmed_docs
    success, failed = paper_indexer.bulk_index(all_papers)
    logger.info(f"  Indicizzati {success} articoli, {failed} falliti")
    
    # Indicizza tabelle
    logger.info("\n[INDEX] Indicizzazione tabelle...")
    table_indexer = TableIndexer()
    success, failed = table_indexer.bulk_index(all_tables)
    logger.info(f"  Indicizzate {success} tabelle, {failed} fallite")
    
    # Indicizza figure
    logger.info("\n[INDEX] Indicizzazione figure...")
    figure_indexer = FigureIndexer()
    success, failed = figure_indexer.bulk_index(all_figures)
    logger.info(f"  Indicizzate {success} figure, {failed} fallite")
    
    # Statistiche finali
    logger.info("\n" + "=" * 60)
    logger.info("[STATS] STATISTICHE FINALI")
    logger.info("=" * 60)
    
    stats = es_setup.get_stats()
    for index, count in stats.items():
        logger.info(f"  {index}: {count} documenti")


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
        
        # Esegui pipeline
        arxiv_articles, pubmed_articles = run_scraping()
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
