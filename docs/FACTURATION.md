# Factures d'abonnement

Comment sortir du site tout ce dont la comptable a besoin, et ce qu'il faut
renseigner avant la première facture.

## 1. Renseigner l'identité de l'entreprise (à faire une fois)

Tant que ces deux variables ne sont pas définies, **aucune facture n'est émise** :
un PDF sans mentions légales n'a aucune valeur comptable, et il vaut mieux un
message clair qu'un document invalide envoyé à la comptable.

```
INVOICE_COMPANY_NAME=...          # raison sociale
INVOICE_COMPANY_LEGAL_ID=...      # numéro d'entreprise (ח.פ / ע.מ)
```

Facultatif, mais tout ce qui est renseigné apparaît en tête de facture :
`INVOICE_COMPANY_ADDRESS`, `INVOICE_COMPANY_CITY`, `INVOICE_COMPANY_COUNTRY`,
`INVOICE_COMPANY_EMAIL`, `INVOICE_COMPANY_PHONE`, `INVOICE_COMPANY_VAT_ID`,
`INVOICE_FOOTER`.

TVA : `INVOICE_VAT_RATE` vaut **18** par défaut (Ma'am israélienne depuis
janvier 2025). Les tarifs de `hyp_plans.json` sont des prix à la consommation,
donc TTC : le montant HT est recalculé à partir du total
(`INVOICE_PRICES_INCLUDE_VAT=true`). Mets `false` si tes tarifs sont hors taxes.

Vérifier ce qu'il reste à remplir :

```
GET /api/admin/invoices/config
```

## 2. Rattraper l'historique (à faire une fois)

Les paiements encaissés avant la mise en place de la facturation n'ont pas de
facture. Une seule requête les rattrape :

```
POST /api/admin/invoices/generate     { }                       → tout l'historique
POST /api/admin/invoices/generate     { "since": "2026-01-01" } → depuis une date
```

Relançable sans risque : un paiement déjà facturé est ignoré. Les accès offerts
par code promo (montant nul) ne sont pas facturés, mais sont comptés à part dans
la réponse pour que le rapprochement ne semble pas incomplet.

## 3. Au quotidien : rien à faire

À chaque paiement encaissé, la facture est émise automatiquement. Si l'émission
échoue (mentions manquantes, base indisponible), **le paiement aboutit quand
même** — l'élève a payé, il a son accès — et la facture se rattrape avec
`/generate`.

Un paiement encaissé sans compte élève est tout de même facturé, avec l'adresse
utilisée pour payer : la recette existe, elle doit être déclarée. Quand l'élève
réclame ensuite son paiement, son nom vient compléter la facture (le numéro et
les montants, eux, ne bougent pas).

## 4. Envoyer la période à la comptable

```
GET /api/admin/invoices/export.zip?month=2026-03
```

Une archive contenant toutes les factures PDF du mois **et** le récapitulatif
CSV. C'est le seul fichier à transmettre.

Séparément si besoin :

| Route | Contenu |
|---|---|
| `GET /api/admin/invoices?month=2026-03` | la liste, en JSON |
| `GET /api/admin/invoices/summary?month=2026-03` | chiffre d'affaires et TVA collectée |
| `GET /api/admin/invoices/export.csv?month=2026-03` | le récapitulatif seul |
| `GET /api/admin/invoices/{id}.pdf` | une facture |

Le CSV est encodé en UTF-8 avec BOM et séparé par des points-virgules, avec la
virgule comme séparateur décimal : il s'ouvre directement dans un Excel
français, sans écran d'import.

Les périodes s'expriment au choix en `month=AAAA-MM` (le plus simple) ou en
`since` / `until` au format `AAAA-MM-JJ`.

## 5. Corriger une erreur

On n'annule pas une facture, on émet un avoir :

```
POST /api/admin/invoices/{id}/cancel   { "reason": "Remboursement demandé" }
```

La facture d'origine reste en base, marquée annulée, et un avoir portant son
propre numéro et des montants négatifs vient la neutraliser. **Rien ne se
supprime** : un trou dans la numérotation invaliderait toute la série lors d'un
contrôle. Le récapitulatif et le CSV additionnent toutes les pièces, donc les
avoirs se déduisent d'eux-mêmes du chiffre d'affaires.

## Ce que le code garantit

- **Numérotation continue** : `INV-2026-0001`, `INV-2026-0002`… sans trou ni
  doublon, même si deux paiements tombent à la même seconde (la contrainte
  d'unicité en base arbitre, l'émission perdante reprend le numéro suivant).
- **Immuabilité** : nom du client, intitulé de la formule, montants, taux de TVA
  et coordonnées de l'entreprise sont recopiés dans la facture à l'émission.
  Réimprimer une facture de l'an dernier redonne exactement le document remis à
  l'époque, même si l'élève a changé de nom entre-temps.
- **Cohérence des montants** : total = HT + TVA au centime, la TVA étant
  calculée par différence. Le récapitulatif et le CSV donnent toujours le même
  total pour une même période.
- **Un paiement = une facture** : les webhooks se répètent, jamais la facture.

## Police des PDF

Par défaut le PDF utilise DejaVu Sans si elle est présente sur le serveur
(accents et hébreu), sinon Helvetica (accents seulement). Pour imposer une
police : `INVOICE_FONT_PATH` et `INVOICE_FONT_BOLD_PATH`.

Le document est rédigé en français. Si tu as besoin d'une facture en hébreu
avec mise en page de droite à gauche, c'est un travail à part : il faut une
bibliothèque de rendu bidirectionnel, ce que reportlab ne fait pas seul.
