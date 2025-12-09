import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { AlertTriangle, CheckCircle, ArrowLeft } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

// Hook pour importer les données officielles (questions, catégories, panneaux)
function useOfficialData() {
  const [questions, setQuestions] = useState([]);
  const [categories, setCategories] = useState({});
  const [panels, setPanels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      setLoading(true);
      try {
        // Paginate via skip parameter to fetch full dataset
        const all = [];
        let skip = 0;
        const pageSize = 1000; // gov.il endpoint typically supports large pages
        while (true) {
          const url = `https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data?skip=${skip}`;
          const res = await fetch(url);
          const data = await res.json();
          const chunk = data?.data || [];
          all.push(...chunk);
          if (chunk.length === 0 || chunk.length < pageSize) break;
          skip += pageSize;
        }
        setQuestions(all);
        // Catégories à partir du champ Sujet
        const cats = {};
        for (const q of all) {
          const cat = q.Sujet || 'Autre';
          if (!cats[cat]) cats[cat] = [];
          cats[cat].push(q);
        }
        setCategories(cats);
        // Panneaux: filtrer par signalisation
        const panneaux = all.filter(q => (q.Sujet || '').toLowerCase().includes('signalisation'));
        setPanels(panneaux);
      } catch {
        setQuestions([]);
        setCategories({});
        setPanels([]);
      }
      setLoading(false);
    }
    fetchAll();
  }, []);

  return { questions, categories, panels, loading };
}

