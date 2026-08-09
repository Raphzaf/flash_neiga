/**
 * Client Kimi (Moonshot AI) — Flash Neiga
 * =======================================
 *
 * ⚠️  CE MODULE EST STRICTEMENT CÔTÉ SERVEUR.
 * Il lit `process.env.MOONSHOT_API_KEY` : ne l'importe JAMAIS depuis
 * `frontend/src/**` (bundle React envoyé au navigateur), sous peine d'exposer
 * la clé à tous les visiteurs. Il est prévu pour un runtime Node : script
 * d'administration, tâche de génération de contenu, route serveur.
 *
 * Le coach IA de la plateforme, lui, tourne dans le backend Python sur Render :
 * voir `backend/ai_client.py` (AI_PROVIDER=moonshot), qui applique exactement
 * les mêmes règles (max_retries=0, max_completion_tokens, gestion des 429).
 *
 * Installation : npm install openai
 *
 * Variables d'environnement :
 *   MOONSHOT_API_KEY   clé secrète (obligatoire)  — jamais commitée
 *   MOONSHOT_BASE_URL  https://api.moonshot.ai/v1 (défaut)
 *   MOONSHOT_MODEL     kimi-k3                    (défaut)
 *
 * Modèles disponibles :
 *   - kimi-k3        : flagship, 1M de contexte, raisonnement toujours actif, cher
 *   - kimi-k2.7-code : orienté code, 262k de contexte, rapide
 *   - kimi-k2.6      : généraliste multimodal, 262k de contexte
 *   - kimi-k2.5      : économique, 262k de contexte
 */
import OpenAI from 'openai';

export const KIMI_MODELS = {
  /** Flagship : 1M de contexte, raisonnement toujours actif, le plus cher. */
  FLAGSHIP: 'kimi-k3',
  /** Code : 262k de contexte, rapide. */
  CODE: 'kimi-k2.7-code',
  /** Généraliste multimodal : 262k de contexte. */
  MULTIMODAL: 'kimi-k2.6',
  /** Économique : 262k de contexte. */
  CHEAP: 'kimi-k2.5',
} as const;

export type KimiModel = (typeof KIMI_MODELS)[keyof typeof KIMI_MODELS] | (string & {});

/** Valeur volontairement modeste : Moonshot réserve le quota à l'avance
 *  (tokens d'entrée + max_completion_tokens). Trop haut ⇒ 429 immédiat. */
const DEFAULT_MAX_COMPLETION_TOKENS = 4096;

export class KimiError extends Error {
  readonly status?: number;
  readonly isRateLimit: boolean;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'KimiError';
    this.status = status;
    this.isRateLimit = status === 429;
  }
}

let client: OpenAI | null = null;

/** Client OpenAI pointé vers Moonshot (créé une seule fois). */
export function getKimiClient(): OpenAI {
  if (client) return client;

  const apiKey = process.env.MOONSHOT_API_KEY;
  if (!apiKey) {
    throw new KimiError(
      "MOONSHOT_API_KEY absente. Renseigne-la dans .env.local en local, et dans les variables d'environnement Render en production.",
    );
  }

  client = new OpenAI({
    apiKey,
    baseURL: process.env.MOONSHOT_BASE_URL || 'https://api.moonshot.ai/v1',
    // CRITIQUE : Moonshot gère mal les relances automatiques du SDK — elles
    // amplifient les 429 (chaque tentative reréserve le quota) au lieu de les absorber.
    maxRetries: 0,
    timeout: 120_000,
  });
  return client;
}

export interface AskKimiOptions {
  /** Modèle à utiliser (défaut : MOONSHOT_MODEL, sinon kimi-k3). */
  model?: KimiModel;
  /** Consigne système (rôle, ton, format attendu). */
  system?: string;
  /** Plafond de tokens générés (défaut : 4096). Attention au quota réservé à l'avance. */
  maxCompletionTokens?: number;
  /** 0 = déterministe, 1 = créatif. */
  temperature?: number;
  /** Force une réponse JSON valide. */
  json?: boolean;
  /** Historique de conversation, à la place d'un simple prompt. */
  messages?: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>;
  /** Signal d'annulation. */
  signal?: AbortSignal;
}

