import React from 'react';

function Terms() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold mb-4">Conditions Générales d’Utilisation</h1>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
        Dernière mise à jour : 31 décembre 2025
      </p>
      <section className="space-y-4 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
        <p>
          Ces conditions générales d’utilisation (« CGU ») régissent l’accès et l’utilisation
          du service. En accédant au site ou en utilisant nos fonctionnalités, vous acceptez
          ces CGU.
        </p>
        <p>
          Le service est fourni « en l’état ». Nous pouvons modifier le contenu ou les
          fonctionnalités à tout moment pour améliorer l’expérience utilisateur.
        </p>
        <p>
          Vous vous engagez à utiliser le service de manière conforme aux lois applicables
          et à ne pas tenter d’en perturber le fonctionnement.
        </p>
        <p>
          Pour toute question concernant ces CGU, contactez-nous via le support indiqué
          dans l’application.
        </p>
      </section>
    </main>
  );
}

export default Terms;
