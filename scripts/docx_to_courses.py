#!/usr/bin/env python3
"""
Convertit le support de cours Word (.docx) en un seul cours Flash Neiga.

    python scripts/docx_to_courses.py chemin/vers/code_de_la_route.docx

Produit :
  * data/courses_code_de_la_route.json — le cours complet (titre, résumé, HTML),
    chargé en base au démarrage du serveur (voir backend/course_seed.py) ;
  * frontend/public/course-media/*.jpg — les illustrations, redimensionnées et
    servies par le front à l'adresse /course-media/<fichier>.

Le document est publié d'un seul tenant, de A à Z. Il n'utilise pas de styles
de titre : un paragraphe écrit tout en majuscules est traité comme un
intertitre, et CHAPTERS liste ceux qui ouvrent une grande partie — ils
deviennent des titres <h2 id="…"> qui forment le sommaire du lecteur.
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

COURSE_TITLE = "Code de la route"
COURSE_DESCRIPTION = (
    "Le cours complet, de A à Z : documents officiels, signalisation, priorités, "
    "règles de circulation, usagers vulnérables, dépassement, éclairage, conduite "
    "par mauvais temps, éco-conduite, véhicule et prise de conscience des risques."
)

# (intertitre qui ouvre une grande partie, titre affiché dans le cours)
CHAPTERS = [
    ("LE CODE DE LA ROUTE", "Le code de la route et les documents officiels"),
    ("SIGNALISATIONS VERTICALE ET HORIZONTALE", "La signalisation"),
    ("2. LES RÉGIMES DE PRIORITÉ", "Les régimes de priorité"),
    ("RÈGLES DE CIRCULATION", "Les règles de circulation"),
    ("LE CODE DE LA RUE", "Le code de la rue et les usagers vulnérables"),
    ("CROISEMENT ET DÉPASSEMENT", "Croisement et dépassement"),
    ("VISIBILITÉ ET ÉCLAIRAGE", "Visibilité et éclairage"),
    ("RISQUES ET COMPORTEMENTS", "Conduire la nuit et par mauvais temps"),
    ("ÉCO-CONDUITE", "L'éco-conduite"),
    ("LE VÉHICULE ET LA SÉCURITÉ", "Le véhicule et la sécurité"),
    ("PRISE DE CONSCIENCE DES RISQUES", "Prise de conscience des risques"),
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
        self.sizes: dict[str, tuple[int, int]] = {}  # URL publiée → (largeur, hauteur)

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
            self.sizes[self.images[target]] = image.size
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
    def convert(self) -> dict:
        body = ET.fromstring(self.zip.read("word/document.xml")).find(W + "body")
        parts: list[str] = []
        images: list[str] = []
        self.chapters_found: list[str] = []
        in_list = False
        starts = {_norm(heading): title for heading, title in CHAPTERS}

        def close_list():
            nonlocal in_list
            if in_list:
                parts.append("</ul>")
            in_list = False

        for element in body:
            tag = element.tag.replace(W, "")
            if tag == "tbl":
                close_list()
                parts.append(self.table_html(element))
                continue
            if tag != "p":
                continue

            text = self.paragraph_text(element)
            urls = [u for u in (self.image_url(r) for r in self._blips(element)) if u]

            if text in starts:
                close_list()
                self.chapters_found.append(text)
                number = len(self.chapters_found)
                parts.append(f'<h2 id="partie-{number}">{html.escape(starts[text])}</h2>')
                continue

            for url in urls:
                close_list()
                images.append(url)
                width, height = self.sizes[url]
                parts.append(f'<p><img src="{url}" alt="" width="{width}" height="{height}"></p>')

            if not text:
                continue
            is_item = element.find(f"{W}pPr/{W}numPr") is not None
            if _is_heading(text) and not is_item:
                close_list()
                if len(text) > MAX_HEADING_LENGTH:
                    parts.append(f"<p><strong>{html.escape(_heading_text(text))}</strong></p>")
                else:
                    parts.append(f"<h3>{html.escape(_heading_text(text))}</h3>")
                continue
            content = self.runs_html(element)
            if is_item:
                if not in_list:
                    parts.append("<ul>")
                    in_list = True
                parts.append(f"<li>{content}</li>")
            else:
                close_list()
                parts.append(f"<p>{content}</p>")
        close_list()

        return {
            "title": COURSE_TITLE,
            "description": COURSE_DESCRIPTION,
            "content": "\n".join(parts),
            "order": 10,
            "image_url": images[0] if images else None,
            "category": None,
        }

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
    course = converter.convert()
    if len(converter.chapters_found) != len(CHAPTERS):
        print(f"⚠️  {len(converter.chapters_found)} parties trouvées sur {len(CHAPTERS)} attendues", file=sys.stderr)
        return 2
    OUT_JSON.write_text(json.dumps([course], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"1 cours ({len(CHAPTERS)} parties) → {OUT_JSON.relative_to(ROOT)}")
    print(f"{len(converter.images)} images → {OUT_MEDIA.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
