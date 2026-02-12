import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { BookOpen, Video, FileText, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { sanitizeHtml, sanitizeVideoUrl } from '../lib/sanitize';

export default function Courses() {
    const [courses, setCourses] = useState([]);
    const [selectedCourse, setSelectedCourse] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchCourses();
    }, []);

    const fetchCourses = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/courses');
            setCourses(res.data);
        } catch (error) {
            toast.error("Erreur lors du chargement des cours");
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const openCourse = (course) => {
        setSelectedCourse(course);
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <p className="text-slate-600 dark:text-slate-300">Chargement des cours...</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen pb-20 md:pb-0">
            {/* Header */}
            <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-30 p-4">
                <div className="max-w-5xl mx-auto flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <Link to="/">
                            <Button variant="ghost" size="icon">
                                <ArrowLeft className="h-5 w-5" />
                            </Button>
                        </Link>
                        <h1 className="text-2xl font-heading font-bold text-slate-900 dark:text-white">Cours Théoriques</h1>
                    </div>
                </div>
            </header>

            <main className="max-w-5xl mx-auto p-4 space-y-6 mt-6">
                {courses.length === 0 ? (
                    <div className="text-center p-12 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl">
                        <BookOpen className="h-12 w-12 mx-auto mb-4 text-slate-400" />
                        <p className="text-slate-600 dark:text-slate-300">Aucun cours disponible pour le moment.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {courses.map((course) => (
                            <Card 
                                key={course.id}
                                className="cursor-pointer hover:shadow-lg transition-all hover:border-primary/50 border-slate-200 dark:border-slate-700"
                                onClick={() => openCourse(course)}
                            >
                                {course.image_url && (
                                    <div className="w-full h-40 overflow-hidden rounded-t-lg">
                                        <img 
                                            src={course.image_url} 
                                            alt={course.title}
                                            className="w-full h-full object-cover"
                                        />
                                    </div>
                                )}
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                        <BookOpen className="h-5 w-5 text-purple-600" />
                                        {course.title}
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-sm text-slate-600 dark:text-slate-300 line-clamp-3">
                                        {course.description || "Cliquez pour voir les détails"}
                                    </p>
                                    <div className="flex gap-2 mt-4">
                                        {course.video_url && (
                                            <div className="flex items-center gap-1 text-xs text-sky-600 dark:text-sky-400">
                                                <Video className="h-3 w-3" />
                                                Vidéo
                                            </div>
                                        )}
                                        {course.pdf_url && (
                                            <div className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                                                <FileText className="h-3 w-3" />
                                                PDF
                                            </div>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </main>

            {/* Course Detail Dialog */}
            {selectedCourse && (
                <Dialog open={!!selectedCourse} onOpenChange={() => setSelectedCourse(null)}>
                    <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                <BookOpen className="h-5 w-5 text-purple-600" />
                                {selectedCourse.title}
                            </DialogTitle>
                        </DialogHeader>

                        <div className="space-y-4">
                            {selectedCourse.description && (
                                <p className="text-slate-600 dark:text-slate-300">
                                    {selectedCourse.description}
                                </p>
                            )}

                            {selectedCourse.video_url && sanitizeVideoUrl(selectedCourse.video_url) && (
                                <div className="aspect-video">
                                    <iframe
                                        src={sanitizeVideoUrl(selectedCourse.video_url)}
                                        className="w-full h-full rounded-lg border border-slate-200 dark:border-slate-700"
                                        allowFullScreen
                                        title={selectedCourse.title}
                                    />
                                </div>
                            )}

                            {selectedCourse.content && (
                                <div className="prose dark:prose-invert max-w-none">
                                    <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(selectedCourse.content) }} />
                                </div>
                            )}

                            {selectedCourse.pdf_url && (
                                <a
                                    href={selectedCourse.pdf_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-2 text-blue-600 hover:underline"
                                >
                                    <FileText className="h-4 w-4" />
                                    Télécharger le support PDF
                                </a>
                            )}
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </div>
    );
}