export interface KimiUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface KimiResult {
  text: string;
  model: string;
  usage: KimiUsage | null;
}

/**
 * Interroge Kimi et renvoie la réponse texte.
 *
 * @throws {KimiError} avec `isRateLimit = true` en cas de 429.
 */
export async function askKimi(prompt: string, options: AskKimiOptions = {}): Promise<KimiResult> {
  const {
    model = process.env.MOONSHOT_MODEL || KIMI_MODELS.FLAGSHIP,
    system,
    maxCompletionTokens = DEFAULT_MAX_COMPLETION_TOKENS,
    temperature,
    json = false,
    messages,
    signal,
  } = options;

  const conversation: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = [];
  if (system) conversation.push({ role: 'system', content: system });
  if (messages?.length) {
    conversation.push(...messages);
  } else {
    conversation.push({ role: 'user', content: prompt });
  }

  try {
    const response = await getKimiClient().chat.completions.create(
      {
        model,
        messages: conversation,
        // `max_completion_tokens` remplace `max_tokens`, déprécié.
        max_completion_tokens: maxCompletionTokens,
        ...(temperature != null ? { temperature } : {}),
        ...(json ? { response_format: { type: 'json_object' as const } } : {}),
      },
      signal ? { signal } : undefined,
    );

    const text = response.choices?.[0]?.message?.content?.trim();
    if (!text) {
      throw new KimiError('Réponse Kimi vide.');
    }

    const usage: KimiUsage | null = response.usage
      ? {
          promptTokens: response.usage.prompt_tokens ?? 0,
          completionTokens: response.usage.completion_tokens ?? 0,
          totalTokens: response.usage.total_tokens ?? 0,
        }
      : null;

    if (process.env.NODE_ENV !== 'production' && usage) {
      console.log(
        `[kimi] ${model} — ${usage.promptTokens} tokens entrée + ${usage.completionTokens} sortie = ${usage.totalTokens}`,
      );
    }

    return { text, model, usage };
  } catch (error: any) {
    if (error instanceof KimiError) throw error;

    const status: number | undefined = error?.status ?? error?.response?.status;

    if (status === 429) {
      throw new KimiError(
        "Limite de débit Moonshot atteinte (429). Moonshot réserve le quota à l'avance " +
          '(tokens d\'entrée + max_completion_tokens) : baisse maxCompletionTokens, espace les appels, ' +
          'ou recharge le compte pour passer au palier supérieur.',
        429,
      );
    }
    if (status === 401) {
      throw new KimiError(
        'Clé MOONSHOT_API_KEY invalide ou non activée. La clé doit être créditée (1 $ minimum) sur platform.moonshot.ai.',
        401,
      );
    }
    if (status === 400) {
      throw new KimiError(`Requête refusée par Moonshot : ${error?.message || 'paramètres invalides'}`, 400);
    }
    throw new KimiError(`Appel Kimi en échec : ${error?.message || error}`, status);
  }
}

/** Variante pratique : demande une réponse JSON et la parse. */
export async function askKimiJson<T = unknown>(
  prompt: string,
  options: Omit<AskKimiOptions, 'json'> = {},
): Promise<T> {
  const { text } = await askKimi(prompt, { ...options, json: true });
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new KimiError(`Kimi n'a pas renvoyé un JSON valide : ${text.slice(0, 200)}`);
  }
}

/** Kimi est-il configuré (clé présente) ? Utile pour un endpoint de santé. */
export function isKimiConfigured(): boolean {
  return Boolean(process.env.MOONSHOT_API_KEY);
}
