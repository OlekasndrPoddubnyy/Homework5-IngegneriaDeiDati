"""
Interfaccia Web Flask per la ricerca nel sistema.
Ingegneria dei Dati 2025/2026 - Homework 5

Funzionalità:
- Ricerca articoli, tabelle e figure
- Ricerca booleana
- Visualizzazione risultati con highlighting
- API REST per integrazione
"""

import os
import sys
from flask import Flask, render_template, request, jsonify
from elasticsearch import Elasticsearch

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ELASTICSEARCH_URL, INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

# Connessione Elasticsearch
es = Elasticsearch(ELASTICSEARCH_URL)

# Costanti per i campi di ricerca
PAPER_FIELDS = ["title^3", "abstract^2", "full_text", "authors"]
TABLE_FIELDS = ["caption^3", "body^2", "mentions", "context_paragraphs", "informative_terms^2"]
FIGURE_FIELDS = ["caption^3", "mentions^2", "context_paragraphs", "informative_terms"]


def search_index(index: str, query: str, fields: list, size: int = 20, source_filter: str = None):
    """Esegue una ricerca su un indice specifico."""
    try:
        # Costruisci la query base
        base_query = {
            "multi_match": {
                "query": query,
                "fields": fields,
                "type": "best_fields",
                "fuzziness": "AUTO"
            }
        }
        
        # Aggiungi filtro per fonte se specificato
        if source_filter and source_filter != 'all':
            query_body = {
                "bool": {
                    "must": base_query,
                    "filter": {
                        "term": {"source": source_filter}
                    }
                }
            }
        else:
            query_body = base_query
        
        body = {
            "query": query_body,
            "size": size,
            "highlight": {
                "fields": {field.split('^')[0]: {"fragment_size": 200} for field in fields},
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            }
        }
        
        return es.search(index=index, body=body)
    except Exception as e:
        return {"error": str(e), "hits": {"hits": [], "total": {"value": 0}}}


def parse_boolean_query(query_str: str):
    """Converte una stringa in componenti booleani."""
    must_terms = []
    should_terms = []
    must_not_terms = []
    
    # Parse semplice
    parts = query_str.upper().replace(' AND ', '|AND|').replace(' OR ', '|OR|').replace(' NOT ', '|NOT|').split('|')
    
    current_op = 'AND'
    for part in parts:
        part = part.strip()
        if part == 'AND':
            current_op = 'AND'
        elif part == 'OR':
            current_op = 'OR'
        elif part == 'NOT':
            current_op = 'NOT'
        elif part:
            # Recupera il termine originale (case-sensitive)
            term = query_str[query_str.upper().find(part):query_str.upper().find(part)+len(part)]
            if current_op == 'AND':
                must_terms.append(term)
            elif current_op == 'OR':
                should_terms.append(term)
            elif current_op == 'NOT':
                must_not_terms.append(term)
    
    return must_terms, should_terms, must_not_terms


