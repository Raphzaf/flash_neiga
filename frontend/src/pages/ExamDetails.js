import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { AlertTriangle, CheckCircle, ArrowLeft } from 'lucide-react';

export default function ExamDetails() {
  const { id } = useParams();
  const [details, setDetails] = useState(null);
  const [filter, setFilter] = useState('all'); // all | correct | incorrect
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
        <h1 className="text-2xl font-heading font-bold">Détails de l'examen</h1>
        <Button variant="ghost" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Retour
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Résumé</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-center">
            <div>
              <div className="text-sm text-muted-foreground">Score</div>
              <div className="font-bold text-lg">{correct}/{total} ({Math.round((correct/(total||1))*100)}%)</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Résultat</div>
              <div className={`font-bold ${details.passed ? 'text-emerald-600' : 'text-red-600'}`}>
                {details.passed ? 'Admis' : 'Ajourné'}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Début</div>
              <div className="font-medium">{details.created_at ? new Date(details.created_at).toLocaleString() : '—'}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Fin</div>
              <div className="font-medium">{details.completed_at ? new Date(details.completed_at).toLocaleString() : '—'}</div>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <Button size="sm" variant={filter==='all'?'default':'outline'} onClick={() => setFilter('all')}>Toutes ({total})</Button>
            <Button size="sm" variant={filter==='correct'?'default':'outline'} onClick={() => setFilter('correct')}>Correctes ({correct})</Button>
            <Button size="sm" variant={filter==='incorrect'?'default':'outline'} onClick={() => setFilter('incorrect')}>Incorrectes ({incorrect})</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Erreurs et réponses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {filtered.length > 0 ? (
            filtered.map((q, idx) => {
              const selected = (q.options || []).find(o => o.id === q.selected_option_id);
              const correctOpt = (q.options || []).find(o => o.id === q.correct_option_id);
              const isCorrect = !!q.is_correct;
              return (
                <div key={q.question_id || idx} className={`p-4 rounded-xl border ${isCorrect ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'}`}>
                  <div className="flex items-start gap-3">
                    {isCorrect ? (
                      <CheckCircle className="h-5 w-5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="h-5 w-5 text-amber-600" />
                    )}
                    <div>
                      <div className="font-medium mb-1">{q.text}</div>
                      <div className="text-sm">
                        <div>
                          Votre réponse: <span className="font-medium">{selected?.text || '—'}</span>
                        </div>
                        {!isCorrect && (
                          <div>
                            Bonne réponse: <span className="font-medium">{correctOpt?.text || '—'}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-muted-foreground">Aucune question à afficher.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
