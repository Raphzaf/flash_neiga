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

La mise en forme du Word est reproduite telle quelle : couleurs, tailles (en
proportion du corps de texte, 14 pt = 1em), polices, gras, italique,
soulignement, surlignage, exposants, puces et tirets, retraits, et taille des
illustrations (en proportion de la largeur de la page). Le texte n'est jamais
réécrit : un intertitre en majuscules reste en majuscules ; son libellé
adouci ne sert qu'au sommaire (attribut title).
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


# Corps de texte du document : 14 pt (sz=28) = 1em dans le lecteur.
BASE_HALF_POINTS = 28
THEME_FONTS = {"minor": "Aptos", "major": "Aptos Display"}
# Police par défaut du lecteur (voir .course-book dans index.css) : pas de classe.
BASE_FONT = "Segoe UI Symbol"
FONT_CLASSES = {"Aptos": "ff-aptos", "Aptos Display": "ff-aptos", "Segoe UI Emoji": "ff-emoji"}
HIGHLIGHTS = {
    "yellow": "#FFFF00", "green": "#00FF00", "red": "#FF0000", "black": "#000000",
    "cyan": "#00FFFF", "magenta": "#FF00FF", "blue": "#0000FF", "lightGray": "#D3D3D3",
    "darkGray": "#A9A9A9", "darkYellow": "#808000", "darkGreen": "#008000",
}
# Puces Word (caractère, police) → style de liste CSS.
BULLETS = {"": "disc", "": "square", "o": "circle", "": "circle",
           "-": "'- '", "–": "'– '", "\uf0d8": "'➢ '", "\uf076": "'❖ '", "\uf0fc": "'✓ '"}
NUMBER_FORMATS = {"decimal": "decimal", "lowerLetter": "lower-alpha", "upperLetter": "upper-alpha",
                  "lowerRoman": "lower-roman", "upperRoman": "upper-roman"}
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"


def _on(element) -> bool:
    return element is not None and element.get(W + "val") not in ("0", "false", "none")


