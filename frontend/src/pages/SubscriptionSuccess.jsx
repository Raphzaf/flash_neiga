import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function SubscriptionSuccess() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkPayment = async () => {
      try {
        // Simulate short verification delay; webhook would normally confirm
        setTimeout(() => {
          setLoading(false);
        }, 1500);
      } catch (error) {
        console.error('Erreur:', error);
        setLoading(false);
      }
    };

    checkPayment();
  }, []);

  if (loading) {
    return <div className="text-center p-4">Vérification du paiement...</div>;
  }

  return (
    <div className="success-container p-6">
      <div className="success-card max-w-md mx-auto text-center border rounded-lg p-6">
        <h1 className="text-2xl font-bold mb-2">✓ Paiement Réussi !</h1>
        <p className="mb-2">Ton abonnement est maintenant actif.</p>
        <p className="text-muted mb-4">Tu peux accéder à tous tes contenus.</p>
        <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
          Accéder à mon abonnement
        </button>
      </div>
    </div>
  );
}
