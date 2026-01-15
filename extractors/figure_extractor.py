"""
Estrazione delle figure dagli articoli scientifici.
Ingegneria dei Dati 2025/2026 - Homework 5

Per ogni figura estrae:
- URL dell'immagine
- Caption
- Paragrafi che citano la figura
- Paragrafi con termini presenti nella caption
"""

import os
import sys
import json
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from tqdm import tqdm

# Aggiungi il path principale al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ARXIV_DATA_DIR, PUBMED_DATA_DIR, FIGURES_DIR, STOPWORDS,
    ARXIV_BASE_URL, PUBMED_BASE_URL
)


class FigureExtractor:
    """
    Estrae figure dagli articoli HTML con contesto associato.
    """
    
    def __init__(self):
        self.figures: List[Dict] = []
        self.figures_file = os.path.join(FIGURES_DIR, "figures_metadata.json")
    
    def extract_from_html(
        self, 
        html_content: str, 
        paper_id: str, 
        source: str,
        base_url: str
    ) -> List[Dict]:
        """
        Estrae tutte le figure da un documento HTML.
        
        Args:
            html_content: Contenuto HTML dell'articolo
            paper_id: ID dell'articolo
            source: "arxiv" o "pubmed"
            base_url: URL base per risolvere URL relativi
            
        Returns:
            Lista di figure estratte con contesto
        """
        soup = BeautifulSoup(html_content, 'lxml')
        figures = []
        
        # Estrai tutti i paragrafi per il contesto
        paragraphs = self._extract_paragraphs(soup)
        
        # Metodo 1: Cerca elementi <figure>
        figure_elements = soup.find_all('figure')
        
        for idx, fig_elem in enumerate(figure_elements, 1):
            figure_data = self._extract_figure_data(
                fig_elem, paper_id, source, idx, paragraphs, base_url
            )
            if figure_data:
                figures.append(figure_data)
        
        # Metodo 2: Cerca immagini con caption (se non abbiamo trovato figure)
        if not figures:
            figures = self._extract_from_images(
                soup, paper_id, source, paragraphs, base_url
            )
        
        return figures
    
    def _extract_paragraphs(self, soup: BeautifulSoup) -> List[Dict]:
        """Estrae tutti i paragrafi dal documento."""
        paragraphs = []
        
        p_elements = soup.find_all(['p', 'div'], class_=lambda x: x and 'para' in str(x).lower())
        if not p_elements:
            p_elements = soup.find_all('p')
        
        for idx, p in enumerate(p_elements):
            text = p.get_text(separator=' ', strip=True)
            if len(text) > 20:
                paragraphs.append({
                    'index': idx,
                    'text': text,
                    'text_lower': text.lower()
                })
        
        return paragraphs
    
    def _extract_figure_data(
        self,
        fig_elem,
        paper_id: str,
        source: str,
        position: int,
        paragraphs: List[Dict],
        base_url: str
    ) -> Optional[Dict]:
        """Estrae i dati di una singola figura."""
        
        # Trova l'immagine
        img = fig_elem.find('img')
        if not img:
            # Prova a cercare un'immagine in un link
            link = fig_elem.find('a')
            if link:
                img = link.find('img')
        
        if not img:
            return None
        
        # Estrai l'URL dell'immagine
        img_url = img.get('src', '') or img.get('data-src', '')
        if not img_url:
            return None
        
        # Risolvi URL relativi
        if not img_url.startswith(('http://', 'https://')):
            img_url = urljoin(base_url, img_url)
        
        # Estrai la caption
        caption = self._extract_caption(fig_elem)
        
        # Trova il riferimento della figura
        fig_ref = self._find_figure_reference(fig_elem, position)
        
        # Trova i paragrafi che citano la figura
        mentions = self._find_mentions(paragraphs, fig_ref, position)
        
        # Trova i paragrafi con termini della caption
        terms = self._extract_informative_terms(caption)
        context_paragraphs = self._find_context_paragraphs(paragraphs, terms, mentions)
        
        return {
            'figure_id': f"{paper_id}_fig_{position}",
            'paper_id': paper_id,
            'source': source,
            'url': img_url,
            'caption': caption,
            'mentions': mentions,
            'context_paragraphs': context_paragraphs,
            'position': position
        }
    
    def _extract_from_images(
        self,
        soup: BeautifulSoup,
        paper_id: str,
        source: str,
        paragraphs: List[Dict],
        base_url: str
    ) -> List[Dict]:
        """Estrae figure cercando direttamente le immagini."""
        figures = []
        
        # Cerca tutte le immagini
        images = soup.find_all('img')
        
        position = 0
        for img in images:
            src = img.get('src', '') or img.get('data-src', '')
            if not src:
                continue
            
            # Filtra immagini non significative (icone, loghi, etc.)
            if any(x in src.lower() for x in ['icon', 'logo', 'button', 'arrow', 'pixel']):
                continue
            
            # Controlla le dimensioni se disponibili
            width = img.get('width', '')
            height = img.get('height', '')
            if width and height:
                try:
                    if int(width) < 100 or int(height) < 100:
                        continue
                except ValueError:
                    pass
            
            position += 1
            
            # Risolvi URL
            if not src.startswith(('http://', 'https://')):
                src = urljoin(base_url, src)
            
            # Cerca caption nel contesto
            caption = self._find_image_caption(img)
            
            fig_ref = f"Figure {position}"
            mentions = self._find_mentions(paragraphs, fig_ref, position)
            terms = self._extract_informative_terms(caption)
            context_paragraphs = self._find_context_paragraphs(paragraphs, terms, mentions)
            
            figures.append({
                'figure_id': f"{paper_id}_fig_{position}",
                'paper_id': paper_id,
                'source': source,
                'url': src,
                'caption': caption,
                'mentions': mentions,
                'context_paragraphs': context_paragraphs,
                'position': position
            })
        
        return figures
    
    def _extract_caption(self, fig_elem) -> str:
        """Estrae la caption della figura."""
        # Cerca figcaption
        figcaption = fig_elem.find('figcaption')
        if figcaption:
            return figcaption.get_text(separator=' ', strip=True)
        
        # Cerca elementi con classe caption
        caption_elem = fig_elem.find(class_=lambda x: x and 'caption' in str(x).lower())
        if caption_elem:
            return caption_elem.get_text(separator=' ', strip=True)
        
        # Cerca testo dopo l'immagine
        img = fig_elem.find('img')
        if img:
            next_text = img.find_next(['p', 'span', 'div'])
            if next_text and next_text.parent == fig_elem:
                text = next_text.get_text(strip=True)
                if re.match(r'^(Figure|Fig\.?)\s*\d+', text, re.IGNORECASE):
                    return text
        
        return ""
    
    def _find_image_caption(self, img) -> str:
        """Cerca la caption di un'immagine standalone."""
        # Cerca nel parent
        parent = img.parent
        if parent:
            # Cerca testo seguente
            next_elem = img.find_next(['p', 'span', 'div', 'figcaption'])
            if next_elem:
                text = next_elem.get_text(strip=True)
                if len(text) < 500:  # Non troppo lungo
                    return text
            
            # Cerca attributo alt
            alt = img.get('alt', '')
            if alt and len(alt) > 10:
                return alt
        
        return ""
    
    def _find_figure_reference(self, fig_elem, position: int) -> str:
        """Trova il riferimento usato per citare la figura."""
        fig_id = fig_elem.get('id', '')
        if fig_id:
            return fig_id
        
        caption = self._extract_caption(fig_elem)
        match = re.search(r'(Figure|Fig\.?)\s*(\d+)', caption, re.IGNORECASE)
        if match:
            return f"Figure {match.group(2)}"
        
        return f"Figure {position}"
    
    def _find_mentions(
        self,
        paragraphs: List[Dict],
        fig_ref: str,
        position: int
    ) -> List[str]:
        """Trova i paragrafi che citano esplicitamente la figura."""
        mentions = []
        
        patterns = [
            rf'\b{re.escape(fig_ref)}\b',
            rf'\bFigure\s*{position}\b',
            rf'\bFig\.\s*{position}\b',
        ]
        
        for para in paragraphs:
            text = para['text']
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    mentions.append(text)
                    break
        
        return mentions[:10]
    
    def _extract_informative_terms(self, caption: str) -> Set[str]:
        """Estrae termini informativi dalla caption."""
        words = re.findall(r'\b[a-z]{3,}\b', caption.lower())
        
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
        """Trova paragrafi contenenti termini della caption."""
        context = []
        exclude_set = set(exclude_mentions)
        
        for para in paragraphs:
            if para['text'] in exclude_set:
                continue
            
            term_count = sum(1 for term in terms if term in para['text_lower'])
            
            if term_count >= 2:  # Almeno 2 termini
                context.append(para['text'])
        
        return context[:10]
    
    def process_arxiv_articles(self) -> int:
        """Processa tutti gli articoli arXiv."""
        html_files = [f for f in os.listdir(ARXIV_DATA_DIR) if f.endswith('.html')]
        
        if not html_files:
            print("[WARN] Nessun file HTML trovato in arXiv")
            return 0
        
        count = 0
        print(f"\n[INFO] Elaborazione {len(html_files)} articoli arXiv...")
        
        for filename in tqdm(html_files, desc="Estrazione figure arXiv"):
            filepath = os.path.join(ARXIV_DATA_DIR, filename)
            paper_id = filename.replace('.html', '')
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                base_url = f"{ARXIV_BASE_URL}/html/{paper_id}/"
                figures = self.extract_from_html(html_content, paper_id, "arxiv", base_url)
                self.figures.extend(figures)
                count += len(figures)
                
            except Exception as e:
                pass
        
        return count
    
    def process_pubmed_articles(self) -> int:
        """Processa tutti gli articoli PubMed."""
        html_files = [f for f in os.listdir(PUBMED_DATA_DIR) if f.endswith('.html')]
        
        if not html_files:
            print("[WARN] Nessun file HTML trovato in PubMed")
            return 0
        
        count = 0
        print(f"\n[INFO] Elaborazione {len(html_files)} articoli PubMed...")
        
        for filename in tqdm(html_files, desc="Estrazione figure PubMed"):
            filepath = os.path.join(PUBMED_DATA_DIR, filename)
            paper_id = filename.replace('.html', '')
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                base_url = f"{PUBMED_BASE_URL}/articles/{paper_id}/"
                figures = self.extract_from_html(html_content, paper_id, "pubmed", base_url)
                self.figures.extend(figures)
                count += len(figures)
                
            except Exception as e:
                pass
        
        return count
    
    def run(self):
        """Esegue l'estrazione completa delle figure."""
        print("=" * 60)
        print("Figure Extractor - Ingegneria dei Dati Homework 5")
        print("=" * 60)
        
        arxiv_count = self.process_arxiv_articles()
        pubmed_count = self.process_pubmed_articles()
        
        # Salva i risultati
        print(f"\n[INFO] Salvataggio {len(self.figures)} figure...")
        with open(self.figures_file, 'w', encoding='utf-8') as f:
            json.dump(self.figures, f, indent=2, ensure_ascii=False)
        
        # Statistiche
        print("\n" + "=" * 60)
        print("[OK] Estrazione completata!")
        print(f"   Figure da arXiv: {arxiv_count}")
        print(f"   Figure da PubMed: {pubmed_count}")
        print(f"   Totale figure: {len(self.figures)}")
        print(f"   Salvate in: {self.figures_file}")
        print("=" * 60)
        
        return self.figures


def main():
    extractor = FigureExtractor()
    extractor.run()


if __name__ == "__main__":
    main()
