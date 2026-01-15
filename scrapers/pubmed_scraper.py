"""
Scraper per PubMed Central - Recupera almeno 500 articoli open access.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PUBMED_BASE_URL, PUBMED_SEARCH_URL, PUBMED_KEYWORDS,
    PUBMED_DATA_DIR, PUBMED_MIN_ARTICLES,
    HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT, MAX_RETRIES
)

# Numero di thread per il download parallelo (ridotto per rispettare rate limits)
MAX_WORKERS = 5


class PubMedScraper:
    """
    Scraper per recuperare articoli open access da PubMed Central.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.articles: List[Dict] = []
        self.articles_metadata_file = os.path.join(PUBMED_DATA_DIR, "articles_metadata.json")
    
    def search_articles(self, query: str, max_results: int = 600) -> List[Dict]:
        """
        Cerca articoli open access su PubMed Central.
        
        Args:
            query: La query di ricerca
            max_results: Numero massimo di risultati
            
        Returns:
            Lista di dizionari con i metadati degli articoli
        """
        articles = []
        page = 1
        
        print(f"\n[INFO] Ricerca articoli per: '{query}'")
        print(f"   Filtro: Open Access")
        
        with tqdm(total=max_results, desc="Ricerca articoli") as pbar:
            while len(articles) < max_results:
                # URL di ricerca PubMed Central con filtro open access
                search_url = (
                    f"{PUBMED_SEARCH_URL}?term={quote_plus(query)}"
                    f"&filter=open%20access&page={page}"
                )
                
                try:
                    response = self._make_request(search_url)
                    if response is None:
                        break
                    
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    # Trova i risultati
                    results = soup.find_all('article', class_='article')
                    
                    # Alternativa: cerca nella struttura della pagina
                    if not results:
                        results = soup.find_all('div', class_='rprt')
                    
                    if not results:
                        results = soup.find_all('div', class_='rslt')
                    
                    if not results:
                        # Prova con la struttura più recente di PMC
                        search_results = soup.find('div', class_='search-results')
                        if search_results:
                            results = search_results.find_all('div', recursive=False)
                    
                    if not results:
                        print(f"\n[WARN] Nessun altro risultato trovato (pagina {page})")
                        break
                    
                    found_in_page = 0
                    for result in results:
                        if len(articles) >= max_results:
                            break
                        
                        article = self._parse_search_result(result)
                        if article:
                            articles.append(article)
                            pbar.update(1)
                            found_in_page += 1
                    
                    if found_in_page == 0:
                        print(f"\n[WARN] Nessun articolo valido trovato nella pagina {page}")
                        break
                    
                    page += 1
                    time.sleep(REQUEST_DELAY)
                    
                except Exception as e:
                    print(f"\n[ERROR] Errore durante la ricerca: {e}")
                    break
        
        return articles
    
    def _parse_search_result(self, result) -> Optional[Dict]:
        """Estrae i metadati di un articolo dal risultato di ricerca."""
        try:
            # Cerca il link all'articolo
            link = result.find('a', href=True)
            if not link:
                return None
            
            href = link.get('href', '')
            
            # Estrai PMC ID
            pmc_match = re.search(r'PMC\d+', href)
            if not pmc_match:
                pmc_match = re.search(r'PMC\d+', result.get_text())
            
            if not pmc_match:
                return None
            
            pmc_id = pmc_match.group(0)
            
            # Titolo
            title_elem = result.find('a', class_='title') or result.find('h1') or link
            title = title_elem.get_text(strip=True) if title_elem else "No title"
            
            # Autori
            authors_elem = result.find('div', class_='authors') or result.find('span', class_='authors')
            authors = []
            if authors_elem:
                authors = [a.strip() for a in authors_elem.get_text().split(',')]
            
            # Abstract (potrebbe non essere nel risultato di ricerca)
            abstract = ""
            
            # Data
            date_elem = result.find('span', class_='date') or result.find('time')
            date = date_elem.get_text(strip=True) if date_elem else ""
            
            # URL dell'articolo
            article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
            
            return {
                'pmc_id': pmc_id,
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'date': date,
                'url': article_url,
                'source': 'pubmed'
            }
            
        except Exception as e:
            return None
    
    def download_article(self, article: Dict) -> Optional[str]:
        """
        Scarica il contenuto completo di un articolo PubMed usando l'API efetch.
        
        Args:
            article: Dizionario con i metadati dell'articolo
            
        Returns:
            Percorso del file XML se il download è riuscito, None altrimenti
        """
        pmc_id = article['pmc_id']
        # Estrai l'ID numerico (rimuovi "PMC" se presente)
        numeric_id = pmc_id.replace('PMC', '')
        
        try:
            # Usa l'API efetch per recuperare il full-text XML
            efetch_url = (
                f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                f"?db=pmc&id={numeric_id}&rettype=full&retmode=xml"
            )
            
            response = self._make_request(efetch_url)
            
            if response is None or response.status_code != 200:
                return None
            
            xml_content = response.text
            
            # Verifica che sia un XML valido con contenuto
            if '<article' not in xml_content and '<pmc-articleset' not in xml_content:
                return None
            
            # Parsing XML per estrarre testo
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Estrai abstract se non presente
            if not article.get('abstract'):
                abstract_elem = soup.find('abstract')
                if abstract_elem:
                    article['abstract'] = abstract_elem.get_text(separator=' ', strip=True)
            
            # Estrai autori se non presenti
            if not article.get('authors') or len(article.get('authors', [])) == 0:
                contrib_group = soup.find('contrib-group')
                if contrib_group:
                    authors = []
                    for contrib in contrib_group.find_all('contrib', {'contrib-type': 'author'}):
                        name_elem = contrib.find('name')
                        if name_elem:
                            surname = name_elem.find('surname')
                            given = name_elem.find('given-names')
                            if surname and given:
                                authors.append(f"{given.get_text(strip=True)} {surname.get_text(strip=True)}")
                            elif surname:
                                authors.append(surname.get_text(strip=True))
                    if authors:
                        article['authors'] = authors
            
            # Estrai testo completo dal body
            body = soup.find('body')
            if body:
                full_text = body.get_text(separator=' ', strip=True)
                # Rimuovi spazi multipli
                full_text = re.sub(r'\s+', ' ', full_text)
                article['full_text'] = full_text
            else:
                article['full_text'] = article.get('abstract', '')
            
            # Salva l'XML (che può essere usato per estrazione tabelle/figure)
            xml_file = os.path.join(str(PUBMED_DATA_DIR), f"{pmc_id}.xml")
            with open(xml_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            article['html_path'] = xml_file  # Anche se è XML, lo trattiamo come file di contenuto
            article['xml_path'] = xml_file
            return xml_file
            
        except Exception as e:
            return None
    
    def download_articles_parallel(self, articles: List[Dict], max_workers: int = MAX_WORKERS) -> List[Dict]:
        """
        Scarica articoli in parallelo usando ThreadPoolExecutor.
        
        Args:
            articles: Lista di articoli da scaricare
            max_workers: Numero di thread paralleli
            
        Returns:
            Lista di articoli con html_path aggiornato
        """
        print(f"\n[INFO] Download parallelo con {max_workers} thread...")
        
        successful = 0
        failed = 0
        lock = threading.Lock()
        
        def download_one(article):
            nonlocal successful, failed
            try:
                result = self.download_article(article)
                with lock:
                    if result:
                        successful += 1
                    else:
                        failed += 1
            except Exception as e:
                with lock:
                    failed += 1
            return article
        
        # Download sequenziale in batch per evitare problemi con ThreadPoolExecutor
        batch_size = max_workers
        with tqdm(total=len(articles), desc="Download articoli") as pbar:
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i+batch_size]
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(download_one, art): art for art in batch}
                    for future in as_completed(futures, timeout=60):
                        try:
                            future.result(timeout=30)
                        except Exception as e:
                            with lock:
                                failed += 1
                        pbar.update(1)
                time.sleep(0.3)  # Pausa tra batch
        
        print(f"[OK] Download completato: {successful} successi, {failed} falliti")
        return articles
    
    def _extract_full_text(self, soup: BeautifulSoup) -> str:
        """Estrae il testo completo dall'HTML dell'articolo."""
        # Rimuovi elementi non testuali
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Cerca il contenuto principale
        main_content = soup.find('div', class_='article-full-text')
        if not main_content:
            main_content = soup.find('div', class_='jig-ncbi-full-text')
        if not main_content:
            main_content = soup.find('article')
        if not main_content:
            main_content = soup.find('div', id='maincontent')
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
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
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))
                else:
                    return None
        return None
    
    def search_via_api(self, query: str, max_results: int = 600) -> List[Dict]:
        """
        Cerca articoli usando l'API E-utilities di NCBI.
        Metodo alternativo più affidabile.
        """
        articles = []
        
        print(f"\n[INFO] Ricerca via NCBI API per: '{query}'")
        
        # Step 1: Cerca gli ID
        esearch_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pmc&term={quote_plus(query)}+AND+open+access[filter]"
            f"&retmax={max_results}&retmode=json"
        )
        
        try:
            response = self._make_request(esearch_url)
            if response is None:
                return articles
            
            data = response.json()
            id_list = data.get('esearchresult', {}).get('idlist', [])
            
            print(f"   Trovati {len(id_list)} ID articoli")
            
            # Step 2: Recupera i dettagli
            if id_list:
                # Processa in batch
                batch_size = 50
                with tqdm(total=len(id_list), desc="Recupero metadati") as pbar:
                    for i in range(0, len(id_list), batch_size):
                        batch = id_list[i:i+batch_size]
                        ids_str = ','.join(batch)
                        
                        esummary_url = (
                            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                            f"?db=pmc&id={ids_str}&retmode=json"
                        )
                        
                        response = self._make_request(esummary_url)
                        if response:
                            summary_data = response.json()
                            results = summary_data.get('result', {})
                            
                            for pmc_uid in batch:
                                if pmc_uid in results:
                                    item = results[pmc_uid]
                                    pmc_id = f"PMC{pmc_uid}"
                                    
                                    article = {
                                        'pmc_id': pmc_id,
                                        'title': item.get('title', 'No title'),
                                        'authors': [a.get('name', '') for a in item.get('authors', [])],
                                        'abstract': '',
                                        'date': item.get('pubdate', ''),
                                        'url': f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/",
                                        'source': 'pubmed'
                                    }
                                    articles.append(article)
                                
                                pbar.update(1)
                        
                        time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print(f"\n[ERROR] Errore API: {e}")
        
        return articles
    
    def run(self, min_articles: int = PUBMED_MIN_ARTICLES):
        """
        Esegue lo scraping completo da PubMed.
        
        Args:
            min_articles: Numero minimo di articoli da recuperare (default 500)
        """
        print("=" * 60)
        print("PubMed Scraper - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        print(f"Keywords: {PUBMED_KEYWORDS}")
        print(f"Obiettivo: almeno {min_articles} articoli open access")
        print("=" * 60)
        
        all_articles = []
        seen_ids = set()
        
        for keyword in PUBMED_KEYWORDS:
            # Usa l'API per cercare
            articles = self.search_via_api(keyword, max_results=min_articles + 100)
            
            # Rimuovi duplicati
            for article in articles:
                if article['pmc_id'] not in seen_ids:
                    seen_ids.add(article['pmc_id'])
                    all_articles.append(article)
                
                if len(all_articles) >= min_articles:
                    break
        
        print(f"\n[INFO] Trovati {len(all_articles)} articoli unici")
        
        if len(all_articles) < min_articles:
            print(f"[WARN] Attenzione: trovati solo {len(all_articles)} articoli (richiesti {min_articles})")
        
        # Scarica gli articoli
        print("\n[INFO] Download articoli completi...")
        successful_downloads = 0
        
        with tqdm(total=len(all_articles), desc="Download articoli") as pbar:
            for article in all_articles:
                if self.download_article(article):
                    successful_downloads += 1
                
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
        print(f"   Download riusciti: {successful_downloads}")
        print(f"   Dati salvati in: {PUBMED_DATA_DIR}")
        print("=" * 60)
        
        return all_articles


def main():
    scraper = PubMedScraper()
    scraper.run(min_articles=500)


if __name__ == "__main__":
    main()
