"""
Scraper per arXiv - Recupera articoli in formato HTML.
Keywords: "Query processing" / "Query optimization"

Ingegneria dei Dati 2025/2026 - Homework 5
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ARXIV_BASE_URL, ARXIV_SEARCH_URL, ARXIV_KEYWORDS,
    ARXIV_DATA_DIR, HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT, MAX_RETRIES
)


class ArxivScraper:
    """
    Scraper per recuperare articoli da arXiv in formato HTML.
    Cerca articoli il cui titolo o abstract contiene le keywords specificate.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.articles: List[Dict] = []
        self.articles_metadata_file = os.path.join(ARXIV_DATA_DIR, "articles_metadata.json")
    
    def search_articles(self, query: str, max_results: int = 200) -> List[Dict]:
        """
        Cerca articoli su arXiv per una query specifica.
        
        Args:
            query: La query di ricerca
            max_results: Numero massimo di risultati da recuperare
            
        Returns:
            Lista di dizionari con i metadati degli articoli
        """
        articles = []
        start = 0
        size = 50  # Risultati per pagina
        
        print(f"\n[INFO] Ricerca articoli per: '{query}'")
        
        with tqdm(total=max_results, desc="Ricerca articoli") as pbar:
            while len(articles) < max_results:
                # Costruisci URL di ricerca
                search_url = (
                    f"{ARXIV_SEARCH_URL}?searchtype=all&query={quote_plus(query)}"
                    f"&start={start}&size={size}"
                )
                
                try:
                    response = self._make_request(search_url)
                    if response is None:
                        break
                    
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    # Trova tutti i risultati
                    results = soup.find_all('li', class_='arxiv-result')
                    
                    if not results:
                        print(f"\n[WARN] Nessun altro risultato trovato dopo {len(articles)} articoli")
                        break
                    
                    for result in results:
                        if len(articles) >= max_results:
                            break
                        
                        article = self._parse_search_result(result)
                        if article:
                            articles.append(article)
                            pbar.update(1)
                    
                    start += size
                    time.sleep(REQUEST_DELAY)
                    
                except Exception as e:
                    print(f"\n[ERROR] Errore durante la ricerca: {e}")
                    break
        
        return articles
    
    def _parse_search_result(self, result) -> Optional[Dict]:
        """Estrae i metadati di un articolo dal risultato di ricerca."""
        try:
            # ID articolo
            arxiv_id_elem = result.find('p', class_='list-title')
            if not arxiv_id_elem:
                return None
            
            arxiv_id_link = arxiv_id_elem.find('a')
            if not arxiv_id_link:
                return None
            
            arxiv_id = arxiv_id_link.text.strip().replace('arXiv:', '')
            
            # Titolo
            title_elem = result.find('p', class_='title')
            title = title_elem.text.strip() if title_elem else "No title"
            
            # Autori
            authors_elem = result.find('p', class_='authors')
            authors = []
            if authors_elem:
                author_links = authors_elem.find_all('a')
                authors = [a.text.strip() for a in author_links]
            
            # Abstract
            abstract_elem = result.find('span', class_='abstract-full')
            if not abstract_elem:
                abstract_elem = result.find('p', class_='abstract')
            abstract = ""
            if abstract_elem:
                abstract = abstract_elem.text.strip()
                # Rimuovi "Less" button text se presente
                abstract = abstract.replace('△ Less', '').strip()
            
            # Data
            submitted_elem = result.find('p', class_='is-size-7')
            date = ""
            if submitted_elem:
                date_match = re.search(r'Submitted\s+(\d+\s+\w+,\s+\d{4})', submitted_elem.text)
                if date_match:
                    date = date_match.group(1)
            
            # URL dell'articolo HTML
            html_url = f"https://arxiv.org/html/{arxiv_id}"
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            abs_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            return {
                'arxiv_id': arxiv_id,
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'date': date,
                'html_url': html_url,
                'pdf_url': pdf_url,
                'abs_url': abs_url,
                'source': 'arxiv'
            }
            
        except Exception as e:
            print(f"\n[WARN] Errore parsing risultato: {e}")
            return None
    
    def download_html_article(self, article: Dict) -> Optional[str]:
        """
        Scarica il contenuto HTML completo di un articolo.
        
        Args:
            article: Dizionario con i metadati dell'articolo
            
        Returns:
            Contenuto HTML dell'articolo o None se non disponibile
        """
        html_url = article['html_url']
        arxiv_id = article['arxiv_id'].replace('/', '_')
        
        try:
            response = self._make_request(html_url)
            
            if response is None:
                return None
            
            if response.status_code == 404:
                # L'articolo potrebbe non essere disponibile in HTML
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Verifica se è una pagina valida
            if soup.find('div', class_='ltx_page_content') or soup.find('article'):
                # Salva l'HTML
                html_file = os.path.join(ARXIV_DATA_DIR, f"{arxiv_id}.html")
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Estrai il testo completo
                full_text = self._extract_full_text(soup)
                
                return full_text
            else:
                return None
                
        except Exception as e:
            print(f"\n[WARN] Errore download {arxiv_id}: {e}")
            return None
    
    def _extract_full_text(self, soup: BeautifulSoup) -> str:
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
    
    def _make_request(self, url: str, retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """Effettua una richiesta HTTP con retry."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if response.status_code == 404:
                    return response  # 404 è gestito dal chiamante
                if attempt < retries - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))
                else:
                    raise
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
        print("arXiv Scraper - Ingegneria dei Dati Homework 5")
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
        
        # Scarica gli articoli HTML
        print("\n[INFO] Download articoli HTML...")
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
                time.sleep(REQUEST_DELAY)
        
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
