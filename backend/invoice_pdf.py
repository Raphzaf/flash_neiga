"""
Rendu des factures : PDF (une pièce par paiement) et CSV (récapitulatif comptable).

Le PDF est le document remis au client et à la comptable ; le CSV est le fichier
qu'elle ouvre dans son tableur pour saisir la période d'un coup.

Le module ne dépend de reportlab qu'au moment de produire un PDF : l'application
démarre même si la bibliothèque n'est pas installée, et l'export CSV — qui, lui,
n'a besoin de rien — continue de fonctionner.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Polices Unicode courantes sur les images Linux. Sans elles, reportlab se
# rabat sur Helvetica, qui ne sait pas dessiner l'hébreu ni le symbole ₪.
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

_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_fonts_ready = False


class PdfUnavailable(Exception):
    """reportlab n'est pas installé sur ce serveur."""


def _ensure_fonts() -> None:
    """Enregistre une police Unicode si l'on en trouve une. Sans effet ensuite."""
    global _FONT_REGULAR, _FONT_BOLD, _fonts_ready
    if _fonts_ready:
        return
    _fonts_ready = True

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def _register(name: str, candidates: Iterable[str]) -> Optional[str]:
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    return name
                except Exception as exc:  # pragma: no cover - dépend du système
                    logger.warning("Police %s inutilisable (%s)", path, exc)
        return None

    regular = _register("InvoiceFont", _FONT_CANDIDATES)
    bold = _register("InvoiceFont-Bold", _BOLD_CANDIDATES)
    if regular:
        _FONT_REGULAR = regular
        _FONT_BOLD = bold or regular
    else:
        logger.info("Aucune police Unicode trouvée : PDF en Helvetica "
                    "(accents corrects, mais pas d'hébreu). Définis INVOICE_FONT_PATH au besoin.")


def _money(amount: Optional[float], currency: str) -> str:
    """Montant en écriture française : espace pour les milliers, virgule décimale.

    Le code ISO plutôt que le symbole (₪) : il est lisible avec n'importe quelle
    police et ne laisse aucun doute sur la devise. La virgule aligne le PDF sur
    l'export CSV — deux écritures différentes du même montant sèment le doute.
    """
    formatted = f"{(amount or 0):,.2f}"          # 1,234.56
    formatted = formatted.replace(",", "\u202f")  # espace fine insécable pour les milliers
    formatted = formatted.replace(".", ",")      # virgule décimale
    return f"{formatted} {currency}"


def _date(value: Optional[datetime]) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def _label(invoice) -> str:
    return "AVOIR" if invoice.document_type == "avoir" else "FACTURE"


def _description(invoice) -> str:
    """Intitulé de la prestation, période de service comprise."""
    lines = [invoice.plan_name or invoice.plan_id or "Abonnement Flash Neiga"]
    if invoice.service_start and invoice.service_end:
        lines.append(f"Période : du {_date(invoice.service_start)} au {_date(invoice.service_end)}")
    if invoice.document_type == "avoir" and invoice.cancellation_reason:
        lines.append(f"Motif : {invoice.cancellation_reason}")
    return "<br/>".join(lines)


