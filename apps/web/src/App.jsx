import { useCallback, useEffect, useRef, useState } from 'react';
import Overview from './screens/Overview.jsx';
import Activities from './screens/Activities.jsx';
import ActivityDetail from './screens/ActivityDetail.jsx';
import Profile from './screens/Profile.jsx';
import InsightTrend from './screens/InsightTrend.jsx';
import Insights from './screens/Insights.jsx';
import Performance from './screens/Performance.jsx';
import Login from './screens/Login.jsx';

const API_BASE = '/api/v1';
const OVERVIEW_CACHE_KEY = 'fitness_overview_cache';
const OVERVIEW_CACHE_TTL_MS = 5 * 60 * 1000;
const ASSISTANT_SESSION_KEY = 'assistant_session_id';

const EMPTY_OVERVIEW = {
  weekLabel: '—',
  weekStart: null,
  allTimeCards: [],
  weeklyCards: [],
  insights: [],
  performance: []
};

const EMPTY_ACTIVITY = {
  activityId: null,
  name: '',
  subtitle: '',
  weather: null,
  heroStats: [],
  tabs: ['Overview', 'Laps', 'Charts'],
  overview: [],
  charts: { pace: null, hr: null, cadence: null, elevation: null },
  laps: [],
  lapTotals: null,
  segments: null
};

const EMPTY_ACTIVITIES = { title: 'Activities', filterLabel: 'All activities', items: [] };
const EMPTY_PROFILE = { name: '', age: null, height_cm: null, weight_kg: null, resting_hr: null };

