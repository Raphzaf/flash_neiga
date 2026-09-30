#!/usr/bin/env python3
"""
Convertit un support de cours Word (.docx) en cours Flash Neiga.

    python scripts/docx_to_courses.py chemin/vers/code_de_la_route.docx

Produit :
  * data/courses_code_de_la_route.json — les chapitres (titre, résumé, HTML),
    chargés en base au démarrage du serveur (voir backend/course_seed.py) ;
  * frontend/public/course-media/*.jpg — les illustrations, redimensionnées et
    servies par le front à l'adresse /course-media/<fichier>.

Le document n'utilise pas de styles de titre : un paragraphe écrit tout en
majuscules est traité comme un intertitre, et CHAPTERS liste ceux qui ouvrent
un nouveau cours.
"""
from __future__ import annotations

import html
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "data" / "courses_code_de_la_route.json"
OUT_MEDIA = ROOT / "frontend" / "public" / "course-media"
MEDIA_URL = "/course-media"
MEDIA_PREFIX = "cdr-"
MAX_WIDTH = 1200

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

# (intertitre qui ouvre le chapitre, titre du cours, résumé affiché sur la carte)
CHAPTERS = [
    ("LE CODE DE LA ROUTE", "Le code de la route et les documents officiels",
     "Carte grise, permis, assurance, nouveau conducteur : ce que tout conducteur doit savoir et avoir sur lui."),
    ("SIGNALISATIONS VERTICALE ET HORIZONTALE", "La signalisation",
     "Panneaux de danger, d'interdiction, d'obligation, de priorité, feux et marquage au sol."),
    ("2. LES RÉGIMES DE PRIORITÉ", "Les régimes de priorité",
     "Priorité à droite, stop, cédez-le-passage, ronds-points et carrefours à feux."),
    ("RÈGLES DE CIRCULATION", "Les règles de circulation",
     "Avertir, changer de direction, circuler sur autoroute, limitations de vitesse et distances de sécurité."),
    ("LE CODE DE LA RUE", "Le code de la rue et les usagers vulnérables",
     "Zones 30, zones de rencontre, piétons, cyclistes, trottinettes, deux-roues et poids lourds."),
    ("CROISEMENT ET DÉPASSEMENT", "Croisement et dépassement",
     "Croiser sur une chaussée étroite, dépasser en sécurité, et se laisser dépasser."),
    ("VISIBILITÉ ET ÉCLAIRAGE", "Visibilité et éclairage",
     "Quels feux utiliser, quand, et comment ne pas éblouir les autres usagers."),
    ("RISQUES ET COMPORTEMENTS", "Conduire la nuit et par mauvais temps",
     "Nuit, brouillard, pluie, aquaplanage, neige, verglas et vent."),
    ("ÉCO-CONDUITE", "L'éco-conduite",
     "Conduire en consommant moins, en ville, sur route et en montagne."),
    ("LE VÉHICULE ET LA SÉCURITÉ", "Le véhicule et la sécurité",
     "Poste de conduite, tableau de bord, ceintures, airbags, chargement, pneus et freinage."),
    ("PRISE DE CONSCIENCE DES RISQUES", "Prise de conscience des risques",
     "Percevoir, analyser, agir : vitesse, fatigue, vigilance et pression des pairs."),
]


