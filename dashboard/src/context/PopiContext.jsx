import React, { createContext, useState, useContext, useCallback, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function titleize(value = '') {
  return String(value)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function toRelativeDayLabel(iso) {
  if (!iso) return 'Never';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return 'Unknown';
  const now = new Date();
  const days = Math.floor((now.setHours(0, 0, 0, 0) - new Date(when).setHours(0, 0, 0, 0)) / (1000 * 60 * 60 * 24));
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  return `${days} days ago`;
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `POST ${path} failed`);
  }
  return res.json();
}

function mapAlertsForUI(alertRows, childNameById) {
  return alertRows.map((a) => ({
    id: a.id,
    child_id: a.child_id,
    type: String(a.alert_type || '').toUpperCase(),
    category: titleize(a.category),
    message: a.message,
    child_name: childNameById[a.child_id] || 'Child',
    created_at: a.created_at || 'Unknown',
    dismissed: false,
  }));
}

function mapChildSummaryForUI(summary, profile, planWords, alertRows) {
  const sessions = profile?.session_history || [];
  const dailyScores = profile?.daily_scores || [];
  const activeAlerts = alertRows || [];

  const scoredSessions = sessions.filter((s) => typeof s.final_score_avg === 'number');
  const avgScore = scoredSessions.length
    ? Number((scoredSessions.reduce((acc, s) => acc + s.final_score_avg, 0) / scoredSessions.length).toFixed(2))
    : 0;

  const currentLevel = sessions[0]?.level || 'word_init';
  const latestActivity = sessions[0]?.started_at || null;
  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
  const sessionsThisWeek = sessions.filter((s) => s.started_at && new Date(s.started_at) >= oneWeekAgo).length;

  let status = 'on_track';
  if (activeAlerts.some((a) => String(a.alert_type).toLowerCase() === 'slp')) status = 'clinical_flag';
  else if (activeAlerts.some((a) => String(a.category).includes('no_practice'))) status = 'no_practice';

  const chartDaily = dailyScores.map((d) => {
    const avg = Number(d.avg_score || 0);
    return {
      date: new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' }),
      avg,
      pitch: Math.min(1, avg + 0.08),
      breath: Math.max(0, avg - 0.06),
      crispness: Math.max(0, avg - 0.03),
      duration: Math.max(0, avg - 0.1),
    };
  });

  const mappedSessions = sessions.slice(0, 12).map((s) => ({
    id: s.session_id,
    date: s.started_at ? new Date(s.started_at).toLocaleString() : 'Unknown',
    attempts: s.total_attempts ?? 0,
    avg_score: Number(s.final_score_avg ?? 0).toFixed(2),
    level_reached: s.level || 'word_init',
  }));

  return {
    id: summary.id,
    name: summary.name,
    age: summary.age,
    disorder_type: titleize(summary.disorder_type),
    target_phoneme: summary.target_phoneme,
    slp_notes: profile?.child?.notes || '',
    current_level: currentLevel,
    pass_threshold: 0.70,
    max_attempts: 5,
    sessions_this_week: sessionsThisWeek,
    avg_score: avgScore,
    status,
    last_active: toRelativeDayLabel(latestActivity),
    avatarBg: status === 'clinical_flag' ? 'bg-pink-100' : status === 'no_practice' ? 'bg-warning-100' : 'bg-primary-100',
    avatarText: status === 'clinical_flag' ? 'text-pink-600' : status === 'no_practice' ? 'text-warning-600' : 'text-primary-600',
    daily_scores: chartDaily,
    sessions: mappedSessions,
    attempts: [],
    plan: planWords,
  };
}

export const PopiContext = createContext();

export function PopiProvider({ children }) {
  const [childrenMap, setChildrenMap] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const hydrateFromBackend = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const childrenResp = await apiGet('/children');
      const list = childrenResp.children || [];

      const childNameById = Object.fromEntries(list.map((c) => [c.id, c.name]));

      const hydratedEntries = await Promise.all(
        list.map(async (c) => {
          const [profileResp, planResp, childAlertsResp] = await Promise.all([
            apiGet(`/child/${c.id}`),
            apiGet(`/plan/sync?child_id=${encodeURIComponent(c.id)}`),
            apiGet(`/alerts/${c.id}`),
          ]);

          const planWords = (planResp?.plan?.word_list || []).map((w) =>
            typeof w === 'string' ? w : w.word,
          );

          const mapped = mapChildSummaryForUI(c, profileResp, planWords, childAlertsResp.alerts || []);

          if (mapped.sessions.length > 0) {
            try {
              const latestSession = await apiGet(`/session/${mapped.sessions[0].id}`);
              mapped.attempts = (latestSession.attempts || []).slice(0, 12).map((a) => ({
                id: a.attempt_number,
                word: a.target_word || mapped.plan[0] || 'attempt',
                score: Number(a.score || 0),
                feedback: `${a.feedback_type || 'feedback'} - hint: ${a.hint || 'none'}`,
              }));
            } catch {
              mapped.attempts = [];
            }
          }

          return [String(c.id), mapped];
        }),
      );

      const allAlerts = (
        await Promise.all(list.map((c) => apiGet(`/alerts/${c.id}`).then((x) => x.alerts || [])))
      ).flat();

      setChildrenMap(Object.fromEntries(hydratedEntries));
      setAlerts(mapAlertsForUI(allAlerts, childNameById));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed loading data');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = async () => {
    setIsAuthenticated(true);
    await hydrateFromBackend();
  };

  const logout = () => setIsAuthenticated(false);

  const addChild = useCallback(async (childData) => {
    const payload = {
      name: childData.name,
      age: Number(childData.age),
      disorder_type: childData.disorder_type,
      target_phoneme: String(childData.target_phoneme || 's').replaceAll('/', ''),
      notes: childData.slp_notes || '',
    };
    const created = await apiPost('/child/create', payload);
    await hydrateFromBackend();
    return created.child_id;
  }, [hydrateFromBackend]);

  const pushPlan = useCallback(async ({ childId, words, passThreshold, maxAttempts, startLevel }) => {
    const now = new Date();
    const day = now.getDay();
    const diffToMonday = (day + 6) % 7;
    const monday = new Date(now);
    monday.setDate(now.getDate() - diffToMonday);
    const weekStart = monday.toISOString().slice(0, 10);

    await apiPost('/plan/push', {
      child_id: childId,
      week_start: weekStart,
      word_list: words.map((w) => ({ word: w.word || w, prompt: `Can you help me say ${w.word || w}?` })),
      start_level: startLevel,
      pass_threshold: passThreshold,
      max_attempts: maxAttempts,
    });
    await hydrateFromBackend();
  }, [hydrateFromBackend]);

  const dismissAlert = useCallback(async (alertId) => {
    await apiPost('/alert/dismiss', { alert_id: alertId, dismissed_by: 'slp' });
    await hydrateFromBackend();
  }, [hydrateFromBackend]);

  const value = useMemo(() => ({
    childrenList: Object.values(childrenMap),
    getChildById: (id) => childrenMap[String(id)],
    alerts,
    setAlerts,
    addChild,
    pushPlan,
    dismissAlert,
    isAuthenticated,
    login,
    logout,
    refresh: hydrateFromBackend,
    isLoading,
    error,
    apiBase: API_BASE,
  }), [childrenMap, alerts, addChild, pushPlan, dismissAlert, isAuthenticated, isLoading, error, hydrateFromBackend]);

  return (
    <PopiContext.Provider value={value}>
      {children}
    </PopiContext.Provider>
  );
}

export const usePopi = () => useContext(PopiContext);