def boolean_search(index: str, must_terms: list, should_terms: list, must_not_terms: list, size: int = 20, source_filter: str = None):
    """Esegue una ricerca booleana."""
    bool_query = {"bool": {}}
    
    if must_terms:
        bool_query["bool"]["must"] = [
            {"multi_match": {"query": term, "fields": ["*"]}}
            for term in must_terms
        ]
    
    if should_terms:
        bool_query["bool"]["should"] = [
            {"multi_match": {"query": term, "fields": ["*"]}}
            for term in should_terms
        ]
        bool_query["bool"]["minimum_should_match"] = 1
    
    if must_not_terms:
        bool_query["bool"]["must_not"] = [
            {"multi_match": {"query": term, "fields": ["*"]}}
            for term in must_not_terms
        ]
    
    # Aggiungi filtro per fonte se specificato
    if source_filter and source_filter != 'all':
        bool_query["bool"]["filter"] = {
            "term": {"source": source_filter}
        }
    
    body = {
        "query": bool_query,
        "size": size,
        "highlight": {
            "fields": {"*": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"]
        }
    }
    
    try:
        return es.search(index=index, body=body)
    except Exception as e:
        return {"error": str(e), "hits": {"hits": [], "total": {"value": 0}}}


@app.route('/')
def home():
    """Pagina principale con form di ricerca."""
    # Ottieni statistiche generali
    stats = {}
    for index in [INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES]:
        try:
            if es.indices.exists(index=index):
                stats[index] = es.count(index=index)['count']
            else:
                stats[index] = 0
        except Exception:
            stats[index] = 0
    
    # Ottieni statistiche per fonte (arXiv vs PubMed)
    arxiv_stats = {'papers': 0, 'tables': 0, 'figures': 0}
    pubmed_stats = {'papers': 0, 'tables': 0, 'figures': 0}
    
    try:
        if es.indices.exists(index=INDEX_PAPERS):
            # Conta articoli arXiv
            arxiv_count = es.count(
                index=INDEX_PAPERS,
                body={"query": {"term": {"source": "arxiv"}}}
            )
            arxiv_stats['papers'] = arxiv_count.get('count', 0)
            
            # Conta articoli PubMed
            pubmed_count = es.count(
                index=INDEX_PAPERS,
                body={"query": {"term": {"source": "pubmed"}}}
            )
            pubmed_stats['papers'] = pubmed_count.get('count', 0)
    except Exception:
        pass
    
    try:
        if es.indices.exists(index=INDEX_TABLES):
            # Conta tabelle arXiv
            arxiv_tables = es.count(
                index=INDEX_TABLES,
                body={"query": {"term": {"source": "arxiv"}}}
            )
            arxiv_stats['tables'] = arxiv_tables.get('count', 0)
            
            # Conta tabelle PubMed
            pubmed_tables = es.count(
                index=INDEX_TABLES,
                body={"query": {"term": {"source": "pubmed"}}}
            )
            pubmed_stats['tables'] = pubmed_tables.get('count', 0)
    except Exception:
        pass
    
    try:
        if es.indices.exists(index=INDEX_FIGURES):
            # Conta figure arXiv
            arxiv_figures = es.count(
                index=INDEX_FIGURES,
                body={"query": {"term": {"source": "arxiv"}}}
            )
            arxiv_stats['figures'] = arxiv_figures.get('count', 0)
            
            # Conta figure PubMed
            pubmed_figures = es.count(
                index=INDEX_FIGURES,
                body={"query": {"term": {"source": "pubmed"}}}
            )
            pubmed_stats['figures'] = pubmed_figures.get('count', 0)
    except Exception:
        pass
    
    return render_template(
        'index.html', 
        stats=stats, 
        arxiv_stats=arxiv_stats, 
        pubmed_stats=pubmed_stats
    )


@app.route('/search')
def search():
    """Endpoint di ricerca principale."""
    query = request.args.get('q', '').strip()
    doc_type = request.args.get('type', 'papers')
    search_type = request.args.get('search_type', 'fulltext')
    source_filter = request.args.get('source', 'all')
    size = min(int(request.args.get('size', 20)), 100)
    
    if not query:
        return render_template('results.html', results=[], query='', doc_type=doc_type, source_filter=source_filter, total=0)
    
    # Determina indice e campi
    if doc_type == 'tables':
        index = INDEX_TABLES
        fields = TABLE_FIELDS
    elif doc_type == 'figures':
        index = INDEX_FIGURES
        fields = FIGURE_FIELDS
    else:  # papers o tipo non valido
        index = INDEX_PAPERS
        fields = PAPER_FIELDS
    
    # Esegui ricerca
    if search_type == 'boolean':
        must_terms, should_terms, must_not_terms = parse_boolean_query(query)
        results = boolean_search(index, must_terms, should_terms, must_not_terms, size, source_filter)
    else:
        results = search_index(index, query, fields, size, source_filter)
    
    # Estrai risultati
    hits = results.get('hits', {}).get('hits', [])
    total = results.get('hits', {}).get('total', {})
    if isinstance(total, dict):
        total = total.get('value', 0)
    
    # Formatta risultati per il template
    formatted_results = []
    for hit in hits:
        source = hit['_source']
        highlight = hit.get('highlight', {})
        
        result = {
            'id': hit['_id'],
            'score': round(hit['_score'], 2),
            'source': source,
            'highlight': highlight
        }
        formatted_results.append(result)
    
    return render_template(
        'results.html',
        results=formatted_results,
        query=query,
        doc_type=doc_type,
        search_type=search_type,
        source_filter=source_filter,
        total=total
    )


@app.route('/api/search')
def api_search():
    """API REST per ricerca programmatica."""
    query = request.args.get('q', '').strip()
    doc_type = request.args.get('type', 'papers')
    search_type = request.args.get('search_type', 'fulltext')
    source_filter = request.args.get('source', 'all')
    size = min(int(request.args.get('size', 20)), 100)
    
    if not query:
        return jsonify({'error': 'Query non specificata', 'results': [], 'total': 0})
    
    # Determina indice e campi
    if doc_type == 'papers':
        index = INDEX_PAPERS
        fields = PAPER_FIELDS
    elif doc_type == 'tables':
        index = INDEX_TABLES
        fields = TABLE_FIELDS
    elif doc_type == 'figures':
        index = INDEX_FIGURES
        fields = FIGURE_FIELDS
    else:
        return jsonify({'error': 'Tipo documento non valido', 'results': [], 'total': 0})
    
    # Esegui ricerca
    if search_type == 'boolean':
        must_terms, should_terms, must_not_terms = parse_boolean_query(query)
        results = boolean_search(index, must_terms, should_terms, must_not_terms, size, source_filter)
    else:
        results = search_index(index, query, fields, size, source_filter)
    
    # Estrai e restituisci risultati
    hits = results.get('hits', {}).get('hits', [])
    total = results.get('hits', {}).get('total', {})
    if isinstance(total, dict):
        total = total.get('value', 0)
    
    return jsonify({
        'query': query,
        'type': doc_type,
        'source': source_filter,
        'total': total,
        'results': [
            {
                'id': hit['_id'],
                'score': hit['_score'],
                'data': hit['_source'],
                'highlight': hit.get('highlight', {})
            }
            for hit in hits
        ]
    })


@app.route('/api/stats')
def api_stats():
    """API per statistiche degli indici."""
    stats = {}
    for index in [INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES]:
        try:
            if es.indices.exists(index=index):
                stats[index] = es.count(index=index)['count']
            else:
                stats[index] = 0
        except Exception as e:
            stats[index] = {'error': str(e)}
    
    return jsonify(stats)


@app.route('/paper/<paper_id>')
def view_paper(paper_id):
    """Visualizza dettagli di un articolo."""
    try:
        result = es.get(index=INDEX_PAPERS, id=paper_id)
        source = result['_source']
        
        # Estrai il vero paper_id dal source (senza prefisso arxiv_ o pubmed_)
        actual_paper_id = source.get('paper_id') or source.get('arxiv_id') or source.get('pmc_id') or source.get('pmid')
        if not actual_paper_id and paper_id.startswith('arxiv_'):
            actual_paper_id = paper_id.replace('arxiv_', '')
        elif not actual_paper_id and paper_id.startswith('pubmed_'):
            actual_paper_id = paper_id.replace('pubmed_', '')
        
        # Debug
        print(f"[DEBUG] URL paper_id: {paper_id}")
        print(f"[DEBUG] Actual paper_id from source: {actual_paper_id}")
        print(f"[DEBUG] Source keys: {list(source.keys())}")
        
        # Cerca tabelle e figure associate usando il paper_id reale
        tables_response = es.search(
            index=INDEX_TABLES,
            body={
                "query": {"term": {"paper_id": actual_paper_id}}, 
                "size": 100,
                "_source": ["table_id", "paper_id", "caption", "body", "mentions", "context_paragraphs", "position"],
                "sort": [{"position": {"order": "asc"}}]
            }
        )
        
        figures_response = es.search(
            index=INDEX_FIGURES,
            body={
                "query": {"term": {"paper_id": actual_paper_id}}, 
                "size": 100,
                "_source": ["figure_id", "paper_id", "caption", "url", "mentions", "context_paragraphs", "position"],
                "sort": [{"position": {"order": "asc"}}]
            }
        )
        
        # Formatta tabelle e figure per il template
        tables = [hit['_source'] for hit in tables_response['hits']['hits']]
        figures = [hit['_source'] for hit in figures_response['hits']['hits']]
        
        # Debug: aggiungi log per verificare cosa viene recuperato
        print(f"[DEBUG] Tabelle trovate: {len(tables)}")
        print(f"[DEBUG] Figure trovate: {len(figures)}")
        if tables:
            print(f"[DEBUG] Prima tabella: {tables[0].get('table_id', 'N/A')}")
            print(f"[DEBUG] Prima tabella ha 'body': {'body' in tables[0]}")
            if 'body' in tables[0]:
                print(f"[DEBUG] Lunghezza body: {len(tables[0].get('body', ''))}")
        if figures:
            print(f"[DEBUG] Prima figura: {figures[0].get('figure_id', 'N/A')}")
        
        return render_template(
            'paper_detail.html',
            paper=source,
            paper_id=paper_id,
            tables=tables,
            figures=figures
        )
    except Exception as e:
        print(f"[ERROR] view_paper exception: {e}")
        return render_template('error.html', error=str(e)), 404


if __name__ == '__main__':
    print("=" * 60)
    print("Sistema di Ricerca Articoli Scientifici - Homework 5")
    print("Ingegneria dei Dati 2025/2026")
    print("=" * 60)
    print(f"\nElasticsearch: {ELASTICSEARCH_URL}")
    print("Server: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
