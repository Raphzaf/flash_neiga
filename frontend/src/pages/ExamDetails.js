import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { AlertTriangle, CheckCircle, ArrowLeft } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function ExamDetails() {
  const { id } = useParams();
  const [exam, setExam] = useState(null);
  const [questionsMap, setQuestionsMap] = useState({});
  const navigate = useNavigate();

  useEffect(() => {
    const fetchExam = async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/exam/${id}`);
        setExam(res.data);
        // Build question map for text/options lookup
        const map = {};
        for (const q of res.data.questions) {
          map[q.question_id] = q;
        }
        setQuestionsMap(map);
      } catch (e) {
        navigate('/');
      }
    };
    fetchExam();
  }, [id, navigate]);

  if (!exam) return <div className="p-6">Chargement...</div>;

  const total = exam.questions.length;
  const correct = (exam.answers || []).filter(a => a.is_correct).length;

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
          <div className="flex gap-6">
            <div className="font-bold text-lg">Score: {correct}/{total}</div>
            <div className={`${correct >= 25 ? 'text-emerald-600' : 'text-red-600'} font-bold`}>
              {correct >= 25 ? 'Admis' : 'Ajourné'}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Erreurs et réponses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {exam.answers && exam.answers.length > 0 ? (
            exam.answers.map((ans, idx) => {
              const q = questionsMap[ans.question_id];
              const selected = q?.options.find(o => o.id === ans.selected_option_id);
              const correctOpt = q?.options.find(o => o.is_correct);
              const isCorrect = !!ans.is_correct;
              return (
                <div key={idx} className={`p-4 rounded-xl border ${isCorrect ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'}`}>
                  <div className="flex items-start gap-3">
                    {isCorrect ? (
                      <CheckCircle className="h-5 w-5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="h-5 w-5 text-amber-600" />
                    )}
                    <div>
                      <div className="font-medium mb-1">{q?.text || 'Question'}</div>
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
            <div className="text-muted-foreground">Aucune réponse enregistrée.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
