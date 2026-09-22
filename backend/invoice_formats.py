"""
Rendu des factures en HTML et en image (PNG / JPG).

Le PDF (`invoice_pdf.py`) reste le document de référence remis à la comptable.
Deux autres formes lui sont ajoutées parce qu'un PDF ne s'ouvre pas partout
aussi simplement :

* **HTML** — s'affiche dans n'importe quel navigateur et s'imprime en PDF depuis
  le navigateur. Ne dépend d'aucune bibliothèque : c'est la forme qui marche
  toujours, même si `reportlab` manque sur le serveur.
* **PNG / JPG** — une image, qu'on colle dans une conversation WhatsApp ou un
  e-mail sans que le destinataire ait à télécharger quoi que ce soit.

Les trois formes lisent les mêmes données, par le même modèle de vue
(`invoice_view`) : une facture affiche donc les mêmes montants et les mêmes
mentions, quelle que soit la forme demandée. C'est la seule façon de garantir
qu'un client et sa comptable ne reçoivent pas deux documents divergents pour un
même paiement.
"""
from __future__ import annotations

import html
import io
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ImageUnavailable(Exception):
    """Pillow n'est pas installé sur ce serveur."""


# Polices Unicode, comme pour le PDF : sans elles, pas d'accents corrects.
_FONT_CANDIDATES = (
    os.environ.get("INVOICE_FONT_PATH") or "",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)
