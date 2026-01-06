import React from 'react';

function Refund() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold mb-4 text-slate-900 dark:text-white">Politique de remboursement – Flash Neiga</h1>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">Dernière mise à jour : 31 décembre 2025</p>

      <section className="space-y-6 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">1. Champ d’application</h2>
          <p>
            La présente politique de remboursement s’applique à tous les achats d’abonnements et de contenus numériques
            effectués sur la plateforme Flash Neiga (https://appflashneiga.netlify.app/).
          </p>
          <p className="mt-2">Elle concerne notamment :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Les abonnements au code en ligne.</li>
            <li>Les abonnements aux vidéos pédagogiques.</li>
            <li>Les offres combinées (Code + Vidéos + leçons de conduite).</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">2. Nature des services et contenus</h2>
          <p>Flash Neiga propose principalement :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Des contenus numériques accessibles immédiatement (web app, e‑book, questions officielles, vidéos pédagogiques).</li>
            <li>Des services assurés par des intervenants humains (coaching, cours de code, leçons de conduite).</li>
          </ul>
          <p className="mt-2">En raison de la nature numérique des contenus, l’accès est généralement fourni dès la confirmation de paiement.</p>
        </div>

        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">3. Délai et conditions de remboursement</h2>
          <p>Sauf indication contraire dans une offre spécifique, les règles suivantes s’appliquent :</p>
          <p className="mt-2 font-medium">Contenus numériques (code en ligne, e‑book, questions, vidéos)</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Une fois l’accès aux contenus activé, les frais ne sont en principe pas remboursables, notamment si tu as commencé à utiliser la plateforme (connexion, consultation de cours, vidéos, tests).</li>
            <li>En cas de problème technique empêchant l’accès (et non résolu par notre support), nous pourrons étudier un remboursement au cas par cas.</li>
          </ul>
          <p className="mt-3 font-medium">Leçons de conduite / coaching</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Toute leçon programmée et annulée moins de 24 heures avant l’horaire prévu peut être considérée comme due et non remboursable.</li>
            <li>Les leçons offertes dans le cadre d’une formule (par exemple 2 leçons offertes) ne donnent lieu à aucun remboursement en numéraire.</li>
          </ul>
          <p className="mt-3 font-medium">Offres promotionnelles / remises</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Les promotions et réductions appliquées lors de l’achat ne sont pas remboursées séparément.</li>
          </ul>
          <p className="mt-3 text-muted-foreground">
            Tu peux adapter ici : Exemple : droit de rétractation de 14 jours tant que aucun contenu n’a été consulté / aucune leçon réalisée.
          </p>
        </div>

        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">4. Abonnements et résiliation</h2>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Tu peux demander la résiliation de ton abonnement à tout moment.</li>
            <li>La résiliation empêche les futurs prélèvements, mais n’implique pas automatiquement le remboursement des périodes déjà facturées.</li>
            <li>Sauf mention contraire, les montants déjà payés pour une période en cours restent dus et ne sont pas remboursés (tu conserves l’accès jusqu’à la fin de la période).</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">5. Comment demander un remboursement</h2>
          <p>Pour toute demande de remboursement, contacte-nous à : +972 53-708-0667</p>
          <p className="mt-2">En indiquant :</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>Ton nom et ton adresse e‑mail utilisée pour l’inscription.</li>
            <li>La date de l’achat et la formule souscrite.</li>
            <li>Le motif de ta demande (problème technique, erreur de facturation, etc.).</li>
          </ul>
          <p className="mt-2">
            Nous examinerons ta demande et te répondrons dans un délai raisonnable pour confirmer si un remboursement est possible et, le cas échéant, selon quelles modalités (remboursement total, partiel, avoir, prolongation d’abonnement, etc.).
          </p>
        </div>

        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">6. Paiements et rôle de Paddle</h2>
          <p>Les paiements sur Flash Neiga sont traités par notre prestataire Paddle.</p>
          <ul className="list-disc pl-6 mt-2 space-y-1">
            <li>En cas de remboursement accepté, celui‑ci sera effectué par Paddle selon leurs propres délais de traitement bancaires.</li>
            <li>Certains moyens de paiement peuvent avoir des délais supplémentaires ou des restrictions (par exemple selon la banque ou le pays).</li>
          </ul>
        </div>

        <div>
          <h2 className="font-medium mb-1 text-slate-800 dark:text-slate-100">7. Cas de fraude ou d’abus</h2>
          <p>
            Nous nous réservons le droit de refuser un remboursement en cas de fraude avérée ou tentative de fraude, ou d’abus manifeste de la politique de remboursement.
          </p>
        </div>
      </section>
    </main>
  );
}

export default Refund;
