"""
Estrazione delle tabelle dagli articoli scientifici.
Ingegneria dei Dati 2025/2026 - Homework 5

Per ogni tabella estrae:
- Corpo della tabella
- Caption
- Paragrafi che citano la tabella
- Paragrafi con termini presenti nella tabella/caption
"""

import os
import sys
import json
import re
from typing import Dict, List, Optional, Set
from collections import defaultdict

from lxml import html as lxml_html
from lxml import etree
from tqdm import tqdm
import warnings
warnings.filterwarnings("ignore")

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ARXIV_DATA_DIR, PUBMED_DATA_DIR, TABLES_DIR, STOPWORDS
)


class TableExtractor:
    """
    Estrae tabelle dagli articoli HTML con contesto associato.
    """
    
    def __init__(self):
        self.tables: List[Dict] = []
        self.tables_file = os.path.join(TABLES_DIR, "tables_metadata.json")
    
    def extract_from_html(self, html_content: str, paper_id: str, source: str) -> List[Dict]:
        """
        Estrae tutte le tabelle da un documento HTML.
        
        Args:
            html_content: Contenuto HTML dell'articolo
            paper_id: ID dell'articolo
            source: "arxiv" o "pubmed"
            
        Returns:
            Lista di tabelle estratte con contesto
        """
        # Usa lxml per compatibilità con Python 3.14
        try:
            doc = lxml_html.fromstring(html_content)
        except Exception:
            return []
        tables = []
        
        # Estrai tutti i paragrafi per il contesto
        paragraphs = self._extract_paragraphs(doc)
        
        # Trova tutte le tabelle
        table_elements = doc.xpath('//table')
        
        for idx, table_elem in enumerate(table_elements, 1):
            table_data = self._extract_table_data(
                table_elem, 
                paper_id, 
                source, 
                idx, 
                paragraphs
            )
            if table_data:
                tables.append(table_data)
        
        return tables
    
    def _extract_paragraphs(self, doc) -> List[Dict]:
        """Estrae tutti i paragrafi dal documento."""
        paragraphs = []
        
        # Trova tutti i paragrafi
        p_elements = doc.xpath('//p[contains(@class, "para")] | //div[contains(@class, "para")]')
        if not p_elements:
            p_elements = doc.xpath('//p')
        
        for idx, p in enumerate(p_elements):
            text = ' '.join(p.text_content().split())
            if len(text) > 20:  # Ignora paragrafi troppo corti
                paragraphs.append({
                    'index': idx,
                    'text': text,
                    'text_lower': text.lower()
                })
        
        return paragraphs
    
    def _extract_table_data(
        self, 
        table_elem, 
        paper_id: str, 
        source: str, 
        position: int,
        paragraphs: List[Dict]
    ) -> Optional[Dict]:
        """Estrae i dati di una singola tabella."""
        
        # Estrai il corpo della tabella
        body = self._extract_table_body(table_elem)
        if not body or len(body) < 10:
            return None
        
        # Estrai la caption
        caption = self._extract_caption(table_elem)
        
        # Trova l'ID della tabella (es. "Table 1", "tab1", ecc.)
        table_ref = self._find_table_reference(table_elem, position)
        
        # Trova i paragrafi che citano la tabella
        mentions = self._find_mentions(paragraphs, table_ref, position)
        
        # Trova i paragrafi con termini della tabella/caption
        terms = self._extract_informative_terms(body, caption)
        context_paragraphs = self._find_context_paragraphs(paragraphs, terms, mentions)
        
        return {
            'table_id': f"{paper_id}_table_{position}",
            'paper_id': paper_id,
            'source': source,
            'caption': caption,
            'body': body,
            'mentions': mentions,
            'context_paragraphs': context_paragraphs,
            'position': position,
            'terms': list(terms)[:50]  # Limita i termini salvati
        }
    
    def _extract_table_body(self, table_elem) -> str:
        """Estrae il contenuto testuale della tabella."""
        rows = []
        
        for tr in table_elem.xpath('.//tr'):
            cells = []
            for cell in tr.xpath('.//th | .//td'):
                cell_text = ' '.join(cell.text_content().split())
                cells.append(cell_text)
            if cells:
                rows.append(' | '.join(cells))
        
        return '\n'.join(rows)
    
    def _extract_caption(self, table_elem) -> str:
        """Estrae la caption della tabella."""
        # Cerca caption come elemento figlio
        caption = table_elem.xpath('.//caption')
        if caption:
            return ' '.join(caption[0].text_content().split())
        
        # Cerca nel parent (figure o div wrapper)
        parent = table_elem.getparent()
        if parent is not None:
            # Cerca figcaption
            figcaption = parent.xpath('.//figcaption')
            if figcaption:
                return ' '.join(figcaption[0].text_content().split())
            
            # Cerca elementi con classe caption
            caption_elem = parent.xpath('.//*[contains(@class, "caption")]')
            if caption_elem:
                return ' '.join(caption_elem[0].text_content().split())
            
            # Cerca elementi precedenti con "Table X"
            prev = table_elem.xpath('preceding-sibling::*[self::p or self::div or self::span][1]')
            if prev:
                text = ' '.join(prev[0].text_content().split())
                if re.match(r'^Table\s+\d+', text, re.IGNORECASE):
                    return text
        
        return ""
    
    def _find_table_reference(self, table_elem, position: int) -> str:
        """Trova il riferimento usato per citare la tabella."""
        # Cerca ID o attributi
        table_id = table_elem.get('id', '')
        if table_id:
            return table_id
        
        # Cerca nella caption
        caption = self._extract_caption(table_elem)
        match = re.search(r'Table\s*(\d+)', caption, re.IGNORECASE)
        if match:
            return f"Table {match.group(1)}"
        
        return f"Table {position}"
    
    def _find_mentions(
        self, 
        paragraphs: List[Dict], 
        table_ref: str, 
        position: int
    ) -> List[str]:
        """Trova i paragrafi che citano esplicitamente la tabella."""
        mentions = []
        
        # Pattern per trovare citazioni
        patterns = [
            rf'\b{re.escape(table_ref)}\b',
            rf'\bTable\s*{position}\b',
            rf'\btab\.\s*{position}\b',
            rf'\btbl\.\s*{position}\b',
        ]
        
        for para in paragraphs:
            text = para['text']
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    mentions.append(text)
                    break
        
        return mentions[:10]  # Limita a 10 menzioni
    
    def _extract_informative_terms(self, body: str, caption: str) -> Set[str]:
        """Estrae termini informativi dalla tabella e caption."""
        combined_text = f"{caption} {body}".lower()
        
        # Tokenizza
        words = re.findall(r'\b[a-z]{3,}\b', combined_text)
        
        # Rimuovi stopwords e termini troppo comuni
        informative_terms = set()
        for word in words:
            if word not in STOPWORDS and len(word) >= 4:
                informative_terms.add(word)
        
        return informative_terms
    
    def _find_context_paragraphs(
        self, 
        paragraphs: List[Dict], 
        terms: Set[str],
        exclude_mentions: List[str]
    ) -> List[str]:
        """Trova paragrafi contenenti termini della tabella."""
        context = []
        exclude_set = set(exclude_mentions)
        
        for para in paragraphs:
            if para['text'] in exclude_set:
                continue
            
            # Conta quanti termini sono presenti
            term_count = sum(1 for term in terms if term in para['text_lower'])
            
            # Richiedi almeno 3 termini
            if term_count >= 3:
                context.append(para['text'])
        
        return context[:15]  # Limita a 15 paragrafi di contesto
    
    def process_arxiv_articles(self) -> int:
        """Processa tutti gli articoli arXiv."""
        html_files = [f for f in os.listdir(ARXIV_DATA_DIR) if f.endswith('.html')]
        
        if not html_files:
            print("[WARN] Nessun file HTML trovato in arXiv")
            return 0
        
        count = 0
        print(f"\n[INFO] Elaborazione {len(html_files)} articoli arXiv...")
        
        for filename in tqdm(html_files, desc="Estrazione tabelle arXiv"):
            filepath = os.path.join(ARXIV_DATA_DIR, filename)
            paper_id = filename.replace('.html', '')
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                tables = self.extract_from_html(html_content, paper_id, "arxiv")
                self.tables.extend(tables)
                count += len(tables)
                
            except Exception as e:
                print(f"\n[WARN] Errore elaborazione {filename}: {e}")
        
        return count
    
    def process_pubmed_articles(self) -> int:
        """Processa tutti gli articoli PubMed (HTML o XML)."""
        # Cerca sia file HTML che XML
        all_files = [f for f in os.listdir(PUBMED_DATA_DIR) 
                     if f.endswith('.html') or f.endswith('.xml')]
        
        if not all_files:
            print("[WARN] Nessun file HTML/XML trovato in PubMed")
            return 0
        
        count = 0
        print(f"\n[INFO] Elaborazione {len(all_files)} articoli PubMed...")
        
        for filename in tqdm(all_files, desc="Estrazione tabelle PubMed"):
            filepath = os.path.join(PUBMED_DATA_DIR, filename)
            paper_id = filename.replace('.html', '').replace('.xml', '')
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tables = self.extract_from_html(content, paper_id, "pubmed")
                self.tables.extend(tables)
                count += len(tables)
                
            except Exception as e:
                pass  # Silently skip problematic files
        
        return count
    
    def run(self):
        """Esegue l'estrazione completa delle tabelle."""
        print("=" * 60)
        print("Table Extractor - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        
        arxiv_count = self.process_arxiv_articles()
        pubmed_count = self.process_pubmed_articles()
        
        # Salva i risultati
        print(f"\n[INFO] Salvataggio {len(self.tables)} tabelle...")
        with open(self.tables_file, 'w', encoding='utf-8') as f:
            json.dump(self.tables, f, indent=2, ensure_ascii=False)
        
        # Statistiche
        print("\n" + "=" * 60)
        print("[OK] Estrazione completata!")
        print(f"   Tabelle da arXiv: {arxiv_count}")
        print(f"   Tabelle da PubMed: {pubmed_count}")
        print(f"   Totale tabelle: {len(self.tables)}")
        print(f"   Salvate in: {self.tables_file}")
        print("=" * 60)
        
        return self.tables


def main():
    extractor = TableExtractor()
    extractor.run()


if __name__ == "__main__":
    main()
