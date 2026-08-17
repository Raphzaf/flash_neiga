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
    Trash2, Save, KeyRound, ShieldAlert, Ticket, Plus, Power, UserPlus,
    AlertTriangle,
} from 'lucide-react';

const money = (v, currency = 'ILS') =>
    v == null ? '—' : `${Number(v).toLocaleString('fr-FR')} ${currency === 'ILS' ? '₪' : currency}`;

const date = (v) => (v ? new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—');

/**
 * Pourquoi cet élève n'a-t-il pas d'abonnement ?
 *
 * La question revient à chaque fois qu'un compte apparaît « sans abonnement ».
 * La réponse est déjà dans ses paiements : on la formule au lieu de laisser
 * l'équipe la deviner.
 */
function explainNoSubscription(transactions = []) {
    if (!transactions.length) {
        return "Aucun paiement engagé : le compte a été créé, mais le parcours s'est arrêté avant le paiement.";
    }
    const pending = transactions.find((t) => t.status === 'pending');
    if (pending) {
        return `Paiement lancé le ${date(pending.created_at)} et jamais confirmé : abandon en cours de route, `
            + 'refus de la banque, ou notification de paiement non reçue par le serveur.';
    }
    const failed = transactions.find((t) => t.status === 'failed');
    if (failed) {
        return `Dernier paiement refusé le ${date(failed.created_at)}. L'élève peut réessayer depuis son espace.`;
    }
    const completed = transactions.find((t) => t.status === 'completed');
    if (completed) {
        return `Un paiement du ${date(completed.created_at)} est encaissé sans abonnement ouvert : `
            + 'à signaler, cela ne devrait pas arriver.';
    }
    return null;
}

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
    // Rattachement d'un paiement encaissé sans compte
    const [attachTx, setAttachTx] = useState(null);
    const [attachForm, setAttachForm] = useState({ email: '', first_name: '', last_name: '', phone: '' });
    const [attachSaving, setAttachSaving] = useState(false);
    const [attachResult, setAttachResult] = useState(null);

    // Codes promo
    const [promos, setPromos] = useState([]);
    const [promoLoading, setPromoLoading] = useState(false);
    const [promoStats, setPromoStats] = useState({ redemptions: 0, granted: 0 });
    const [newPromo, setNewPromo] = useState({
        code: '', description: '', discount_type: 'percent', discount_value: '',
        plan_ids: [], max_uses: '', max_uses_per_user: 1, valid_until: '',
    });

    // Fiche élève
    const [detail, setDetail] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [editForm, setEditForm] = useState({ first_name: '', last_name: '', email: '', phone: '' });
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

    // Les critères sont passés en arguments (et non lus dans la closure) pour que
    // ce chargeur reste stable : le premier chargement ne se relance pas à chaque
    // frappe dans le champ de recherche.
    const loadUsers = useCallback(async (nextOffset, searchTerm, status) => {
        setUsersLoading(true);
        try {
            const { data } = await axios.get('/api/admin/crm/users', {
                params: { search: searchTerm || undefined, status, limit: LIMIT, offset: nextOffset },
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
    }, [handleError]);

    const fetchUsers = useCallback(
        (nextOffset = 0) => loadUsers(nextOffset, search, statusFilter),
        [loadUsers, search, statusFilter],
    );

    const loadPromos = useCallback(async () => {
        setPromoLoading(true);
        try {
            const { data } = await axios.get('/api/admin/crm/promo-codes');
            setPromos(data.items || []);
            setPromoStats({ redemptions: data.total_redemptions, granted: data.total_discount_granted });
        } catch (error) {
            handleError(error, 'Impossible de charger les codes promo');
        } finally {
            setPromoLoading(false);
        }
    }, [handleError]);

    const loadPlans = useCallback(async () => {
        try {
            const { data } = await axios.get('/api/admin/crm/plans');
            setPlans(data.plans || []);
        } catch {
            /* le sélecteur reste vide : non bloquant */
        }
    }, []);

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

    // Rattache un paiement encaissé à un compte élève : le compte est créé s'il
    // n'existe pas, et l'abonnement payé est ouvert dans la foulée.
    const attachTransaction = useCallback(async () => {
        if (!attachTx) return;
        setAttachSaving(true);
        try {
            const { data } = await axios.post(
                `/api/admin/crm/transactions/${attachTx.id}/attach`,
                {
                    email: attachForm.email.trim(),
                    first_name: attachForm.first_name.trim() || null,
                    last_name: attachForm.last_name.trim() || null,
                    phone: attachForm.phone.trim() || null,
                },
            );
            setAttachResult(data);
            toast.success('Paiement rattaché et abonnement ouvert');
            fetchTransactions();
            fetchStats();
        } catch (error) {
            handleError(error, 'Impossible de rattacher ce paiement');
        } finally {
            setAttachSaving(false);
        }
    }, [attachTx, attachForm, fetchTransactions, fetchStats, handleError]);

    useEffect(() => {
        fetchStats();
        loadUsers(0, '', 'all');
        loadPlans();
    }, [fetchStats, loadUsers, loadPlans]);

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
                phone: data.phone || '',
            });
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

    const createPromo = async () => {
        if (!newPromo.code.trim()) {
            toast.error('Saisis un code');
            return;
        }
        if (newPromo.discount_type !== 'free' && !Number(newPromo.discount_value)) {
            toast.error('Saisis la valeur de la remise');
            return;
        }
        try {
            await axios.post('/api/admin/crm/promo-codes', {
                code: newPromo.code,
                description: newPromo.description || null,
                discount_type: newPromo.discount_type,
                discount_value: newPromo.discount_type === 'free' ? 0 : Number(newPromo.discount_value),
                plan_ids: newPromo.plan_ids,
                max_uses: newPromo.max_uses ? Number(newPromo.max_uses) : null,
                max_uses_per_user: Number(newPromo.max_uses_per_user) || 1,
                valid_until: newPromo.valid_until ? new Date(newPromo.valid_until).toISOString() : null,
            });
            toast.success('Code promo créé');
            setNewPromo({
                code: '', description: '', discount_type: 'percent', discount_value: '',
                plan_ids: [], max_uses: '', max_uses_per_user: 1, valid_until: '',
            });
            loadPromos();
        } catch (error) {
            handleError(error, 'Création impossible');
        }
    };

    const togglePromo = async (promo) => {
        try {
            await axios.patch(`/api/admin/crm/promo-codes/${promo.id}`, { active: !promo.active });
            toast.success(promo.active ? 'Code désactivé' : 'Code réactivé');
            loadPromos();
        } catch (error) {
            handleError(error, 'Modification impossible');
        }
    };

    const deletePromo = async (promo) => {
        if (!window.confirm(`Supprimer définitivement le code ${promo.code} ?`)) return;
        try {
            await axios.delete(`/api/admin/crm/promo-codes/${promo.id}`);
            toast.success('Code supprimé');
            loadPromos();
        } catch (error) {
            handleError(error, 'Suppression impossible');
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

            <Tabs
                defaultValue="users"
                onValueChange={(v) => {
                    if (v === 'transactions' && !transactions.length) fetchTransactions();
                    if (v === 'promos' && !promos.length) loadPromos();
                }}
            >
                <TabsList className="grid w-full grid-cols-4 mb-6">
                    <TabsTrigger value="users">Élèves <Badge variant="outline" className="ml-2">{usersTotal}</Badge></TabsTrigger>
                    <TabsTrigger value="promos">Codes promo</TabsTrigger>
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
                                        placeholder="Rechercher un email, un prénom, un nom, un téléphone…"
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
                                                        {u.phone && (
                                                            <a href={`tel:${u.phone}`} className="text-xs text-sky-600 hover:underline dark:text-sky-400">
                                                                {u.phone}
                                                            </a>
                                                        )}
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

                {/* ===== Codes promo ===== */}
                <TabsContent value="promos">
                    <div className="space-y-6">
                        {/* Création */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
                                    <Ticket className="h-5 w-5" /> Créer un code promo
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
                                    <Input
                                        placeholder="Code (ex : RENTREE25)"
                                        value={newPromo.code}
                                        onChange={(e) => setNewPromo({ ...newPromo, code: e.target.value.toUpperCase() })}
                                    />
                                    <Select
                                        value={newPromo.discount_type}
                                        onValueChange={(v) => setNewPromo({ ...newPromo, discount_type: v })}
                                    >
                                        <SelectTrigger><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="percent">Réduction en %</SelectItem>
                                            <SelectItem value="amount">Réduction en ₪</SelectItem>
                                            <SelectItem value="free">Abonnement offert (100 %)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Input
                                        type="number" min="1"
                                        placeholder={newPromo.discount_type === 'percent' ? 'Valeur en %' : 'Valeur en ₪'}
                                        value={newPromo.discount_value}
                                        disabled={newPromo.discount_type === 'free'}
                                        onChange={(e) => setNewPromo({ ...newPromo, discount_value: e.target.value })}
                                    />
                                    <Input
                                        placeholder="Description (interne)"
                                        value={newPromo.description}
                                        onChange={(e) => setNewPromo({ ...newPromo, description: e.target.value })}
                                    />
                                </div>
                                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
                                    <Select
                                        value={newPromo.plan_ids.length === 1 ? newPromo.plan_ids[0] : 'all'}
                                        onValueChange={(v) => setNewPromo({ ...newPromo, plan_ids: v === 'all' ? [] : [v] })}
                                    >
                                        <SelectTrigger><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">Toutes les formules</SelectItem>
                                            {plans.map((p) => (
                                                <SelectItem key={p.plan_id} value={p.plan_id}>{p.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Input
                                        type="number" min="1" placeholder="Nombre max d'utilisations (vide = illimité)"
                                        value={newPromo.max_uses}
                                        onChange={(e) => setNewPromo({ ...newPromo, max_uses: e.target.value })}
                                    />
                                    <Input
                                        type="number" min="1" placeholder="Max par élève"
                                        value={newPromo.max_uses_per_user}
                                        onChange={(e) => setNewPromo({ ...newPromo, max_uses_per_user: e.target.value })}
                                    />
                                    <Input
                                        type="date" title="Date d'expiration"
                                        value={newPromo.valid_until}
                                        onChange={(e) => setNewPromo({ ...newPromo, valid_until: e.target.value })}
                                    />
                                </div>
                                <Button onClick={createPromo}><Plus className="h-4 w-4 mr-2" /> Créer le code</Button>
                            </CardContent>
                        </Card>

                        {/* Liste */}
                        <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle className="text-slate-900 dark:text-white">
                                    Codes existants
                                    <span className="ml-2 text-xs font-normal text-slate-500 dark:text-slate-400">
                                        {promoStats.redemptions} utilisation(s) · {money(promoStats.granted)} de remises accordées
                                    </span>
                                </CardTitle>
                                <Button size="sm" variant="outline" onClick={loadPromos}>
                                    <RefreshCw className="h-4 w-4 mr-2" /> Actualiser
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {promoLoading ? (
                                    <div className="space-y-2">
                                        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
                                    </div>
                                ) : promos.length === 0 ? (
                                    <p className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">
                                        Aucun code promo pour l'instant.
                                    </p>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                                                    <th className="py-2 pr-3">Code</th>
                                                    <th className="py-2 pr-3">Remise</th>
                                                    <th className="py-2 pr-3">Formules</th>
                                                    <th className="py-2 pr-3">Utilisations</th>
                                                    <th className="py-2 pr-3">Expire le</th>
                                                    <th className="py-2 pr-3">État</th>
                                                    <th className="py-2" />
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {promos.map((p) => (
                                                    <tr key={p.id} className="border-b border-slate-100 dark:border-slate-700/50">
                                                        <td className="py-2 pr-3">
                                                            <div className="font-mono font-bold text-slate-900 dark:text-white">{p.code}</div>
                                                            {p.description && (
                                                                <div className="text-xs text-slate-500 dark:text-slate-400">{p.description}</div>
                                                            )}
                                                        </td>
                                                        <td className="py-2 pr-3 font-semibold text-slate-700 dark:text-slate-200">{p.label}</td>
                                                        <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">
                                                            {p.plan_ids.length === 0 ? 'Toutes' : p.plan_ids.join(', ')}
                                                        </td>
                                                        <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">
                                                            {p.used_count}{p.max_uses != null ? ` / ${p.max_uses}` : ''}
                                                        </td>
                                                        <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">{date(p.valid_until)}</td>
                                                        <td className="py-2 pr-3">
                                                            <Badge variant={p.is_usable ? 'default' : 'secondary'}>{p.status}</Badge>
                                                        </td>
                                                        <td className="py-2 text-right whitespace-nowrap">
                                                            <Button size="sm" variant="outline" className="mr-2" onClick={() => togglePromo(p)}>
                                                                <Power className="h-3.5 w-3.5 mr-1" />
                                                                {p.active ? 'Désactiver' : 'Activer'}
                                                            </Button>
                                                            <Button size="sm" variant="destructive" onClick={() => deletePromo(p)}>
                                                                <Trash2 className="h-3.5 w-3.5" />
                                                            </Button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
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
                            {transactions.some((t) => t.needs_account) && (
                                <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 p-3">
                                    <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                                    <div className="text-sm text-amber-800 dark:text-amber-200">
                                        <strong>{transactions.filter((t) => t.needs_account).length} paiement(s) encaissé(s) sans compte.</strong>{' '}
                                        L'élève a payé mais aucun abonnement n'a pu être ouvert : rattache-le à un compte
                                        pour lui donner l'accès.
                                    </div>
                                </div>
                            )}
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
                                                <th className="py-2 pr-3"></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {transactions.map((t) => (
                                                <tr key={t.id} className="border-b border-slate-100 dark:border-slate-700/50">
                                                    <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">{date(t.created_at)}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">
                                                        {t.user_email || '—'}
                                                        {t.needs_account && (
                                                            <span className="block text-xs text-amber-600 dark:text-amber-400">
                                                                payé sans compte
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{t.plan_name}</td>
                                                    <td className="py-2 pr-3 text-slate-700 dark:text-slate-200">{money(t.amount, t.currency)}</td>
                                                    <td className="py-2 pr-3">
                                                        <Badge variant={t.status === 'completed' ? 'default' : 'secondary'}>{t.status}</Badge>
                                                    </td>
                                                    <td className="py-2 pr-3 text-right">
                                                        {t.needs_account && (
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                onClick={() => {
                                                                    setAttachTx(t);
                                                                    setAttachResult(null);
                                                                    setAttachForm({ email: t.user_email || '', first_name: '', last_name: '', phone: '' });
                                                                }}
                                                            >
                                                                <UserPlus className="h-4 w-4 mr-1" /> Rattacher
                                                            </Button>
                                                        )}
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
                                <div className="flex flex-wrap items-center gap-3">
                                    <Input className="max-w-xs" placeholder="Téléphone" type="tel" value={editForm.phone}
                                        onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
                                    {detail.phone && (
                                        <a href={`tel:${detail.phone}`} className="text-sm text-sky-600 hover:underline dark:text-sky-400">
                                            Appeler {detail.phone}
                                        </a>
                                    )}
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

                            {/* Abonnements (lecture seule : c'est l'élève qui souscrit) */}
                            <section className="space-y-3">
                                <h3 className="font-semibold text-slate-900 dark:text-white">Abonnements</h3>
                                {detail.subscriptions.length === 0 ? (
                                    <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 space-y-1">
                                        <p className="text-sm font-medium text-slate-900 dark:text-white">Aucun abonnement.</p>
                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                            {explainNoSubscription(detail.transactions)}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {detail.subscriptions.map((s) => (
                                            <div key={s.id} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                                                <SubscriptionBadge sub={s} />
                                                <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                                    {date(s.start_date)} → {date(s.end_date)}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                    L'abonnement appartient à l'élève : il le souscrit, le change et le
                                    renouvelle depuis son espace. Le CRM l'affiche, sans le modifier.
                                </p>
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

            {/* ===== Rattacher un paiement à un compte ===== */}
            <Dialog open={!!attachTx} onOpenChange={(open) => { if (!open) { setAttachTx(null); setAttachResult(null); } }}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Rattacher le paiement à un compte</DialogTitle>
                        <DialogDescription>
                            {attachTx && (
                                <>{money(attachTx.amount, attachTx.currency)} — {attachTx.plan_name} — {date(attachTx.created_at)}</>
                            )}
                        </DialogDescription>
                    </DialogHeader>

                    {attachResult ? (
                        <div className="space-y-3">
                            <p className="text-sm text-slate-700 dark:text-slate-200">
                                Abonnement ouvert pour <strong>{attachResult.user.email}</strong>
                                {attachResult.subscription?.end_date && <> jusqu'au {date(attachResult.subscription.end_date)}</>}.
                            </p>
                            {attachResult.temporary_password && (
                                <div className="rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 p-3">
                                    <div className="text-xs text-amber-700 dark:text-amber-300 mb-1">
                                        Mot de passe provisoire à communiquer à l'élève (affiché une seule fois) :
                                    </div>
                                    <code className="text-sm font-mono text-slate-900 dark:text-white">
                                        {attachResult.temporary_password}
                                    </code>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                Le compte est créé s'il n'existe pas encore ; s'il existe déjà, le paiement lui est
                                simplement rattaché.
                            </p>
                            <Input placeholder="Email de l'élève" type="email" value={attachForm.email}
                                onChange={(e) => setAttachForm((f) => ({ ...f, email: e.target.value }))} />
                            <div className="grid grid-cols-2 gap-2">
                                <Input placeholder="Prénom" value={attachForm.first_name}
                                    onChange={(e) => setAttachForm((f) => ({ ...f, first_name: e.target.value }))} />
                                <Input placeholder="Nom" value={attachForm.last_name}
                                    onChange={(e) => setAttachForm((f) => ({ ...f, last_name: e.target.value }))} />
                            </div>
                            <Input placeholder="Téléphone (facultatif)" type="tel" value={attachForm.phone}
                                onChange={(e) => setAttachForm((f) => ({ ...f, phone: e.target.value }))} />
                        </div>
                    )}

                    <DialogFooter>
                        {attachResult ? (
                            <Button size="sm" onClick={() => { setAttachTx(null); setAttachResult(null); }}>Fermer</Button>
                        ) : (
                            <Button size="sm" onClick={attachTransaction} disabled={attachSaving || !attachForm.email.trim()}>
                                <UserPlus className="h-4 w-4 mr-2" /> {attachSaving ? 'Rattachement…' : 'Rattacher et ouvrir l\'accès'}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
