import React, { useState, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import {
    BookOpen, Video, FileText, ArrowLeft, Search, CheckCircle2,
    ChevronLeft, ChevronRight, X, Clock, Download,
} from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { sanitizeHtml, sanitizeVideoUrl } from '../lib/sanitize';
import InlineChat from '../components/InlineChat';

// Cours déjà ouverts sur cet appareil : simple repère visuel pour l'élève.
const READ_KEY = 'flash_neiga_courses_read';

function loadRead() {
    try {
        return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]'));
    } catch {
        return new Set();
    }
}

function saveRead(set) {
    try {
        localStorage.setItem(READ_KEY, JSON.stringify([...set]));
    } catch {
        /* stockage indisponible : le repère n'est simplement pas conservé */
    }
}

const stripHtml = (html) => (html || '').replace(/<[^>]+>/g, ' ');

// Environ 200 mots par minute, arrondi à la minute supérieure.
function readingMinutes(course) {
    const words = `${course.description || ''} ${stripHtml(course.content)}`
        .split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.ceil(words / 200));
}

export default function Courses() {
    const [courses, setCourses] = useState([]);
    const [selectedIndex, setSelectedIndex] = useState(null);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState('');
    const [category, setCategory] = useState('all');
    const [readIds, setReadIds] = useState(loadRead);
    const readerRef = useRef(null);

    useEffect(() => {
        fetchCourses();
    }, []);

    const fetchCourses = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/courses');
            const sorted = [...res.data].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
            setCourses(sorted);
        } catch (error) {
            toast.error("Erreur lors du chargement des cours");
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const categories = useMemo(
        () => [...new Set(courses.map((c) => c.category).filter(Boolean))],
        [courses],
    );

    const visibleCourses = useMemo(() => {
        const q = query.trim().toLowerCase();
        return courses.filter((c) => {
            if (category !== 'all' && c.category !== category) return false;
            if (!q) return true;
            return `${c.title} ${c.description || ''} ${stripHtml(c.content)}`
                .toLowerCase().includes(q);
        });
    }, [courses, query, category]);

    const selectedCourse = selectedIndex !== null ? courses[selectedIndex] : null;
    const readCount = courses.filter((c) => readIds.has(c.id)).length;
    const progress = courses.length ? Math.round((readCount / courses.length) * 100) : 0;

    const openCourse = (course) => {
        const index = courses.findIndex((c) => c.id === course.id);
        setSelectedIndex(index);
        setReadIds((prev) => {
            if (prev.has(course.id)) return prev;
            const next = new Set(prev);
            next.add(course.id);
            saveRead(next);
            return next;
        });
    };

    const closeCourse = () => setSelectedIndex(null);

    // Lecteur plein écran : on bloque le défilement de la page derrière,
    // on revient en haut à chaque changement de cours et Échap le ferme.
    useEffect(() => {
        if (!selectedCourse) return undefined;
        const previous = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        readerRef.current?.scrollTo({ top: 0 });
        const onKey = (e) => { if (e.key === 'Escape') closeCourse(); };
        window.addEventListener('keydown', onKey);
        return () => {
            document.body.style.overflow = previous;
            window.removeEventListener('keydown', onKey);
        };
    }, [selectedCourse]);

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white dark:from-slate-900 dark:to-slate-900">
                <div className="max-w-3xl mx-auto px-4 pt-24 space-y-3">
                    {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="h-24 rounded-2xl bg-white/80 dark:bg-slate-800 animate-pulse" />
                    ))}
                    <p className="text-center text-sm text-slate-500 dark:text-slate-400 pt-4">
                        Chargement des cours…
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen pb-24 md:pb-10 bg-gradient-to-b from-sky-50 via-teal-50/40 to-white dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
            {/* En-tête */}
            <header className="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur border-b border-sky-100 dark:border-slate-800">
                <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
                    <Link
                        to="/"
                        aria-label="Retour"
                        className="h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-slate-600 hover:bg-sky-100 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </Link>
                    <div className="min-w-0">
                        <h1 className="text-lg sm:text-xl font-heading font-semibold text-slate-800 dark:text-white truncate">
                            Cours Théoriques
                        </h1>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                            Avance à ton rythme, un chapitre après l'autre
                        </p>
                    </div>
                </div>
            </header>

            <main className="max-w-3xl mx-auto px-4 pt-5 space-y-5">
                {courses.length > 0 && (
                    <>
                        {/* Progression */}
                        <section className="rounded-2xl bg-white dark:bg-slate-800 border border-sky-100 dark:border-slate-700 p-4 sm:p-5 shadow-sm">
                            <div className="flex items-baseline justify-between gap-2">
                                <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                    Ta progression
                                </p>
                                <p className="text-sm text-slate-500 dark:text-slate-400">
                                    <span className="font-semibold text-teal-700 dark:text-teal-300">{readCount}</span>
                                    {' '}/ {courses.length} cours consultés
                                </p>
                            </div>
                            <div
                                className="mt-3 h-2 rounded-full bg-sky-100 dark:bg-slate-700 overflow-hidden"
                                role="progressbar"
                                aria-valuenow={progress}
                                aria-valuemin={0}
                                aria-valuemax={100}
                            >
                                <div
                                    className="h-full rounded-full bg-gradient-to-r from-sky-400 to-teal-400 transition-all duration-500"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                        </section>

                        {/* Recherche et catégories */}
                        <div className="space-y-3">
                            <label className="relative block">
                                <span className="sr-only">Rechercher un cours</span>
                                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                <input
                                    type="search"
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    placeholder="Rechercher un cours, un mot-clé…"
                                    className="w-full h-12 rounded-full pl-11 pr-4 text-base bg-white dark:bg-slate-800 border border-sky-100 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-300 dark:focus:ring-teal-600 shadow-sm"
                                />
                            </label>

                            {categories.length > 1 && (
                                <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-none">
                                    {['all', ...categories].map((cat) => {
                                        const active = category === cat;
                                        return (
                                            <button
                                                key={cat}
                                                type="button"
                                                onClick={() => setCategory(cat)}
                                                className={`shrink-0 h-9 px-4 rounded-full text-sm transition-colors border ${active
                                                    ? 'bg-teal-600 border-teal-600 text-white'
                                                    : 'bg-white dark:bg-slate-800 border-sky-100 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-sky-50 dark:hover:bg-slate-700'}`}
                                            >
                                                {cat === 'all' ? 'Tous' : cat}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* Liste des cours */}
                {courses.length === 0 ? (
                    <div className="text-center px-6 py-16 rounded-2xl border border-dashed border-sky-200 dark:border-slate-700 bg-white/60 dark:bg-slate-800/60">
                        <BookOpen className="h-10 w-10 mx-auto mb-3 text-sky-300" />
                        <p className="text-slate-600 dark:text-slate-300">Aucun cours disponible pour le moment.</p>
                    </div>
                ) : visibleCourses.length === 0 ? (
                    <div className="text-center px-6 py-12 text-slate-500 dark:text-slate-400">
                        Aucun cours ne correspond à ta recherche.
                    </div>
                ) : (
                    <ol className="space-y-3">
                        {visibleCourses.map((course) => {
                            const number = courses.indexOf(course) + 1;
                            const isRead = readIds.has(course.id);
                            return (
                                <li key={course.id}>
                                    <button
                                        type="button"
                                        onClick={() => openCourse(course)}
                                        className="group w-full text-left flex items-stretch gap-4 rounded-2xl bg-white dark:bg-slate-800 border border-sky-100 dark:border-slate-700 p-3 sm:p-4 shadow-sm hover:shadow-md hover:border-teal-200 dark:hover:border-teal-700 active:scale-[0.99] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
                                    >
                                        {course.image_url ? (
                                            <img
                                                src={course.image_url}
                                                alt=""
                                                loading="lazy"
                                                className="h-16 w-16 sm:h-20 sm:w-20 shrink-0 rounded-xl object-cover"
                                            />
                                        ) : (
                                            <span
                                                className={`h-12 w-12 sm:h-14 sm:w-14 shrink-0 self-center rounded-xl flex items-center justify-center text-base font-semibold ${isRead
                                                    ? 'bg-teal-50 text-teal-600 dark:bg-teal-900/40 dark:text-teal-300'
                                                    : 'bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300'}`}
                                            >
                                                {isRead ? <CheckCircle2 className="h-6 w-6" /> : number}
                                            </span>
                                        )}

                                        <span className="min-w-0 flex-1 flex flex-col justify-center">
                                            <span className="font-semibold text-slate-800 dark:text-white leading-snug">
                                                {course.title}
                                            </span>
                                            {course.description && (
                                                <span className="mt-1 text-sm text-slate-500 dark:text-slate-400 line-clamp-2">
                                                    {course.description}
                                                </span>
                                            )}
                                            <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400 dark:text-slate-500">
                                                <span className="inline-flex items-center gap-1">
                                                    <Clock className="h-3.5 w-3.5" />
                                                    {readingMinutes(course)} min
                                                </span>
                                                {course.video_url && (
                                                    <span className="inline-flex items-center gap-1 text-sky-600 dark:text-sky-400">
                                                        <Video className="h-3.5 w-3.5" /> Vidéo
                                                    </span>
                                                )}
                                                {course.pdf_url && (
                                                    <span className="inline-flex items-center gap-1 text-teal-600 dark:text-teal-400">
                                                        <FileText className="h-3.5 w-3.5" /> PDF
                                                    </span>
                                                )}
                                                {isRead && course.image_url && (
                                                    <span className="inline-flex items-center gap-1 text-teal-600 dark:text-teal-400">
                                                        <CheckCircle2 className="h-3.5 w-3.5" /> Consulté
                                                    </span>
                                                )}
                                            </span>
                                        </span>

                                        <ChevronRight className="h-5 w-5 shrink-0 self-center text-slate-300 group-hover:text-teal-500 transition-colors" />
                                    </button>
                                </li>
                            );
                        })}
                    </ol>
                )}
            </main>

            {/* Lecteur de cours : plein écran sur mobile, fenêtre centrée sur grand écran */}
            {selectedCourse && (
                <div
                    className="fixed inset-0 z-50 flex items-stretch sm:items-center justify-center sm:p-6 bg-slate-900/40 backdrop-blur-sm"
                    onClick={closeCourse}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="course-reader-title"
                >
                    <div
                        className="relative flex flex-col w-full sm:max-w-3xl h-full sm:h-auto sm:max-h-[90vh] bg-white dark:bg-slate-900 sm:rounded-3xl shadow-2xl overflow-hidden"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Barre du lecteur */}
                        <div className="flex items-center gap-2 px-3 sm:px-5 py-3 border-b border-sky-100 dark:border-slate-800 bg-white/95 dark:bg-slate-900/95">
                            <button
                                type="button"
                                onClick={closeCourse}
                                aria-label="Fermer le cours"
                                className="h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-slate-500 hover:bg-sky-50 dark:hover:bg-slate-800"
                            >
                                <ArrowLeft className="h-5 w-5 sm:hidden" />
                                <X className="h-5 w-5 hidden sm:block" />
                            </button>
                            <p className="text-xs font-medium uppercase tracking-wide text-teal-700 dark:text-teal-300">
                                Cours {selectedIndex + 1} sur {courses.length}
                            </p>
                        </div>

                        {/* Contenu */}
                        <div ref={readerRef} className="flex-1 overflow-y-auto overscroll-contain">
                            <article className="px-5 sm:px-10 py-6 sm:py-8 space-y-6">
                                <header className="space-y-3">
                                    <h2
                                        id="course-reader-title"
                                        className="text-2xl sm:text-3xl font-heading font-semibold text-slate-800 dark:text-white leading-tight"
                                    >
                                        {selectedCourse.title}
                                    </h2>
                                    <p className="inline-flex items-center gap-1.5 text-sm text-slate-400">
                                        <Clock className="h-4 w-4" />
                                        Environ {readingMinutes(selectedCourse)} min de lecture
                                    </p>
                                    {selectedCourse.description && (
                                        <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                                            {selectedCourse.description}
                                        </p>
                                    )}
                                </header>

                                {selectedCourse.video_url && sanitizeVideoUrl(selectedCourse.video_url) && (
                                    <div className="aspect-video -mx-5 sm:mx-0">
                                        <iframe
                                            src={sanitizeVideoUrl(selectedCourse.video_url)}
                                            className="w-full h-full sm:rounded-2xl border-0"
                                            allowFullScreen
                                            title={selectedCourse.title}
                                        />
                                    </div>
                                )}

                                {selectedCourse.content && (
                                    <div
                                        className="course-content course-reader"
                                        dangerouslySetInnerHTML={{ __html: sanitizeHtml(selectedCourse.content) }}
                                    />
                                )}

                                {selectedCourse.pdf_url && (
                                    <a
                                        href={selectedCourse.pdf_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-3 rounded-2xl border border-teal-100 dark:border-teal-900 bg-teal-50/60 dark:bg-teal-900/20 p-4 text-teal-800 dark:text-teal-200 hover:bg-teal-50 dark:hover:bg-teal-900/30 transition-colors"
                                    >
                                        <span className="h-10 w-10 shrink-0 rounded-xl bg-white dark:bg-slate-800 flex items-center justify-center">
                                            <Download className="h-5 w-5" />
                                        </span>
                                        <span className="font-medium">Télécharger le support PDF</span>
                                    </a>
                                )}

                                {/* Discussion contextuelle avec le prof, sur ce cours */}
                                <div className="pt-4 border-t border-sky-100 dark:border-slate-800">
                                    <InlineChat
                                        context={`Cours consulté par l'élève : "${selectedCourse.title}".\n`
                                            + `${selectedCourse.description || ''}\n`
                                            + `${stripHtml(selectedCourse.content).slice(0, 1500)}`}
                                        title="💬 Une question sur ce cours ? Demande à ton prof"
                                    />
                                </div>
                            </article>
                        </div>

                        {/* Navigation entre les cours */}
                        <nav className="grid grid-cols-2 gap-2 px-3 sm:px-5 py-3 border-t border-sky-100 dark:border-slate-800 bg-white dark:bg-slate-900 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
                            <button
                                type="button"
                                disabled={selectedIndex === 0}
                                onClick={() => openCourse(courses[selectedIndex - 1])}
                                className="h-12 rounded-xl flex items-center justify-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-300 bg-sky-50 dark:bg-slate-800 hover:bg-sky-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                            >
                                <ChevronLeft className="h-4 w-4" /> Précédent
                            </button>
                            {selectedIndex < courses.length - 1 ? (
                                <button
                                    type="button"
                                    onClick={() => openCourse(courses[selectedIndex + 1])}
                                    className="h-12 rounded-xl flex items-center justify-center gap-1 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 transition-colors"
                                >
                                    Suivant <ChevronRight className="h-4 w-4" />
                                </button>
                            ) : (
                                <button
                                    type="button"
                                    onClick={closeCourse}
                                    className="h-12 rounded-xl flex items-center justify-center gap-1 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 transition-colors"
                                >
                                    <CheckCircle2 className="h-4 w-4" /> Terminer
                                </button>
                            )}
                        </nav>
                    </div>
                </div>
            )}
        </div>
    );
}
