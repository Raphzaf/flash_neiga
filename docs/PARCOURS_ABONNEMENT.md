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

## Ce que l'élève gère lui-même (`/profile`)

| Depuis son compte | Route |
|---|---|
| Prénom / nom / téléphone | `PATCH /api/profile` |
| Mot de passe | `POST /api/profile/password` (ancien mot de passe exigé) |
| Email de connexion | `POST /api/profile/email` (mot de passe exigé, unicité vérifiée) |
| Historique de ses paiements | `GET /api/profile/payments` |
| Résilier son abonnement | `POST /api/profile/subscription/cancel` |
| Changer de formule / renouveler | tunnel `/subscribe` → `/checkout` |

**Résilier veut dire « ne pas renouveler ».** L'abonnement est déjà payé : son
statut passe à `cancelled` mais l'accès reste ouvert jusqu'à la date de fin.
C'est `auth.current_subscription()` qui fait foi partout (paywall, gardes de
routes, profil) : elle accepte les statuts `active` et `cancelled` tant que
`end_date` n'est pas dépassée.

## L'abonnement appartient à l'élève

C'est l'élève qui souscrit, change de formule et renouvelle, depuis son espace.
**Le CRM ne modifie aucun abonnement** : il n'existe plus de route pour en
accorder un, le prolonger ou le résilier. La fiche élève les affiche en lecture
seule.

Le seul geste possible côté équipe est de **rattacher un paiement réellement
encaissé** resté sans compte : onglet **Paiements**, bouton **Rattacher**
(`POST /api/admin/crm/transactions/{id}/attach`). On ne crée pas un droit, on
répare l'affectation d'un paiement déjà effectué par l'élève ; le compte est créé
si besoin, avec un mot de passe provisoire affiché une seule fois. Pour ne lister
que ces paiements : `GET /api/admin/crm/transactions?needs_account=true`.

## « Cet élève n'a aucun abonnement » : par où chercher

Le compte peut exister sans abonnement, et c'est souvent normal — le parcours
crée le compte AVANT le paiement. La fiche élève du CRM donne la réponse, tirée
de ses paiements :

| Ce qu'affiche la fiche | Ce qui s'est passé |
|---|---|
| Aucun paiement engagé | Compte créé, parcours abandonné avant le paiement. Le plus fréquent. |
| Paiement lancé, jamais confirmé (`pending`) | Abandon sur la page bancaire, refus de la banque, **ou** résultat du paiement jamais reçu par notre serveur. |
| Dernier paiement refusé (`failed`) | La banque a refusé ; l'élève peut réessayer depuis son espace. |
| Paiement encaissé sans abonnement | Anomalie : à rattacher depuis l'onglet Paiements. |

Le troisième cas de la deuxième ligne est le seul vraiment technique : si HYP
n'a pas notre URL de retour, un paiement réussi peut rester `pending` chez nous.
Ces URLs se règlent **dans le back-office HYP**, pas dans le code : les variables
`HYP_SUCCESS_URL`, `HYP_ERROR_URL` et `HYP_CALLBACK_URL` existent dans la
configuration mais ne sont envoyées nulle part — elles ne servent à rien
aujourd'hui.

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

`frontend/src/components/funnel/` porte l'ossature et les champs communs au
tunnel (`FunnelShell`, `fields.jsx`). Ils s'appuient sur le système d'interface
déjà utilisé partout ailleurs (`components/ui` : Card, Input, Label, Button,
palette slate, couleur primaire) : le parcours d'abonnement doit ressembler au
reste du produit, pas former un univers à part. Toute nouvelle page du parcours
réutilise ces composants plutôt que de redéfinir ses propres styles.

## Limite connue

Il n'existe pas d'envoi d'email transactionnel dans le projet. Un élève
**connecté** change son mot de passe depuis son compte ; en revanche, un élève
qui l'a **oublié** ne peut pas le réinitialiser seul : la page de connexion
renvoie vers le support, qui réinitialise depuis le CRM (fiche élève →
*Réinitialiser le mot de passe*). Brancher un service d'envoi (SMTP ou API) est
le prérequis pour automatiser cette dernière étape.