_BOLD_CANDIDATES = (
    os.environ.get("INVOICE_FONT_BOLD_PATH") or "",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


# ===== Modèle de vue commun =====
def _money(amount: Optional[float], currency: str) -> str:
    """Montant en écriture française, identique au PDF et au CSV.

    Deux écritures différentes du même montant sur deux documents sèment le
    doute chez la comptable : le formatage est donc volontairement recopié tel
    quel depuis `invoice_pdf`.
    """
    formatted = f"{(amount or 0):,.2f}"
    formatted = formatted.replace(",", " ")  # espace fine pour les milliers
    formatted = formatted.replace(".", ",")       # virgule décimale
    return f"{formatted} {currency}"


def _date(value: Optional[datetime]) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def invoice_view(invoice) -> Dict[str, Any]:
    """Tout ce qu'un rendu a besoin de savoir, déjà mis en forme.

    Les coordonnées de l'entreprise sont lues sur la facture (`issuer_snapshot`),
    jamais sur la configuration courante : réimprimer une facture de l'an dernier
    doit redonner exactement le document remis à l'époque.
    """
    issuer: Dict[str, Any] = invoice.issuer_snapshot or {}
    currency = invoice.currency or "ILS"
    is_credit_note = invoice.document_type == "avoir"

    issuer_lines: List[str] = []
    if issuer.get("legal_id"):
        issuer_lines.append(f"N° d'entreprise : {issuer['legal_id']}")
    if issuer.get("vat_id"):
        issuer_lines.append(f"N° TVA : {issuer['vat_id']}")
    for key in ("address", "city", "country", "email", "phone"):
        if issuer.get(key):
            issuer_lines.append(str(issuer[key]))

    customer_lines: List[str] = []
    if invoice.customer_name:
        customer_lines.append(str(invoice.customer_name))
    if invoice.customer_email:
        customer_lines.append(str(invoice.customer_email))
    if not customer_lines:
        # Un encaissement sans identité connue reste une recette à déclarer : on
        # le dit, plutôt que de laisser un blanc qui ressemble à un oubli.
        customer_lines.append("Client non identifié")

    description_lines = [invoice.plan_name or invoice.plan_id or "Abonnement Flash Neiga"]
    if invoice.service_start and invoice.service_end:
        description_lines.append(
            f"Période : du {_date(invoice.service_start)} au {_date(invoice.service_end)}"
        )
    if is_credit_note and invoice.cancellation_reason:
        description_lines.append(f"Motif : {invoice.cancellation_reason}")

    return {
        "label": "AVOIR" if is_credit_note else "FACTURE",
        "number": invoice.number,
        "is_credit_note": is_credit_note,
        "cancelled": invoice.status == "cancelled",
        "cancellation_reason": invoice.cancellation_reason or "annulée par avoir",
        "issuer_name": issuer.get("name") or "Flash Neiga",
        "issuer_lines": issuer_lines,
        "customer_lines": customer_lines,
        "description_lines": description_lines,
        "issued_at": _date(invoice.issued_at),
        "paid_at": _date(invoice.paid_at) if invoice.paid_at else None,
        "currency": currency,
        "vat_rate": f"{(invoice.vat_rate or 0):.2f}".rstrip("0").rstrip(".") + " %",
        "amount_net": _money(invoice.amount_net, currency),
        "amount_vat": _money(invoice.vat_amount, currency),
        "amount_total": _money(invoice.amount_total, currency),
        "footer": (invoice.issuer_snapshot or {}).get("footer") or "",
    }


# ===== HTML =====
def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def render_invoice_html(invoice) -> str:
    """Facture en HTML autonome : aucune ressource externe, aucun script.

    Tout le style est en ligne, ce qui rend le fichier lisible hors ligne et
    imprimable à l'identique — c'est la forme de secours quand la génération PDF
    n'est pas disponible, et la plus simple à transmettre par e-mail.
    """
    view = invoice_view(invoice)
    accent = "#b91c1c" if view["is_credit_note"] else "#0f172a"

    banner = ""
    if view["cancelled"]:
        banner = (
            '<div style="background:#b91c1c;color:#fff;padding:10px 14px;'
            'border-radius:6px;margin:0 0 20px;font-weight:700">'
            f'FACTURE ANNULÉE — {_esc(view["cancellation_reason"])}</div>'
        )

    def block(lines: List[str]) -> str:
        return "<br>".join(_esc(line) for line in lines)

    doc_lines = [f"Date d'émission : {view['issued_at']}"]
    if view["paid_at"]:
        doc_lines.append(f"Date de paiement : {view['paid_at']}")

    footer = ""
    if view["footer"]:
        footer = (
            '<p style="margin:28px 0 0;font-size:11px;color:#64748b;'
            'border-top:1px solid #e2e8f0;padding-top:12px">'
            f'{_esc(view["footer"])}</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(view['label'])} {_esc(view['number'])}</title>
<style>
  @page {{ size: A4; margin: 16mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:24px; background:#f1f5f9;
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         color:#0f172a; font-size:13px; line-height:1.5; }}
  .sheet {{ max-width:780px; margin:0 auto; background:#fff; padding:40px;
            border-radius:10px; box-shadow:0 1px 3px rgba(15,23,42,.12); }}
  table {{ width:100%; border-collapse:collapse; }}
  .totals td {{ padding:7px 0; }}
  .totals .grand td {{ border-top:2px solid {accent}; font-weight:700; font-size:16px; padding-top:12px; }}
  /* À l'impression, le fond gris et l'ombre ne servent à rien et coûtent de l'encre. */
  @media print {{
    body {{ background:#fff; padding:0; }}
    .sheet {{ box-shadow:none; border-radius:0; padding:0; max-width:none; }}
    .noprint {{ display:none !important; }}
  }}
</style>
</head>
<body>
<div class="sheet">
  <table style="margin-bottom:34px">
    <tr style="vertical-align:top">
      <td style="width:58%">
        <div style="font-weight:700;font-size:15px">{_esc(view['issuer_name'])}</div>
        <div style="color:#475569;font-size:12px;margin-top:4px">{block(view['issuer_lines'])}</div>
      </td>
      <td style="text-align:right;color:#475569;font-size:12px">{block(doc_lines)}</td>
    </tr>
  </table>

  <h1 style="margin:0 0 20px;font-size:26px;letter-spacing:-.4px;color:{accent}">
    {_esc(view['label'])} {_esc(view['number'])}
  </h1>

  {banner}

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin-bottom:26px">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:#64748b;margin-bottom:5px">Client</div>
    <div>{block(view['customer_lines'])}</div>
  </div>

  <table style="margin-bottom:26px">
    <thead>
      <tr style="background:#0f172a;color:#fff;text-align:left">
        <th style="padding:10px 12px;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Prestation</th>
        <th style="padding:10px 12px;font-size:11px;text-transform:uppercase;letter-spacing:.6px;text-align:right;white-space:nowrap">Montant HT</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:14px 12px;border-bottom:1px solid #e2e8f0">{block(view['description_lines'])}</td>
        <td style="padding:14px 12px;border-bottom:1px solid #e2e8f0;text-align:right;white-space:nowrap">{_esc(view['amount_net'])}</td>
      </tr>
    </tbody>
  </table>

  <table style="width:auto;margin-left:auto;min-width:290px" class="totals">
    <tr><td style="color:#475569">Total HT</td>
        <td style="text-align:right;white-space:nowrap">{_esc(view['amount_net'])}</td></tr>
    <tr><td style="color:#475569">TVA ({_esc(view['vat_rate'])})</td>
        <td style="text-align:right;white-space:nowrap">{_esc(view['amount_vat'])}</td></tr>
    <tr class="grand"><td>Total TTC</td>
        <td style="text-align:right;white-space:nowrap">{_esc(view['amount_total'])}</td></tr>
  </table>

  {footer}

  <p class="noprint" style="margin:30px 0 0;font-size:11px;color:#94a3b8">
    Astuce : « Imprimer » puis « Enregistrer au format PDF » produit un PDF depuis cette page.
  </p>
</div>
</body>
</html>"""


# ===== Image (PNG / JPG) =====
# Gabarit A4 à 150 ppp : assez net pour être lu à l'écran comme imprimé, et
# assez léger pour être envoyé par messagerie.
_IMG_WIDTH = 1240
_IMG_HEIGHT = 1754
_MARGIN = 96


def _load_fonts() -> Dict[str, Any]:
    from PIL import ImageFont

    def _pick(candidates, size: int):
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception as exc:  # pragma: no cover - dépend du système
                    logger.warning("Police %s inutilisable (%s)", path, exc)
        # Repli : police bitmap intégrée à Pillow. Le document reste lisible,
        # seulement moins soigné — mieux que pas d'image du tout.
        return ImageFont.load_default()

    return {
        "title": _pick(_BOLD_CANDIDATES, 44),
        "h2": _pick(_BOLD_CANDIDATES, 22),
        "bold": _pick(_BOLD_CANDIDATES, 19),
        "body": _pick(_FONT_CANDIDATES, 19),
        "small": _pick(_FONT_CANDIDATES, 16),
        "total": _pick(_BOLD_CANDIDATES, 28),
    }


def _wrap(draw, text: str, font, max_width: int) -> List[str]:
    """Découpe un texte pour qu'il tienne dans la largeur donnée."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_invoice_image(invoice, fmt: str = "png") -> bytes:
    """Produit la facture sous forme d'image.

    `fmt` : "png" (sans perte, fond transparent impossible ici — le fond est
    blanc) ou "jpeg" (plus léger, à privilégier pour un envoi par messagerie).
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - dépend de l'installation
        raise ImageUnavailable(
            "Pillow n'est pas installé sur le serveur : ajoute `pillow` à "
            "backend/requirements.txt puis redéploie. Les formats PDF et HTML "
            "restent disponibles."
        ) from exc

    normalized = (fmt or "png").lower()
    if normalized in ("jpg", "jpeg"):
        pil_format, mode = "JPEG", "RGB"
    elif normalized == "png":
        pil_format, mode = "PNG", "RGB"
    else:
        raise ValueError(f"Format d'image non pris en charge : {fmt}")

    view = invoice_view(invoice)
    fonts = _load_fonts()
    ink = (15, 23, 42)
    muted = (71, 85, 105)
    accent = (185, 28, 28) if view["is_credit_note"] else (15, 23, 42)
    right_edge = _IMG_WIDTH - _MARGIN
    content_width = right_edge - _MARGIN

    image = Image.new(mode, (_IMG_WIDTH, _IMG_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    def text(xy: Tuple[int, int], value: str, font, fill=ink, anchor: Optional[str] = None) -> None:
        draw.text(xy, value or "", font=font, fill=fill, anchor=anchor)

    y = _MARGIN

    # --- En-tête : émetteur à gauche, dates à droite ---
    text((_MARGIN, y), view["issuer_name"], fonts["h2"])
    header_y = y + 34
    for line in view["issuer_lines"]:
        text((_MARGIN, header_y), line, fonts["small"], muted)
        header_y += 24

    right_y = y
    text((right_edge, right_y), f"Date d'émission : {view['issued_at']}",
         fonts["small"], muted, anchor="ra")
    right_y += 24
    if view["paid_at"]:
        text((right_edge, right_y), f"Date de paiement : {view['paid_at']}",
             fonts["small"], muted, anchor="ra")
        right_y += 24

    y = max(header_y, right_y) + 46

    # --- Titre ---
    text((_MARGIN, y), f"{view['label']} {view['number']}", fonts["title"], accent)
    y += 74

    # --- Bandeau d'annulation : doit se voir au premier coup d'œil ---
    if view["cancelled"]:
        draw.rectangle([_MARGIN, y, right_edge, y + 48], fill=(185, 28, 28))
        label = f"FACTURE ANNULÉE — {view['cancellation_reason']}"
        text((_MARGIN + 16, y + 24), label, fonts["bold"], (255, 255, 255), anchor="lm")
        y += 74

    # --- Client ---
    customer_height = 34 + 28 * len(view["customer_lines"])
    draw.rounded_rectangle([_MARGIN, y, right_edge, y + customer_height],
                           radius=10, fill=(248, 250, 252), outline=(226, 232, 240))
    text((_MARGIN + 18, y + 14), "CLIENT", fonts["small"], muted)
    line_y = y + 42
    for line in view["customer_lines"]:
        text((_MARGIN + 18, line_y), line, fonts["body"])
        line_y += 28
    y += customer_height + 44

    # --- Prestation ---
    draw.rectangle([_MARGIN, y, right_edge, y + 44], fill=(15, 23, 42))
    text((_MARGIN + 16, y + 22), "PRESTATION", fonts["small"], (255, 255, 255), anchor="lm")
    text((right_edge - 16, y + 22), "MONTANT HT", fonts["small"], (255, 255, 255), anchor="rm")
    y += 44

    description_y = y + 18
    amount_column = 260
    for raw_line in view["description_lines"]:
        for wrapped in _wrap(draw, raw_line, fonts["body"], content_width - amount_column - 40):
            text((_MARGIN + 16, description_y), wrapped, fonts["body"])
            description_y += 28
    text((right_edge - 16, y + 18), view["amount_net"], fonts["body"], anchor="ra")
    y = max(description_y, y + 46) + 10
    draw.line([_MARGIN, y, right_edge, y], fill=(226, 232, 240), width=2)
    y += 40

    # --- Totaux, alignés à droite ---
    # Le bloc est large : « Total TTC » en corps 28 et un montant à quatre
    # chiffres ne doivent jamais se toucher.
    label_x = right_edge - 380
    for label, value in (
        ("Total HT", view["amount_net"]),
        (f"TVA ({view['vat_rate']})", view["amount_vat"]),
    ):
        text((label_x, y), label, fonts["body"], muted)
        text((right_edge, y), value, fonts["body"], anchor="ra")
        y += 34

    y += 8
    draw.line([label_x, y, right_edge, y], fill=accent, width=3)
    y += 18
    text((label_x, y), "Total TTC", fonts["total"], accent)
    text((right_edge, y), view["amount_total"], fonts["total"], accent, anchor="ra")
    y += 60

    # --- Mention libre de l'émetteur (RIB, conditions de règlement…) ---
    if view["footer"]:
        y += 20
        draw.line([_MARGIN, y, right_edge, y], fill=(226, 232, 240), width=1)
        y += 18
        for wrapped in _wrap(draw, view["footer"], fonts["small"], content_width):
            text((_MARGIN, y), wrapped, fonts["small"], muted)
            y += 24

    buffer = io.BytesIO()
    save_options: Dict[str, Any] = {"format": pil_format}
    if pil_format == "JPEG":
        save_options.update(quality=92, optimize=True)
    image.save(buffer, **save_options)
    return buffer.getvalue()
