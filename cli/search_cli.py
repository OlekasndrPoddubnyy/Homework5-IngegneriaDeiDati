"""
Interfaccia CLI per la ricerca nel sistema.
Ingegneria dei Dati 2025/2026 - Homework 5

Funzionalità:
- Ricerca articoli (titolo, autori, abstract, full-text)
- Ricerca tabelle (caption, body, mentions, context)
- Ricerca figure (caption, mentions, context)
- Ricerca booleana e full-text
- Visualizzazione risultati formattata
"""

import os
import sys
import cmd
from typing import Dict, List, Optional

from elasticsearch import Elasticsearch
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ELASTICSEARCH_URL, INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES
)


class SearchEngine:
    """Motore di ricerca per articoli, tabelle e figure."""
    
    def __init__(self):
        self.es = Elasticsearch(ELASTICSEARCH_URL)
        if not self.es.ping():
            raise ConnectionError(f"Impossibile connettersi a Elasticsearch: {ELASTICSEARCH_URL}")
    
    def search_papers(
        self,
        query: str,
        fields: List[str] = None,
        size: int = 10,
        source_filter: str = None
    ) -> Dict:
        """
        Cerca negli articoli scientifici.
        
        Args:
            query: Stringa di ricerca
            fields: Campi su cui cercare (default: tutti)
            size: Numero massimo di risultati
            source_filter: "arxiv" o "pubmed" per filtrare
        """
        if fields is None:
            fields = ["title^3", "abstract^2", "full_text", "authors"]
        
        body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": fields,
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        }
                    ]
                }
            },
            "size": size,
            "highlight": {
                "fields": {
                    "title": {},
                    "abstract": {"fragment_size": 200},
                    "full_text": {"fragment_size": 200}
                }
            }
        }
        
        if source_filter:
            body["query"]["bool"]["filter"] = [
                {"term": {"source": source_filter}}
            ]
        
        return self.es.search(index=INDEX_PAPERS, body=body)
    
    def search_tables(
        self,
        query: str,
        fields: List[str] = None,
        size: int = 10
    ) -> Dict:
        """
        Cerca nelle tabelle.
        
        Args:
            query: Stringa di ricerca
            fields: Campi su cui cercare
            size: Numero massimo di risultati
        """
        if fields is None:
            fields = ["caption^3", "body^2", "mentions", "context_paragraphs"]
        
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": fields,
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "size": size,
            "highlight": {
                "fields": {
                    "caption": {},
                    "body": {"fragment_size": 200},
                    "mentions": {"fragment_size": 200}
                }
            }
        }
        
        return self.es.search(index=INDEX_TABLES, body=body)
    
    def search_figures(
        self,
        query: str,
        fields: List[str] = None,
        size: int = 10
    ) -> Dict:
        """
        Cerca nelle figure.
        
        Args:
            query: Stringa di ricerca
            fields: Campi su cui cercare
            size: Numero massimo di risultati
        """
        if fields is None:
            fields = ["caption^3", "mentions^2", "context_paragraphs"]
        
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": fields,
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "size": size,
            "highlight": {
                "fields": {
                    "caption": {},
                    "mentions": {"fragment_size": 200}
                }
            }
        }
        
        return self.es.search(index=INDEX_FIGURES, body=body)
    
    def boolean_search(
        self,
        must_terms: List[str] = None,
        should_terms: List[str] = None,
        must_not_terms: List[str] = None,
        index: str = INDEX_PAPERS,
        size: int = 10
    ) -> Dict:
        """
        Esegue una ricerca booleana.
        
        Args:
            must_terms: Termini che DEVONO essere presenti (AND)
            should_terms: Termini che POSSONO essere presenti (OR)
            must_not_terms: Termini che NON devono essere presenti (NOT)
            index: Indice su cui cercare
            size: Numero massimo di risultati
        """
        bool_query = {"bool": {}}
        
        if must_terms:
            bool_query["bool"]["must"] = [
                {"match": {"_all": term}} if index == INDEX_PAPERS 
                else {"multi_match": {"query": term, "fields": ["*"]}}
                for term in must_terms
            ]
        
        if should_terms:
            bool_query["bool"]["should"] = [
                {"match": {"_all": term}} if index == INDEX_PAPERS 
                else {"multi_match": {"query": term, "fields": ["*"]}}
                for term in should_terms
            ]
            bool_query["bool"]["minimum_should_match"] = 1
        
        if must_not_terms:
            bool_query["bool"]["must_not"] = [
                {"match": {"_all": term}} if index == INDEX_PAPERS 
                else {"multi_match": {"query": term, "fields": ["*"]}}
                for term in must_not_terms
            ]
        
        body = {
            "query": bool_query,
            "size": size
        }
        
        return self.es.search(index=index, body=body)
    
    def get_stats(self) -> Dict:
        """Restituisce statistiche sugli indici."""
        stats = {}
        for index in [INDEX_PAPERS, INDEX_TABLES, INDEX_FIGURES]:
            try:
                if self.es.indices.exists(index=index):
                    stats[index] = self.es.count(index=index)['count']
                else:
                    stats[index] = 0
            except:
                stats[index] = 0
        return stats


