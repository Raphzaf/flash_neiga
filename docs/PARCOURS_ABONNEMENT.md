# Parcours d'abonnement : du paiement à l'accès

Ce document décrit comment un élève passe de la page Formules à son entraînement,
et ce qu'il faut faire quand un paiement n'ouvre pas d'accès.

## Règle de base

**Un abonnement n'existe que rattaché à un compte.** Sans compte, un paiement est
encaissé mais aucun accès ne peut être ouvert : l'élève se retrouve devant une
page de connexion pour un compte qu'il n'a jamais créé.

Le compte (donc le mot de passe) est donc demandé **avant** la redirection vers
la banque.

## Le parcours nominal

1. `/pricing` — l'élève choisit sa formule.
2. S'il n'est pas connecté, une fenêtre lui fait créer son compte (prénom, nom,
   email, mot de passe) ou se connecter. Le paiement repart tout seul ensuite.
3. `POST /api/payments/hyp/create-payment` — le compte est obligatoire :
   l'identité vient du token, jamais du corps de la requête. Sans compte, la
   route répond `401` et aucun paiement n'est amorcé.
4. Redirection vers HYP, paiement.
5. Retour sur `/payment/success` : la notification est transmise au backend, qui
   vérifie la signature (APISign VERIFY) et ouvre l'abonnement.
6. L'élève est connecté : il entre directement dans son entraînement.

L'email est enregistré sur chaque transaction (`event_data.user_email`), y
compris sans code promo : c'est la piste qui permet de retrouver un élève.

## Rattrapage 1 — l'élève, depuis la page de confirmation

Si un paiement arrive sans compte rattaché (ancien parcours anonyme, session
perdue en route), `GET /api/payments/hyp/transaction/{id}` renvoie
`needs_account: true` et la page de confirmation affiche un formulaire
« Choisis ton mot de passe » au lieu du bouton d'accès.

`POST /api/payments/hyp/claim` crée le compte, ouvre l'abonnement payé et
connecte l'élève immédiatement. Garde-fous :

- le paiement doit être confirmé (`completed`) ;
- un paiement déjà rattaché ne peut pas être repris (`409`) ;
- si l'email correspond à un compte existant, son mot de passe est exigé
  (`403`) — on ne prend jamais la main sur le compte d'un tiers.

## Rattrapage 2 — l'équipe, depuis le CRM

Onglet **Paiements** du CRM :

- un bandeau signale les paiements encaissés sans compte ;
- le bouton **Rattacher** crée le compte s'il n'existe pas et ouvre l'abonnement
  payé (`POST /api/admin/crm/transactions/{id}/attach`) ;
- si le compte est créé, un **mot de passe provisoire** est affiché une seule
  fois : à communiquer à l'élève, qui pourra le changer ;
- si le compte existe déjà, son mot de passe n'est pas touché.

Pour lister uniquement ces paiements :
`GET /api/admin/crm/transactions?needs_account=true`.

## Connexion : pièges déjà traités

- Les emails sont normalisés (minuscules, sans espaces) à l'inscription et la
  recherche est insensible à la casse : `Sarah@Gmail.com` et `sarah@gmail.com`
  ouvrent le même compte, y compris pour les comptes créés avant cette règle.
- Le mot de passe fait au minimum 6 caractères, contrôlé côté serveur.

## Limite connue

Il n'existe pas d'envoi d'email transactionnel dans le projet : il n'y a donc
pas de « mot de passe oublié » en libre-service. Un élève qui a perdu son mot de
passe doit passer par l'équipe (CRM → fiche élève → *Réinitialiser le mot de
passe*). Brancher un service d'envoi (SMTP ou API) est le prérequis pour
automatiser cette étape.