# Noms propres à garder avec leur majuscule dans les intertitres.
PROPER_NOUNS = ("Israël", "Eilat")
# Accents oubliés dans les intertitres tapés en majuscules.
ACCENTS = {
    "differentes": "différentes", "regles": "règles", "depasser": "dépasser",
    "depasser,": "dépasser,", "priorites": "priorités", "meme": "même",
    "trotinettes": "trottinettes", "trotinette": "trottinette",
    "l'eco-conduite": "l'éco-conduite", "securité": "sécurité", "energie": "énergie",
    "medicaments": "médicaments", "nécéssaires": "nécessaires", "qu'est-ce-que": "qu'est-ce que",
}
# Au-delà, un paragraphe en majuscules est une phrase à souligner, pas un titre.
MAX_HEADING_LENGTH = 80


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_heading(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and not any(c.islower() for c in letters)


def _heading_text(text: str) -> str:
    """« . LES PIÉTONS » → « Les piétons » ; garde les sigles courts tels quels."""
    text = _norm(text).lstrip(". ").rstrip(" :.")
    text = re.sub(r"^\d+\.\s*", "", text)
    lowered = text.lower()
    lowered = " ".join(ACCENTS.get(word, word) for word in lowered.split(" "))
    for proper in PROPER_NOUNS:
        lowered = re.sub(rf"\b{proper.lower()}\b", proper, lowered)
    return lowered[:1].upper() + lowered[1:]


class Converter:
    def __init__(self, docx_path: Path):
        self.zip = zipfile.ZipFile(docx_path)
        rels = ET.fromstring(self.zip.read("word/_rels/document.xml.rels"))
        self.rels = {r.get("Id"): r.get("Target") for r in rels}
        self.images: dict[str, str] = {}  # cible du .docx → URL publiée

    # --- Images -----------------------------------------------------------
    def image_url(self, rel_id: str) -> str | None:
        target = self.rels.get(rel_id)
        if not target:
            return None
        if target not in self.images:
            index = len(self.images) + 1
            name = f"{MEDIA_PREFIX}{index:02d}.jpg"
            image = Image.open(io.BytesIO(self.zip.read("word/" + target)))
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            if image.width > MAX_WIDTH:
                image = image.resize(
                    (MAX_WIDTH, round(image.height * MAX_WIDTH / image.width)), Image.LANCZOS
                )
            OUT_MEDIA.mkdir(parents=True, exist_ok=True)
            image.save(OUT_MEDIA / name, "JPEG", quality=82, optimize=True, progressive=True)
            self.images[target] = f"{MEDIA_URL}/{name}"
        return self.images[target]

    def _blips(self, element) -> list[str]:
        """Images d'un élément, sans les doublons de repli (mc:Fallback)."""
        found: list[str] = []

        def walk(node):
            if node.tag == MC + "Fallback":
                return
            if node.tag == A + "blip":
                rel_id = node.get(R + "embed")
                if rel_id and rel_id not in found:
                    found.append(rel_id)
            for child in node:
                walk(child)

        walk(element)
        return found

    # --- Texte ------------------------------------------------------------
    def runs_html(self, paragraph) -> str:
        parts: list[str] = []
        for run in paragraph.iter(W + "r"):
            props = run.find(W + "rPr")
            bold = props is not None and props.find(W + "b") is not None \
                and props.find(W + "b").get(W + "val") not in ("0", "false")
            italic = props is not None and props.find(W + "i") is not None \
                and props.find(W + "i").get(W + "val") not in ("0", "false")
            text = ""
            for child in run:
                if child.tag == W + "t":
                    text += html.escape(child.text or "")
                elif child.tag == W + "tab":
                    text += " "
                elif child.tag == W + "br":
                    text += "<br>"
            if not text:
                continue
            if bold and text.strip():
                text = f"<strong>{text}</strong>"
            if italic and text.strip():
                text = f"<em>{text}</em>"
            parts.append(text)
        joined = "".join(parts)
        joined = joined.replace("</strong><strong>", "").replace("</em><em>", "")
        return re.sub(r"\s+", " ", joined).strip()

    def paragraph_text(self, paragraph) -> str:
        return _norm("".join(t.text or "" for t in paragraph.iter(W + "t")))

    # --- Document ---------------------------------------------------------
    def convert(self) -> list[dict]:
        body = ET.fromstring(self.zip.read("word/document.xml")).find(W + "body")
        chapters: list[dict] = []
        current: dict | None = None
        in_list = False
        starts = {_norm(title): (course_title, summary) for title, course_title, summary in CHAPTERS}

        def close_list():
            nonlocal in_list
            if in_list and current is not None:
                current["html"].append("</ul>")
            in_list = False

        for element in body:
            tag = element.tag.replace(W, "")
            if tag == "tbl":
                close_list()
                if current is not None:
                    current["html"].append(self.table_html(element))
                continue
            if tag != "p":
                continue

            text = self.paragraph_text(element)
            images = [self.image_url(r) for r in self._blips(element)]
            images = [u for u in images if u]

            if text in starts:
                close_list()
                course_title, summary = starts[text]
                current = {"title": course_title, "description": summary, "html": [], "images": []}
                chapters.append(current)
                continue
            if current is None:
                continue

            for url in images:
                close_list()
                current["images"].append(url)
                current["html"].append(f'<p><img src="{url}" alt=""></p>')

            if not text:
                continue
            is_item = element.find(f"{W}pPr/{W}numPr") is not None
            if _is_heading(text) and not is_item:
                close_list()
                if len(text) > MAX_HEADING_LENGTH:
                    current["html"].append(f"<p><strong>{html.escape(_heading_text(text))}</strong></p>")
                else:
                    current["html"].append(f"<h3>{html.escape(_heading_text(text))}</h3>")
                continue
            content = self.runs_html(element)
            if is_item:
                if not in_list:
                    current["html"].append("<ul>")
                    in_list = True
                current["html"].append(f"<li>{content}</li>")
            else:
                close_list()
                current["html"].append(f"<p>{content}</p>")
        close_list()

        courses = []
        for position, chapter in enumerate(chapters, start=1):
            courses.append({
                "title": chapter["title"],
                "description": chapter["description"],
                "content": "\n".join(chapter["html"]),
                "order": position * 10,
                "image_url": chapter["images"][0] if chapter["images"] else None,
                "category": "Code de la route",
            })
        return courses

    def table_html(self, table) -> str:
        rows = []
        for index, row in enumerate(table.iter(W + "tr")):
            cell_tag = "th" if index == 0 else "td"
            cells = []
            for cell in row.iter(W + "tc"):
                content = "<br>".join(
                    filter(None, (self.runs_html(p) for p in cell.iter(W + "p")))
                )
                cells.append(f"<{cell_tag}>{content}</{cell_tag}>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return "<table>" + "".join(rows) + "</table>"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    for old in OUT_MEDIA.glob(f"{MEDIA_PREFIX}*.jpg"):
        old.unlink()
    converter = Converter(Path(sys.argv[1]))
    courses = converter.convert()
    if len(courses) != len(CHAPTERS):
        print(f"⚠️  {len(courses)} chapitres trouvés sur {len(CHAPTERS)} attendus", file=sys.stderr)
        return 2
    OUT_JSON.write_text(json.dumps(courses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(courses)} cours → {OUT_JSON.relative_to(ROOT)}")
    print(f"{len(converter.images)} images → {OUT_MEDIA.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
