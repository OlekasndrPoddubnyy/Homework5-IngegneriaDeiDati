"""
Scraper per arXiv - Usa l'API ufficiale (non scraping HTML).
Keywords: "Query processing" / "Query optimization"

API Docs: https://info.arxiv.org/help/api/user-manual.html

Ingegneria dei Dati 2025/2026 - Homework 5
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
from tqdm import tqdm

# Ignora warning BeautifulSoup per XML
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ARXIV_KEYWORDS, ARXIV_DATA_DIR, HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT, MAX_RETRIES
)

# API ufficiale arXiv
ARXIV_API_URL = "https://export.arxiv.org/api/query"

# Numero di thread per il download parallelo (ridotto per evitare rate limit)
MAX_WORKERS = 3

# Namespace per parsing XML Atom
NAMESPACES = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom'
}


class ArxivScraper:
    """
    Scraper per recuperare articoli da arXiv tramite API ufficiale.
    Cerca articoli il cui titolo o abstract contiene le keywords specificate.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.articles: List[Dict] = []
        self.articles_metadata_file = os.path.join(str(ARXIV_DATA_DIR), "articles_metadata.json")
    
    def search_articles(self, query: str, max_results: int = 200) -> List[Dict]:
        """
        Cerca articoli su arXiv tramite API ufficiale.
        
        Args:
            query: La query di ricerca
            max_results: Numero massimo di risultati da recuperare
            
        Returns:
            Lista di dizionari con i metadati degli articoli
        """
        articles = []
        start = 0
        batch_size = 100  # Max consentito dall'API
        
        print(f"\n[INFO] Ricerca articoli via API per: '{query}'")
        
        with tqdm(total=max_results, desc="Ricerca articoli") as pbar:
            while len(articles) < max_results:
                # Costruisci query per l'API
                # Cerca nel titolo E nell'abstract
                search_query = f'all:"{query}"'
                
                params = {
                    'search_query': search_query,
                    'start': start,
                    'max_results': min(batch_size, max_results - len(articles)),
                    'sortBy': 'relevance',
                    'sortOrder': 'descending'
                }
                
                try:
                    response = self._make_request(ARXIV_API_URL, params=params)
                    if response is None:
                        break
                    
                    # Parse XML response
                    batch_articles = self._parse_api_response(response.text)
                    
                    if not batch_articles:
                        print(f"\n[INFO] Nessun altro risultato dopo {len(articles)} articoli")
                        break
                    
                    for article in batch_articles:
                        if len(articles) >= max_results:
                            break
                        articles.append(article)
                        pbar.update(1)
                    
                    start += batch_size
                    
                    # Rispetta rate limit API (3 secondi tra richieste)
                    time.sleep(3)
                    
                except Exception as e:
                    print(f"\n[ERROR] Errore durante la ricerca: {e}")
                    break
        
        return articles
    
    def _parse_api_response(self, xml_content: str) -> List[Dict]:
        """Parse la risposta XML dell'API arXiv."""
        articles = []
        
        try:
            root = ET.fromstring(xml_content)
            
            for entry in root.findall('atom:entry', NAMESPACES):
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)
                    
        except ET.ParseError as e:
            print(f"\n[ERROR] Errore parsing XML: {e}")
        
        return articles
    
    def _parse_entry(self, entry) -> Optional[Dict]:
        """Estrae i metadati da un entry Atom."""
        try:
            # ID (es: http://arxiv.org/abs/2301.12345v1)
            id_elem = entry.find('atom:id', NAMESPACES)
            if id_elem is None:
                return None
            
            full_id = id_elem.text
            # Estrai solo l'ID (es: 2301.12345v1)
            arxiv_id = full_id.split('/abs/')[-1] if '/abs/' in full_id else full_id
            # Rimuovi versione per ID base
            arxiv_id_base = re.sub(r'v\d+$', '', arxiv_id)
            
            # Titolo
            title_elem = entry.find('atom:title', NAMESPACES)
            title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else "No title"
            title = re.sub(r'\s+', ' ', title)
            
            # Autori
            authors = []
            for author in entry.findall('atom:author', NAMESPACES):
                name_elem = author.find('atom:name', NAMESPACES)
                if name_elem is not None:
                    authors.append(name_elem.text.strip())
            
            # Abstract
            summary_elem = entry.find('atom:summary', NAMESPACES)
            abstract = ""
            if summary_elem is not None and summary_elem.text:
                abstract = summary_elem.text.strip().replace('\n', ' ')
                abstract = re.sub(r'\s+', ' ', abstract)
            
            # Data pubblicazione
            published_elem = entry.find('atom:published', NAMESPACES)
            date = ""
            if published_elem is not None:
                date = published_elem.text[:10]  # YYYY-MM-DD
            
            # Data ultimo aggiornamento
            updated_elem = entry.find('atom:updated', NAMESPACES)
            updated = ""
            if updated_elem is not None:
                updated = updated_elem.text[:10]
            
            # Categorie
            categories = []
            for category in entry.findall('atom:category', NAMESPACES):
                term = category.get('term')
                if term:
                    categories.append(term)
            
            # Link PDF
            pdf_url = ""
            for link in entry.findall('atom:link', NAMESPACES):
                if link.get('title') == 'pdf':
                    pdf_url = link.get('href', '')
                    break
            
            if not pdf_url:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id_base}.pdf"
            
            # URL
            html_url = f"https://arxiv.org/html/{arxiv_id_base}"
            abs_url = f"https://arxiv.org/abs/{arxiv_id_base}"
            
            return {
                'arxiv_id': arxiv_id_base,
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'date': date,
                'updated': updated,
                'categories': categories,
                'html_url': html_url,
                'pdf_url': pdf_url,
                'abs_url': abs_url,
                'source': 'arxiv'
            }
            
        except Exception as e:
            print(f"\n[WARN] Errore parsing entry: {e}")
            return None
    
    def download_html_article(self, article: Dict) -> Optional[str]:
        """
        Scarica il contenuto HTML completo di un articolo (se disponibile).
        
        Args:
            article: Dizionario con i metadati dell'articolo
            
        Returns:
            Path del file HTML o None se non disponibile
        """
        html_url = article['html_url']
        arxiv_id = article['arxiv_id'].replace('/', '_')
        
        try:
            response = self._make_request(html_url)
            
            if response is None or response.status_code != 200:
                return None
            
            # Verifica se è una pagina HTML valida (non redirect a PDF)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                return None
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Verifica se è una pagina valida con contenuto
            if soup.find('div', class_='ltx_page_content') or soup.find('article'):
                # Salva l'HTML
                html_file = os.path.join(str(ARXIV_DATA_DIR), f"{arxiv_id}.html")
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Estrai il testo completo e salvalo nell'articolo
                full_text = self._extract_full_text(soup)
                article['full_text'] = full_text
                article['html_available'] = True
                
                return html_file
            
            return None
                
        except Exception as e:
            return None
    
    def download_articles_parallel(self, articles: List[Dict], max_workers: int = MAX_WORKERS) -> List[Dict]:
        """
        Scarica articoli in parallelo usando ThreadPoolExecutor.
        
        Args:
            articles: Lista di articoli da scaricare
            max_workers: Numero di thread paralleli
            
        Returns:
            Lista di articoli aggiornati
        """
        print(f"\n[INFO] Download parallelo con {max_workers} thread...")
        
        successful = 0
        failed = 0
        lock = threading.Lock()
        
        def download_one(article):
            nonlocal successful, failed
            result = self.download_html_article(article)
            time.sleep(1)  # Rate limit: 1 secondo tra richieste
            with lock:
                if result:
                    article['html_path'] = result
                    successful += 1
                else:
                    article['full_text'] = article.get('abstract', '')
                    article['html_available'] = False
                    failed += 1
            return article
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_one, art): art for art in articles}
            
            with tqdm(total=len(articles), desc="Download HTML") as pbar:
                for future in as_completed(futures):
                    pbar.update(1)
        
        print(f"[OK] Download completato: {successful} con HTML, {failed} solo abstract")
        return articles
    
    def _extract_full_text(self, soup) -> str:
        """Estrae il testo completo dall'HTML dell'articolo."""
        # Rimuovi script e style
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()
        
        # Cerca il contenuto principale
        main_content = soup.find('div', class_='ltx_page_content')
        if not main_content:
            main_content = soup.find('article')
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
            # Pulisci spazi multipli
            text = re.sub(r'\s+', ' ', text)
            return text
        
        return ""
    
    def _make_request(self, url: str, params: dict = None, retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """Effettua una richiesta HTTP con retry."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 404:
                    return response  # 404 gestito dal chiamante
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.HTTPError as e:
                if attempt < retries - 1:
                    wait_time = REQUEST_DELAY * (attempt + 1)
                    print(f"\n[WARN] Retry {attempt + 1}/{retries} dopo {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"\n[ERROR] Richiesta fallita: {e}")
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))
                else:
                    print(f"\n[ERROR] Richiesta fallita dopo {retries} tentativi: {url}")
                    return None
        return None
    
    def run(self, max_per_keyword: int = 100):
        """
        Esegue lo scraping completo per tutte le keywords.
        
        Args:
            max_per_keyword: Numero massimo di articoli per keyword
        """
        print("=" * 60)
        print("arXiv Scraper (API) - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        print(f"Keywords: {ARXIV_KEYWORDS}")
        print(f"Max articoli per keyword: {max_per_keyword}")
        print("=" * 60)
        
        all_articles = []
        seen_ids = set()
        
        for keyword in ARXIV_KEYWORDS:
            articles = self.search_articles(keyword, max_per_keyword)
            
            # Rimuovi duplicati
            for article in articles:
                if article['arxiv_id'] not in seen_ids:
                    seen_ids.add(article['arxiv_id'])
                    all_articles.append(article)
        
        print(f"\n[INFO] Trovati {len(all_articles)} articoli unici")
        
        # Scarica gli articoli HTML (opzionale, molti non hanno HTML)
        print("\n[INFO] Tentativo download HTML (se disponibile)...")
        html_available = 0
        
        with tqdm(total=len(all_articles), desc="Download HTML") as pbar:
            for article in all_articles:
                full_text = self.download_html_article(article)
                
                if full_text:
                    article['full_text'] = full_text
                    article['html_available'] = True
                    html_available += 1
                else:
                    article['full_text'] = article['abstract']  # Fallback
                    article['html_available'] = False
                
                pbar.update(1)
                time.sleep(0.5)  # Rate limit gentile per HTML
        
        self.articles = all_articles
        
        # Salva i metadati
        print(f"\n[INFO] Salvataggio metadati...")
        with open(self.articles_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_articles, f, indent=2, ensure_ascii=False)
        
        # Statistiche finali
        print("\n" + "=" * 60)
        print("[OK] Scraping completato!")
        print(f"   Articoli totali: {len(all_articles)}")
        print(f"   Con HTML disponibile: {html_available}")
        print(f"   Solo abstract: {len(all_articles) - html_available}")
        print(f"   Dati salvati in: {ARXIV_DATA_DIR}")
        print("=" * 60)
        
        return all_articles


def main():
    scraper = ArxivScraper()
    scraper.run(max_per_keyword=150)


if __name__ == "__main__":
    main()
