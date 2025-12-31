import React from 'react';

function Privacy() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold mb-4">Politique de confidentialité – Flash Neiga</h1>
      <p className="text-sm text-muted-foreground mb-6">Dernière mise à jour : 31 décembre 2025</p>

      <section className="space-y-6 text-sm leading-relaxed">
        <div>
          <h2 className="font-medium mb-1">1. Qui sommes-nous ?</h2>
          <p>
            Flash Neiga est une plateforme en ligne d’apprentissage du code de la route et de la conduite,
            proposant des contenus numériques (web app, e‑book, vidéos pédagogiques) et des services de coaching
            assurés par des intervenants humains.
          </p>
          <p className="mt-2">Si tu as des questions, tu peux nous contacter à : +972 53-708-0667</p>
        </div>

        <div>
          <h2 className="font-medium mb-1">2. Données que nous collectons</h2>
          <p>Nous pouvons collecter les données suivantes :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Informations de compte : nom, prénom, adresse e‑mail, numéro de téléphone.</li>
            <li>Données de connexion : identifiants, mot de passe (stocké de façon chiffrée).</li>
            <li>Données d’utilisation : pages consultées, progression dans les cours, résultats aux tests.</li>
            <li>Données de paiement : certaines informations de facturation (via notre prestataire de paiement Paddle).</li>
            <li>Échanges avec nous : e‑mails, messages de support.</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1">3. Comment nous collectons ces données</h2>
          <p>Les données sont collectées :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Lorsque tu crées un compte ou mets ton profil à jour.</li>
            <li>Lorsque tu t’abonnes, effectues un paiement ou utilises nos contenus.</li>
            <li>Lorsque tu nous contactes (e‑mail, formulaire, support).</li>
            <li>Via des cookies et outils de mesure d’audience (voir section Cookies).</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1">4. Pourquoi nous utilisons tes données ?</h2>
          <p>Nous utilisons tes données pour :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Créer et gérer ton compte utilisateur.</li>
            <li>Fournir l’accès à la web app, aux contenus pédagogiques et au suivi de progression.</li>
            <li>Gérer les abonnements, paiements et factures (via Paddle, notre partenaire de paiement).</li>
            <li>Assurer le support client et répondre à tes demandes.</li>
            <li>Améliorer notre plateforme (statistiques anonymisées).</li>
            <li>Respecter nos obligations légales et comptables.</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1">5. Base légale (RGPD)</h2>
          <p>Selon le RGPD, nous traitons tes données sur les bases légales suivantes :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Exécution du contrat : fournir la plateforme et les abonnements souscrits.</li>
            <li>Intérêt légitime : sécuriser le service, prévenir la fraude, améliorer nos contenus.</li>
            <li>Obligation légale : conservation de certaines données de facturation.</li>
            <li>Consentement : pour certains cookies ou communications marketing, lorsque requis.</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1">6. Avec qui nous partageons les données</h2>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Paddle, notre prestataire de paiement, pour traiter les paiements et la facturation.</li>
            <li>Outils d’hébergement, d’envoi d’e‑mails et de statistiques (hébergeur, e‑mailing, analytics).</li>
            <li>Nos coachs / instructeurs, uniquement les informations nécessaires au suivi pédagogique.</li>
          </ul>
          <p className="mt-2">Nous ne vendons pas tes données personnelles.</p>
        </div>

        <div>
          <h2 className="font-medium mb-1">7. Durée de conservation</h2>
          <p>Nous conservons tes données :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Tant que ton compte est actif.</li>
            <li>Puis pendant une durée limitée nécessaire au respect de nos obligations légales (ex. factures).</li>
          </ul>
          <p className="mt-2">Au‑delà, les données sont supprimées ou anonymisées.</p>
        </div>

        <div>
          <h2 className="font-medium mb-1">8. Tes droits</h2>
          <p>Conformément à la réglementation applicable (notamment RGPD), tu disposes de :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Droit d’accès : obtenir une copie de tes données.</li>
            <li>Droit de rectification : corriger des données inexactes.</li>
            <li>Droit d’effacement (droit à l’oubli) : supprimer certaines données, sous conditions.</li>
            <li>Droit d’opposition / limitation : limiter certains traitements.</li>
            <li>Droit à la portabilité : recevoir certaines données dans un format structuré.</li>
          </ul>
          <p className="mt-2">Pour exercer tes droits, écris-nous à : [ton email de contact].</p>
        </div>

        <div>
          <h2 className="font-medium mb-1">9. Cookies et traceurs</h2>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Assurer le bon fonctionnement du site (authentification, session).</li>
            <li>Mesurer l’audience et améliorer l’expérience utilisateur.</li>
          </ul>
          <p className="mt-2">
            Tu peux configurer ton navigateur pour refuser tout ou partie des cookies, mais certaines fonctionnalités
            risquent de ne plus fonctionner correctement.
          </p>
        </div>

        <div>
          <h2 className="font-medium mb-1">10. Sécurité</h2>
          <p>
            Nous mettons en œuvre des mesures techniques et organisationnelles raisonnables pour protéger tes données
            (chiffrement des mots de passe, accès restreint aux données, etc.).
          </p>
        </div>

        <div>
          <h2 className="font-medium mb-1">11. Transferts hors UE</h2>
          <p>
            Certains de nos prestataires (comme les services de paiement ou d’hébergement) peuvent être situés en dehors
            de l’EEE. Dans ce cas, nous veillons à ce que des garanties appropriées soient en place
            (clauses contractuelles types, équivalence de protection, etc.).
          </p>
        </div>

        <div>
          <h2 className="font-medium mb-1">12. Mise à jour de cette politique</h2>
          <p>
            Nous pouvons modifier cette Politique de confidentialité de temps à autre. En cas de changement important,
            nous t’en informerons par e‑mail ou via la plateforme. La version la plus récente sera toujours disponible
            sur cette page.
          </p>
        </div>
      </section>
    </main>
  );
}

export default Privacy;
