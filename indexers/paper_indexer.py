"""
Indicizzazione degli articoli scientifici in Elasticsearch.
Ingegneria dei Dati 2025/2026 - Homework 5
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List

from elasticsearch import Elasticsearch, helpers
from tqdm import tqdm

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ELASTICSEARCH_URL, INDEX_PAPERS,
    ARXIV_DATA_DIR, PUBMED_DATA_DIR
)
from indexers.elasticsearch_setup import get_elasticsearch_client, create_indices


class PaperIndexer:
    """
    Indicizza gli articoli scientifici in Elasticsearch.
    Campi: titolo, autori, data, abstract, testo completo.
    """
    
    def __init__(self):
        self.es = get_elasticsearch_client()
        self.indexed_count = 0
    
    def load_arxiv_articles(self) -> List[Dict]:
        """Carica gli articoli arXiv dal file JSON."""
        metadata_file = os.path.join(ARXIV_DATA_DIR, "articles_metadata.json")
        
        if not os.path.exists(metadata_file):
            print(f"[WARN] File non trovato: {metadata_file}")
            return []
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        
        print(f"[INFO] Caricati {len(articles)} articoli da arXiv")
        return articles
    
    def load_pubmed_articles(self) -> List[Dict]:
        """Carica gli articoli PubMed dal file JSON."""
        metadata_file = os.path.join(PUBMED_DATA_DIR, "articles_metadata.json")
        
        if not os.path.exists(metadata_file):
            print(f"[WARN] File non trovato: {metadata_file}")
            return []
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        
        print(f"[INFO] Caricati {len(articles)} articoli da PubMed")
        return articles
    
    def prepare_arxiv_document(self, article: Dict) -> Dict:
        """Prepara un documento arXiv per l'indicizzazione."""
        return {
            "_index": INDEX_PAPERS,
            "_id": f"arxiv_{article['arxiv_id'].replace('/', '_')}",
            "_source": {
                "paper_id": article['arxiv_id'],
                "source": "arxiv",
                "title": article.get('title', ''),
                "authors": ', '.join(article.get('authors', [])),
                "date": article.get('date', ''),
                "abstract": article.get('abstract', ''),
                "full_text": article.get('full_text', article.get('abstract', '')),
                "url": article.get('abs_url', article.get('html_url', '')),
                "html_available": article.get('html_available', False),
                "indexed_at": datetime.utcnow().isoformat()
            }
        }
    
    def prepare_pubmed_document(self, article: Dict) -> Dict:
        """Prepara un documento PubMed per l'indicizzazione."""
        return {
            "_index": INDEX_PAPERS,
            "_id": f"pubmed_{article['pmc_id']}",
            "_source": {
                "paper_id": article['pmc_id'],
                "source": "pubmed",
                "title": article.get('title', ''),
                "authors": ', '.join(article.get('authors', [])) if isinstance(article.get('authors'), list) else article.get('authors', ''),
                "date": article.get('date', ''),
                "abstract": article.get('abstract', ''),
                "full_text": article.get('full_text', article.get('abstract', '')),
                "url": article.get('url', ''),
                "html_available": True,
                "indexed_at": datetime.utcnow().isoformat()
            }
        }
    
    def index_articles(self, articles: List[Dict], source: str) -> int:
        """
        Indicizza una lista di articoli.
        
        Args:
            articles: Lista di articoli
            source: "arxiv" o "pubmed"
            
        Returns:
            Numero di articoli indicizzati
        """
        if not articles:
            return 0
        
        # Prepara i documenti
        if source == "arxiv":
            documents = [self.prepare_arxiv_document(a) for a in articles]
        else:
            documents = [self.prepare_pubmed_document(a) for a in articles]
        
        # Indicizza in bulk
        print(f"\n📤 Indicizzazione {len(documents)} articoli da {source}...")
        
        success_count = 0
        failed_count = 0
        
        # Usa bulk helper per efficienza
        try:
            with tqdm(total=len(documents), desc="Indicizzazione") as pbar:
                for success, info in helpers.streaming_bulk(
                    self.es,
                    documents,
                    chunk_size=100,
                    raise_on_error=False
                ):
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                    pbar.update(1)
            
        except Exception as e:
            print(f"[ERROR] Errore durante indicizzazione bulk: {e}")
            # Fallback: indicizza uno per uno
            for doc in tqdm(documents, desc="Indicizzazione (fallback)"):
                try:
                    self.es.index(
                        index=doc['_index'],
                        id=doc['_id'],
                        body=doc['_source']
                    )
                    success_count += 1
                except Exception as e:
                    failed_count += 1
        
        print(f"[OK] Indicizzati: {success_count}, Falliti: {failed_count}")
        return success_count
    
    def run(self):
        """Esegue l'indicizzazione completa di tutti gli articoli."""
        print("=" * 60)
        print("Paper Indexer - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        
        # Assicurati che l'indice esista
        create_indices(self.es, force_recreate=False)
        
        total_indexed = 0
        
        # Indicizza articoli arXiv
        arxiv_articles = self.load_arxiv_articles()
        if arxiv_articles:
            count = self.index_articles(arxiv_articles, "arxiv")
            total_indexed += count
        
        # Indicizza articoli PubMed
        pubmed_articles = self.load_pubmed_articles()
        if pubmed_articles:
            count = self.index_articles(pubmed_articles, "pubmed")
            total_indexed += count
        
        # Refresh dell'indice
        self.es.indices.refresh(index=INDEX_PAPERS)
        
        # Statistiche finali
        final_count = self.es.count(index=INDEX_PAPERS)['count']
        
        print("\n" + "=" * 60)
        print("[OK] Indicizzazione completata!")
        print(f"   Articoli totali nell'indice: {final_count}")
        print("=" * 60)
        
        return total_indexed


def main():
    indexer = PaperIndexer()
    indexer.run()


if __name__ == "__main__":
    main()
