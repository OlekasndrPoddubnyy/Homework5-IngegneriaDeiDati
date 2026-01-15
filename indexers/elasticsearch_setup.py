"""
Setup indici Elasticsearch per il sistema di ricerca.
Ingegneria dei Dati 2025/2026 - Homework 5
"""

import os
import sys
from elasticsearch import Elasticsearch

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ELASTICSEARCH_URL, INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES
)


def get_elasticsearch_client() -> Elasticsearch:
    """Crea e restituisce un client Elasticsearch."""
    es = Elasticsearch(ELASTICSEARCH_URL)
    
    if not es.ping():
        raise ConnectionError(f"Impossibile connettersi a Elasticsearch: {ELASTICSEARCH_URL}")
    
    print(f"[OK] Connesso a Elasticsearch: {ELASTICSEARCH_URL}")
    return es


# ============== MAPPINGS ==============

# Mapping per gli articoli scientifici
PAPERS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "paper_id": {
                "type": "keyword"
            },
            "source": {
                "type": "keyword"  # "arxiv" o "pubmed"
            },
            "title": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "authors": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "date": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "abstract": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "full_text": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "url": {
                "type": "keyword"
            },
            "html_available": {
                "type": "boolean"
            },
            "indexed_at": {
                "type": "date"
            }
        }
    }
}

# Mapping per le tabelle
TABLES_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "table_id": {
                "type": "keyword"
            },
            "paper_id": {
                "type": "keyword"
            },
            "caption": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "body": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "mentions": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "context_paragraphs": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "position": {
                "type": "integer"  # Posizione della tabella nell'articolo
            },
            "indexed_at": {
                "type": "date"
            }
        }
    }
}

# Mapping per le figure
FIGURES_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "figure_id": {
                "type": "keyword"
            },
            "paper_id": {
                "type": "keyword"
            },
            "url": {
                "type": "keyword"
            },
            "caption": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "mentions": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "context_paragraphs": {
                "type": "text",
                "analyzer": "text_analyzer"
            },
            "position": {
                "type": "integer"
            },
            "indexed_at": {
                "type": "date"
            }
        }
    }
}


def create_indices(es: Elasticsearch, force_recreate: bool = False):
    """
    Crea gli indici Elasticsearch.
    
    Args:
        es: Client Elasticsearch
        force_recreate: Se True, elimina e ricrea gli indici esistenti
    """
    indices = [
        (INDEX_PAPERS, PAPERS_MAPPING),
        (INDEX_TABLES, TABLES_MAPPING),
        (INDEX_FIGURES, FIGURES_MAPPING)
    ]
    
    for index_name, mapping in indices:
        if es.indices.exists(index=index_name):
            if force_recreate:
                print(f"🗑️ Eliminazione indice esistente: {index_name}")
                es.indices.delete(index=index_name)
            else:
                print(f"[SKIP] Indice gia esistente: {index_name}")
                continue
        
        print(f"[INFO] Creazione indice: {index_name}")
        es.indices.create(index=index_name, body=mapping)
        print(f"[OK] Indice creato: {index_name}")


def delete_indices(es: Elasticsearch):
    """Elimina tutti gli indici."""
    for index_name in [INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES]:
        if es.indices.exists(index=index_name):
            es.indices.delete(index=index_name)
            print(f"[DEL] Indice eliminato: {index_name}")


def get_index_stats(es: Elasticsearch):
    """Mostra statistiche degli indici."""
    print("\n[STATS] Statistiche Indici")
    print("=" * 50)
    
    for index_name in [INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES]:
        if es.indices.exists(index=index_name):
            count = es.count(index=index_name)['count']
            print(f"   {index_name}: {count} documenti")
        else:
            print(f"   {index_name}: non esistente")
    
    print("=" * 50)


def main():
    """Setup completo degli indici Elasticsearch."""
    print("=" * 60)
    print("Elasticsearch Setup - Ingegneria dei Dati Homework 5")
    print("=" * 60)
    
    try:
        es = get_elasticsearch_client()
        
        # Chiedi se ricreare gli indici
        import sys
        force = "--force" in sys.argv or "-f" in sys.argv
        
        if force:
            print("\n[WARN] Modalita force: gli indici esistenti saranno eliminati")
        
        create_indices(es, force_recreate=force)
        get_index_stats(es)
        
        print("\n[OK] Setup completato!")
        
    except ConnectionError as e:
        print(f"\n[ERROR] Errore: {e}")
        print("\n[HINT] Assicurati che Elasticsearch sia in esecuzione.")
        print("   Con Docker: docker run -d -p 9200:9200 -e 'discovery.type=single-node' -e 'xpack.security.enabled=false' elasticsearch:8.12.1")


if __name__ == "__main__":
    main()
