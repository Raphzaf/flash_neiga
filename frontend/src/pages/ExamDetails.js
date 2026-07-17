import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertTriangle, CheckCircle, ArrowLeft, BookOpen } from 'lucide-react';
import { ExplanationWithLinks } from '../components/ExplanationWithLinks';
import AiLesson from '../components/AiLesson';
import { toast } from 'sonner';
import { sanitizeHtml, sanitizeVideoUrl } from '../lib/sanitize';

export default function ExamDetails() {
  const { id } = useParams();
  const [details, setDetails] = useState(null);
  const [filter, setFilter] = useState('all'); // all | correct | incorrect
  const [selectedCourse, setSelectedCourse] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchExam = async () => {
      try {
        const res = await axios.get(`/api/exam/${id}/details`);
        setDetails(res.data);
      } catch (e) {
        navigate('/');
      }
    };
    fetchExam();
  }, [id, navigate]);

  if (!details) return <div className="p-6">Chargement...</div>;

  const handleCourseClick = async (courseId) => {
    try {
      const res = await axios.get(`/api/courses/${courseId}`);
      setSelectedCourse(res.data);
    } catch (e) {
      toast.error("Cours introuvable");
    }
  };

  const total = details.total_questions || (details.questions?.length || 0);
  const correct = details.correct_answers ?? (details.questions?.filter(q => q.is_correct).length || 0);
  const incorrect = total - correct;

  const filtered = (details.questions || []).filter(q => {
    if (filter === 'correct') return q.is_correct;
    if (filter === 'incorrect') return !q.is_correct;
    return true;
  });

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-heading font-bold text-slate-900 dark:text-white">Détails de l'examen</h1>
        <Button variant="ghost" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Retour
        </Button>
      </div>

      <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
        <CardHeader>
          <CardTitle className="text-slate-900 dark:text-white">Résumé</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-center">
            <div>
              <div className="text-sm text-slate-600 dark:text-slate-300">Score</div>
              <div className="font-bold text-lg text-slate-900 dark:text-white">{correct}/{total} ({Math.round((correct/(total||1))*100)}%)</div>
            </div>
            <div>
              <div className="text-sm text-slate-600 dark:text-slate-300">Résultat</div>
              <div className={`font-bold ${details.passed ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                {details.passed ? 'Admis' : 'Ajourné'}
              </div>
            </div>
            <div>
              <div className="text-sm text-slate-600 dark:text-slate-300">Début</div>
              <div className="font-medium text-slate-900 dark:text-white">{details.created_at ? new Date(details.created_at).toLocaleString() : '—'}</div>
            </div>
            <div>
              <div className="text-sm text-slate-600 dark:text-slate-300">Fin</div>
              <div className="font-medium text-slate-900 dark:text-white">{details.completed_at ? new Date(details.completed_at).toLocaleString() : '—'}</div>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <Button size="sm" variant={filter==='all'?'default':'outline'} onClick={() => setFilter('all')}>Toutes ({total})</Button>
            <Button size="sm" variant={filter==='correct'?'default':'outline'} onClick={() => setFilter('correct')}>Correctes ({correct})</Button>
            <Button size="sm" variant={filter==='incorrect'?'default':'outline'} onClick={() => setFilter('incorrect')}>Incorrectes ({incorrect})</Button>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
        <CardHeader>
          <CardTitle className="text-slate-900 dark:text-white">Erreurs et réponses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {filtered.length > 0 ? (
            filtered.map((q, idx) => {
              const selected = (q.options || []).find(o => o.id === q.selected_option_id);
              const correctOpt = (q.options || []).find(o => o.id === q.correct_option_id);
              const isCorrect = !!q.is_correct;
              return (
                <div key={q.question_id || idx} className={`p-4 rounded-xl border ${isCorrect ? 'border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/30' : 'border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30'}`}>
                  <div className="flex items-start gap-3">
                    {isCorrect ? (
                      <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                    ) : (
                      <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    )}
                    <div>
                      <div className="font-medium mb-1 text-slate-900 dark:text-white">{q.text}</div>
                      <div className="text-sm text-slate-700 dark:text-slate-200">
                        <div>
                          Votre réponse: <span className="font-medium">{selected?.text || '—'}</span>
                        </div>
                        {!isCorrect && (
                          <div>
                            Bonne réponse: <span className="font-medium">{correctOpt?.text || '—'}</span>
                          </div>
                        )}
                        {q.explanation && (
                          <div className="mt-3 p-3 rounded-lg bg-white/70 dark:bg-slate-700/70 text-slate-800 dark:text-slate-200">
                            <div className="font-semibold mb-1 text-slate-900 dark:text-white">Explication</div>
                            <ExplanationWithLinks
                              explanation={q.explanation}
                              onCourseClick={handleCourseClick}
                            />
                          </div>
                        )}
                        {!isCorrect && q.selected_option_id && (
                          <div className="mt-3">
                            <AiLesson
                              questionId={q.question_id}
                              selectedOptionId={q.selected_option_id}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-slate-600 dark:text-slate-400">Aucune question à afficher.</div>
          )}
        </CardContent>
      </Card>

      {/* Dialog popup pour afficher le cours */}
      {selectedCourse && (
        <Dialog open={!!selectedCourse} onOpenChange={() => setSelectedCourse(null)}>
          <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                {selectedCourse.title}
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4">
              {selectedCourse.video_url && sanitizeVideoUrl(selectedCourse.video_url) && (
                <div className="aspect-video">
                  <iframe 
                    src={sanitizeVideoUrl(selectedCourse.video_url)} 
                    className="w-full h-full rounded-lg" 
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
                  <BookOpen className="h-4 w-4" />
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
