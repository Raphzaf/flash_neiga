import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { ArrowLeft, User as UserIcon, Mail, CalendarDays, CreditCard, Save, LogOut, ArrowUpRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('fr-FR') : '—');

export default function Profile() {
    const { logout } = useAuth();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [profile, setProfile] = useState(null);
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [saving, setSaving] = useState(false);
    const [confirmCancel, setConfirmCancel] = useState(false);
    const [cancelling, setCancelling] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/profile');
            setProfile(res.data);
            setFirstName(res.data.first_name || '');
            setLastName(res.data.last_name || '');
        } catch (e) {
            toast.error('Impossible de charger ton profil.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const saveName = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await axios.patch('/api/profile', { first_name: firstName, last_name: lastName });
            toast.success('Profil mis à jour ✅');
            setProfile((p) => ({ ...p, first_name: firstName, last_name: lastName }));
        } catch (err) {
            toast.error('La mise à jour a échoué.');
        } finally {
            setSaving(false);
        }
    };

    const doCancel = async () => {
        setCancelling(true);
        try {
            const res = await axios.post('/api/profile/subscription/cancel');
            toast.success(res.data.message || 'Abonnement résilié.');
            setConfirmCancel(false);
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'La résiliation a échoué.');
        } finally {
            setCancelling(false);
        }
    };

    const sub = profile?.subscription;

    return (
        <div className="min-h-screen pb-16">
            <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-30 p-4">
                <div className="max-w-3xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link to="/">
                            <Button variant="ghost" size="icon" aria-label="Retour à l'accueil">
                                <ArrowLeft className="h-5 w-5" />
                            </Button>
                        </Link>
                        <h1 className="text-xl font-heading font-bold text-slate-900 dark:text-white">Mon profil</h1>
                    </div>
                    <Button variant="ghost" size="sm" onClick={logout} className="gap-2">
                        <LogOut className="h-4 w-4" /> Déconnexion
                    </Button>
                </div>
            </header>

            <main className="max-w-3xl mx-auto p-4 space-y-6 mt-2">
                {loading ? (
                    <div className="py-16 text-center text-slate-600 dark:text-slate-300 flex items-center justify-center gap-2">
                        <Loader2 className="h-5 w-5 animate-spin" /> Chargement…
                    </div>
                ) : (
                    <>
                        {/* Infos personnelles */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <UserIcon className="h-5 w-5 text-sky-600" /> Informations personnelles
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={saveName} className="space-y-4">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <Label htmlFor="firstName">Prénom</Label>
                                            <Input id="firstName" value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="Ton prénom" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="lastName">Nom</Label>
                                            <Input id="lastName" value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Ton nom" />
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                        <Mail className="h-4 w-4" /> {profile?.email}
                                        <span className="text-xs text-slate-400">(l'email ne peut pas être modifié)</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                        <CalendarDays className="h-4 w-4" /> Membre depuis le {fmtDate(profile?.created_at)}
                                    </div>
                                    <Button type="submit" disabled={saving} className="gap-2">
                                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                        Enregistrer
                                    </Button>
                                </form>
                            </CardContent>
                        </Card>

                        {/* Abonnement */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <CreditCard className="h-5 w-5 text-sky-600" /> Mon abonnement
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {sub ? (
                                    <>
                                        <div className="flex flex-wrap items-center justify-between gap-3">
                                            <div>
                                                <div className="font-semibold text-slate-900 dark:text-white">{sub.plan_name}</div>
                                                {sub.plan_description && (
                                                    <div className="text-sm text-slate-600 dark:text-slate-300">{sub.plan_description}</div>
                                                )}
                                            </div>
                                            {sub.is_active ? (
                                                <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200 hover:bg-emerald-100">Actif</Badge>
                                            ) : (
                                                <Badge variant="secondary">{sub.status === 'cancelled' ? 'Résilié' : 'Inactif'}</Badge>
                                            )}
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 text-sm">
                                            <div><span className="text-slate-500 dark:text-slate-400">Début : </span>{fmtDate(sub.start_date)}</div>
                                            <div><span className="text-slate-500 dark:text-slate-400">Fin : </span>{fmtDate(sub.end_date)}</div>
                                            {sub.amount != null && (
                                                <div><span className="text-slate-500 dark:text-slate-400">Prix : </span>{sub.amount} {sub.currency}</div>
                                            )}
                                            {sub.canceled_at && (
                                                <div><span className="text-slate-500 dark:text-slate-400">Résilié le : </span>{fmtDate(sub.canceled_at)}</div>
                                            )}
                                        </div>
                                    </>
                                ) : (
                                    <p className="text-slate-600 dark:text-slate-300">Tu n'as pas d'abonnement actif pour le moment.</p>
                                )}

                                <div className="flex flex-wrap gap-3 pt-2">
                                    <Link to="/pricing">
                                        <Button className="gap-2">
                                            <ArrowUpRight className="h-4 w-4" />
                                            {sub && sub.is_active ? 'Changer / améliorer mon abonnement' : "Voir les abonnements"}
                                        </Button>
                                    </Link>
                                    {sub && sub.is_active && (
                                        <Button variant="outline" onClick={() => setConfirmCancel(true)} className="text-red-600 border-red-300 hover:bg-red-50 dark:hover:bg-red-950/30">
                                            Résilier mon abonnement
                                        </Button>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </>
                )}
            </main>

            {/* Confirmation de résiliation */}
            <Dialog open={confirmCancel} onOpenChange={setConfirmCancel}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Résilier ton abonnement ?</DialogTitle>
                        <DialogDescription>
                            Ton abonnement ne sera pas renouvelé. Tu gardes l'accès à toutes les fonctionnalités
                            jusqu'à la date de fin{sub?.end_date ? ` (${fmtDate(sub.end_date)})` : ''}.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setConfirmCancel(false)}>Annuler</Button>
                        <Button variant="destructive" onClick={doCancel} disabled={cancelling} className="gap-2">
                            {cancelling && <Loader2 className="h-4 w-4 animate-spin" />}
                            Confirmer la résiliation
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
