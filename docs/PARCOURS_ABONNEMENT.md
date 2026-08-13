# Parcours d'abonnement : de la connexion à la plateforme

Ce document décrit le tunnel complet — création de compte, choix de la formule,
paiement, connexion — et ce qu'il faut faire quand un paiement n'ouvre pas
d'accès.

## Le parcours

```
/login ──« Je n'ai pas encore de compte »──► /register
                                                │ compte créé (session ouverte)
                                                ▼
                                           /subscribe   (choix de la formule)
                                                │ formule retenue
                                                ▼
                                           /checkout    (récapitulatif + paiement)
                                                │ redirection HYP
                                                ▼
                                      page bancaire sécurisée
                                                │ retour
                                                ▼
                                       /payment/success  (abonnement ouvert)
                                                │
                                                ▼
                                          l'application
```

La page publique `/pricing` (argumentaire commercial) alimente le même tunnel :
son bouton emmène vers `/register?plan=…` (visiteur) ou `/checkout?plan=…`
(élève déjà connecté).

## Règles qui tiennent le parcours

**Un abonnement n'existe que rattaché à un compte.** Le compte — donc le mot de
passe — est créé avant la redirection vers la banque. `create-payment` refuse un
paiement sans compte (`401`) et retient l'identité du jeton, jamais celle
envoyée par le navigateur.

**La base est la seule source de vérité.** `GET /api/subscriptions/me` dit si
l'élève a accès ; c'est ce que consultent la redirection après connexion et les
gardes de routes. La formule facturée est celle enregistrée sur la transaction,
et les prix affichés viennent du catalogue serveur (`hyp_plans.json`, exposé par
`GET /api/payments/hyp/plans?visible_only=true`).

**Le choix de formule survit à tout.** Il est porté par l'URL (`?plan=`) et
mémorisé localement : rechargement, retour arrière, échec de paiement ou
reconnexion le retrouvent. Cette mémoire est un confort — elle ne décide jamais
de ce qui est facturé.

**Aucune route morte.** Les anciennes URLs (`/pricing/success`,
`/subscription-success`, `/pricing/cancel`) redirigent vers le parcours unique,
et toute adresse inconnue revient à l'accueil.

## Ce que voit l'élève selon son état

| État | Destination |
|---|---|
| Non connecté | `/login` (avec la raison affichée : session expirée, abonnement requis, paiement validé) |
| Connecté, sans abonnement | `/subscribe` |
| Connecté, abonnement actif | l'application |
| Administrateur | l'application (non soumis au paywall) |

## Rattrapage 1 — l'élève, depuis la page de confirmation

Si un paiement arrive sans compte rattaché (ancien parcours anonyme, session
perdue en route), `GET /api/payments/hyp/transaction/{id}` renvoie
`needs_account: true` et la page de confirmation propose de choisir un mot de
passe. `POST /api/payments/hyp/claim` crée le compte, ouvre l'abonnement payé et
connecte l'élève. Garde-fous :

- le paiement doit être confirmé (`completed`) ;
- un paiement déjà rattaché ne peut pas être repris (`409`) ;
- si l'email correspond à un compte existant, son mot de passe est exigé
  (`403`) — on ne prend jamais la main sur le compte d'un tiers.

## Rattrapage 2 — l'équipe, depuis le CRM

Onglet **Paiements** : un bandeau signale les paiements encaissés sans compte,
et le bouton **Rattacher** crée le compte au besoin puis ouvre l'abonnement
(`POST /api/admin/crm/transactions/{id}/attach`). Un mot de passe provisoire est
affiché une seule fois, à transmettre à l'élève. Pour ne lister que ces
paiements : `GET /api/admin/crm/transactions?needs_account=true`.

## Si le paiement se passe mal

- **Refusé / annulé** : `/payment/failure` explique, ne débite rien, et propose
  de réessayer sur la même formule.
- **Élève parti avant le retour** : la notification serveur à serveur de HYP
  ouvre l'abonnement ; à sa visite suivante, l'accès est là sans rien faire.
- **Retour sans notification serveur** : la page de confirmation transmet
  elle-même le résultat au backend, qui en vérifie la signature, puis sonde la
  transaction jusqu'à confirmation.
- **Notification rejouée** : la transaction déjà traitée est ignorée — jamais
  deux abonnements pour un paiement.

## Design

`frontend/src/components/funnel/` porte le décor et les champs communs à tout le
tunnel (`FunnelShell`, `fields.jsx`). Toute nouvelle page du parcours doit les
réutiliser plutôt que redéfinir ses propres styles : c'est ce qui garantit la
continuité visuelle entre connexion, inscription, formules et paiement.

## Limite connue

Il n'existe pas d'envoi d'email transactionnel dans le projet : pas de « mot de
passe oublié » en libre-service. La page de connexion renvoie vers le support,
qui réinitialise depuis le CRM (fiche élève → *Réinitialiser le mot de passe*).
Brancher un service d'envoi (SMTP ou API) est le prérequis pour automatiser
cette étape.
