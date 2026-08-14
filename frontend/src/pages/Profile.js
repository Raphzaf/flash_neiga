import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
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
import {
    ArrowLeft, User as UserIcon, Mail, CalendarDays, CreditCard, Save, LogOut,
    ArrowUpRight, Loader2, Lock, Receipt, Eye, EyeOff,
} from 'lucide-react';
import { toast } from 'sonner';

const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('fr-FR') : '—');
const fmtPrice = (amount, currency = 'ILS') =>
    amount == null ? '—' : `${Number(amount).toLocaleString('fr-FR')} ${currency === 'ILS' ? '₪' : currency}`;

/** Champ mot de passe avec bascule d'affichage, réutilisé dans les deux formulaires. */
function PasswordInput({ id, value, onChange, placeholder, autoComplete }) {
    const [visible, setVisible] = useState(false);
    return (
        <div className="relative">
            <Input
                id={id}
                type={visible ? 'text' : 'password'}
                className="pr-10"
                value={value}
                onChange={onChange}
                placeholder={placeholder}
                autoComplete={autoComplete}
            />
            <button
                type="button"
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
                {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
        </div>
    );
}

export default function Profile() {
    const { logout, refreshSubscription } = useAuth();
    const [loading, setLoading] = useState(true);
    const [profile, setProfile] = useState(null);
    const [payments, setPayments] = useState([]);

    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [saving, setSaving] = useState(false);

    const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });
    const [changingPassword, setChangingPassword] = useState(false);

    const [emailForm, setEmailForm] = useState({ email: '', password: '' });
    const [changingEmail, setChangingEmail] = useState(false);

    const [confirmCancel, setConfirmCancel] = useState(false);
    const [cancelling, setCancelling] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [profileRes, paymentsRes] = await Promise.all([
                axios.get('/api/profile'),
                axios.get('/api/profile/payments').catch(() => ({ data: { items: [] } })),
            ]);
            setProfile(profileRes.data);
            setFirstName(profileRes.data.first_name || '');
            setLastName(profileRes.data.last_name || '');
            setPayments(paymentsRes.data.items || []);
        } catch (e) {
            toast.error('Impossible de charger ton profil.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const saveName = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await axios.patch('/api/profile', { first_name: firstName, last_name: lastName });
            toast.success('Profil mis à jour');
            setProfile((p) => ({ ...p, first_name: firstName, last_name: lastName }));
        } catch (err) {
            toast.error(err.response?.data?.detail || 'La mise à jour a échoué.');
        } finally {
            setSaving(false);
        }
    };

    const changePassword = async (e) => {
        e.preventDefault();
        if (passwords.next.length < 6) {
            toast.error('Le nouveau mot de passe doit contenir au moins 6 caractères.');
            return;
        }
        if (passwords.next !== passwords.confirm) {
            toast.error('Les deux nouveaux mots de passe ne correspondent pas.');
            return;
        }
        setChangingPassword(true);
        try {
            await axios.post('/api/profile/password', {
                current_password: passwords.current,
                new_password: passwords.next,
            });
            toast.success('Mot de passe modifié');
            setPasswords({ current: '', next: '', confirm: '' });
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Le changement a échoué.');
        } finally {
            setChangingPassword(false);
        }
    };

    const changeEmail = async (e) => {
        e.preventDefault();
        setChangingEmail(true);
        try {
            const { data } = await axios.post('/api/profile/email', {
                new_email: emailForm.email.trim(),
                current_password: emailForm.password,
            });
            toast.success('Email de connexion mis à jour');
            setProfile((p) => ({ ...p, email: data.email }));
            setEmailForm({ email: '', password: '' });
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Le changement a échoué.');
        } finally {
            setChangingEmail(false);
        }
    };

    const doCancel = async () => {
        setCancelling(true);
        try {
            const res = await axios.post('/api/profile/subscription/cancel');
            toast.success(res.data.message || 'Abonnement résilié.');
            setConfirmCancel(false);
            await load();
            // L'état global doit suivre : l'accès reste ouvert jusqu'à la date de fin.
            refreshSubscription();
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
                        <h1 className="text-xl font-heading font-bold text-slate-900 dark:text-white">Mon compte</h1>
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
                        {/* ===== Informations personnelles ===== */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <UserIcon className="h-5 w-5 text-primary" /> Informations personnelles
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
                                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
                                        <span className="flex items-center gap-2"><Mail className="h-4 w-4" /> {profile?.email}</span>
                                        <span className="flex items-center gap-2">
                                            <CalendarDays className="h-4 w-4" /> Membre depuis le {fmtDate(profile?.created_at)}
                                        </span>
                                    </div>
                                    <Button type="submit" disabled={saving} className="gap-2" data-testid="profile-save-name">
                                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                        Enregistrer
                                    </Button>
                                </form>
                            </CardContent>
                        </Card>

                        {/* ===== Abonnement ===== */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <CreditCard className="h-5 w-5 text-primary" /> Mon abonnement
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {sub ? (
                                    <>
                                        <div className="flex flex-wrap items-center justify-between gap-3">
                                            <div>
                                                <div className="font-semibold text-slate-900 dark:text-white">{sub.plan_name}</div>
                                                {sub.days_left != null && sub.is_active && (
                                                    <div className="text-sm text-slate-600 dark:text-slate-300">
                                                        Il te reste {sub.days_left} jour{sub.days_left > 1 ? 's' : ''} d'accès.
                                                    </div>
                                                )}
                                            </div>
                                            {sub.is_active ? (
                                                <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200 hover:bg-emerald-100">
                                                    {sub.status === 'cancelled' ? 'Actif jusqu\'à la fin' : 'Actif'}
                                                </Badge>
                                            ) : (
                                                <Badge variant="secondary">Terminé</Badge>
                                            )}
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 text-sm">
                                            <div><span className="text-slate-500 dark:text-slate-400">Début : </span>{fmtDate(sub.start_date)}</div>
                                            <div><span className="text-slate-500 dark:text-slate-400">Fin : </span>{fmtDate(sub.end_date)}</div>
                                            {sub.canceled_at && (
                                                <div className="col-span-2 text-slate-500 dark:text-slate-400">
                                                    Résilié le {fmtDate(sub.canceled_at)} — ton accès reste ouvert jusqu'au {fmtDate(sub.end_date)}.
                                                </div>
                                            )}
                                        </div>
                                    </>
                                ) : (
                                    <p className="text-slate-600 dark:text-slate-300">Tu n'as pas encore d'abonnement.</p>
                                )}

                                <div className="flex flex-wrap gap-3 pt-1">
                                    <Button asChild className="gap-2">
                                        <Link to="/subscribe">
                                            <ArrowUpRight className="h-4 w-4" />
                                            {sub?.is_active ? 'Changer de formule' : 'Choisir une formule'}
                                        </Link>
                                    </Button>
                                    {sub?.is_active && sub.status !== 'cancelled' && (
                                        <Button
                                            variant="outline"
                                            onClick={() => setConfirmCancel(true)}
                                            className="text-red-600 border-red-300 hover:bg-red-50 dark:hover:bg-red-950/30"
                                            data-testid="profile-cancel-subscription"
                                        >
                                            Résilier mon abonnement
                                        </Button>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* ===== Connexion et sécurité ===== */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <Lock className="h-5 w-5 text-primary" /> Connexion et sécurité
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-8">
                                <form onSubmit={changePassword} className="space-y-3">
                                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                                        Changer mon mot de passe
                                    </h3>
                                    <div className="space-y-2">
                                        <Label htmlFor="currentPassword">Mot de passe actuel</Label>
                                        <PasswordInput
                                            id="currentPassword"
                                            autoComplete="current-password"
                                            value={passwords.current}
                                            onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))}
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <Label htmlFor="newPassword">Nouveau mot de passe</Label>
                                            <PasswordInput
                                                id="newPassword"
                                                autoComplete="new-password"
                                                placeholder="Au moins 6 caractères"
                                                value={passwords.next}
                                                onChange={(e) => setPasswords((p) => ({ ...p, next: e.target.value }))}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="confirmPassword">Confirmer</Label>
                                            <PasswordInput
                                                id="confirmPassword"
                                                autoComplete="new-password"
                                                value={passwords.confirm}
                                                onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
                                            />
                                        </div>
                                    </div>
                                    <Button
                                        type="submit"
                                        disabled={changingPassword || !passwords.current || !passwords.next}
                                        className="gap-2"
                                        data-testid="profile-change-password"
                                    >
                                        {changingPassword && <Loader2 className="h-4 w-4 animate-spin" />}
                                        Modifier le mot de passe
                                    </Button>
                                </form>

                                <form onSubmit={changeEmail} className="space-y-3 border-t border-slate-200 dark:border-slate-700 pt-6">
                                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                                        Changer mon email de connexion
                                    </h3>
                                    <p className="text-sm text-slate-500 dark:text-slate-400">
                                        Actuellement : {profile?.email}
                                    </p>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <Label htmlFor="newEmail">Nouvel email</Label>
                                            <Input
                                                id="newEmail"
                                                type="email"
                                                inputMode="email"
                                                autoComplete="email"
                                                placeholder="nom@exemple.com"
                                                value={emailForm.email}
                                                onChange={(e) => setEmailForm((f) => ({ ...f, email: e.target.value }))}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="emailPassword">Ton mot de passe</Label>
                                            <PasswordInput
                                                id="emailPassword"
                                                autoComplete="current-password"
                                                value={emailForm.password}
                                                onChange={(e) => setEmailForm((f) => ({ ...f, password: e.target.value }))}
                                            />
                                        </div>
                                    </div>
                                    <Button
                                        type="submit"
                                        variant="outline"
                                        disabled={changingEmail || !emailForm.email || !emailForm.password}
                                        className="gap-2"
                                        data-testid="profile-change-email"
                                    >
                                        {changingEmail && <Loader2 className="h-4 w-4 animate-spin" />}
                                        Modifier l'email
                                    </Button>
                                </form>
                            </CardContent>
                        </Card>

                        {/* ===== Paiements ===== */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <Receipt className="h-5 w-5 text-primary" /> Mes paiements
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {payments.length === 0 ? (
                                    <p className="text-slate-600 dark:text-slate-300">Aucun paiement pour le moment.</p>
                                ) : (
                                    <ul className="divide-y divide-slate-200 dark:divide-slate-700">
                                        {payments.map((p) => (
                                            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
                                                <div>
                                                    <div className="text-sm font-medium text-slate-900 dark:text-white">{p.plan_name}</div>
                                                    <div className="text-xs text-slate-500 dark:text-slate-400">
                                                        {fmtDate(p.paid_at)} · référence {p.reference}
                                                    </div>
                                                </div>
                                                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                                                    {fmtPrice(p.amount, p.currency)}
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                )}
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
