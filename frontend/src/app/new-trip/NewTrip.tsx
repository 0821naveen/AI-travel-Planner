import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../../components/Card';
import {
  cancelRun,
  clearActiveRunId,
  clearClarificationState,
  clearPlannerState,
  fetchRun,
  fetchRunSteps,
  fetchTrip,
  rerunRun,
  loadActiveRunId,
  saveActiveRunId,
  savePlannerRequest,
  savePlannerState,
  type PlannerRequest,
  type PlannerJobResponse,
  type WorkflowRunResponse,
  type WorkflowRunStepResponse,
} from '../../lib/planner';
import styles from '../AppPage.module.css';

const IconFrame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className={styles.titleIcon}>{children}</span>
);

const SectionTitle: React.FC<{ title: string; icon: React.ReactNode }> = ({ title, icon }) => (
  <div className={styles.cardHeader}>
    <IconFrame>{icon}</IconFrame>
    <h2 className={styles.title}>{title}</h2>
  </div>
);

type TripForm = {
  originCity: string;
  destination: string;
  startDate: string;
  endDate: string;
  budget: string;
  travelerCount: string;
  tripPurpose: string;
  budgetTier: string;
  pace: string;
  preferences: string;
  accommodationPreference: string;
  transportPreference: string;
  constraints: string;
};

const initialForm: TripForm = {
  originCity: '',
  destination: '',
  startDate: '',
  endDate: '',
  budget: '',
  travelerCount: '1',
  tripPurpose: 'leisure',
  budgetTier: 'mid_range',
  pace: 'balanced',
  preferences: '',
  accommodationPreference: '',
  transportPreference: '',
  constraints: '',
};

const requiredFields: Array<keyof TripForm> = [
  'originCity',
  'destination',
  'startDate',
  'endDate',
  'budget',
];

const fieldLabel: Record<keyof TripForm, string> = {
  originCity: 'Origin City',
  destination: 'Destination',
  startDate: 'Start Date',
  endDate: 'End Date',
  budget: 'Budget',
  travelerCount: 'Traveler Count',
  tripPurpose: 'Trip Purpose',
  budgetTier: 'Budget Tier',
  pace: 'Pace',
  preferences: 'Preferences',
  accommodationPreference: 'Accommodation Preference',
  transportPreference: 'Transport Preference',
  constraints: 'Constraints',
};

const RUNTIME_PHASES = [
  'clarification',
  'research',
  'itinerary',
  'parallel_planning',
  'budget',
  'review',
  'governance',
] as const;

function normalizeRuntimeStep(stepName?: string | null): string {
  if (!stepName) {
    return '';
  }
  const value = stepName.trim().toLowerCase();
  if (['clarification', 'clarification_validator'].includes(value)) return 'clarification';
  if (['research_signal_agent', 'destination_research', 'destination_research_agent'].includes(value)) return 'research';
  if (['itinerary', 'itinerary_planning_agent'].includes(value)) return 'itinerary';
  if (['parallel_batch', 'stay', 'stay_recommendation_agent', 'transport', 'local_transport_agent', 'food', 'food_recommendation_agent', 'safety', 'solo_women_safety_advisor_agent'].includes(value)) {
    return 'parallel_planning';
  }
  if (['budget', 'budget_optimization_agent'].includes(value)) return 'budget';
  if (['review', 'review_and_consistency_agent'].includes(value)) return 'review';
  if (['governance', 'governance_gate_agent'].includes(value)) return 'governance';
  if (value === 'coordinator_agent') return 'coordination';
  return value;
}

function formatRuntimeLabel(stepName?: string | null): string {
  const normalized = normalizeRuntimeStep(stepName);
  const labels: Record<string, string> = {
    clarification: 'Clarification',
    research: 'Destination Research',
    itinerary: 'Itinerary Planning',
    parallel_planning: 'Parallel Planning',
    budget: 'Budget Review',
    review: 'Consistency Review',
    governance: 'Governance Check',
    coordination: 'Coordinator Routing',
  };
  return labels[normalized] || stepName || 'Waiting to start';
}