export default function App() {
  const isDev = import.meta?.env?.DEV;
  const prevPathRef = useRef(null);
  const authRedirectRef = useRef(null);
  const currentPathRef = useRef(null);
  const syncTriggeredRef = useRef(false);
  const syncInFlightRef = useRef(false);
  const [routePath, setRoutePath] = useState(
    typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : '/dashboard'
  );
  const [screen, setScreen] = useState('overview');
  const [previousScreen, setPreviousScreen] = useState('overview');
  const tokenKey = 'fitness_token';
  const [authToken, setAuthToken] = useState(() => {
    if (typeof window === 'undefined') return null;
    return window.localStorage.getItem(tokenKey);
  });
  const [authRequired, setAuthRequired] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState(null);
  const [overviewData, setOverviewData] = useState(EMPTY_OVERVIEW);
  const [activityList, setActivityList] = useState([]);
  const [activeActivity, setActiveActivity] = useState(EMPTY_ACTIVITY);
  const [activeInsight, setActiveInsight] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [lastUpdateRaw, setLastUpdateRaw] = useState(null);
  const [syncNonce, setSyncNonce] = useState(0);
  const [activitiesData, setActivitiesData] = useState(EMPTY_ACTIVITIES);
  const [activityFilter, setActivityFilter] = useState({ type: 'run', range: 'all', start: null, end: null, label: 'All activities' });
  const [activityOffset, setActivityOffset] = useState(0);
  const [activityHasMore, setActivityHasMore] = useState(true);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [profileData] = useState(EMPTY_PROFILE);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantQuestion, setAssistantQuestion] = useState('');
  const [assistantResponse, setAssistantResponse] = useState(null);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState(null);
  const [assistantFeedback, setAssistantFeedback] = useState(null);
  const [assistantOverview, setAssistantOverview] = useState(null);
  const [assistantOverviewLoading, setAssistantOverviewLoading] = useState(false);
  const [assistantOverviewError, setAssistantOverviewError] = useState(null);
  const [assistantSessionId, setAssistantSessionId] = useState(() => {
    if (typeof window === 'undefined') return null;
    return window.localStorage.getItem(ASSISTANT_SESSION_KEY);
  });
  const [assistantMessages, setAssistantMessages] = useState([]);

  const formatDuration = useCallback((value) => {
    if (value === null || value === undefined) return '—';
    const total = Number(value);
    if (Number.isNaN(total) || total <= 0) return '—';
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = Math.round(total % 60);
    const mm = String(minutes).padStart(hours ? 2 : 1, '0');
    const ss = String(seconds).padStart(2, '0');
    return hours ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.localStorage.getItem(OVERVIEW_CACHE_KEY);
    if (!raw) return;
    try {
      const cached = JSON.parse(raw);
      if (!cached?.data || !cached?.cachedAt) return;
      if (Date.now() - cached.cachedAt > OVERVIEW_CACHE_TTL_MS) return;
      setOverviewData(cached.data);
      setLastUpdate(cached.lastUpdate || null);
      setLastUpdateRaw(cached.lastUpdateRaw || null);
    } catch {
      // ignore cache parse errors
    }
  }, []);

  const navigate = useCallback((path) => {
    if (typeof window === 'undefined') return;
    if (`${window.location.pathname}${window.location.search}` === path) return;
    window.history.pushState({}, '', path);
    setRoutePath(path);
  }, []);

  const goBack = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    if (prevPathRef.current) {
      navigate(prevPathRef.current);
      return;
    }
    navigate('/activities');
  }, [navigate]);

  const saveToken = useCallback((token) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(tokenKey, token);
    }
    setAuthToken(token);
    setAuthRequired(false);
    setAuthError(null);
  }, [tokenKey]);

  const clearToken = useCallback((message = null) => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(tokenKey);
    }
    setAuthToken(null);
    setAuthRequired(true);
    if (message) setAuthError(message);
  }, [tokenKey]);

  const apiFetch = useCallback(async (path, options = {}, tokenOverride = null) => {
    const headers = new Headers(options.headers || {});
    const token = tokenOverride ?? authToken;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      clearToken('Please sign in to continue.');
      throw new Error('unauthorized');
    }
    return res;
  }, [authToken, clearToken]);

  const postContextEvent = useCallback(async (eventType, payload) => {
    const res = await apiFetch('/insights/context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: eventType, payload, source: 'ui' })
    });
    return res.json();
  }, [apiFetch]);

  const handleAskAssistant = useCallback(async (questionOverride = null) => {
    if (!authToken && !isDev) {
      setAssistantError('Please sign in to use the assistant.');
      return;
    }
    const question = (questionOverride ?? assistantQuestion).trim();
    if (!question) return;
    setAssistantLoading(true);
    setAssistantError(null);
    setAssistantResponse(null);
    setAssistantFeedback(null);
    setAssistantMessages((prev) => [
      ...prev,
      { role: 'user', text: question, id: Date.now() }
    ]);
    setAssistantQuestion('');
    try {
      const res = await apiFetch('/insights/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          context: {},
          session_id: assistantSessionId || null
        })
      });
      const json = await res.json();
      setAssistantResponse(json);
      if (json?.session_id) {
        setAssistantSessionId(json.session_id);
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(ASSISTANT_SESSION_KEY, json.session_id);
        }
      }
      if (json?.answer) {
        setAssistantMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: json.answer,
            recommendations: json.recommendations || [],
            followUps: json.follow_ups || [],
            todayRecommendation: json.today_recommendation || null,
            trendInsight: json.trend_insight || null,
            predicted5k: json.predicted_5k_time_s ?? null,
            predicted10k: json.predicted_10k_time_s ?? null,
            id: Date.now() + 1
          }
        ]);
      }
    } catch {
      setAssistantError('Unable to reach the assistant right now.');
    } finally {
      setAssistantLoading(false);
    }
  }, [assistantQuestion, apiFetch, assistantSessionId, authToken, isDev]);

  const handleFollowUp = useCallback((question) => {
    setAssistantQuestion(question);
    handleAskAssistant(question);
  }, [handleAskAssistant]);

  const resetAssistantSession = useCallback(() => {
    setAssistantSessionId(null);
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(ASSISTANT_SESSION_KEY);
    }
    setAssistantMessages([]);
    setAssistantResponse(null);
    setAssistantFeedback(null);
    setAssistantError(null);
    setAssistantQuestion('');
  }, []);

  useEffect(() => {
    if (!assistantOpen) return;
    if (authRequired || (!authToken && !isDev)) {
      setAssistantOverviewError('Please sign in to load assistant insights.');
      setAssistantOverviewLoading(false);
      return;
    }
    if (assistantOverviewLoading || assistantOverview) return;
    let cancelled = false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 8000);
    setAssistantOverviewLoading(true);
    setAssistantOverviewError(null);
    apiFetch('/assistant/overview', { signal: controller.signal })
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        setAssistantOverview(json);
      })
      .catch(() => {
        if (cancelled) return;
        setAssistantOverviewError('Failed to load assistant overview.');
      })
      .finally(() => {
        if (cancelled) return;
        window.clearTimeout(timeoutId);
        setAssistantOverviewLoading(false);
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [
    assistantOpen,
    assistantOverviewLoading,
    assistantOverview,
    apiFetch,
    authRequired,
    authToken,
    isDev
  ]);

  const handleFeedback = useCallback((value) => {
    setAssistantFeedback(value);
    try {
      void postContextEvent('assistant_feedback', {
        question: assistantQuestion,
        helpful: value,
        answer: assistantResponse?.answer || null
      });
    } catch {
      // ignore feedback failures
    }
  }, [assistantQuestion, assistantResponse, postContextEvent]);

  const triggerSync = useCallback(async ({ force = false, tokenOverride = null } = {}) => {
    if (syncInFlightRef.current) return;
    syncInFlightRef.current = true;
    try {
      const suffix = force ? '?force=1' : '';
      const res = await apiFetch(`/sync${suffix}`, { method: 'POST' }, tokenOverride);
      let startLast = lastUpdateRaw;
      try {
        const payload = await res.json();
        if (payload?.last_update) startLast = payload.last_update;
      } catch {
        // ignore parse errors
      }
      const deadline = Date.now() + 60000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        try {
          const healthRes = await apiFetch('/health', {}, tokenOverride);
          const health = await healthRes.json();
          if (health?.last_update && health.last_update !== startLast) {
            setLastUpdateRaw(health.last_update);
            setLastUpdate(formatLastUpdate(health.last_update));
            setSyncNonce((value) => value + 1);
            return;
          }
        } catch {
          // ignore transient errors
        }
      }
      setSyncNonce((value) => value + 1);
    } finally {
      syncInFlightRef.current = false;
    }
  }, [apiFetch, lastUpdateRaw]);

  const handleLogin = useCallback(async (username, password) => {
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (!res.ok) {
        throw new Error('invalid');
      }
      const json = await res.json();
      if (!json?.access_token) throw new Error('invalid');
      saveToken(json.access_token);
      syncTriggeredRef.current = false;
      triggerSync({ force: true, tokenOverride: json.access_token });
      const target = authRedirectRef.current || '/dashboard';
      authRedirectRef.current = null;
      navigate(target);
      setScreen(target.startsWith('/activities') ? 'activities' : 'overview');
    } catch {
      setAuthError('Invalid username or password.');
    } finally {
      setAuthLoading(false);
    }
  }, [navigate, saveToken, triggerSync]);

  const applyActivityFilter = useCallback((type, range, startOverride = null, endOverride = null) => {
    const weekStart = overviewData.weekStart || null;
    const weekRange = weekStart ? buildWeekRange(weekStart) : null;
    if (range === 'week' && (weekRange || (startOverride && endOverride))) {
      const start = startOverride || weekRange?.start || null;
      const end = endOverride || weekRange?.end || null;
      setActivityFilter({ type, range: 'week', start, end, label: `This week • ${type}` });
    } else {
      setActivityFilter({ type, range: 'all', start: null, end: null, label: `All time • ${type}` });
    }
  }, [overviewData.weekStart]);

  const findInsightById = useCallback((id) => {
    if (!id) return null;
    return (overviewData.insights || []).find((item) => item.id === id) || null;
  }, [overviewData.insights]);

  const findPerformanceById = useCallback((id) => {
    if (!id) return null;
    return (overviewData.performance || []).find((item) => item.id === id) || null;
  }, [overviewData.performance]);

  const fetchActivities = useCallback(async (offset, append) => {
    setActivityLoading(true);
    setActivityError(null);
    try {
      const json = await fetchActivitiesPage(apiFetch, activityFilter, offset, PAGE_SIZE);
      const activities = json.activities || [];
      const merged = append ? [...activityList, ...activities] : activities;
      setActivityList(merged);
      setActivitiesData(buildActivities(activityFilter, merged));
      setActivityOffset(offset + activities.length);
      setActivityHasMore(activities.length === PAGE_SIZE);
    } catch {
      setActivityError('Failed to load activities.');
      setActivitiesData({ ...EMPTY_ACTIVITIES, items: [], filterLabel: activityFilter.label });
      setActivityHasMore(false);
    } finally {
      setActivityLoading(false);
    }
  }, [activityFilter, activityList, apiFetch]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const onPop = () => setRoutePath(`${window.location.pathname}${window.location.search}`);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    if (syncTriggeredRef.current) return;
    if (authRequired) return;
    if (!authToken && !isDev) return;
    syncTriggeredRef.current = true;
    triggerSync({ force: false });
  }, [authRequired, authToken, isDev, triggerSync]);

  useEffect(() => {
    currentPathRef.current = routePath;
  }, [routePath]);

  useEffect(() => {
    if (!authRequired) return;
    setAssistantOpen(false);
    if (routePath !== '/login') {
      authRedirectRef.current = routePath;
      navigate('/login');
      setScreen('login');
    }
  }, [authRequired, routePath, navigate]);

  useEffect(() => {
    const url = typeof window !== 'undefined' ? new URL(routePath || '/dashboard', window.location.origin) : null;
    const path = url?.pathname || '/dashboard';
    const params = url?.searchParams;
    if (path === '/' || path === '/dashboard') {
      setPreviousScreen('overview');
      setScreen('overview');
      return;
    }
    if (path === '/login') {
      setPreviousScreen('overview');
      setScreen('login');
      return;
    }
    if (path.startsWith('/activities')) {
      const parts = path.split('/').filter(Boolean);
      const segment = parts[1] || 'run';
      const id = parts[2] || null;
      if (id) {
        setActiveId(id);
        setPreviousScreen('activities');
        setScreen('detail');
        return;
      }
      if (segment && !['run', 'golf', 'walk'].includes(segment)) {
        setActiveId(segment);
        setPreviousScreen('activities');
        setScreen('detail');
        return;
      }
      const type = segment || 'run';
      const range = params?.get('range') || 'all';
      const start = params?.get('start');
      const end = params?.get('end');
      applyActivityFilter(type, range, start, end);
      setPreviousScreen('overview');
      setScreen('activities');
      return;
    }
    if (path.startsWith('/activity/')) {
      const id = path.replace('/activity/', '').trim();
      if (id) setActiveId(id);
      setPreviousScreen('activities');
      setScreen('detail');
      return;
    }
    if (path.startsWith('/insights/')) {
      const id = path.replace('/insights/', '').trim();
      const insight = findInsightById(id);
      if (insight) {
        setActiveInsight(insight);
        setPreviousScreen('insights');
        setScreen('insight');
        return;
      }
    }
    if (path === '/insights') {
      setPreviousScreen('overview');
      setScreen('insights');
      return;
    }
    if (path.startsWith('/performance/')) {
      const id = path.replace('/performance/', '').trim();
      const perf = findPerformanceById(id);
      if (perf) {
        setActiveInsight({ ...perf, id: perf.id, label: perf.label });
        setPreviousScreen('performance');
        setScreen('insight');
        return;
      }
    }
    if (path === '/performance') {
      setPreviousScreen('overview');
      setScreen('performance');
      return;
    }
    if (path === '/profile') {
      setPreviousScreen('overview');
      setScreen('profile');
      return;
    }
    // fallback
    setScreen('overview');
  }, [routePath, applyActivityFilter, findInsightById, findPerformanceById]);

  useEffect(() => {
    if (authRequired) return;
    if (!authToken && !isDev) return;
    const load = async () => {
      setOverviewLoading(true);
      setOverviewError(null);
      try {
        const [healthRes, weeklyRes, totalsAllRes, insightsRes] = await Promise.all([
          apiFetch('/health'),
          apiFetch('/weekly?limit=4'),
          apiFetch('/activity_totals'),
          apiFetch('/insights')
        ]);
        const [healthJson, weeklyJson, totalsAllJson, insightsJson] = await Promise.all([
          healthRes.json(),
          weeklyRes.json(),
          totalsAllRes.json(),
          insightsRes.json()
        ]);
        setLastUpdateRaw(healthJson.last_update || null);
        setLastUpdate(formatLastUpdate(healthJson.last_update));

        const weekly = weeklyJson.weekly || [];
        const weekStart = weekly[0]?.week || null;
        const weekRange = weekStart ? buildWeekRange(weekStart) : null;

        let totalsWeekJson = { totals: [] };
        if (weekRange) {
          const totalsWeekRes = await apiFetch(
            `/activity_totals?start=${encodeURIComponent(weekRange.start)}&end=${encodeURIComponent(weekRange.end)}`
          );
          totalsWeekJson = await totalsWeekRes.json();
        }

        const { insights, performance } = buildInsights(insightsJson);
        const nextOverview = buildOverview(
          weekly,
          totalsAllJson.totals || [],
          totalsWeekJson.totals || [],
          insights,
          performance
        );
        setOverviewData(nextOverview);
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(
            OVERVIEW_CACHE_KEY,
            JSON.stringify({
              data: nextOverview,
              lastUpdate: formatLastUpdate(healthJson.last_update),
              lastUpdateRaw: healthJson.last_update || null,
              cachedAt: Date.now()
            })
          );
        }
      } catch {
        setOverviewError('Failed to load dashboard data.');
        if (!isDev) setOverviewData(EMPTY_OVERVIEW);
      } finally {
        setOverviewLoading(false);
      }
    };
    load();
  }, [apiFetch, authRequired, authToken, isDev, syncNonce]);

  useEffect(() => {
    if (!activeId) return;
    if (authRequired) return;
    if (!authToken && !isDev) return;
    const loadDetail = async () => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const [
          detailRes,
          summaryRes,
          seriesRes,
          routeRes,
          lapsRes,
          activitySegmentsRes,
          segmentsRes
        ] = await Promise.all([
          apiFetch(`/activity/${activeId}`),
          apiFetch(`/activity/${activeId}/summary`),
          apiFetch(`/activity/${activeId}/series`),
          apiFetch(`/activity/${activeId}/route`),
          apiFetch(`/activity/${activeId}/laps`),
          apiFetch(`/activity/${activeId}/segments`),
          apiFetch(`/segments_best`)
        ]);
        const [detail, summary, series, route, lapsJson, activitySegments, segments] = await Promise.all([
          detailRes.json(),
          summaryRes.json(),
          seriesRes.json(),
          routeRes.json(),
          lapsRes.json(),
          activitySegmentsRes.json(),
          segmentsRes.json()
        ]);
        setActiveActivity(buildActivityDetail(detail, summary, lapsJson.laps || [], series.series || {}, route.route || [], segments, activitySegments.segments || {}));
      } catch {
        setDetailError('Failed to load activity.');
        setActiveActivity(EMPTY_ACTIVITY);
      } finally {
        setDetailLoading(false);
      }
    };
    loadDetail();
  }, [activeId, apiFetch, authRequired, authToken, isDev]);

  useEffect(() => {
    if (screen !== 'activities') return;
    setActivityOffset(0);
    setActivityHasMore(true);
    setActivityList([]);
    fetchActivities(0, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activityFilter, screen, syncNonce]);

  return (
    <div className="app">
      {screen === 'overview' && (
        <Overview
          contract={overviewData}
          lastUpdate={lastUpdate}
          loading={overviewLoading}
          error={overviewError}
          onOpenAssistant={() => setAssistantOpen(true)}
          onSelectActivityType={(type, range) => {
            applyActivityFilter(type, range);
            if (range === 'all') {
              prevPathRef.current = window.location.pathname;
              navigate(`/activities/${type}`);
            } else {
              const weekStart = overviewData.weekStart || null;
              const weekRange = weekStart ? buildWeekRange(weekStart) : null;
              prevPathRef.current = window.location.pathname;
              if (weekRange) {
                navigate(`/activities/${type}?range=week&start=${encodeURIComponent(weekRange.start)}&end=${encodeURIComponent(weekRange.end)}`);
              } else {
                navigate(`/activities/${type}?range=week`);
              }
            }
            setScreen('activities');
          }}
          onSelectInsight={(insight) => {
            setActiveInsight(insight);
            setPreviousScreen('overview');
            prevPathRef.current = window.location.pathname;
            navigate(`/insights/${insight.id}`);
            setScreen('insight');
          }}
        />
      )}
      {screen === 'insights' && (
        <Insights
          contract={overviewData}
          loading={overviewLoading}
          error={overviewError}
          onSelectInsight={(insight) => {
            setActiveInsight(insight);
            setPreviousScreen('insights');
            prevPathRef.current = window.location.pathname;
            navigate(`/insights/${insight.id}`);
            setScreen('insight');
          }}
        />
      )}
      {screen === 'performance' && (
        <Performance
          contract={overviewData}
          loading={overviewLoading}
          error={overviewError}
          onSelectMetric={(metric) => {
            setActiveInsight(metric);
            setPreviousScreen('performance');
            prevPathRef.current = window.location.pathname;
            navigate(`/performance/${metric.id}`);
            setScreen('insight');
          }}
        />
      )}
      {screen === 'activities' && (
        <Activities
          contract={activitiesData}
          hasMore={activityHasMore}
          loading={activityLoading}
          error={activityError}
          onLoadMore={() => {
            if (activityLoading || !activityHasMore) return;
            fetchActivities(activityOffset, true);
          }}
          onSelectActivity={(activity) => {
            if (activity?.id) setActiveId(activity.id);
            if (activity?.id) navigate(`/activities/${activity.id}`);
            prevPathRef.current = window.location.pathname;
            setPreviousScreen('activities');
            setScreen('detail');
          }}
        />
      )}
      {screen === 'detail' && (
        <ActivityDetail
          contract={activeActivity}
          loading={detailLoading}
          error={detailError}
          onBack={goBack}
        />
      )}
      {screen === 'insight' && (
        <InsightTrend
          insight={activeInsight}
          onBack={goBack}
          apiFetch={apiFetch}
        />
      )}
      {screen === 'login' && (
        <Login
          onSubmit={handleLogin}
          loading={authLoading}
          error={authError}
        />
      )}
      {screen === 'profile' && <Profile contract={profileData} />}
      {assistantOpen && <div className="assistant-backdrop" onClick={() => setAssistantOpen(false)} />}
      <div className={`assistant-drawer ${assistantOpen ? 'is-open' : ''}`}>
        <div className="assistant-panel">
          <div className="assistant-header">
            <div>
              <h2>Assistant</h2>
              <div className="muted">Daily guidance + trend summary</div>
            </div>
            <div className="assistant-header-actions">
              <button className="assistant-chip" type="button" onClick={resetAssistantSession}>New chat</button>
              <button
                className="assistant-chip"
                type="button"
                onClick={() => {
                  setAssistantOverview(null);
                  setAssistantOverviewError(null);
                }}
                disabled={assistantOverviewLoading}
              >
                {assistantOverviewLoading ? 'Refreshing…' : 'Refresh'}
              </button>
              <button className="icon-btn" type="button" onClick={() => setAssistantOpen(false)}>Close</button>
            </div>
          </div>

          <div className="assistant-section">
            <div className="assistant-label">Today + Trends</div>
            <div className="assistant-summary-grid">
              <div className="assistant-summary-card">
                <div className="assistant-subtitle">Today recommended run</div>
                <p>{assistantOverview?.today?.text || assistantResponse?.today_recommendation || assistantMessages.at(-1)?.todayRecommendation || (assistantOverviewLoading ? 'Loading…' : '—')}</p>
              </div>
              <div className="assistant-summary-card">
                <div className="assistant-subtitle">Trend insight</div>
                <p>{assistantOverview?.trend?.text || assistantResponse?.trend_insight || assistantMessages.at(-1)?.trendInsight || (assistantOverviewLoading ? 'Loading…' : '—')}</p>
              </div>
              <div className="assistant-summary-card">
                <div className="assistant-subtitle">Predicted 5k / 10k</div>
                <p>
                  5k {formatDuration(assistantOverview?.predictions?.predicted_5k_time_s ?? assistantResponse?.predicted_5k_time_s ?? assistantMessages.at(-1)?.predicted5k)} ·
                  10k {formatDuration(assistantOverview?.predictions?.predicted_10k_time_s ?? assistantResponse?.predicted_10k_time_s ?? assistantMessages.at(-1)?.predicted10k)}
                </p>
              </div>
            </div>
            {assistantOverviewError && <div className="muted">{assistantOverviewError}</div>}
          </div>

          <div className="assistant-section">
            <div className="assistant-label">Chat</div>
            <div className="assistant-thread card">
              {assistantMessages.length > 0 ? (
                assistantMessages.map((msg) => (
                  <div key={msg.id} className={`assistant-message ${msg.role}`}>
                    <div className="assistant-message-label">
                      {msg.role === 'user' ? 'You' : 'Assistant'}
                    </div>
                    <p>{msg.text}</p>
                    {msg.role === 'assistant' && msg.recommendations?.length > 0 && (
                      <>
                        <div className="assistant-subtitle">Recommendations</div>
                        <ul>
                          {msg.recommendations.map((rec, idx) => (
                            <li key={idx}>{rec}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {msg.role === 'assistant' && msg.followUps?.length > 0 && (
                      <>
                        <div className="assistant-subtitle">Follow‑ups</div>
                        <div className="assistant-row">
                          {msg.followUps.map((q, idx) => (
                            <button
                              key={idx}
                              className="assistant-chip"
                              type="button"
                              onClick={() => handleFollowUp(q)}
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                ))
              ) : (
                <div className="muted">Ask a question to start the conversation.</div>
              )}
            </div>
            <textarea
              className="assistant-input"
              rows={2}
              placeholder="Ask about your training, trends, or goals…"
              value={assistantQuestion}
              onChange={(e) => setAssistantQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAskAssistant();
                }
              }}
            />
            <div className="assistant-actions">
              <button
                className="primary-btn"
                type="button"
                onClick={() => handleAskAssistant()}
                disabled={assistantLoading || !assistantQuestion.trim()}
              >
                {assistantLoading ? 'Thinking…' : 'Send'}
              </button>
              {assistantError && <span className="muted">{assistantError}</span>}
            </div>
            {assistantResponse?.answer && (
              <div className="assistant-actions">
                <span className="muted">Helpful?</span>
                <button
                  className={`assistant-chip ${assistantFeedback === true ? 'is-active' : ''}`}
                  type="button"
                  onClick={() => handleFeedback(true)}
                >
                  Yes
                </button>
                <button
                  className={`assistant-chip ${assistantFeedback === false ? 'is-active' : ''}`}
                  type="button"
                  onClick={() => handleFeedback(false)}
                >
                  No
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      {screen !== 'login' && (
        <nav className="bottom-nav">
          <button className={`nav-item ${screen === 'overview' ? 'is-active' : ''}`} type="button" onClick={() => { setPreviousScreen('overview'); navigate('/dashboard'); }}>Home</button>
          <button className={`nav-item ${screen === 'activities' ? 'is-active' : ''}`} type="button" onClick={() => { setPreviousScreen('activities'); navigate('/activities'); }}>Activities</button>
          <button className={`nav-item ${screen === 'profile' ? 'is-active' : ''}`} type="button" onClick={() => { setPreviousScreen('profile'); navigate('/profile'); }}>Profile</button>
          <button className="nav-item" type="button" onClick={() => setAssistantOpen(true)}>Assistant</button>
        </nav>
      )}
    </div>
  );
}

function buildOverview(weekly, totalsAll, totalsWeek, insights = EMPTY_OVERVIEW.insights, performance = EMPTY_OVERVIEW.performance) {
  const latest = weekly[0];
  const weekLabel = latest ? latest.week : EMPTY_OVERVIEW.weekLabel;
  const allTimeCards = buildSummaryCards(totalsAll);
  const weeklyCards = buildSummaryCards(totalsWeek);
  return {
    weekLabel,
    weekStart: latest ? latest.week : null,
    allTimeCards,
    weeklyCards,
    insights,
    performance
  };
}

function buildActivityDetail(detail, summary = {}, laps = [], series = {}, route = [], segments = {}, activitySegments = {}) {
  if (!detail || detail.error) return EMPTY_ACTIVITY;
  const weather = detail.weather;
  const weatherLabel = weather?.temp_c != null ? `${weather.temp_c}°C` : (weather?.avg_temp_c != null ? `${weather.avg_temp_c}°C` : 'n/a');
  const lapRows = laps.map((lap) => ({
    lap: lap.lap,
    time: formatTime(lap.time),
    distance: (lap.distance_m / 1000).toFixed(2),
    pace: lap.pace_sec ? formatPace(lap.pace_sec) : '—',
    elev: lap.elev_change_m != null ? `${Math.round(lap.elev_change_m)} m` : '—',
    flat: lap.flat_pace_sec ? formatPace(lap.flat_pace_sec) : '—'
  }));
  const lapTotals = buildLapTotals(laps);
  return {
    id: detail.activity_id,
    type: detail.activity_type,
    title: detail.name || 'Activity',
    date: (detail.start_time || '').slice(0, 16).replace('T', ' @ '),
    location: detail.location || '',
    weather: weatherLabel,
    heroStats: [
      { label: 'Distance', value: summary.distance_m ? `${(summary.distance_m / 1000).toFixed(2)} km` : '—' },
      { label: 'Avg Pace', value: summary.avg_pace_sec ? formatPace(summary.avg_pace_sec) : '—' },
      { label: 'Moving Time', value: summary.moving_s ? formatTime(summary.moving_s) : '—' },
      { label: 'Elevation', value: summary.elev_gain != null ? `${summary.elev_gain} m` : '—' },
      { label: 'Calories', value: summary.calories != null ? `${summary.calories}` : '—' },
      { label: 'Avg HR', value: summary.avg_hr_norm != null ? `${Math.round(summary.avg_hr_norm)} bpm` : '—' }
    ],
    tabs: ['Overview', 'Laps', 'Charts'],
    laps: lapRows,
    lapTotals,
    summary,
    series,
    route,
    segments,
    activitySegments
  };
}

function buildActivities(filter, activities) {
  const filtered = activities.filter((a) => normalizeAccent(a.activity_type) === normalizeAccent(filter.type));
  return {
    title: 'Activities',
    filterLabel: filter.label,
    items: filtered.map((a) => ({
      id: a.activity_id,
      type: normalizeAccent(a.activity_type),
      title: a.name || 'Activity',
      date: (a.start_time || '').slice(0, 10),
      stats: [
        a.distance_m ? `${(a.distance_m / 1000).toFixed(1)} km` : '—',
        a.moving_s ? formatTime(a.moving_s) : '—'
      ],
      accent: normalizeAccent(a.activity_type)
    }))
  };
}

function buildSummaryCards(totals) {
  const byType = new Map(totals.map((t) => [t.activity_type, t]));
  return ['run', 'golf', 'walk'].map((type) => {
    const entry = byType.get(type);
    if (!entry) {
      return { id: type, label: labelFor(type), value: '—', accent: normalizeAccent(type) };
    }
    const distance = entry.distance_m ? `${(entry.distance_m / 1000).toFixed(1)} km` : '—';
    const countLabel = `${entry.count} ${type === 'run' ? 'runs' : type === 'golf' ? 'rounds' : 'walks'}`;
    return { id: type, label: labelFor(type), value: `${distance} • ${countLabel}`, accent: normalizeAccent(type) };
  });
}

function buildInsights(payload = {}) {
  const vdot = payload.vdot_best;
  const paceTrend = payload.pace_trend_sec_per_week;
  const hrTrend = payload.hr_trend_bpm_per_week;
  const effTrend = payload.eff_trend_per_week;
  const efficiencyTrend = payload.efficiency_trend_12w;
  const decoupling = payload.decoupling_28d;
  const monotony = payload.monotony;
  const strain = payload.strain;
  const dist7 = payload.dist_7d_km;
  const dist28 = payload.dist_28d_km;
  const fatigueLast = payload.fatigue_last_week;
  const fatigueAvg4w = payload.fatigue_4w_avg;
  const recoveryIndex = payload.recovery_index_28d;
  const pbAll = payload.pb_all || {};
  const pb12m = payload.pb_12m || {};
  const est5k = payload.est_5k_s;
  const est10k = payload.est_10k_s;

  const formatSigned = (value, suffix) => {
    if (value == null || Number.isNaN(value)) return '—';
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}${suffix}`;
  };

  const formatCompact = (value) => {
    if (value == null || Number.isNaN(value)) return '—';
    const abs = Math.abs(value);
    if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
    return `${value.toFixed(0)}`;
  };

  const toneForTrend = (value, betterLower = false) => {
    if (value == null || Number.isNaN(value)) return 'neutral';
    if (betterLower) return value < 0 ? 'good' : 'warn';
    return value > 0 ? 'good' : 'warn';
  };

  const toneForDecoupling = (value) => {
    if (value == null || Number.isNaN(value)) return 'neutral';
    const pct = Math.abs(value * 100);
    return pct <= 5 ? 'good' : (pct <= 10 ? 'warn' : 'bad');
  };

  const tooltip = (summary, calc, improve) => ({
    summary,
    calc,
    improve
  });

  const insights = [
    {
      id: 'vdot',
      label: 'VDOT (best 12m)',
      value: vdot != null ? vdot.toFixed(1) : '—',
      tone: vdot != null ? 'good' : 'neutral',
      hint: 'Performance-based estimate',
      tooltip: tooltip(
        'Estimated aerobic performance based on your best 12‑month race‑equivalent effort.',
        'Calculated using VDOT from the fastest eligible run ≥5K in the last 12 months.',
        'Higher is better.'
      )
    },
    {
      id: 'pace_trend',
      label: 'Pace trend (12w)',
      value: formatSigned(paceTrend, ' sec/km/wk'),
      tone: toneForTrend(paceTrend, true),
      hint: 'Lower is better',
      tooltip: tooltip(
        'Weekly change in average pace over the last 12 weeks.',
        'Linear slope of weekly average pace (sec/km).',
        'More negative = improving.'
      )
    },
    {
      id: 'hr_trend',
      label: 'HR trend (12w)',
      value: formatSigned(hrTrend, ' bpm/wk'),
      tone: toneForTrend(hrTrend, true),
      hint: 'Lower is better',
      tooltip: tooltip(
        'Weekly change in average heart rate over the last 12 weeks.',
        'Linear slope of weekly average HR (bpm).',
        'More negative = improving.'
      )
    },
    {
      id: 'eff_trend',
      label: 'Efficiency trend (12w)',
      value: formatSigned(effTrend, ' /wk'),
      tone: toneForTrend(effTrend, false),
      hint: 'Higher is better',
      tooltip: tooltip(
        'Change in efficiency index over the last 12 weeks.',
        'Linear slope of weekly efficiency index.',
        'Positive = improving.'
      )
    },
    {
      id: 'decoupling',
      label: 'Decoupling (28d)',
      value: decoupling != null ? `${decoupling.toFixed(1)}%` : '—',
      tone: toneForDecoupling(decoupling),
      hint: 'Closer to 0 is better',
      tooltip: tooltip(
        'How much pace and HR drift apart during runs.',
        'Average decoupling across recent runs (last 28 days).',
        'Closer to 0 = better aerobic efficiency.'
      )
    },
    {
      id: 'monotony',
      label: 'Monotony (wk)',
      value: monotony != null ? monotony.toFixed(2) : '—',
      tone: 'neutral',
      hint: 'Higher = less variation',
      tooltip: tooltip(
        'Training variety indicator.',
        'Mean daily load ÷ standard deviation of daily load (weekly).',
        'Lower usually indicates healthier variation.'
      )
    },
    {
      id: 'strain',
      label: 'Strain (wk)',
      value: strain != null ? strain.toFixed(1) : '—',
      tone: 'neutral',
      hint: 'Monotony × volume',
      tooltip: tooltip(
        'Overall training stress for the week.',
        'Weekly load × monotony.',
        'Higher can indicate more stress; watch for spikes.'
      )
    },
    {
      id: 'volume',
      label: 'Run volume',
      value: (dist7 != null && dist28 != null) ? `${dist7.toFixed(1)} / ${dist28.toFixed(1)} km` : '—',
      tone: 'neutral',
      hint: '7d / 28d',
      tooltip: tooltip(
        'Total running distance.',
        'Sum of run distance over the last 7 and 28 days.',
        'Higher usually indicates more training volume.'
      )
    },
    {
      id: 'fatigue_load',
      label: 'Weekly fatigue (4w avg)',
      value: fatigueAvg4w != null ? `${formatCompact(fatigueAvg4w)}` : '—',
      tone: 'neutral',
      hint: fatigueLast != null ? `Last week: ${formatCompact(fatigueLast)}` : 'Load = moving_s × avg HR',
      tooltip: tooltip(
        'Weekly training load proxy.',
        'moving_s × avg HR (weekly), averaged over 4 weeks.',
        'Higher = more load; watch for sudden spikes.'
      )
    },
    {
      id: 'recovery_index',
      label: 'Recovery index (28d)',
      value: recoveryIndex != null ? `${recoveryIndex.toFixed(1)}` : '—',
      tone: recoveryIndex != null ? (recoveryIndex >= 70 ? 'good' : (recoveryIndex >= 50 ? 'warn' : 'bad')) : 'neutral',
      hint: 'Median efficiency vs best (0–100)',
      tooltip: tooltip(
        'How close your typical efficiency is to your best.',
        'Median efficiency ÷ max efficiency (last 28 days) × 100.',
        'Higher = better recovery/readiness.'
      )
    },
    {
      id: 'eff_trend_phr',
      label: 'Pace/HR efficiency trend',
      value: formatSigned(efficiencyTrend, ' /wk'),
      tone: toneForTrend(efficiencyTrend, false),
      hint: 'Higher is better',
      tooltip: tooltip(
        'Trend in pace per bpm.',
        '(1000/pace_sec) ÷ avg HR, trended over 12 weeks.',
        'Positive = improving.'
      )
    }
  ];

  const formatDate = (value) => (value ? String(value).slice(0, 10) : '—');
  const perf = [
    {
      id: 'pb_5k_all',
      label: 'PB 5K (all time)',
      value: pbAll[5000]?.time_s ? formatTime(pbAll[5000].time_s) : '—',
      hint: pbAll[5000]?.date ? formatDate(pbAll[5000].date) : '—'
    },
    {
      id: 'pb_10k_all',
      label: 'PB 10K (all time)',
      value: pbAll[10000]?.time_s ? formatTime(pbAll[10000].time_s) : '—',
      hint: pbAll[10000]?.date ? formatDate(pbAll[10000].date) : '—'
    },
    {
      id: 'pb_5k_12m',
      label: 'PB 5K (12m)',
      value: pb12m[5000]?.time_s ? formatTime(pb12m[5000].time_s) : '—',
      hint: pb12m[5000]?.date ? formatDate(pb12m[5000].date) : '—'
    },
    {
      id: 'pb_10k_12m',
      label: 'PB 10K (12m)',
      value: pb12m[10000]?.time_s ? formatTime(pb12m[10000].time_s) : '—',
      hint: pb12m[10000]?.date ? formatDate(pb12m[10000].date) : '—'
    },
    {
      id: 'est_5k',
      label: 'Estimated 5K',
      value: est5k ? formatTime(est5k) : '—',
      hint: 'Segment-based'
    },
    {
      id: 'est_10k',
      label: 'Estimated 10K',
      value: est10k ? formatTime(est10k) : '—',
      hint: 'Segment-based'
    }
  ];

  return { insights, performance: perf };
}

function labelFor(type) {
  if (type === 'run') return 'Running';
  if (type === 'golf') return 'Golf';
  if (type === 'walk') return 'Walking';
  return type;
}

function normalizeAccent(type) {
  if (type === 'golf') return 'golf';
  if (type === 'walk') return 'neutral';
  return 'run';
}

function buildWeekRange(weekStart) {
  const [year, month, day] = weekStart.split('-').map((part) => Number(part));
  const start = new Date(Date.UTC(year, month - 1, day, 0, 0, 0));
  const end = new Date(Date.UTC(year, month - 1, day, 23, 59, 59, 999));
  end.setUTCDate(end.getUTCDate() + 6);
  return {
    start: start.toISOString(),
    end: end.toISOString()
  };
}

async function fetchActivitiesPage(apiFetch, filter, offset, limit) {
  const params = new URLSearchParams();
  params.set('type', filter.type);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  if (filter.start) params.set('start', filter.start);
  if (filter.end) params.set('end', filter.end);
  const res = await apiFetch(`/activities?${params.toString()}`);
  return res.json();
}

const PAGE_SIZE = 20;

function buildLapTotals(laps) {
  if (!laps.length) return null;
  const totalTime = laps.reduce((sum, lap) => sum + (lap.time || 0), 0);
  const totalDistM = laps.reduce((sum, lap) => sum + (lap.distance_m || 0), 0);
  const totalElev = laps.reduce((sum, lap) => sum + (lap.elev_change_m || 0), 0);
  const totalDistKm = totalDistM / 1000;
  const avgPace = totalDistKm > 0 ? totalTime / totalDistKm : null;
  let flatTime = 0;
  laps.forEach((lap) => {
    if (lap.flat_pace_sec && lap.distance_m) {
      flatTime += lap.flat_pace_sec * (lap.distance_m / 1000);
    }
  });
  const flatPace = totalDistKm > 0 && flatTime > 0 ? flatTime / totalDistKm : null;
  return {
    lap: 'Total',
    time: formatTime(totalTime),
    distance: totalDistKm.toFixed(2),
    pace: avgPace ? formatPace(avgPace) : '—',
    elev: `${Math.round(totalElev)} m`,
    flat: flatPace ? formatPace(flatPace) : '—'
  };
}

function formatLastUpdate(value) {
  if (!value) return null;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  const dd = String(dt.getDate()).padStart(2, '0');
  const mm = String(dt.getMonth() + 1).padStart(2, '0');
  const yyyy = dt.getFullYear();
  const hh = String(dt.getHours()).padStart(2, '0');
  const min = String(dt.getMinutes()).padStart(2, '0');
  return `${dd}/${mm}/${yyyy} - ${hh}:${min}`;
}
function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatPace(secPerKm) {
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${String(s).padStart(2, '0')} /km`;
}
