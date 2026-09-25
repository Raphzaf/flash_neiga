/**
 * Accès au stockage du navigateur qui ne plante jamais.
 *
 * Sur iPhone, Safari rend `localStorage` inaccessible dans plusieurs cas
 * courants : navigation privée sur les anciennes versions d'iOS, réglage
 * « Bloquer tous les cookies », certains bloqueurs de contenu. Le simple fait
 * de lire `window.localStorage` lève alors une SecurityError. Chrome sur le
 * même iPhone n'a pas ces réglages, d'où un site qui marchait partout sauf
 * dans Safari : l'accueil restait sur « Chargement… » et chaque appel au
 * serveur échouait (la connexion affichait « mot de passe incorrect »).
 *
 * Quand le stockage est refusé, on garde les valeurs en mémoire : la session
 * tient le temps de l'onglet au lieu de ne pas exister du tout.
 */

const memory = new Map();

const backend = () => {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

// Valeurs que le navigateur a refusé d'enregistrer. Tant qu'une clé y figure,
// c'est elle qui fait foi ; dès qu'une écriture réussit, on s'en remet de
// nouveau au vrai stockage (partagé entre onglets).
export const storage = {
  get(key) {
    if (memory.has(key)) return memory.get(key);
    try {
      return backend()?.getItem(key) ?? null;
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      const store = backend();
      if (!store) throw new Error('stockage indisponible');
      store.setItem(key, value);
      memory.delete(key);
    } catch {
      memory.set(key, value);
    }
  },
  remove(key) {
    memory.delete(key);
    try {
      backend()?.removeItem(key);
    } catch {
      /* rien à nettoyer : la valeur n'existait qu'en mémoire */
    }
  },
};

export default storage;
