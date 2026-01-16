"""
Indicizzazione delle tabelle estratte in Elasticsearch.
Ingegneria dei Dati 2025/2026 - Homework 5

Campi indicizzati:
- paper_id: ID dell'articolo
- table_id: ID della tabella
- caption: testo della caption
- body: contenuto della tabella
- mentions: paragrafi che citano la tabella
- context_paragraphs: paragrafi con termini della tabella
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, List

from elasticsearch import Elasticsearch, helpers
from tqdm import tqdm

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ELASTICSEARCH_URL, INDEX_TABLES, TABLES_DIR
from indexers.elasticsearch_setup import get_elasticsearch_client, create_indices


class TableIndexer:
    """
    Indicizza le tabelle estratte in Elasticsearch.
    """
    
    def __init__(self):
        self.es = get_elasticsearch_client()
        self.tables_file = os.path.join(TABLES_DIR, "tables_metadata.json")
    
    def load_tables(self) -> List[Dict]:
        """Carica le tabelle dal file JSON."""
        if not os.path.exists(self.tables_file):
            print(f"[WARN] File non trovato: {self.tables_file}")
            print("   Esegui prima: python extractors/table_extractor.py")
            return []
        
        with open(self.tables_file, 'r', encoding='utf-8') as f:
            tables = json.load(f)
        
        print(f"[INFO] Caricate {len(tables)} tabelle")
        return tables
    
    def prepare_document(self, table: Dict) -> Dict:
        """Prepara un documento tabella per l'indicizzazione."""
        paper_id = table['paper_id']
        # Determina la fonte dal paper_id
        source = "pubmed" if paper_id.startswith("PMC") else "arxiv"
        
        return {
            "_index": INDEX_TABLES,
            "_id": table['table_id'],
            "_source": {
                "table_id": table['table_id'],
                "paper_id": paper_id,
                "source": source,
                "caption": table.get('caption', ''),
                "body": table.get('body', ''),
                "mentions": '\n\n'.join(table.get('mentions', [])),
                "context_paragraphs": '\n\n'.join(table.get('context_paragraphs', [])),
                "position": table.get('position', 0),
                "indexed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    
    def index_tables(self, tables: List[Dict]) -> int:
        """
        Indicizza tutte le tabelle.
        
        Returns:
            Numero di tabelle indicizzate
        """
        if not tables:
            return 0
        
        documents = [self.prepare_document(t) for t in tables]
        
        print(f"\n[INFO] Indicizzazione {len(documents)} tabelle...")
        
        success_count = 0
        failed_count = 0
        
        try:
            with tqdm(total=len(documents), desc="Indicizzazione tabelle") as pbar:
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
            # Fallback
            for doc in tqdm(documents, desc="Indicizzazione (fallback)"):
                try:
                    self.es.index(
                        index=doc['_index'],
                        id=doc['_id'],
                        body=doc['_source']
                    )
                    success_count += 1
                except Exception:
                    failed_count += 1
        
        print(f"[OK] Indicizzate: {success_count}, Fallite: {failed_count}")
        return success_count
    
    def run(self):
        """Esegue l'indicizzazione completa delle tabelle."""
        print("=" * 60)
        print("Table Indexer - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        
        # Assicurati che l'indice esista
        create_indices(self.es, force_recreate=False)
        
        # Carica e indicizza
        tables = self.load_tables()
        if tables:
            self.index_tables(tables)
        
        # Refresh
        self.es.indices.refresh(index=INDEX_TABLES)
        
        # Statistiche
        final_count = self.es.count(index=INDEX_TABLES)['count']
        
        print("\n" + "=" * 60)
        print("[OK] Indicizzazione tabelle completata!")
        print(f"   Tabelle nell'indice: {final_count}")
        print("=" * 60)


def main():
    indexer = TableIndexer()
    indexer.run()


if __name__ == "__main__":
    main()