def _em(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") + "em"


def parse_rpr(rpr) -> dict:
    """Propriétés de caractère explicitement posées sur un w:rPr."""
    props: dict = {}
    if rpr is None:
        return props
    for flag in ("b", "i", "strike"):
        el = rpr.find(W + flag)
        if el is not None:
            props[flag] = _on(el)
    u = rpr.find(W + "u")
    if u is not None:
        props["u"] = u.get(W + "val") not in (None, "none", "0", "false")
    color = rpr.find(W + "color")
    if color is not None and color.get(W + "val"):
        props["color"] = color.get(W + "val").upper()
    sz = rpr.find(W + "sz")
    if sz is not None and sz.get(W + "val"):
        props["sz"] = int(sz.get(W + "val"))
    fonts = rpr.find(W + "rFonts")
    if fonts is not None:
        name = fonts.get(W + "ascii") or fonts.get(W + "hAnsi")
        theme = fonts.get(W + "asciiTheme") or fonts.get(W + "hAnsiTheme")
        if name:
            props["font"] = name
        elif theme:
            props["font"] = THEME_FONTS["major" if theme.startswith("major") else "minor"]
    hl = rpr.find(W + "highlight")
    if hl is not None and hl.get(W + "val") in HIGHLIGHTS:
        props["highlight"] = HIGHLIGHTS[hl.get(W + "val")]
    va = rpr.find(W + "vertAlign")
    if va is not None:
        props["vert"] = va.get(W + "val")
    return props


class Converter:
    def __init__(self, docx_path: Path):
        self.zip = zipfile.ZipFile(docx_path)
        rels = ET.fromstring(self.zip.read("word/_rels/document.xml.rels"))
        self.rels = {r.get("Id"): r.get("Target") for r in rels}
        self.images: dict[str, str] = {}  # cible du .docx → URL publiée
        self.sizes: dict[str, tuple[int, int]] = {}  # URL publiée → (largeur, hauteur)
        self._load_styles()
        self._load_numbering()
        body = ET.fromstring(self.zip.read("word/document.xml")).find(W + "body")
        sect = body.find(W + "sectPr")
        page, margins = sect.find(W + "pgSz"), sect.find(W + "pgMar")
        text_twips = int(page.get(W + "w")) - int(margins.get(W + "left")) - int(margins.get(W + "right"))
        self.text_width_emu = text_twips * 635
        self.list_counters: dict[str, int] = {}

    # --- Styles et numérotation ---------------------------------------------
    def _load_styles(self):
        root = ET.fromstring(self.zip.read("word/styles.xml"))
        self.default_rpr = parse_rpr(root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr"))
        self.default_rpr.setdefault("sz", 22)
        self.default_rpr.setdefault("font", THEME_FONTS["minor"])
        self.styles: dict[str, tuple[str | None, dict, int | None]] = {}
        for style in root.findall(W + "style"):
            based = style.find(W + "basedOn")
            ind = style.find(f"{W}pPr/{W}ind")
            self.styles[style.get(W + "styleId")] = (
                based.get(W + "val") if based is not None else None,
                parse_rpr(style.find(W + "rPr")),
                int(ind.get(W + "left")) if ind is not None and ind.get(W + "left") else None,
            )

    def _style_chain(self, style_id):
        chain = []
        while style_id and style_id in self.styles and len(chain) < 10:
            chain.append(self.styles[style_id])
            style_id = self.styles[style_id][0]
        return list(reversed(chain))

    def style_rpr(self, style_id) -> dict:
        props = dict(self.default_rpr)
        for _, rpr, _ in self._style_chain(style_id):
            props.update(rpr)
        return props

    def style_indent(self, style_id) -> int:
        left = 0
        for _, _, ind in self._style_chain(style_id):
            if ind is not None:
                left = ind
        return left

    def _load_numbering(self):
        self.numbering: dict[str, dict] = {}
        if "word/numbering.xml" not in self.zip.namelist():
            return
        root = ET.fromstring(self.zip.read("word/numbering.xml"))
        abstract = {}
        for absn in root.findall(W + "abstractNum"):
            levels = {}
            for lvl in absn.findall(W + "lvl"):
                fmt = lvl.find(W + "numFmt")
                text = lvl.find(W + "lvlText")
                ind = lvl.find(f"{W}pPr/{W}ind")
                start = lvl.find(W + "start")
                levels[lvl.get(W + "ilvl")] = {
                    "fmt": fmt.get(W + "val") if fmt is not None else "bullet",
                    "text": text.get(W + "val") if text is not None else "",
                    "left": int(ind.get(W + "left")) if ind is not None and ind.get(W + "left") else 720,
                    "start": int(start.get(W + "val")) if start is not None else 1,
                    "color": parse_rpr(lvl.find(W + "rPr")).get("color"),
                }
            abstract[absn.get(W + "abstractNumId")] = levels
        for num in root.findall(W + "num"):
            ref = num.find(W + "abstractNumId")
            if ref is not None:
                self.numbering[num.get(W + "numId")] = abstract.get(ref.get(W + "val"), {})

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

    # --- Illustrations ---------------------------------------------------
    def drawing_html(self, drawing) -> tuple[str, bool]:
        """(balise <img>, flottante ?) pour un w:drawing, ou ('', False)."""
        blip = next(drawing.iter(A + "blip"), None)
        url = self.image_url(blip.get(R + "embed")) if blip is not None else None
        if not url:
            return "", False
        frame = drawing[0] if len(drawing) else None
        extent = frame.find(WP + "extent") if frame is not None else None
        style = []
        floating = False
        if extent is not None:
            share = min(100.0, int(extent.get("cx")) * 100 / self.text_width_emu)
            style.append(f"width:{share:.1f}%")
            if frame.tag == WP + "anchor" and share <= 60 and (
                frame.find(WP + "wrapSquare") is not None or frame.find(WP + "wrapTight") is not None
            ):
                pos = frame.find(WP + "positionH")
                align = pos.findtext(WP + "align") if pos is not None else None
                offset = pos.findtext(WP + "posOffset") if pos is not None else None
                right = align == "right" or (offset is not None and int(offset) > self.text_width_emu / 2)
                style.append("float:right" if right else "float:left")
                floating = True
        width, height = self.sizes[url]
        return (f'<img src="{url}" alt="" width="{width}" height="{height}" '
                f'style="{";".join(style)}">'), floating

    # --- Texte ------------------------------------------------------------
    def _content(self, paragraph):
        """Runs et dessins du paragraphe dans l'ordre (sans les replis mc:Fallback)."""
        def walk(node):
            for child in node:
                if child.tag == MC + "Fallback":
                    continue
                if child.tag == W + "r":
                    yield child
                elif child.tag in (W + "pPr",):
                    continue
                else:
                    yield from walk(child)
        yield from walk(paragraph)

    def run_css(self, props: dict, inherited_color: str = "000000") -> tuple[str, str]:
        """(attribut class, attribut style) d'un morceau de texte."""
        styles = []
        color = props.get("color", "AUTO")
        color = "000000" if color == "AUTO" else color
        if color != inherited_color:
            styles.append(f"color:#{color}")
        size = props.get("sz", BASE_HALF_POINTS)
        if size != BASE_HALF_POINTS:
            styles.append(f"font-size:{_em(size / BASE_HALF_POINTS)}")
        if props.get("highlight"):
            styles.append(f"background-color:{props['highlight']}")
        font_class = FONT_CLASSES.get(props.get("font", BASE_FONT), "")
        return font_class, ";".join(styles)

    def runs_html(self, paragraph, inherited_color: str = "000000") -> tuple[str, list[str]]:
        """HTML fidèle du paragraphe, et les illustrations flottantes à placer avant lui."""
        ppr = paragraph.find(W + "pPr")
        style_el = ppr.find(W + "pStyle") if ppr is not None else None
        base = self.style_rpr(style_el.get(W + "val") if style_el is not None else "Normal")
        pieces: list[tuple[tuple, str]] = []  # (clé de mise en forme, html)
        floats: list[str] = []
        for run in self._content(paragraph):
            props = dict(base)
            props.update(parse_rpr(run.find(W + "rPr")))
            for child in run:
                if child.tag == W + "t":
                    text = html.escape(child.text or "", quote=False)
                elif child.tag == W + "tab":
                    text = " "
                elif child.tag == W + "br" and child.get(W + "type") in (None, "textWrapping"):
                    text = "<br>"
                elif child.tag == W + "drawing":
                    img, floating = self.drawing_html(child)
                    if floating:
                        floats.append(img)
                    elif img:
                        pieces.append((("img",), img))
                    continue
                elif child.tag == MC + "AlternateContent":
                    choice = child.find(MC + "Choice")
                    for drawing in (choice.iter(W + "drawing") if choice is not None else ()):
                        img, floating = self.drawing_html(drawing)
                        (floats.append(img) if floating else pieces.append((("img",), img))) if img else None
                    continue
                else:
                    continue
                key = (props.get("b", False), props.get("i", False), props.get("u", False),
                       props.get("strike", False), props.get("vert"),
                       self.run_css(props, inherited_color))
                pieces.append((key, text))

        # Fusionne les morceaux voisins de même mise en forme, puis les habille.
        merged: list[list] = []
        for key, text in pieces:
            if merged and merged[-1][0] == key and key != ("img",):
                merged[-1][1] += text
            else:
                merged.append([key, text])
        out = []
        for key, text in merged:
            if key == ("img",):
                out.append(text)
                continue
            bold, italic, underline, strike, vert, (font_class, css) = key
            if not text.strip(" <br>"):
                out.append(text)
                continue
            if bold:
                text = f"<strong>{text}</strong>"
            if italic:
                text = f"<em>{text}</em>"
            if underline:
                text = f"<u>{text}</u>"
            if strike:
                text = f"<s>{text}</s>"
            if vert == "superscript":
                text = f"<sup>{text}</sup>"
            elif vert == "subscript":
                text = f"<sub>{text}</sub>"
            if font_class or css:
                attrs = (f' class="{font_class}"' if font_class else "") + (f' style="{css}"' if css else "")
                text = f"<span{attrs}>{text}</span>"
            out.append(text)
        joined = re.sub(r"[ \t\r\n]+", " ", "".join(out)).strip()
        return joined, floats

    def paragraph_text(self, paragraph) -> str:
        return _norm("".join(t.text or "" for r in self._content(paragraph) for t in r.iter(W + "t")))

    def indent(self, paragraph) -> int:
        ppr = paragraph.find(W + "pPr")
        if ppr is None:
            return 0
        ind = ppr.find(W + "ind")
        if ind is not None and ind.get(W + "left"):
            return int(ind.get(W + "left"))
        style_el = ppr.find(W + "pStyle")
        return self.style_indent(style_el.get(W + "val")) if style_el is not None else 0

    # --- Document ---------------------------------------------------------
    def convert(self) -> dict:
        body = ET.fromstring(self.zip.read("word/document.xml")).find(W + "body")
        parts: list[str] = []
        self.chapters_found: list[str] = []
        open_list: tuple | None = None  # (numId, niveau, balise)
        starts = {_norm(heading): title for heading, title in CHAPTERS}

        def close_list():
            nonlocal open_list
            if open_list:
                parts.append(f"</{open_list[2]}>")
            open_list = None

        for element in body:
            tag = element.tag.replace(W, "")
            if tag == "tbl":
                close_list()
                parts.append(self.table_html(element))
                continue
            if tag != "p":
                continue

            text = self.paragraph_text(element)
            num = element.find(f"{W}pPr/{W}numPr")
            num_id = num.find(W + "numId").get(W + "val") if num is not None and num.find(W + "numId") is not None else None
            level_id = num.find(W + "ilvl").get(W + "val") if num is not None and num.find(W + "ilvl") is not None else "0"
            level = self.numbering.get(num_id, {}).get(level_id) if num_id and num_id != "0" else None

            if text in starts or (_is_heading(text) and not level and len(text) <= MAX_HEADING_LENGTH):
                close_list()
                content, floats = self.runs_html(element)
                if text in starts:
                    self.chapters_found.append(text)
                    number = len(self.chapters_found)
                    title = html.escape(starts[text])
                    parts.append(f'<h2 id="partie-{number}" title="{title}">{content}</h2>')
                else:
                    title = html.escape(_heading_text(text))
                    parts.append(f'<h3 title="{title}">{content}</h3>')
                parts.extend(f"<p>{img}</p>" for img in floats)
                continue

            if level:
                marker_color = (parse_rpr(element.find(f"{W}pPr/{W}rPr")).get("color")
                                or level.get("color") or "000000")
                content, floats = self.runs_html(element, inherited_color=marker_color)
                if not content and not floats:
                    continue
                ordered = level["fmt"] in NUMBER_FORMATS
                list_tag = "ol" if ordered else "ul"
                if open_list != (num_id, level_id, list_tag):
                    close_list()
                    left = self.indent(element) or level["left"]
                    if ordered:
                        list_style = NUMBER_FORMATS[level["fmt"]]
                    else:
                        list_style = BULLETS.get(level["text"], f"'{level['text']} '" if level["text"] else "disc")
                    css = f"list-style-type:{list_style};padding-left:{_em(left / 20 / 14)}"
                    start = ""
                    if ordered:
                        counter_key = f"{num_id}:{level_id}"
                        first = self.list_counters.get(counter_key, level["start"])
                        start = f' start="{first}"' if first != 1 else ""
                    parts.append(f'<{list_tag}{start} style="{css}">')
                    open_list = (num_id, level_id, list_tag)
                if level["fmt"] in NUMBER_FORMATS:
                    key = f"{num_id}:{level_id}"
                    self.list_counters[key] = self.list_counters.get(key, level["start"]) + 1
                color = f' style="color:#{marker_color}"' if marker_color != "000000" else ""
                parts.extend(f"<p>{img}</p>" for img in floats)
                parts.append(f"<li{color}>{content}</li>")
                continue

            content, floats = self.runs_html(element)
            if not content and not floats:
                continue
            # Un paragraphe en retrait poursuit la liste qui le précède.
            left = self.indent(element)
            if not (open_list and left):
                close_list()
            for img in floats:
                parts.append(f"<p>{img}</p>")
            if content:
                css = f' style="padding-left:{_em(left / 20 / 14)}"' if left and not open_list else ""
                if open_list:
                    parts.append(f'<li class="suite">{content}</li>')
                else:
                    parts.append(f"<p{css}>{content}</p>")
        close_list()

        first_image = re.search(r'<img src="([^"]+)"', "".join(parts))
        return {
            "title": COURSE_TITLE,
            "description": COURSE_DESCRIPTION,
            "content": "\n".join(parts),
            "order": 10,
            "image_url": first_image.group(1) if first_image else None,
            "category": None,
        }

    def table_html(self, table) -> str:
        rows = []
        for index, row in enumerate(table.iter(W + "tr")):
            cell_tag = "th" if index == 0 else "td"
            cells = []
            for cell in row.iter(W + "tc"):
                content = "<br>".join(
                    filter(None, (self.runs_html(p)[0] for p in cell.iter(W + "p")))
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
