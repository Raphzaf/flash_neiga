import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
    ArrowLeft, ArrowUp, BookOpen, ChevronRight, Clock, Download, List,
    PlayCircle, RotateCcw, Type, X, CheckCircle2, Dumbbell,
} from 'lucide-react';
import { sanitizeHtml, sanitizeVideoUrl } from '../lib/sanitize';
import InlineChat from './InlineChat';

/**
 * Lecteur d'un cours complet, d'un seul tenant, de A à Z.
 *
 * Le cours se lit comme un livre : sommaire des grandes parties (titres h2)
 * en colonne sur grand écran, en volet sur mobile ; barre de progression de
 * lecture ; reprise là où l'élève s'était arrêté ; taille du texte réglable ;
 * illustrations agrandies d'un toucher.
 */

const POSITION_KEY = (id) => `flash_neiga_course_position_${id}`;
const SIZE_KEY = 'flash_neiga_course_text_size';
const TEXT_SIZES = ['1rem', '1.0625rem', '1.1875rem'];
// Hauteur de l'en-tête collant, plus une marge : un titre est « atteint »
// quand il passe sous cette ligne.
const HEADER_OFFSET = 96;

function readStorage(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function writeStorage(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch {
        /* stockage indisponible (navigation privée) : rien n'est mémorisé */
    }
}

/** Prépare le HTML du cours : identifiants des titres, sommaire, images différées. */
function prepareContent(rawHtml) {
    const doc = new DOMParser().parseFromString(sanitizeHtml(rawHtml, { keepFormatting: true }), 'text/html');
    const headings = [...doc.body.querySelectorAll('h2, h3')];
    // Sans grande partie (cours saisi à la main dans le CMS), les h3 en tiennent lieu.
    const topTag = headings.some((h) => h.tagName === 'H2') ? 'H2' : 'H3';
    const toc = [];
    headings.forEach((heading, index) => {
        if (!heading.id) heading.id = `section-${index + 1}`;
        // Le titre garde la casse du document ; son libellé adouci (title) sert au sommaire.
        const label = heading.getAttribute('title') || heading.textContent.trim();
        heading.removeAttribute('title');
        const entry = { id: heading.id, title: label, children: [] };
        if (heading.tagName === topTag) {
            toc.push(entry);
        } else if (toc.length) {
            toc[toc.length - 1].children.push(entry);
        }
    });
    doc.body.querySelectorAll('img').forEach((img) => {
        img.setAttribute('loading', 'lazy');
        img.setAttribute('decoding', 'async');
    });
    return {
        html: doc.body.innerHTML,
        toc,
        headingIds: headings.map((h) => h.id),
        words: doc.body.textContent.split(/\s+/).filter(Boolean).length,
    };
}

export default function CourseBook({ course }) {
    const { html, toc, headingIds, words } = useMemo(
        () => prepareContent(course.content || ''),
        [course.content],
    );
    const minutes = Math.max(1, Math.round(words / 200));

    const articleRef = useRef(null);
    const [activeId, setActiveId] = useState(null);
    const [progress, setProgress] = useState(0);
    const [tocOpen, setTocOpen] = useState(false);
    const [zoomSrc, setZoomSrc] = useState(null);
    const [sizeIndex, setSizeIndex] = useState(() => {
        const saved = Number(readStorage(SIZE_KEY));
        return Number.isInteger(saved) && saved >= 0 && saved < TEXT_SIZES.length ? saved : 0;
    });
    // Position enregistrée lors de la visite précédente (lue une seule fois).
    const [resumeId, setResumeId] = useState(() => {
        const saved = readStorage(POSITION_KEY(course.id));
        return saved && saved !== headingIds[0] && headingIds.includes(saved) ? saved : null;
    });

    const activePart = useMemo(() => {
        if (!activeId) return null;
        return toc.find((p) => p.id === activeId || p.children.some((c) => c.id === activeId)) || null;
    }, [activeId, toc]);
    const partNumber = activePart ? toc.indexOf(activePart) + 1 : 0;

    // Suivi de la lecture : titre courant, progression, position mémorisée.
    useEffect(() => {
        let frame = 0;
        const update = () => {
            frame = 0;
            const article = articleRef.current;
            if (!article) return;
            const rect = article.getBoundingClientRect();
            const total = rect.height - window.innerHeight + HEADER_OFFSET;
            const done = Math.min(1, Math.max(0, (HEADER_OFFSET - rect.top) / Math.max(1, total)));
            setProgress(Math.round(done * 100));

            let current = null;
            for (const id of headingIds) {
                const el = document.getElementById(id);
                if (!el) continue;
                if (el.getBoundingClientRect().top - HEADER_OFFSET - 8 <= 0) current = id;
                else break;
            }
            setActiveId(current);
            if (current) writeStorage(POSITION_KEY(course.id), current);
        };
        const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
        update();
        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', onScroll);
        return () => {
            window.removeEventListener('scroll', onScroll);
            window.removeEventListener('resize', onScroll);
            if (frame) cancelAnimationFrame(frame);
        };
    }, [headingIds, course.id]);

    // Une fois la lecture reprise ou avancée, l'invitation à reprendre disparaît.
    useEffect(() => {
        if (resumeId && activeId) setResumeId(null);
    }, [activeId, resumeId]);

    // Le volet du sommaire et l'image agrandie bloquent le défilement derrière eux.
    useEffect(() => {
        if (!tocOpen && !zoomSrc) return undefined;
        const previous = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        const onKey = (e) => {
            if (e.key === 'Escape') { setTocOpen(false); setZoomSrc(null); }
        };
        window.addEventListener('keydown', onKey);
        return () => {
            document.body.style.overflow = previous;
            window.removeEventListener('keydown', onKey);
        };
    }, [tocOpen, zoomSrc]);

    const goTo = useCallback((id) => {
        setTocOpen(false);
        // Laisse le volet se fermer (et le défilement se débloquer) avant de bouger.
        requestAnimationFrame(() => {
            document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }, []);

    const changeSize = () => {
        const next = (sizeIndex + 1) % TEXT_SIZES.length;
        setSizeIndex(next);
        writeStorage(SIZE_KEY, String(next));
    };

    const onArticleClick = (e) => {
        if (e.target.tagName === 'IMG') setZoomSrc(e.target.currentSrc || e.target.src);
    };

    const videoUrl = sanitizeVideoUrl(course.video_url);
    const chatContext = `Cours consulté par l'élève : "${course.title}".\n`
        + (activePart ? `Partie en cours de lecture : "${activePart.title}".\n` : '')
        + `${(articleRef.current?.textContent || '').slice(0, 1500)}`;

    const tocList = (
        <ol className="space-y-1">
            {toc.map((part, index) => {
                const isActive = activePart?.id === part.id;
                return (
                    <li key={part.id}>
                        <button
                            type="button"
                            onClick={() => goTo(part.id)}
                            aria-current={isActive ? 'true' : undefined}
                            className={`w-full text-left flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors ${isActive
                                ? 'bg-teal-50 text-teal-800 dark:bg-teal-900/30 dark:text-teal-200'
                                : 'text-slate-600 hover:bg-sky-50 dark:text-slate-300 dark:hover:bg-slate-800'}`}
                        >
                            <span className={`mt-0.5 h-6 w-6 shrink-0 rounded-full text-xs font-semibold flex items-center justify-center ${isActive
                                ? 'bg-teal-600 text-white'
                                : 'bg-sky-100 text-sky-700 dark:bg-slate-700 dark:text-slate-200'}`}
                            >
                                {index + 1}
                            </span>
                            <span className="text-sm leading-snug font-medium">{part.title}</span>
                        </button>
                        {isActive && part.children.length > 0 && (
                            <ul className="mt-1 mb-2 ml-6 pl-4 border-l border-teal-100 dark:border-teal-900 space-y-0.5">
                                {part.children.map((child) => (
                                    <li key={child.id}>
                                        <button
                                            type="button"
                                            onClick={() => goTo(child.id)}
                                            className={`w-full text-left rounded-lg px-2 py-1.5 text-[13px] leading-snug transition-colors ${activeId === child.id
                                                ? 'text-teal-700 font-medium dark:text-teal-300'
                                                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'}`}
                                        >
                                            {child.title}
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </li>
                );
            })}
        </ol>
    );

    return (
        <div className="min-h-screen pb-28 lg:pb-16 bg-gradient-to-b from-sky-50 via-white to-white dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
            {/* En-tête collant, avec la progression de lecture */}
            <header className="sticky top-0 z-30 bg-white/85 dark:bg-slate-900/85 backdrop-blur border-b border-sky-100 dark:border-slate-800">
                <div className="max-w-6xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-2 sm:gap-3">
                    <Link
                        to="/"
                        aria-label="Retour à l'accueil"
                        className="h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-slate-600 hover:bg-sky-100 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </Link>
                    <div className="min-w-0 flex-1">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-teal-700 dark:text-teal-300">
                            {activePart ? `Partie ${partNumber} sur ${toc.length}` : 'Cours théorique'}
                        </p>
                        <p className="text-sm sm:text-base font-semibold text-slate-800 dark:text-white truncate">
                            {activePart ? activePart.title : course.title}
                        </p>
                    </div>
                    <span className="hidden sm:inline text-xs tabular-nums text-slate-400 dark:text-slate-500">
                        {progress} %
                    </span>
                    <button
                        type="button"
                        onClick={changeSize}
                        aria-label="Changer la taille du texte"
                        title="Taille du texte"
                        className="h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-slate-600 hover:bg-sky-100 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
                    >
                        <Type className="h-5 w-5" style={{ transform: `scale(${0.85 + sizeIndex * 0.15})` }} />
                    </button>
                    {toc.length > 0 && (
                        <button
                            type="button"
                            onClick={() => setTocOpen(true)}
                            className="lg:hidden h-10 shrink-0 rounded-full px-3 flex items-center gap-1.5 text-sm font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 dark:text-teal-200 dark:bg-teal-900/30 dark:hover:bg-teal-900/50 transition-colors"
                        >
                            <List className="h-4 w-4" /> Sommaire
                        </button>
                    )}
                </div>
                <div
                    className="h-1 bg-sky-100/70 dark:bg-slate-800"
                    role="progressbar"
                    aria-label="Progression de lecture"
                    aria-valuenow={progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                >
                    <div
                        className="h-full bg-gradient-to-r from-sky-400 to-teal-500 transition-[width] duration-150"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </header>

            <div className="max-w-6xl mx-auto px-4 lg:grid lg:grid-cols-[17rem_minmax(0,1fr)] lg:gap-10 xl:gap-14">
                {/* Sommaire en colonne (grand écran) */}
                {toc.length > 0 && (
                    <aside className="hidden lg:block">
                        <nav
                            aria-label="Sommaire du cours"
                            className="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto overscroll-contain py-8 pr-2"
                        >
                            <p className="px-3 pb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                Sommaire
                            </p>
                            {tocList}
                        </nav>
                    </aside>
                )}

                <main className="min-w-0 max-w-3xl w-full mx-auto lg:mx-0 pt-6 sm:pt-10">
                    {/* Présentation du cours */}
                    <section className="rounded-3xl bg-white dark:bg-slate-800/70 border border-sky-100 dark:border-slate-700 shadow-sm p-5 sm:p-8">
                        <span className="inline-flex items-center gap-2 rounded-full bg-sky-50 dark:bg-sky-900/30 px-3 py-1 text-xs font-medium text-sky-700 dark:text-sky-300">
                            <BookOpen className="h-3.5 w-3.5" /> Cours complet
                        </span>
                        <h1 className="mt-3 text-3xl sm:text-4xl font-heading font-semibold text-slate-800 dark:text-white leading-tight">
                            {course.title}
                        </h1>
                        {course.description && (
                            <p className="mt-3 text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                                {course.description}
                            </p>
                        )}
                        <p className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-400 dark:text-slate-500">
                            <span className="inline-flex items-center gap-1.5">
                                <Clock className="h-4 w-4" /> Environ {minutes} min de lecture
                            </span>
                            {toc.length > 1 && (
                                <span className="inline-flex items-center gap-1.5">
                                    <List className="h-4 w-4" /> {toc.length} parties
                                </span>
                            )}
                        </p>

                        <div className="mt-6 flex flex-col sm:flex-row gap-2">
                            {resumeId ? (
                                <>
                                    <button
                                        type="button"
                                        onClick={() => goTo(resumeId)}
                                        className="h-12 rounded-xl px-5 inline-flex items-center justify-center gap-2 font-medium text-white bg-teal-600 hover:bg-teal-700 transition-colors"
                                    >
                                        <PlayCircle className="h-5 w-5" /> Reprendre ma lecture
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => { setResumeId(null); goTo(headingIds[0]); }}
                                        className="h-12 rounded-xl px-5 inline-flex items-center justify-center gap-2 font-medium text-slate-600 dark:text-slate-300 bg-sky-50 dark:bg-slate-700 hover:bg-sky-100 dark:hover:bg-slate-600 transition-colors"
                                    >
                                        <RotateCcw className="h-4 w-4" /> Recommencer depuis le début
                                    </button>
                                </>
                            ) : headingIds.length > 0 && (
                                <button
                                    type="button"
                                    onClick={() => goTo(headingIds[0])}
                                    className="h-12 rounded-xl px-5 inline-flex items-center justify-center gap-2 font-medium text-white bg-teal-600 hover:bg-teal-700 transition-colors"
                                >
                                    Commencer la lecture <ChevronRight className="h-5 w-5" />
                                </button>
                            )}
                        </div>
                    </section>

                    {videoUrl && (
                        <div className="mt-8 aspect-video -mx-4 sm:mx-0">
                            <iframe
                                src={videoUrl}
                                className="w-full h-full sm:rounded-2xl border-0"
                                allowFullScreen
                                title={course.title}
                            />
                        </div>
                    )}

                    {/* Le cours, d'un seul tenant */}
                    <article
                        ref={articleRef}
                        onClick={onArticleClick}
                        className="course-book mt-4"
                        style={{ fontSize: TEXT_SIZES[sizeIndex] }}
                        dangerouslySetInnerHTML={{ __html: html }}
                    />

                    {course.pdf_url && (
                        <a
                            href={course.pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-10 flex items-center gap-3 rounded-2xl border border-teal-100 dark:border-teal-900 bg-teal-50/60 dark:bg-teal-900/20 p-4 text-teal-800 dark:text-teal-200 hover:bg-teal-50 dark:hover:bg-teal-900/30 transition-colors"
                        >
                            <span className="h-10 w-10 shrink-0 rounded-xl bg-white dark:bg-slate-800 flex items-center justify-center">
                                <Download className="h-5 w-5" />
                            </span>
                            <span className="font-medium">Télécharger le support PDF</span>
                        </a>
                    )}

                    {/* Fin du cours */}
                    <section className="mt-14 rounded-3xl bg-gradient-to-br from-teal-50 to-sky-50 dark:from-teal-900/20 dark:to-sky-900/20 border border-teal-100 dark:border-teal-900 p-6 sm:p-8 text-center">
                        <CheckCircle2 className="h-10 w-10 mx-auto text-teal-500" />
                        <h2 className="mt-3 text-xl sm:text-2xl font-heading font-semibold text-slate-800 dark:text-white">
                            Bravo, tu es arrivé au bout du cours !
                        </h2>
                        <p className="mt-2 text-slate-600 dark:text-slate-300">
                            Le meilleur moyen de retenir, c'est de t'entraîner maintenant.
                        </p>
                        <div className="mt-5 flex flex-col sm:flex-row gap-2 justify-center">
                            <Link
                                to="/training"
                                className="h-12 rounded-xl px-5 inline-flex items-center justify-center gap-2 font-medium text-white bg-teal-600 hover:bg-teal-700 transition-colors"
                            >
                                <Dumbbell className="h-5 w-5" /> M'entraîner
                            </Link>
                            <button
                                type="button"
                                onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                                className="h-12 rounded-xl px-5 inline-flex items-center justify-center gap-2 font-medium text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 hover:bg-sky-50 dark:hover:bg-slate-700 transition-colors"
                            >
                                <ArrowUp className="h-4 w-4" /> Revenir au début
                            </button>
                        </div>
                    </section>

                    <div className="mt-8">
                        <InlineChat
                            context={chatContext}
                            title="💬 Une question sur le cours ? Demande à ton prof"
                        />
                    </div>
                </main>
            </div>

            {/* Retour en haut (à gauche : la bulle du prof occupe le coin droit) */}
            {progress > 3 && (
                <button
                    type="button"
                    onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                    aria-label="Revenir en haut du cours"
                    className="fixed z-40 left-4 bottom-[max(1.25rem,env(safe-area-inset-bottom))] h-12 w-12 rounded-full flex items-center justify-center bg-white/95 dark:bg-slate-800/95 text-slate-600 dark:text-slate-200 border border-sky-100 dark:border-slate-700 shadow-lg hover:bg-sky-50 dark:hover:bg-slate-700 transition-colors"
                >
                    <ArrowUp className="h-5 w-5" />
                </button>
            )}

            {/* Sommaire en volet (mobile et tablette) */}
            {tocOpen && (
                <div
                    className="lg:hidden fixed inset-0 z-50 flex items-end bg-slate-900/40 backdrop-blur-sm"
                    onClick={() => setTocOpen(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-label="Sommaire du cours"
                >
                    <div
                        className="w-full max-h-[85vh] flex flex-col rounded-t-3xl bg-white dark:bg-slate-900 shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between px-5 pt-4 pb-2">
                            <p className="font-semibold text-slate-800 dark:text-white">Sommaire</p>
                            <button
                                type="button"
                                onClick={() => setTocOpen(false)}
                                aria-label="Fermer le sommaire"
                                className="h-10 w-10 rounded-full flex items-center justify-center text-slate-500 hover:bg-sky-50 dark:hover:bg-slate-800"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>
                        <div className="overflow-y-auto overscroll-contain px-2 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
                            {tocList}
                        </div>
                    </div>
                </div>
            )}

            {/* Illustration agrandie */}
            {zoomSrc && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-8 bg-slate-950/85"
                    onClick={() => setZoomSrc(null)}
                    role="dialog"
                    aria-modal="true"
                    aria-label="Illustration agrandie"
                >
                    <img src={zoomSrc} alt="" className="max-h-full max-w-full object-contain rounded-xl bg-white" />
                    <button
                        type="button"
                        onClick={() => setZoomSrc(null)}
                        aria-label="Fermer l'illustration"
                        className="absolute top-[max(1rem,env(safe-area-inset-top))] right-4 h-11 w-11 rounded-full flex items-center justify-center bg-white/90 text-slate-700"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>
            )}
        </div>
    );
}
