"""
Scraper pour extraire toutes les questions officielles du permis de conduire israélien
depuis https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data

Note: Ce site utilise JavaScript pour charger les réponses dynamiquement.
On va scraper la structure de base et créer des questions avec options génériques,
puis vous pourrez les compléter manuellement ou via une autre source.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from typing import List, Dict
import uuid

BASE_URL = "https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data"
QUESTIONS_PER_PAGE = 10
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def extract_question_details(question_url: str) -> Dict:
    """
    DEPRECATED: Le site utilise JavaScript pour charger les réponses.
    Cette fonction n'est plus utilisée dans la version simplifiée.
    """
    return {"answers": [], "explanation": ""}

def scrape_questions_page(skip: int = 0) -> List[Dict]:
    """
    Scrape une page de questions (10 questions par page)
    """
    url = f"{BASE_URL}?skip={skip}"
    print(f"Scraping page: {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        questions = []
        
        # Le site gov.il utilise une structure avec h3 pour les titres de questions
        # Format: "0001. Texte de la question"
        question_titles = soup.find_all('h3')
        
        for title in question_titles:
            try:
                title_text = title.get_text(strip=True)
                
                # Vérifier si c'est bien une question (format: XXXX. Question?)
                match = re.match(r'(\d+)\.\s*(.+)', title_text)
                if not match:
                    continue
                
                question_number = match.group(1)
                question_text = match.group(2)
                
                # Trouver le parent pour chercher la catégorie
                parent = title.parent
                category = "Général"
                
                # Chercher "Sujet:" dans les éléments suivants
                siblings = parent.find_next_siblings() if parent else []
                for sibling in siblings[:3]:  # Limiter la recherche aux 3 prochains éléments
                    text = sibling.get_text()
                    if 'Sujet:' in text or 'Subject:' in text:
                        category = text.replace('Sujet:', '').replace('Subject:', '').strip()
                        break
                
                # Créer la question avec des options génériques
                # Les vraies réponses nécessiteraient Selenium ou une API
                question = {
                    "number": question_number,
                    "text": question_text,
                    "category": category,
                    "image_url": None,
                    "options": [
                        {"id": str(uuid.uuid4()), "text": "Option A (à compléter)", "is_correct": True},
                        {"id": str(uuid.uuid4()), "text": "Option B (à compléter)", "is_correct": False},
                        {"id": str(uuid.uuid4()), "text": "Option C (à compléter)", "is_correct": False},
                        {"id": str(uuid.uuid4()), "text": "Option D (à compléter)", "is_correct": False}
                    ],
                    "explanation": f"Explication pour la question {question_number} (à compléter)"
                }
                
                questions.append(question)
                print(f"  ✓ Question {question_number}: {question_text[:60]}...")
                
            except Exception as e:
                print(f"  ✗ Erreur lors du traitement: {e}")
                continue
        
        return questions
        
    except Exception as e:
        print(f"Erreur lors du scraping de la page skip={skip}: {e}")
        return []

def scrape_all_questions(total_questions: int = 1802) -> List[Dict]:
    """
    Scrape toutes les questions (1802 au total)
    """
    all_questions = []
    
    # Pagination: 10 questions par page
    for skip in range(0, total_questions, QUESTIONS_PER_PAGE):
        print(f"\n=== Page {skip // QUESTIONS_PER_PAGE + 1} / {(total_questions // QUESTIONS_PER_PAGE) + 1} ===")
        
        questions = scrape_questions_page(skip)
        all_questions.extend(questions)
        
        # Pause entre les pages
        time.sleep(1)
        
        # Sauvegarde intermédiaire tous les 100 questions
        if len(all_questions) % 100 == 0:
            save_questions(all_questions, f"questions_backup_{len(all_questions)}.json")
    
    return all_questions

def save_questions(questions: List[Dict], filename: str = "questions_data.json"):
    """
    Sauvegarde les questions dans un fichier JSON
    """
    filepath = f"../data/{filename}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    print(f"\n✓ {len(questions)} questions sauvegardées dans {filepath}")

if __name__ == "__main__":
    print("=== Scraping des questions officielles du permis de conduire ===\n")
    
    # Tester sur une seule page d'abord
    print("Test sur la première page (10 questions)...\n")
    test_questions = scrape_questions_page(0)
    
    if test_questions:
        print(f"\n✓ Test réussi: {len(test_questions)} questions extraites")
        print("\nExemple de question:")
        print(json.dumps(test_questions[0], ensure_ascii=False, indent=2))
        
        response = input("\nContinuer avec toutes les 1802 questions? (o/n): ")
        if response.lower() == 'o':
            all_questions = scrape_all_questions()
            save_questions(all_questions, "all_questions.json")
            print(f"\n✓ Scraping terminé: {len(all_questions)} questions au total")
        else:
            save_questions(test_questions, "test_questions.json")
    else:
        print("\n✗ Échec du test. Vérifier la structure HTML du site.")