// Zone d'entraînement continue avec feedback immédiat
function TrainingZone() {
  const { categories, loading } = useOfficialData();
  const [selectedCats, setSelectedCats] = useState([]);
  const [current, setCurrent] = useState(null);
  const [showTrain, setShowTrain] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const nextQuestion = () => {
    const pool = selectedCats.length > 0
      ? selectedCats.flatMap(cat => categories[cat] || [])
      : Object.values(categories).flat();
    if (pool.length === 0) {
      setCurrent(null);
      return;
    }
    const q = pool[Math.floor(Math.random() * pool.length)];
    setCurrent(q);
    setFeedback(null);
  };

  const handleStart = () => {
    setShowTrain(true);
    nextQuestion();
  };

  const handleAnswer = (opt) => {
    if (!current) return;
    const isCorrect = !!opt?.is_correct;
    setFeedback({ isCorrect, explanation: current.Explication || current.explanation || '' });
    setTimeout(nextQuestion, 1200);
  };

  if (loading) return <div className="mt-8">Chargement des questions...</div>;

  return (
    <div className="mt-8">
      <h2 className="text-xl font-bold mb-4">Entraînement</h2>
      {!showTrain ? (
        <div>
          <div className="mb-2">Sélectionne une ou plusieurs catégories :</div>
          <div className="flex flex-wrap gap-2 mb-4">
            {Object.keys(categories).map(cat => (
              <Button
                key={cat}
                variant={selectedCats.includes(cat) ? 'default' : 'outline'}
                onClick={() => setSelectedCats(s => s.includes(cat) ? s.filter(c => c !== cat) : [...s, cat])}
              >
                {cat}
              </Button>
            ))}
          </div>
          <Button onClick={handleStart} disabled={selectedCats.length === 0}>Démarrer l'entraînement</Button>
        </div>
      ) : current ? (
        <div className="p-4 border rounded-xl mb-4">
          <div className="font-bold mb-2">{current.Question || current.question || current.text}</div>
          <div className="grid grid-cols-2 gap-2">
            {(current.options || []).slice(0, 4).map((opt, idx) => (
              <Button key={idx} onClick={() => handleAnswer(opt)}>{opt.text}</Button>
            ))}
          </div>
          {feedback && (
            <div className={`mt-3 font-bold ${feedback.isCorrect ? 'text-emerald-600' : 'text-red-600'}`}>
              {feedback.isCorrect ? 'Bonne réponse !' : 'Incorrect'}
              {!feedback.isCorrect && feedback.explanation && (
                <div className="mt-1 text-sm text-gray-700">Explication : {feedback.explanation}</div>
              )}
            </div>
          )}
        </div>
      ) : <div>Fin de l'entraînement.</div>}
    </div>
  );
}

// Section panneaux de signalisation
function PanelsSection() {
  const { panels, loading } = useOfficialData();
  const [selectedPanel, setSelectedPanel] = useState(null);

  if (loading) return <div className="mt-8">Chargement des panneaux...</div>;

  return (
    <div className="mt-8">
      <h2 className="text-xl font-bold mb-4">Panneaux de signalisation ({panels.length})</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {panels.map((p, idx) => (
          <div
            key={idx}
            className="border rounded p-2 cursor-pointer hover:bg-gray-100"
            onClick={() => setSelectedPanel(p)}
          >
            <div className="font-medium mb-1">{p.Question || p.question || p.text}</div>
          </div>
        ))}
      </div>
      {selectedPanel && (
        <div
          className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50"
          onClick={() => setSelectedPanel(null)}
        >
          <div className="bg-white p-6 rounded-xl max-w-md w-full relative" onClick={e => e.stopPropagation()}>
            <button className="absolute top-2 right-2 text-xl" onClick={() => setSelectedPanel(null)}>×</button>
            <div className="font-bold mb-2">{selectedPanel.Question || selectedPanel.question || selectedPanel.text}</div>
            <div className="text-sm text-gray-700">{selectedPanel.Explication || selectedPanel.explanation || 'Pas d’explication.'}</div>
          </div>
        </div>
      )}
    </div>
  );
}

// Zone d'examen simulé (30 questions, timer, navigation, résultats)
function ExamZone() {
  const { categories, questions, loading } = useOfficialData();
  const [started, setStarted] = useState(false);
  const [selectedCats, setSelectedCats] = useState([]);
  const [examQuestions, setExamQuestions] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [timer, setTimer] = useState(40 * 60); // 40 minutes
  const [currentIdx, setCurrentIdx] = useState(0);

  // Simple local error history for adaptive selection
  const getErrorWeights = () => {
    try {
      const raw = localStorage.getItem('flashneiga_error_weights');
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  };
  const saveErrorWeights = (weights) => {
    try { localStorage.setItem('flashneiga_error_weights', JSON.stringify(weights)); } catch {}
  };

  const weightedSample = (pool, count) => {
    const weights = getErrorWeights();
    const items = pool.map(q => {
      const id = q.id || q.question_id || q._id || q.text;
      const w = Math.min(10, (weights[id] || 0) + 1); // base weight 1, cap 10
      return { q, w };
    });
    const result = [];
    const used = new Set();
    while (result.length < Math.min(count, items.length)) {
      const total = items.reduce((s, it) => s + (used.has(it.q) ? 0 : it.w), 0);
      if (total <= 0) break;
      let r = Math.random() * total;
      for (const it of items) {
        if (used.has(it.q)) continue;
        if (r < it.w) { result.push(it.q); used.add(it.q); break; }
        r -= it.w;
      }
    }
    return result;
  };

  useEffect(() => {
    let interval;
    if (started && timer > 0) {
      interval = setInterval(() => setTimer(t => t - 1), 1000);
    }
    if (timer === 0) setStarted(false);
    return () => clearInterval(interval);
  }, [started, timer]);

  const handleStart = () => {
    const pool = selectedCats.length > 0
      ? selectedCats.flatMap(cat => categories[cat] || [])
      : questions;
    const picked = weightedSample(pool, 30);
    setExamQuestions(picked);
    setAnswers([]);
    setStarted(true);
    setTimer(40 * 60);
    setCurrentIdx(0);
  };

  const handleAnswer = (idx, opt) => {
    const isCorrect = !!opt?.is_correct;
    setAnswers(ans => {
      const newAns = [...ans];
      newAns[idx] = { selected: opt, isCorrect };
      return newAns;
    });
    // Update local error weight when wrong
    if (!isCorrect && examQuestions[idx]) {
      const id = examQuestions[idx].id || examQuestions[idx].question_id || examQuestions[idx]._id || examQuestions[idx].text;
      const weights = getErrorWeights();
      weights[id] = (weights[id] || 0) + 1;
      saveErrorWeights(weights);
    }
  };

  if (loading) return <div className="mt-8">Chargement de l’examen...</div>;

  return (
    <div className="mt-8">
      <h2 className="text-xl font-bold mb-4">Démarrer un examen</h2>
      {!started ? (
        <div>
          <div className="mb-2">Sélectionne une ou plusieurs catégories :</div>
          <div className="flex flex-wrap gap-2 mb-4">
            {Object.keys(categories).map(cat => (
              <Button
                key={cat}
                variant={selectedCats.includes(cat) ? 'default' : 'outline'}
                onClick={() => setSelectedCats(s => s.includes(cat) ? s.filter(c => c !== cat) : [...s, cat])}
              >
                {cat}
              </Button>
            ))}
          </div>
          <Button onClick={handleStart} disabled={selectedCats.length === 0}>Démarrer l’examen</Button>
        </div>
      ) : (
        <div>
          <div className="mb-2 font-bold">Temps restant : {Math.floor(timer / 60)}:{String(timer % 60).padStart(2, '0')}</div>
          <div className="mb-4">Question {currentIdx + 1} / 30</div>
          {examQuestions && examQuestions.length > 0 && examQuestions[currentIdx] && (
            <div className="p-4 border rounded-xl mb-4">
              <div className="font-bold mb-2">{examQuestions[currentIdx].Question || examQuestions[currentIdx].question || examQuestions[currentIdx].text}</div>
              <div className="grid grid-cols-2 gap-2">
                {Array.isArray(examQuestions[currentIdx].options) && examQuestions[currentIdx].options.length > 0
                  ? examQuestions[currentIdx].options.slice(0, 4).map((opt, idx) => (
                      <Button key={idx} onClick={() => handleAnswer(currentIdx, opt)}>{opt.text || `Option ${idx+1}`}</Button>
                    ))
                  : (
                      <div className="text-sm text-muted-foreground">Options indisponibles pour cette question.</div>
                    )}
              </div>
            </div>
          )}
          <div className="flex gap-2 mb-4">
            <Button onClick={() => setCurrentIdx(i => Math.max(i - 1, 0))} disabled={currentIdx === 0}>Précédent</Button>
            <Button onClick={() => setCurrentIdx(i => Math.min(i + 1, examQuestions.length - 1))} disabled={currentIdx === examQuestions.length - 1}>Suivant</Button>
            <Button variant="destructive" onClick={() => setStarted(false)}>Terminer l’examen</Button>
          </div>
          {examQuestions && examQuestions.length > 0 && answers.length === examQuestions.length && (
            <div className="mt-6">
              <h3 className="font-bold mb-2">Résultats</h3>
              <div>Score : {answers.filter(a => a && a.isCorrect).length} / {examQuestions.length}</div>
              <div className="mt-2">Erreurs :</div>
              <ul className="list-disc ml-6">
                {answers.map((a, idx) => !a?.isCorrect && (
                  <li key={idx}>
                    <span className="font-medium">{examQuestions[idx].Question || examQuestions[idx].question || examQuestions[idx].text}</span>
                    <span className="ml-2 text-red-600">Réponse incorrecte</span>
                    {examQuestions[idx].Explication && (
                      <span className="ml-2 text-gray-700">Explication : {examQuestions[idx].Explication}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Import et affichage des questions officielles triées par catégorie
function OfficialQuestions() {
  const [loading, setLoading] = useState(false);
  const [categories, setCategories] = useState({});
  const [error, setError] = useState(null);

  const fetchQuestions = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch all pages via skip pagination
      const all = [];
      let skip = 0;
      const pageSize = 1000;
      while (true) {
        const res = await fetch(`https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data?skip=${skip}`);
        const data = await res.json();
        const chunk = data?.data || [];
        all.push(...chunk);
        if (chunk.length === 0 || chunk.length < pageSize) break;
        skip += pageSize;
      }
      const cats = {};
      for (const q of all) {
        const cat = q.Sujet || 'Autre';
        if (!cats[cat]) cats[cat] = [];
        cats[cat].push(q);
      }
      setCategories(cats);
    } catch (e) {
      setError('Erreur lors de l’import des questions.');
    }
    setLoading(false);
  };

  return (
    <div className="mt-8">
      <h2 className="text-xl font-bold mb-4">Questions officielles du code de la route</h2>
      <Button onClick={fetchQuestions} disabled={loading}>
        {loading ? 'Chargement...' : 'Importer les 1802 questions'}
      </Button>
      {error && <div className="text-red-600 mt-2">{error}</div>}
      {Object.keys(categories).length > 0 && (
        <div className="mt-6">
          {Object.entries(categories).map(([cat, qs]) => (
            <div key={cat} className="mb-8">
              <h3 className="text-lg font-semibold mb-2">{cat} ({qs.length})</h3>
              <ul className="list-disc ml-6">
                {qs.map((q, idx) => (
                  <li key={q.id || q.question_id || idx} className="mb-1">
                    <span className="font-medium">{q.Question || q.question || q.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ExamDetails() {
  const { id } = useParams();
  const [exam, setExam] = useState(null);
  const [questionsMap, setQuestionsMap] = useState({});
  const navigate = useNavigate();

  useEffect(() => {
    const fetchExam = async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/exam/${id}`);
        const data = res.data;
        setExam(data);
        const map = {};
        for (const q of data.questions || []) {
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

  const total = Array.isArray(exam.questions) ? exam.questions.length : 0;
  const correct = Array.isArray(exam.answers) ? exam.answers.filter(a => a?.is_correct).length : 0;

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

      {/* Nouvelle zone d'entraînement */}
      <TrainingZone />

      {/* Section panneaux de signalisation */}
      <PanelsSection />

      {/* Zone examen */}
      <ExamZone />

      {/* Import et affichage des questions officielles triées */}
      <OfficialQuestions />

      <Card>
        <CardHeader>
          <CardTitle>Erreurs et réponses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {exam.answers && exam.answers.length > 0 ? (
            exam.answers.map((ans, idx) => {
              const q = questionsMap[ans.question_id];
              const selected = q?.options?.find(o => o.id === ans.selected_option_id);
              const correctOpt = q?.options?.find(o => o.is_correct);
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
