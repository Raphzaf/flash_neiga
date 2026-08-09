import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from '../api/axiosConfig';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
    Search, RefreshCw, Users, CreditCard, TrendingUp, Clock, ArrowLeft,
    Trash2, Save, KeyRound, Gift, ShieldAlert,
} from 'lucide-react';

const money = (v, currency = 'ILS') =>
    v == null ? '—' : `${Number(v).toLocaleString('fr-FR')} ${currency === 'ILS' ? '₪' : currency}`;

const date = (v) => (v ? new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—');

function StatCard({ icon: Icon, label, value, hint }) {
    return (
        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
            <CardContent className="p-4">
                <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-sky-100 dark:bg-sky-500/15 text-sky-600 dark:text-sky-300 flex items-center justify-center shrink-0">
                        <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                        <div className="text-xs text-slate-500 dark:text-slate-400 truncate">{label}</div>
                        <div className="text-xl font-bold text-slate-900 dark:text-white">{value}</div>
                        {hint && <div className="text-[11px] text-slate-400">{hint}</div>}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

function SubscriptionBadge({ sub }) {
    if (!sub) return <Badge variant="outline">Aucun abonnement</Badge>;
    if (sub.is_active) {
        return (
            <Badge className="bg-emerald-500 hover:bg-emerald-500 text-white">
                {sub.plan_name}{sub.days_left != null ? ` · ${sub.days_left} j` : ''}
            </Badge>
        );
    }
    return <Badge variant="secondary">{sub.plan_name} · {sub.status === 'cancelled' ? 'résilié' : 'expiré'}</Badge>;
}

export default function AdminCRM() {
    const [forbidden, setForbidden] = useState(false);
    const [stats, setStats] = useState(null);
    const [statsLoading, setStatsLoading] = useState(true);

    const [users, setUsers] = useState([]);
    const [usersTotal, setUsersTotal] = useState(0);
    const [usersLoading, setUsersLoading] = useState(false);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const LIMIT = 50;

    const [plans, setPlans] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [txLoading, setTxLoading] = useState(false);

    // Fiche élève
    const [detail, setDetail] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [editForm, setEditForm] = useState({ first_name: '', last_name: '', email: '' });
    const [grantPlan, setGrantPlan] = useState('');
    const [grantDays, setGrantDays] = useState('');
    const [newPassword, setNewPassword] = useState('');

    const handleError = useCallback((error, fallback) => {
        if (error?.response?.status === 403) {
            setForbidden(true);
            return;
        }
        toast.error(error?.response?.data?.detail || fallback);
    }, []);

    const fetchStats = useCallback(async () => {
        setStatsLoading(true);
        try {
            const { data } = await axios.get('/api/admin/crm/stats');
            setStats(data);
        } catch (error) {
            handleError(error, 'Impossible de charger les indicateurs');
        } finally {
            setStatsLoading(false);
        }
    }, [handleError]);

    const fetchUsers = useCallback(async (nextOffset = 0) => {
        setUsersLoading(true);
        try {
            const { data } = await axios.get('/api/admin/crm/users', {
                params: { search: search || undefined, status: statusFilter, limit: LIMIT, offset: nextOffset },
            });
            setUsers(data.items || []);
            setUsersTotal(data.total || 0);
            setHasMore(!!data.has_more);
            setOffset(nextOffset);
        } catch (error) {
            handleError(error, 'Impossible de charger les comptes');
        } finally {
            setUsersLoading(false);
        }
    }, [search, statusFilter, handleError]);

    const fetchTransactions = useCallback(async () => {
        setTxLoading(true);
        try {
            const { data } = await axios.get('/api/admin/crm/transactions', { params: { limit: 100 } });
            setTransactions(data.items || []);
        } catch (error) {
            handleError(error, 'Impossible de charger les paiements');
        } finally {
            setTxLoading(false);
        }
    }, [handleError]);

    useEffect(() => {
        fetchStats();
        fetchUsers(0);
        axios.get('/api/admin/crm/plans')
            .then(({ data }) => setPlans(data.plans || []))
            .catch(() => { /* le sélecteur reste vide, non bloquant */ });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const openUser = async (userId) => {
        setDetailLoading(true);
        setDetail({ id: userId });
        try {
            const { data } = await axios.get(`/api/admin/crm/users/${userId}`);
            setDetail(data);
            setEditForm({
                first_name: data.first_name || '',
                last_name: data.last_name || '',
                email: data.email || '',
            });
            setGrantPlan('');
            setGrantDays('');
            setNewPassword('');
        } catch (error) {
            setDetail(null);
            handleError(error, 'Impossible de charger la fiche');
        } finally {
            setDetailLoading(false);
        }
    };

    const saveUser = async () => {
        try {
            await axios.patch(`/api/admin/crm/users/${detail.id}`, editForm);
            toast.success('Fiche mise à jour');
            await openUser(detail.id);
            fetchUsers(offset);
        } catch (error) {
            handleError(error, 'Mise à jour impossible');
        }
    };

    const grantSubscription = async (startNow) => {
        if (!grantPlan) {
            toast.error('Choisis une formule');
            return;
        }
        try {
            const { data } = await axios.post(`/api/admin/crm/users/${detail.id}/subscriptions`, {
                plan_id: grantPlan,
                duration_days: grantDays ? Number(grantDays) : undefined,
                start_now: startNow,
            });
            toast.success(data.status === 'extended' ? 'Abonnement prolongé' : 'Abonnement accordé');
            await openUser(detail.id);
            fetchUsers(offset);
            fetchStats();
        } catch (error) {
            handleError(error, "Impossible d'accorder l'abonnement");
        }
    };

    const cancelSubscription = async (subId) => {
        if (!window.confirm("Résilier cet abonnement ? L'accès reste valable jusqu'à la date de fin.")) return;
        try {
            await axios.post(`/api/admin/crm/subscriptions/${subId}/cancel`);
            toast.success('Abonnement résilié');
            await openUser(detail.id);
            fetchUsers(offset);
            fetchStats();
        } catch (error) {
            handleError(error, 'Résiliation impossible');
        }
    };

    const resetPassword = async () => {
        if (newPassword.length < 6) {
            toast.error('6 caractères minimum');
            return;
        }
        try {
            await axios.post(`/api/admin/crm/users/${detail.id}/password`, { new_password: newPassword });
            toast.success('Mot de passe réinitialisé');
            setNewPassword('');
        } catch (error) {
            handleError(error, 'Réinitialisation impossible');
        }
    };

    const deleteUser = async () => {
        if (!window.confirm(`Supprimer définitivement le compte ${detail.email} et ses données ? Cette action est irréversible.`)) return;
        try {
            await axios.delete(`/api/admin/crm/users/${detail.id}`);
            toast.success('Compte supprimé');
            setDetail(null);
            fetchUsers(0);
            fetchStats();
        } catch (error) {
            handleError(error, 'Suppression impossible');
        }
    };

    if (forbidden) {
        return (
            <div className="max-w-2xl mx-auto p-6 min-h-screen flex items-center">
                <Card className="w-full bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                            <ShieldAlert className="h-5 w-5 text-amber-500" /> Accès réservé aux administrateurs
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm text-slate-600 dark:text-slate-300">
                        <p>
                            Ce CRM contient des données personnelles : il n'est accessible qu'aux comptes déclarés dans la
                            variable d'environnement <code className="font-mono">ADMIN_EMAILS</code> du backend.
                        </p>
                        <Link to="/admin"><Button variant="outline"><ArrowLeft className="h-4 w-4 mr-2" /> Retour au CMS</Button></Link>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto p-6 min-h-screen">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white">CRM — Comptes & Abonnements</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Gère les élèves, leurs abonnements et leurs paiements.</p>
                </div>
                <div className="flex gap-2">
                    <Link to="/admin">
                        <Button variant="outline"><ArrowLeft className="h-4 w-4 mr-2" /> CMS</Button>
                    </Link>
                    <Button variant="outline" onClick={() => { fetchStats(); fetchUsers(offset); }}>
                        <RefreshCw className="h-4 w-4 mr-2" /> Actualiser
                    </Button>
                </div>
            </div>

            {/* Indicateurs */}
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-8">
                {statsLoading || !stats ? (
                    Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-[76px] w-full rounded-xl" />)
                ) : (
                    <>
                        <StatCard icon={Users} label="Comptes" value={stats.total_users} hint={`+${stats.new_users_30d} sur 30 j`} />
                        <StatCard icon={TrendingUp} label="Abonnements actifs" value={stats.active_subscriptions} />
                        <StatCard icon={CreditCard} label="Encaissé (total)" value={money(stats.revenue_total)} />
                        <StatCard icon={CreditCard} label="Encaissé (30 j)" value={money(stats.revenue_30d)} />
                        <StatCard icon={Clock} label="Paiements en attente" value={stats.pending_transactions} />
                    </>
                )}
            </div>

            <Tabs defaultValue="users" onValueChange={(v) => { if (v === 'transactions' && !transactions.length) fetchTransactions(); }}>
                <TabsList className="grid w-full grid-cols-3 mb-6">
                    <TabsTrigger value="users">Élèves <Badge variant="outline" className="ml-2">{usersTotal}</Badge></TabsTrigger>
                    <TabsTrigger value="transactions">Paiements</TabsTrigger>
                    <TabsTrigger value="plans">Formules actives</TabsTrigger>
                </TabsList>

                {/* ===== Élèves ===== */}
                <TabsContent value="users">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader>
                            <CardTitle className="text-slate-900 dark:text-white">Comptes élèves</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-wrap gap-2">
                                <div className="relative flex-1 min-w-[220px]">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                    <Input
                                        className="pl-9"
                                        placeholder="Rechercher un email, un prénom, un nom…"
                                        value={search}
                                        onChange={(e) => setSearch(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && fetchUsers(0)}
                                    />
                                </div>
                                <Select value={statusFilter} onValueChange={setStatusFilter}>
                                    <SelectTrigger className="w-[190px]"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">Tous les comptes</SelectItem>
                                        <SelectItem value="active">Abonnement actif</SelectItem>
                                        <SelectItem value="inactive">Sans abonnement</SelectItem>
                                    </SelectContent>
                                </Select>
                                <Button onClick={() => fetchUsers(0)}><Search className="h-4 w-4 mr-2" /> Rechercher</Button>
                            </div>

                            {usersLoading ? (
                                <div className="space-y-2">
                                    {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14 w-full rounded-lg" />)}
                                </div>
                            ) : users.length === 0 ? (
                                <p className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">Aucun compte trouvé.</p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                                                <th className="py-2 pr-3">Élève</th>
                                                <th className="py-2 pr-3">Abonnement</th>
                                                <th className="py-2 pr-3">Payé</th>
                                                <th className="py-2 pr-3">Séries</th>
                                                <th className="py-2 pr-3">Erreurs</th>
                                                <th className="py-2 pr-3">Inscrit le</th>
                                                <th className="py-2" />
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {users.map((u) => (
                                                <tr key={u.id} className="border-b border-slate-100 dark:border-slate-700/50">
                                                    <td className="py-2 pr-3">
                                                        <div className="font-medium text-slate-900 dark:text-white">
                                                            {[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}
                                                        </div>
                                                        <div className="text-xs text-slate-500 dark:text-slate-400">{u.email}</div>
                                                    </td>
                                                    <td className="py-2 pr-3"><SubscriptionBadge sub={u.subscription} /></td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{money(u.total_spent)}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{u.exam_sessions}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{u.mistakes}</td>
                                                    <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">{date(u.created_at)}</td>
                                                    <td className="py-2 text-right">
                                                        <Button size="sm" variant="outline" onClick={() => openUser(u.id)}>Gérer</Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            <div className="flex items-center justify-between pt-2">
                                <span className="text-xs text-slate-500 dark:text-slate-400">
                                    {users.length} affiché(s) sur {usersTotal}
                                </span>
                                <div className="flex gap-2">
                                    <Button size="sm" variant="outline" disabled={offset === 0 || usersLoading}
                                        onClick={() => fetchUsers(Math.max(0, offset - LIMIT))}>Précédent</Button>
                                    <Button size="sm" variant="outline" disabled={!hasMore || usersLoading}
                                        onClick={() => fetchUsers(offset + LIMIT)}>Suivant</Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ===== Paiements ===== */}
                <TabsContent value="transactions">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <CardTitle className="text-slate-900 dark:text-white">Historique des paiements</CardTitle>
                            <Button size="sm" variant="outline" onClick={fetchTransactions}>
                                <RefreshCw className="h-4 w-4 mr-2" /> Actualiser
                            </Button>
                        </CardHeader>
                        <CardContent>
                            {txLoading ? (
                                <div className="space-y-2">
                                    {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
                                </div>
                            ) : transactions.length === 0 ? (
                                <p className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">Aucun paiement enregistré.</p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                                                <th className="py-2 pr-3">Date</th>
                                                <th className="py-2 pr-3">Élève</th>
                                                <th className="py-2 pr-3">Formule</th>
                                                <th className="py-2 pr-3">Montant</th>
                                                <th className="py-2 pr-3">Statut</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {transactions.map((t) => (
                                                <tr key={t.id} className="border-b border-slate-100 dark:border-slate-700/50">
                                                    <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">{date(t.created_at)}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{t.user_email || '—'}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{t.plan_name}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{money(t.amount, t.currency)}</td>
                                                    <td className="py-2 pr-3">
                                                        <Badge variant={t.status === 'completed' ? 'default' : 'secondary'}>{t.status}</Badge>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ===== Répartition ===== */}
                <TabsContent value="plans">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader><CardTitle className="text-slate-900 dark:text-white">Abonnements actifs par formule</CardTitle></CardHeader>
                        <CardContent>
                            {!stats ? (
                                <Skeleton className="h-24 w-full rounded-lg" />
                            ) : (stats.active_by_plan || []).length === 0 ? (
                                <p className="text-sm text-slate-500 dark:text-slate-400 py-6 text-center">Aucun abonnement actif.</p>
                            ) : (
                                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                    {stats.active_by_plan.map((p) => (
                                        <div key={p.plan_id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
                                            <div className="text-sm text-slate-600 dark:text-slate-300">{p.plan_name}</div>
                                            <div className="text-2xl font-bold text-slate-900 dark:text-white">{p.count}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* ===== Fiche élève ===== */}
            <Dialog open={!!detail} onOpenChange={(open) => !open && setDetail(null)}>
                <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>{detail?.email || 'Fiche élève'}</DialogTitle>
                        <DialogDescription>
                            {detailLoading ? 'Chargement…' : `Inscrit le ${date(detail?.created_at)} · ${money(detail?.total_spent)} encaissés`}
                        </DialogDescription>
                    </DialogHeader>

                    {detailLoading || !detail?.email ? (
                        <div className="space-y-3">
                            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
                        </div>
                    ) : (
                        <div className="space-y-6">
                            {/* Identité */}
                            <section className="space-y-3">
                                <h3 className="font-semibold text-slate-900 dark:text-white">Identité</h3>
                                <div className="grid sm:grid-cols-3 gap-2">
                                    <Input placeholder="Prénom" value={editForm.first_name}
                                        onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })} />
                                    <Input placeholder="Nom" value={editForm.last_name}
                                        onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })} />
                                    <Input placeholder="Email" type="email" value={editForm.email}
                                        onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                                </div>
                                <Button size="sm" onClick={saveUser}><Save className="h-4 w-4 mr-2" /> Enregistrer</Button>
                            </section>

                            {/* Progression */}
                            <section>
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Progression</h3>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                                    {[
                                        ['Séries', detail.activity.exam_sessions],
                                        ['Terminées', detail.activity.completed_sessions],
                                        ['Score moyen', detail.activity.average_score ?? '—'],
                                        ['Erreurs maîtrisées', `${detail.activity.mistakes_mastered}/${detail.activity.mistakes_total}`],
                                    ].map(([label, value]) => (
                                        <div key={label} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                                            <div className="text-[11px] text-slate-500 dark:text-slate-400">{label}</div>
                                            <div className="text-lg font-bold text-slate-900 dark:text-white">{value}</div>
                                        </div>
                                    ))}
                                </div>
                            </section>

                            {/* Abonnements */}
                            <section className="space-y-3">
                                <h3 className="font-semibold text-slate-900 dark:text-white">Abonnements</h3>
                                {detail.subscriptions.length === 0 ? (
                                    <p className="text-sm text-slate-500 dark:text-slate-400">Aucun abonnement.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {detail.subscriptions.map((s) => (
                                            <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <SubscriptionBadge sub={s} />
                                                    </div>
                                                    <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                                        {date(s.start_date)} → {date(s.end_date)}
                                                    </div>
                                                </div>
                                                {s.is_active && (
                                                    <Button size="sm" variant="outline" onClick={() => cancelSubscription(s.id)}>Résilier</Button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}

                                <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-600 p-3 space-y-2">
                                    <div className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
                                        <Gift className="h-4 w-4" /> Accorder / prolonger un abonnement
                                    </div>
                                    <div className="grid sm:grid-cols-2 gap-2">
                                        <Select value={grantPlan} onValueChange={setGrantPlan}>
                                            <SelectTrigger><SelectValue placeholder="Choisir une formule" /></SelectTrigger>
                                            <SelectContent>
                                                {plans.map((p) => (
                                                    <SelectItem key={p.plan_id} value={p.plan_id}>
                                                        {p.name} — {money(p.amount, p.currency)}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        <Input type="number" min="1" placeholder="Durée en jours (défaut : durée du plan)"
                                            value={grantDays} onChange={(e) => setGrantDays(e.target.value)} />
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Button size="sm" onClick={() => grantSubscription(true)}>Nouvel abonnement</Button>
                                        <Button size="sm" variant="outline" onClick={() => grantSubscription(false)}>
                                            Prolonger l'abonnement actif
                                        </Button>
                                    </div>
                                </div>
                            </section>

                            {/* Paiements */}
                            <section>
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Paiements</h3>
                                {detail.transactions.length === 0 ? (
                                    <p className="text-sm text-slate-500 dark:text-slate-400">Aucun paiement.</p>
                                ) : (
                                    <ul className="space-y-1 text-sm">
                                        {detail.transactions.map((t) => (
                                            <li key={t.id} className="flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-700/50 py-1.5">
                                                <span className="text-slate-500 dark:text-slate-400">{date(t.created_at)}</span>
                                                <span className="text-slate-700 dark:text-slate-200">{t.plan_name}</span>
                                                <span className="text-slate-700 dark:text-slate-200">{money(t.amount, t.currency)}</span>
                                                <Badge variant={t.status === 'completed' ? 'default' : 'secondary'}>{t.status}</Badge>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </section>

                            {/* Actions sensibles */}
                            <section className="space-y-3">
                                <h3 className="font-semibold text-slate-900 dark:text-white">Actions sur le compte</h3>
                                <div className="flex flex-wrap gap-2">
                                    <Input className="max-w-xs" type="password" placeholder="Nouveau mot de passe"
                                        value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                                    <Button size="sm" variant="outline" onClick={resetPassword}>
                                        <KeyRound className="h-4 w-4 mr-2" /> Réinitialiser
                                    </Button>
                                </div>
                            </section>
                        </div>
                    )}

                    <DialogFooter className="flex-row justify-between sm:justify-between">
                        <Button variant="destructive" size="sm" onClick={deleteUser} disabled={!detail?.email}>
                            <Trash2 className="h-4 w-4 mr-2" /> Supprimer le compte
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setDetail(null)}>Fermer</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