const NewTrip: React.FC = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<TripForm>(initialForm);
  const [saveMessage, setSaveMessage] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string>('');
  const [activeJob, setActiveJob] = useState<PlannerJobResponse | null>(null);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [activeSteps, setActiveSteps] = useState<WorkflowRunStepResponse[]>([]);
  const shouldNavigateOnRunCompletion = useRef(false);

  const completedFields = requiredFields.filter((field) => form[field].trim().length > 0).length;
  const completeness = Math.round((completedFields / requiredFields.length) * 100);
  const missingFields = requiredFields.filter((field) => form[field].trim().length === 0);

  const start = form.startDate ? new Date(form.startDate) : null;
  const end = form.endDate ? new Date(form.endDate) : null;
  const hasValidDateRange = Boolean(start && end && start <= end);
  const tripDays = hasValidDateRange && start && end
    ? Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1)
    : 0;

  const parsedBudget = Number(form.budget);
  const hasValidBudget = Number.isFinite(parsedBudget) && parsedBudget > 0;

  const preferenceHighlights = useMemo(
    () =>
      form.preferences
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
        .slice(0, 4),
    [form.preferences],
  );

  const readinessChecks = [
    { label: 'All required fields are filled', passed: missingFields.length === 0 },
    { label: 'Travel dates are valid', passed: hasValidDateRange },
    { label: 'Budget is greater than 0', passed: hasValidBudget },
  ];

  const passedChecks = readinessChecks.filter((item) => item.passed).length;
  const isReady = readinessChecks.every((item) => item.passed);
  const uniqueObservedStepCount = useMemo(
    () => new Set(activeSteps.map((step) => step.step_name)).size,
    [activeSteps],
  );
  const observedPhaseCount = useMemo(
    () => new Set(activeSteps.map((step) => normalizeRuntimeStep(step.step_name)).filter(Boolean)).size,
    [activeSteps],
  );
  const retryAttemptCount = useMemo(
    () => Math.max(0, activeSteps.reduce((maxRetry, step) => Math.max(maxRetry, step.retry_count), 0)),
    [activeSteps],
  );
  const activePhase = useMemo(() => {
    const current = normalizeRuntimeStep(activeRun?.current_step);
    if (current && current !== 'coordination') {
      return current;
    }
    const lastCompleted = normalizeRuntimeStep(activeRun?.last_completed_step);
    if (lastCompleted) {
      return lastCompleted;
    }
    return '';
  }, [activeRun]);
  const progressPercent = useMemo(() => {
    if (!activeRun) {
      return 0;
    }
    if (activeRun.status === 'succeeded') {
      return 100;
    }
    if (['failed', 'dead_lettered', 'cancelled'].includes(activeRun.status)) {
      const lastPhaseIndex = RUNTIME_PHASES.indexOf(activePhase as typeof RUNTIME_PHASES[number]);
      return lastPhaseIndex >= 0 ? Math.round(((lastPhaseIndex + 1) / RUNTIME_PHASES.length) * 100) : 0;
    }
    const phaseIndex = RUNTIME_PHASES.indexOf(activePhase as typeof RUNTIME_PHASES[number]);
    if (phaseIndex >= 0) {
      return Math.max(10, Math.round(((phaseIndex + 0.5) / RUNTIME_PHASES.length) * 100));
    }
    return uniqueObservedStepCount > 0 ? Math.min(100, Math.round((observedPhaseCount / RUNTIME_PHASES.length) * 100)) : 8;
  }, [activePhase, activeRun, observedPhaseCount, uniqueObservedStepCount]);
  const canCancelActiveRun = activeRun && ['queued', 'running', 'pending'].includes(activeRun.status);
  const canRerunActiveRun = activeRun && ['failed', 'dead_lettered', 'cancelled'].includes(activeRun.status);
  const currentStageLabel = formatRuntimeLabel(activeRun?.current_step || activeRun?.last_completed_step || '');
  const runtimeSummary = useMemo(() => {
    if (!activeRun) {
      return 'Waiting to start';
    }
    if (activeRun.status === 'succeeded') {
      return 'Workflow complete';
    }
    if (activeRun.status === 'queued' || activeRun.status === 'pending') {
      return 'Queued for execution';
    }
    if (activeRun.status === 'running' && normalizeRuntimeStep(activeRun.current_step) === 'coordination') {
      return 'Coordinator is routing the next specialist';
    }
    if (activeRun.status === 'running' && normalizeRuntimeStep(activeRun.current_step) === 'parallel_planning') {
      return 'Stay, transport, food, and safety planning can run together here';
    }
    if (activeRun.status === 'running') {
      return `${currentStageLabel} is in progress`;
    }
    if (activeRun.status === 'failed' || activeRun.status === 'dead_lettered') {
      return `${currentStageLabel} stopped before completion`;
    }
    if (activeRun.status === 'cancelled') {
      return 'Workflow was cancelled';
    }
    return currentStageLabel;
  }, [activeRun, currentStageLabel]);

  const updateField = (field: keyof TripForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaveMessage('');
    setSubmitError('');
  };

  const fillSample = () => {
    setForm({
      originCity: 'Bengaluru',
      destination: 'Tokyo',
      startDate: '2026-04-05',
      endDate: '2026-04-14',
      budget: '4200',
      travelerCount: '1',
      tripPurpose: 'leisure',
      budgetTier: 'mid_range',
      pace: 'balanced',
      preferences: 'Temple visits, local food, train travel, cherry blossoms',
      accommodationPreference: 'Boutique hotels in lively neighborhoods',
      transportPreference: 'Trains and occasional taxis',
      constraints: 'Vegetarian-friendly options, avoid overnight buses, prefer well-lit late-evening returns',
    });
    setSaveMessage('');
    setSubmitError('');
  };

  const saveDraft = () => {
    localStorage.setItem('tripDraft', JSON.stringify(form));
    setSaveMessage('Draft saved locally.');
  };

  const resetForm = () => {
    shouldNavigateOnRunCompletion.current = false;
    clearPlannerState();
    setForm(initialForm);
    setSaveMessage('Draft cleared.');
    setSubmitError('');
    setActiveJob(null);
    setActiveRun(null);
    setActiveSteps([]);
  };

  const buildRequest = useCallback((): PlannerRequest => ({
    origin_city: form.originCity.trim(),
    destination: form.destination.trim(),
    start_date: form.startDate,
    end_date: form.endDate,
    traveler_count: Number(form.travelerCount),
    trip_purpose: form.tripPurpose,
    total_budget: Number(form.budget),
    budget_tier: form.budgetTier,
    pace: form.pace,
    interests: form.preferences.split(',').map((item) => item.trim()).filter(Boolean),
    accommodation_preference: form.accommodationPreference.trim(),
    transport_preference: form.transportPreference.trim(),
    constraints: {
      dietary_restrictions: [],
      accessibility_needs: [],
      visa_required: null,
      child_friendly: false,
      elderly_travelers: false,
      remote_work_needs: false,
      notes: form.constraints.trim() || null,
    },
  }), [form]);

  const handleCompletedRun = useCallback(async (run: WorkflowRunResponse) => {
    const trip = await fetchTrip(run.trip_id);
    savePlannerState(buildRequest(), trip);
    if (trip.clarification_needed) {
      navigate('/clarification');
      return;
    }
    if (trip.trip.status === 'ready_for_review') {
      navigate(`/review?tripId=${trip.trip.trip_id}`);
      return;
    }
    navigate('/research');
  }, [buildRequest, navigate]);

  const refreshRunState = useCallback(async (runId: string, navigateOnCompletion = false) => {
    try {
      const [run, steps] = await Promise.all([fetchRun(runId), fetchRunSteps(runId)]);
      setActiveRun(run);
      setActiveSteps(steps);
      saveActiveRunId(run.run_id);
      if (run.status === 'succeeded' && navigateOnCompletion) {
        await handleCompletedRun(run);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to refresh workflow status.';
      if (message.includes('Run not found')) {
        clearActiveRunId();
        setActiveRun(null);
        setActiveJob(null);
        setActiveSteps([]);
        setSubmitError('');
        return;
      }
      throw error;
    }
  }, [handleCompletedRun]);

  useEffect(() => {
    const runId = loadActiveRunId();
    if (!runId) {
      return;
    }
    void refreshRunState(runId, false).catch((error) => {
      setSubmitError(error instanceof Error ? error.message : 'Failed to refresh workflow status.');
    });
  }, [refreshRunState]);

  useEffect(() => {
    if (!activeRun || !['queued', 'running', 'pending'].includes(activeRun.status)) {
      return;
    }

    const timer = window.setInterval(() => {
      void refreshRunState(activeRun.run_id, shouldNavigateOnRunCompletion.current).catch((error) => {
        setSubmitError(error instanceof Error ? error.message : 'Failed to refresh workflow status.');
      });
    }, 2000);

    return () => window.clearInterval(timer);
  }, [activeRun, refreshRunState]);

  const submitTrip = async () => {
    if (!isReady || isSubmitting) {
      return;
    }
    const request = buildRequest();

    setIsSubmitting(true);
    setSubmitError('');

    try {
      shouldNavigateOnRunCompletion.current = false;
      clearPlannerState();
      clearClarificationState();
      clearActiveRunId();
      savePlannerRequest(request);
      setActiveJob(null);
      setActiveRun(null);
      setActiveSteps([]);
      navigate('/clarification');
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to prepare clarification.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const requestRunCancellation = async () => {
    if (!activeRun || !canCancelActiveRun) {
      return;
    }
    try {
      const updated = await cancelRun(activeRun.run_id);
      setActiveRun(updated);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to cancel the run.');
    }
  };

  const requestRunRerun = async () => {
    if (!activeRun || !canRerunActiveRun) {
      return;
    }
    try {
      shouldNavigateOnRunCompletion.current = true;
      const updated = await rerunRun(activeRun.run_id);
      setActiveRun(updated);
      setActiveSteps([]);
      saveActiveRunId(updated.run_id);
      await refreshRunState(updated.run_id, true);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to rerun the workflow.');
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.mainSidebar}>
        <Card variant="default">
          <SectionTitle
            title="Trip Details"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 21s7-4.4 7-11a7 7 0 1 0-14 0c0 6.6 7 11 7 11Z" />
                <circle cx="12" cy="10" r="2.5" />
              </svg>
            }
          />
          <form className={styles.form}>
            <label>
              Origin City
              <input
                type="text"
                placeholder="e.g. Bengaluru"
                value={form.originCity}
                onChange={(event) => updateField('originCity', event.target.value)}
              />
            </label>
            <label>
              Destination
              <input
                type="text"
                placeholder="e.g. Tokyo"
                value={form.destination}
                onChange={(event) => updateField('destination', event.target.value)}
              />
            </label>
            <label>
              Start Date
              <input
                type="date"
                value={form.startDate}
                onChange={(event) => updateField('startDate', event.target.value)}
              />
            </label>
            <label>
              End Date
              <input
                type="date"
                value={form.endDate}
                onChange={(event) => updateField('endDate', event.target.value)}
              />
            </label>
            <label>
              Budget (USD)
              <input
                type="number"
                placeholder="e.g. 5000"
                value={form.budget}
                onChange={(event) => updateField('budget', event.target.value)}
              />
            </label>
            <label>
              Traveler Count
              <input
                type="number"
                min="1"
                value={form.travelerCount}
                onChange={(event) => updateField('travelerCount', event.target.value)}
              />
            </label>
            <label>
              Trip Purpose
              <select
                value={form.tripPurpose}
                onChange={(event) => updateField('tripPurpose', event.target.value)}
              >
                <option value="leisure">Leisure</option>
                <option value="family">Family</option>
                <option value="workation">Workation</option>
                <option value="honeymoon">Honeymoon</option>
                <option value="adventure">Adventure</option>
              </select>
            </label>
            <label>
              Budget Tier
              <select
                value={form.budgetTier}
                onChange={(event) => updateField('budgetTier', event.target.value)}
              >
                <option value="budget">Budget</option>
                <option value="mid_range">Mid Range</option>
                <option value="premium">Premium</option>
                <option value="luxury">Luxury</option>
              </select>
            </label>
            <label>
              Pace
              <select
                value={form.pace}
                onChange={(event) => updateField('pace', event.target.value)}
              >
                <option value="slow">Slow</option>
                <option value="balanced">Balanced</option>
                <option value="fast">Fast</option>
              </select>
            </label>
            <label>
              Preferences
              <textarea
                placeholder="e.g. Museums, beaches, local food"
                value={form.preferences}
                onChange={(event) => updateField('preferences', event.target.value)}
              />
            </label>
            <label>
              Accommodation Preference
              <input
                type="text"
                placeholder="e.g. Boutique hotels, central neighborhoods"
                value={form.accommodationPreference}
                onChange={(event) => updateField('accommodationPreference', event.target.value)}
              />
            </label>
            <label>
              Transport Preference
              <input
                type="text"
                placeholder="e.g. Trains, metro, minimal flights"
                value={form.transportPreference}
                onChange={(event) => updateField('transportPreference', event.target.value)}
              />
            </label>
            <label>
              Constraints
              <textarea
                placeholder="e.g. Vegetarian meals, accessibility needs, late-night safety preferences"
                value={form.constraints}
                onChange={(event) => updateField('constraints', event.target.value)}
              />
            </label>
          </form>
        </Card>
        <div className={styles.stack}>
          <Card variant="metric">
            <SectionTitle
              title="Traveler Profile Preview"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M5 21a7 7 0 0 1 14 0" />
                </svg>
              }
            />
            <div className={styles.kvList}>
              <div><span className={styles.muted}>Route</span><strong>{form.originCity && form.destination ? `${form.originCity} to ${form.destination}` : 'Not set'}</strong></div>
              <div><span className={styles.muted}>Duration</span><strong>{tripDays ? `${tripDays} days` : 'Set dates'}</strong></div>
              <div><span className={styles.muted}>Budget / Day</span><strong>{tripDays && hasValidBudget ? `$${Math.round(parsedBudget / tripDays)}` : '-'}</strong></div>
            </div>
            <div className={styles.chips}>
              {preferenceHighlights.length > 0 ? preferenceHighlights.map((item) => (
                <span key={item} className={styles.chip}>{item}</span>
              )) : <span className={styles.placeholder}>Add preferences to generate traveler profile highlights.</span>}
            </div>
            <div className={styles.inlineActions}>
              <button type="button" onClick={fillSample}>Use Sample</button>
            </div>
          </Card>

          <Card variant="insight">
            <SectionTitle
              title="Input Completeness"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 12h4l2 5 4-10 2 5h4" />
                </svg>
              }
            />
            <div className={styles.progressMeta}>
              <span>{completedFields}/{requiredFields.length} fields completed</span>
              <strong>{completeness}%</strong>
            </div>
            <div className={styles.progressTrack}>
              <div className={styles.progressFill} style={{ width: `${completeness}%` }} />
            </div>
            {missingFields.length > 0 ? (
              <ul className={styles.missingList}>
                {missingFields.map((field) => <li key={field}>{fieldLabel[field]} missing</li>)}
              </ul>
            ) : (
              <div className={styles.okText}>All required inputs provided.</div>
            )}
          </Card>

          <Card variant="review">
            <SectionTitle
              title="Agent Readiness"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 11l3 3L22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
              }
            />
            <ul className={styles.readinessList}>
              {readinessChecks.map((check) => (
                <li key={check.label}>
                  <span className={check.passed ? styles.okDot : styles.pendingDot} />
                  {check.label}
                </li>
              ))}
            </ul>
            <div className={styles.readinessSummary}>
              <span className={styles.muted}>Checks passed</span>
              <strong>{passedChecks}/{readinessChecks.length}</strong>
            </div>
          </Card>

          {(activeRun || activeJob) ? (
            <Card variant={activeRun && ['failed', 'dead_lettered', 'cancelled'].includes(activeRun.status) ? 'caution' : 'review'}>
              <SectionTitle
                title="Workflow Runtime"
                icon={
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="6" cy="18" r="2" />
                    <circle cx="18" cy="6" r="2" />
                    <circle cx="18" cy="18" r="2" />
                    <path d="M8 18h8" />
                    <path d="M18 8v8" />
                    <path d="M7.5 16.5 16.5 7.5" />
                  </svg>
                }
              />
              <div className={styles.kvList}>
                <div><span className={styles.muted}>Run</span><strong>{activeRun?.run_id || activeJob?.run_id || '-'}</strong></div>
                <div><span className={styles.muted}>Job</span><strong>{activeJob?.job_id || activeRun?.job_id || '-'}</strong></div>
                <div><span className={styles.muted}>Status</span><strong>{activeRun?.status || activeJob?.status || 'queued'}</strong></div>
                <div><span className={styles.muted}>Live Phase</span><strong>{currentStageLabel}</strong></div>
              </div>
              <div className={styles.progressMeta}>
                <span>{runtimeSummary}</span>
                <strong>{progressPercent}%</strong>
              </div>
              <div className={styles.progressTrack}>
                <div className={styles.progressFill} style={{ width: `${progressPercent}%` }} />
              </div>
              <div className={styles.muted}>
                {observedPhaseCount > 0
                  ? `${observedPhaseCount}/${RUNTIME_PHASES.length} major phases observed`
                  : 'Detailed agent steps appear as the coordinator records progress.'}
              </div>
              {retryAttemptCount > 0 ? (
                <div className={styles.muted}>Retries attempted: {retryAttemptCount}</div>
              ) : null}
              {activeRun?.error ? <div className={styles.errorText}>{activeRun.error}</div> : null}
              <div className={styles.inlineActions}>
                <button type="button" onClick={requestRunCancellation} disabled={!canCancelActiveRun}>Cancel Run</button>
                <button type="button" onClick={requestRunRerun} disabled={!canRerunActiveRun}>Rerun Workflow</button>
              </div>
            </Card>
          ) : null}
        </div>
      </div>
      <div className={styles.stickyActions}>
        <button type="button" onClick={saveDraft}>Save Draft</button>
        <button type="button" onClick={resetForm}>Reset</button>
        <button type="button" className={styles.primary} disabled={!isReady || isSubmitting} onClick={submitTrip}>
          {isSubmitting ? 'Preparing...' : 'Continue to Clarification'}
        </button>
      </div>
      {saveMessage && <div className={styles.saveNotice}>{saveMessage}</div>}
      {!isReady && (
        <div className={styles.placeholder}>
          Fill the required fields: {missingFields.map((field) => fieldLabel[field]).join(', ')}.
        </div>
      )}
      {submitError && <div className={styles.errorText}>{submitError}</div>}
    </div>
  );
};

export default NewTrip;