def render_invoice_pdf(invoice) -> bytes:
    """Produit le PDF d'une facture ou d'un avoir.

    Tout est lu sur la facture elle-même (y compris les coordonnées de
    l'entreprise, recopiées à l'émission) : réimprimer une facture de l'an
    dernier redonne exactement le document remis à l'époque.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:  # pragma: no cover - dépend de l'installation
        raise PdfUnavailable(
            "reportlab n'est pas installé sur le serveur : "
            "ajoute `reportlab` à backend/requirements.txt puis redéploie."
        ) from exc

    _ensure_fonts()

    issuer: Dict[str, Any] = invoice.issuer_snapshot or {}
    currency = invoice.currency or "ILS"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{_label(invoice)} {invoice.number}",
        author=issuer.get("name") or "Flash Neiga",
    )

    base = ParagraphStyle("base", fontName=_FONT_REGULAR, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=base, fontSize=8, textColor=colors.HexColor("#555555"))
    strong = ParagraphStyle("strong", parent=base, fontName=_FONT_BOLD)
    title = ParagraphStyle("title", parent=base, fontName=_FONT_BOLD, fontSize=20, leading=24)
    heading = ParagraphStyle("heading", parent=base, fontName=_FONT_BOLD, fontSize=10,
                             textColor=colors.HexColor("#334155"), spaceAfter=2)

    story: List[Any] = []

    # --- En-tête : émetteur à gauche, document à droite ---
    issuer_lines = [f"<b>{issuer.get('name') or ''}</b>"]
    if issuer.get("legal_id"):
        issuer_lines.append(f"N° d'entreprise : {issuer['legal_id']}")
    if issuer.get("vat_id"):
        issuer_lines.append(f"N° TVA : {issuer['vat_id']}")
    for key in ("address", "city", "country"):
        if issuer.get(key):
            issuer_lines.append(str(issuer[key]))
    for key in ("email", "phone"):
        if issuer.get(key):
            issuer_lines.append(str(issuer[key]))

    doc_lines = [
        f"Date d'émission : {_date(invoice.issued_at)}",
    ]
    if invoice.paid_at:
        doc_lines.append(f"Date de paiement : {_date(invoice.paid_at)}")

    story.append(Table(
        [[Paragraph("<br/>".join(issuer_lines), base),
          Paragraph("<br/>".join(doc_lines), base)]],
        colWidths=[95 * mm, 75 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]),
    ))
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph(f"{_label(invoice)} {invoice.number}", title))
    story.append(Spacer(1, 5 * mm))

    # Une facture annulée doit se voir au premier coup d'œil.
    if invoice.status == "cancelled":
        story.append(Table(
            [[Paragraph(
                f"<b>FACTURE ANNULÉE</b> — {invoice.cancellation_reason or 'annulée par avoir'}",
                ParagraphStyle("cancel", parent=base, textColor=colors.white))]],
            colWidths=[170 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#b91c1c")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]),
        ))
        story.append(Spacer(1, 5 * mm))

    # --- Client ---
    story.append(Paragraph("Facturé à", heading))
    customer = [invoice.customer_name or "Client"]
    if invoice.customer_email:
        customer.append(invoice.customer_email)
    story.append(Paragraph("<br/>".join(customer), base))
    story.append(Spacer(1, 7 * mm))

    # --- Détail de la prestation ---
    rate_txt = f"{invoice.vat_rate:g} %" if invoice.vat_rate else "—"
    rows = [
        [Paragraph("<b>Désignation</b>", base), Paragraph("<b>Montant HT</b>", base),
         Paragraph("<b>TVA</b>", base), Paragraph("<b>Total TTC</b>", base)],
        [Paragraph(_description(invoice), base),
         Paragraph(_money(invoice.amount_net, currency), base),
         Paragraph(rate_txt, base),
         Paragraph(_money(invoice.amount_total, currency), base)],
    ]
    story.append(Table(
        rows, colWidths=[85 * mm, 30 * mm, 20 * mm, 35 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#cbd5e1")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]),
    ))
    story.append(Spacer(1, 6 * mm))

    # --- Totaux ---
    totals = [
        ["Total HT", _money(invoice.amount_net, currency)],
        [f"TVA {rate_txt}", _money(invoice.vat_amount, currency)],
        ["Total TTC", _money(invoice.amount_total, currency)],
    ]
    story.append(Table(
        totals, colWidths=[130 * mm, 40 * mm], hAlign="RIGHT",
        style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), _FONT_REGULAR),
            ("FONTNAME", (0, 2), (-1, 2), _FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.HexColor("#334155")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]),
    ))
    story.append(Spacer(1, 10 * mm))

    if invoice.document_type != "avoir" and invoice.paid_at:
        story.append(Paragraph(
            f"Payé le {_date(invoice.paid_at)} — cette facture est acquittée.", strong))
        story.append(Spacer(1, 4 * mm))

    if issuer.get("footer"):
        story.append(Paragraph(str(issuer["footer"]), small))

    doc.build(story)
    return buffer.getvalue()


# ===== Export CSV pour la comptable =====
CSV_COLUMNS = [
    ("number", "Numéro"),
    ("document_type", "Type"),
    ("issued_at", "Date d'émission"),
    ("paid_at", "Date de paiement"),
    ("customer_name", "Client"),
    ("customer_email", "E-mail"),
    ("plan_name", "Formule"),
    ("service_start", "Début de période"),
    ("service_end", "Fin de période"),
    ("amount_net", "Montant HT"),
    ("vat_rate", "Taux TVA (%)"),
    ("vat_amount", "TVA"),
    ("amount_total", "Total TTC"),
    ("currency", "Devise"),
    ("status", "Statut"),
]


def render_invoices_csv(invoices: Iterable[Any]) -> bytes:
    """Récapitulatif de période, prêt à ouvrir dans un tableur.

    Encodé en UTF-8 **avec BOM** et séparé par des points-virgules : c'est ce
    qu'attend Excel en configuration française, sans quoi les accents sortent
    illisibles et tout atterrit dans une seule colonne.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([label for _, label in CSV_COLUMNS])

    totals = {"amount_net": 0.0, "vat_amount": 0.0, "amount_total": 0.0}
    currencies = set()

    for invoice in invoices:
        row = []
        for field, _ in CSV_COLUMNS:
            value = getattr(invoice, field, None)
            if isinstance(value, datetime):
                row.append(_date(value))
            elif field in totals:
                amount = float(value or 0)
                totals[field] += amount
                # Virgule décimale : c'est ce qu'attend un tableur français.
                row.append(f"{amount:.2f}".replace(".", ","))
            elif field == "vat_rate":
                row.append(f"{float(value or 0):g}".replace(".", ","))
            else:
                row.append("" if value is None else str(value))
        currencies.add(invoice.currency or "ILS")
        writer.writerow(row)

    # Ligne de total : le premier réflexe de la comptable est de vérifier la somme.
    if totals["amount_total"] or totals["amount_net"]:
        total_row = [""] * len(CSV_COLUMNS)
        index = {field: i for i, (field, _) in enumerate(CSV_COLUMNS)}
        total_row[0] = "TOTAL"
        for field in ("amount_net", "vat_amount", "amount_total"):
            total_row[index[field]] = f"{totals[field]:.2f}".replace(".", ",")
        total_row[index["currency"]] = " / ".join(sorted(currencies)) if currencies else ""
        writer.writerow(total_row)

    return output.getvalue().encode("utf-8-sig")
