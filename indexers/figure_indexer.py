"""
Indicizzazione delle figure estratte in Elasticsearch.
Ingegneria dei Dati 2025/2026 - Homework 5

Campi indicizzati:
- figure_id: ID della figura
- paper_id: ID dell'articolo
- url: URL dell'immagine
- caption: testo della caption
- mentions: paragrafi che citano la figura
- context_paragraphs: paragrafi con termini della caption
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
from config import ELASTICSEARCH_URL, INDEX_FIGURES, FIGURES_DIR
from indexers.elasticsearch_setup import get_elasticsearch_client, create_indices


class FigureIndexer:
    """
    Indicizza le figure estratte in Elasticsearch.
    """
    
    def __init__(self):
        self.es = get_elasticsearch_client()
        self.figures_file = os.path.join(FIGURES_DIR, "figures_metadata.json")
    
    def load_figures(self) -> List[Dict]:
        """Carica le figure dal file JSON."""
        if not os.path.exists(self.figures_file):
            print(f"[WARN] File non trovato: {self.figures_file}")
            print("   Esegui prima: python extractors/figure_extractor.py")
            return []
        
        with open(self.figures_file, 'r', encoding='utf-8') as f:
            figures = json.load(f)
        
        print(f"[INFO] Caricate {len(figures)} figure")
        return figures
    
    def prepare_document(self, figure: Dict) -> Dict:
        """Prepara un documento figura per l'indicizzazione."""
        return {
            "_index": INDEX_FIGURES,
            "_id": figure['figure_id'],
            "_source": {
                "figure_id": figure['figure_id'],
                "paper_id": figure['paper_id'],
                "url": figure.get('url', ''),
                "caption": figure.get('caption', ''),
                "mentions": '\n\n'.join(figure.get('mentions', [])),
                "context_paragraphs": '\n\n'.join(figure.get('context_paragraphs', [])),
                "position": figure.get('position', 0),
                "indexed_at": datetime.utcnow().isoformat()
            }
        }
    
    def index_figures(self, figures: List[Dict]) -> int:
        """
        Indicizza tutte le figure.
        
        Returns:
            Numero di figure indicizzate
        """
        if not figures:
            return 0
        
        documents = [self.prepare_document(f) for f in figures]
        
        print(f"\n[INFO] Indicizzazione {len(documents)} figure...")
        
        success_count = 0
        failed_count = 0
        
        try:
            with tqdm(total=len(documents), desc="Indicizzazione figure") as pbar:
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
            print(f"[ERROR] Errore bulk: {e}")
            for doc in tqdm(documents, desc="Indicizzazione (fallback)"):
                try:
                    self.es.index(
                        index=doc['_index'],
                        id=doc['_id'],
                        body=doc['_source']
                    )
                    success_count += 1
                except:
                    failed_count += 1
        
        print(f"[OK] Indicizzate: {success_count}, Fallite: {failed_count}")
        return success_count
    
    def run(self):
        """Esegue l'indicizzazione completa delle figure."""
        print("=" * 60)
        print("Figure Indexer - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        
        # Assicurati che l'indice esista
        create_indices(self.es, force_recreate=False)
        
        # Carica e indicizza
        figures = self.load_figures()
        if figures:
            self.index_figures(figures)
        
        # Refresh
        self.es.indices.refresh(index=INDEX_FIGURES)
        
        # Statistiche
        final_count = self.es.count(index=INDEX_FIGURES)['count']
        
        print("\n" + "=" * 60)
        print("[OK] Indicizzazione figure completata!")
        print(f"   Figure nell'indice: {final_count}")
        print("=" * 60)


def main():
    indexer = FigureIndexer()
    indexer.run()


if __name__ == "__main__":
    main()