class SearchCLI(cmd.Cmd):
    """Interfaccia a riga di comando per il sistema di ricerca."""
    
        intro = """
==================================================================
    Sistema di Ricerca Articoli Scientifici - Homework 5
    Ingegneria dei Dati 2025/2026
==================================================================

Comandi disponibili:
    papers <query>    - Cerca negli articoli
    tables <query>    - Cerca nelle tabelle
  figures <query>   - Cerca nelle figure
  bool <query>      - Ricerca booleana (usa AND, OR, NOT)
  stats             - Mostra statistiche
  help              - Mostra questo aiuto
  quit              - Esci

Esempi:
  papers query optimization
  tables performance results
  figures neural network architecture
  bool query AND optimization NOT distributed
"""
    prompt = "\nsearch> "
    
    def __init__(self):
        super().__init__()
        self.console = Console()
        try:
            self.engine = SearchEngine()
            self.console.print("[green]Connesso a Elasticsearch[/green]")
        except ConnectionError as e:
            self.console.print(f"[red]Errore: {e}[/red]")
            self.engine = None
    
    def do_papers(self, arg: str):
        """Cerca negli articoli: papers <query>"""
        if not arg:
            self.console.print("[yellow]Uso: papers <query>[/yellow]")
            return
        
        if not self.engine:
            self.console.print("[red]Elasticsearch non disponibile[/red]")
            return
        
        try:
            results = self.engine.search_papers(arg)
            self._display_paper_results(results)
        except Exception as e:
            self.console.print(f"[red]Errore: {e}[/red]")
    
    def do_tables(self, arg: str):
        """Cerca nelle tabelle: tables <query>"""
        if not arg:
            self.console.print("[yellow]Uso: tables <query>[/yellow]")
            return
        
        if not self.engine:
            self.console.print("[red]Elasticsearch non disponibile[/red]")
            return
        
        try:
            results = self.engine.search_tables(arg)
            self._display_table_results(results)
        except Exception as e:
            self.console.print(f"[red]Errore: {e}[/red]")
    
    def do_figures(self, arg: str):
        """Cerca nelle figure: figures <query>"""
        if not arg:
            self.console.print("[yellow]Uso: figures <query>[/yellow]")
            return
        
        if not self.engine:
            self.console.print("[red]Elasticsearch non disponibile[/red]")
            return
        
        try:
            results = self.engine.search_figures(arg)
            self._display_figure_results(results)
        except Exception as e:
            self.console.print(f"[red]Errore: {e}[/red]")
    
    def do_bool(self, arg: str):
        """Ricerca booleana: bool <query> (usa AND, OR, NOT)"""
        if not arg:
            self.console.print("[yellow]Uso: bool term1 AND term2 OR term3 NOT term4[/yellow]")
            return
        
        if not self.engine:
            self.console.print("[red]Elasticsearch non disponibile[/red]")
            return
        
        # Parse della query booleana
        must_terms = []
        should_terms = []
        must_not_terms = []
        
        # Semplice parsing
        parts = arg.upper().replace(' AND ', '|AND|').replace(' OR ', '|OR|').replace(' NOT ', '|NOT|').split('|')
        
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
                term = arg[arg.upper().find(part):arg.upper().find(part)+len(part)]
                if current_op == 'AND':
                    must_terms.append(term.lower())
                elif current_op == 'OR':
                    should_terms.append(term.lower())
                elif current_op == 'NOT':
                    must_not_terms.append(term.lower())
        
        try:
            results = self.engine.boolean_search(
                must_terms=must_terms if must_terms else None,
                should_terms=should_terms if should_terms else None,
                must_not_terms=must_not_terms if must_not_terms else None
            )
            self._display_paper_results(results)
        except Exception as e:
            self.console.print(f"[red]Errore: {e}[/red]")
    
    def do_stats(self, arg: str):
        """Mostra statistiche degli indici"""
        if not self.engine:
            self.console.print("[red]Elasticsearch non disponibile[/red]")
            return
        
        try:
            stats = self.engine.get_stats()
            
            table = Table(title="Statistiche Indici")
            table.add_column("Indice", style="cyan")
            table.add_column("Documenti", justify="right", style="green")
            
            for index, count in stats.items():
                table.add_row(index, str(count))
            
            self.console.print(table)
        except Exception as e:
            self.console.print(f"[red]Errore: {e}[/red]")
    
    def do_quit(self, arg: str):
        """Esci dal programma"""
        self.console.print("[blue]Arrivederci![/blue]")
        return True
    
    def do_exit(self, arg: str):
        """Esci dal programma"""
        return self.do_quit(arg)
    
    def _display_paper_results(self, results: Dict):
        """Visualizza i risultati della ricerca articoli."""
        hits = results.get('hits', {}).get('hits', [])
        total = results.get('hits', {}).get('total', {})
        if isinstance(total, dict):
            total = total.get('value', 0)
        
        self.console.print(f"\n[bold]Trovati {total} risultati[/bold]\n")
        
        if not hits:
            self.console.print("[yellow]Nessun risultato trovato[/yellow]")
            return
        
        for i, hit in enumerate(hits, 1):
            source = hit['_source']
            score = hit['_score']
            
            # Crea pannello per ogni risultato
            title = source.get('title', 'N/A')[:100]
            paper_id = source.get('paper_id', 'N/A')
            authors = source.get('authors', 'N/A')[:80]
            src = source.get('source', 'N/A')
            
            # Highlight se disponibile
            highlights = hit.get('highlight', {})
            abstract_hl = highlights.get('abstract', [source.get('abstract', '')[:300]])[0]
            
            content = f"""
[cyan]ID:[/cyan] {paper_id} ([magenta]{src}[/magenta])
[cyan]Autori:[/cyan] {authors}
[cyan]Score:[/cyan] {score:.2f}

[cyan]Abstract:[/cyan]
{abstract_hl}...
"""
            
            panel = Panel(
                content,
                title=f"[bold green]{i}. {title}[/bold green]",
                border_style="blue"
            )
            self.console.print(panel)
    
    def _display_table_results(self, results: Dict):
        """Visualizza i risultati della ricerca tabelle."""
        hits = results.get('hits', {}).get('hits', [])
        total = results.get('hits', {}).get('total', {})
        if isinstance(total, dict):
            total = total.get('value', 0)
        
        self.console.print(f"\n[bold]Trovate {total} tabelle[/bold]\n")
        
        if not hits:
            self.console.print("[yellow]Nessun risultato trovato[/yellow]")
            return
        
        for i, hit in enumerate(hits, 1):
            source = hit['_source']
            score = hit['_score']
            
            table_id = source.get('table_id', 'N/A')
            paper_id = source.get('paper_id', 'N/A')
            caption = source.get('caption', 'N/A')[:200]
            body_preview = source.get('body', '')[:300]
            
            content = f"""
[cyan]Table ID:[/cyan] {table_id}
[cyan]Paper ID:[/cyan] {paper_id}
[cyan]Score:[/cyan] {score:.2f}

[cyan]Caption:[/cyan]
{caption}

[cyan]Contenuto (preview):[/cyan]
{body_preview}...
"""
            
            panel = Panel(
                content,
                title=f"[bold green]{i}. Tabella[/bold green]",
                border_style="yellow"
            )
            self.console.print(panel)
    
    def _display_figure_results(self, results: Dict):
        """Visualizza i risultati della ricerca figure."""
        hits = results.get('hits', {}).get('hits', [])
        total = results.get('hits', {}).get('total', {})
        if isinstance(total, dict):
            total = total.get('value', 0)
        
        self.console.print(f"\n[bold]Trovate {total} figure[/bold]\n")
        
        if not hits:
            self.console.print("[yellow]Nessun risultato trovato[/yellow]")
            return
        
        for i, hit in enumerate(hits, 1):
            source = hit['_source']
            score = hit['_score']
            
            figure_id = source.get('figure_id', 'N/A')
            paper_id = source.get('paper_id', 'N/A')
            url = source.get('url', 'N/A')
            caption = source.get('caption', 'N/A')[:200]
            
            content = f"""
[cyan]Figure ID:[/cyan] {figure_id}
[cyan]Paper ID:[/cyan] {paper_id}
[cyan]URL:[/cyan] {url}
[cyan]Score:[/cyan] {score:.2f}

[cyan]Caption:[/cyan]
{caption}
"""
            
            panel = Panel(
                content,
                title=f"[bold green]{i}. Figura[/bold green]",
                border_style="magenta"
            )
            self.console.print(panel)


def main():
    cli = SearchCLI()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\nArrivederci!")


if __name__ == "__main__":
    main()
