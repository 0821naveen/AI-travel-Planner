import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Card from '../../components/Card';
import {
  cancelRun,
  clearActiveRunId,
  clearClarificationState,
  createTripAsync,
  fetchClarificationCopilot,
  fetchRun,
  fetchRunSteps,
  fetchTrip,
  loadActiveRunId,
  loadClarificationState,
  loadPlannerRequest,
  rerunRun,
  saveActiveRunId,
  saveClarificationState,
  savePlannerRequest,
  savePlannerState,
  type ClarificationAnswer,
  type ClarificationCopilotResponse,
  type PlannerJobResponse,
  type WorkflowRunResponse,
  type WorkflowRunStepResponse,
} from '../../lib/planner';
import styles from '../AppPage.module.css';

type TranscriptAnswer = ClarificationAnswer & { question?: string };

const RUNTIME_PHASES = [
  'clarification',
  'research',
  'itinerary',
  'parallel_planning',
  'budget',
  'review',
  'governance',
] as const;

function sameRequestShape(left: unknown, right: unknown): boolean {
  try {
    return JSON.stringify(left) === JSON.stringify(right);
  } catch {
    return false;
  }
}

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

const Clarification: React.FC = () => {
  const navigate = useNavigate();
  const persisted = loadClarificationState();
  const initialRequest = loadPlannerRequest();
  const [copilot, setCopilot] = useState<ClarificationCopilotResponse | null>(persisted?.state ?? null);
  const [answers, setAnswers] = useState<TranscriptAnswer[]>((persisted?.answers as TranscriptAnswer[] | undefined) ?? []);
  const [customAnswer, setCustomAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStartingRun, setIsStartingRun] = useState(false);
  const [error, setError] = useState('');
  const [activeJob, setActiveJob] = useState<PlannerJobResponse | null>(null);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [activeSteps, setActiveSteps] = useState<WorkflowRunStepResponse[]>([]);
  const shouldNavigateOnRunCompletion = useRef(false);

  const loadCopilot = useCallback(async (overrideAnswers?: TranscriptAnswer[]) => {
    const request = loadPlannerRequest();
    if (!request) {
      return;
    }
    const transcript = overrideAnswers ?? answers;
    setIsLoading(true);
    setError('');
    try {
      const nextState = await fetchClarificationCopilot(
        request,
        transcript.map(({ key, answer }) => ({ key, answer })),
      );
      setCopilot(nextState);
      savePlannerRequest(nextState.normalized_request);
      saveClarificationState(nextState, transcript);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load clarification copilot.');
    } finally {
      setIsLoading(false);
    }
  }, [answers]);

  const handleCompletedRun = useCallback(async (run: WorkflowRunResponse) => {
    const trip = await fetchTrip(run.trip_id);
    if (copilot) {
      savePlannerState(copilot.normalized_request, trip);
    }
    clearClarificationState();
    if (trip.trip.status === 'ready_for_review') {
      navigate(`/review?tripId=${trip.trip.trip_id}`);
      return;
    }
    navigate('/research');
  }, [copilot, navigate]);

  const refreshRunState = useCallback(async (runId: string, navigateOnCompletion = false) => {
    const [run, steps] = await Promise.all([fetchRun(runId), fetchRunSteps(runId)]);
    setActiveRun(run);
    setActiveSteps(steps);
    saveActiveRunId(run.run_id);
    if (run.status === 'succeeded' && navigateOnCompletion) {
      await handleCompletedRun(run);
    }
  }, [handleCompletedRun]);

  useEffect(() => {
    if (!initialRequest) {
      return;
    }
    const needsBootstrap = !copilot
      || (!copilot.ready_to_plan && !copilot.question)
      || !sameRequestShape(copilot.normalized_request, initialRequest);
    if (needsBootstrap) {
      void loadCopilot();
    }
  }, [copilot, initialRequest, loadCopilot]);

  useEffect(() => {
    const runId = loadActiveRunId();
    if (!runId) {
      return;
    }
    void refreshRunState(runId, false).catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to refresh workflow status.');
    });
  }, [refreshRunState]);

  useEffect(() => {
    if (!activeRun || !['queued', 'running', 'pending'].includes(activeRun.status)) {
      return;
    }

    const timer = window.setInterval(() => {
      void refreshRunState(activeRun.run_id, shouldNavigateOnRunCompletion.current).catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to refresh workflow status.');
      });
    }, 2000);

    return () => window.clearInterval(timer);
  }, [activeRun, refreshRunState]);

  const submitAnswer = async (answer: string) => {
    if (!copilot?.question || isLoading) {
      return;
    }
    const nextAnswers = [
      ...answers,
      {
        key: copilot.question.key,
        answer,
        question: copilot.question.prompt,
      },
    ];
    setAnswers(nextAnswers);
    setCustomAnswer('');
    await loadCopilot(nextAnswers);
  };

  const startPlanning = async () => {
    if (!copilot?.ready_to_plan || isStartingRun) {
      return;
    }
    setIsStartingRun(true);
    setError('');
    try {
      shouldNavigateOnRunCompletion.current = true;
      const job = await createTripAsync(copilot.normalized_request);
      setActiveJob(job);
      if (job.run_id) {
        await refreshRunState(job.run_id, true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start the planner.');
    } finally {
      setIsStartingRun(false);
    }
  };

  const requestRunCancellation = async () => {
    if (!activeRun || !['queued', 'running', 'pending'].includes(activeRun.status)) {
      return;
    }
    try {
      const updated = await cancelRun(activeRun.run_id);
      setActiveRun(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel the run.');
    }
  };

  const requestRunRerun = async () => {
    if (!activeRun || !['failed', 'dead_lettered', 'cancelled'].includes(activeRun.status)) {
      return;
    }
    try {
      shouldNavigateOnRunCompletion.current = true;
      const updated = await rerunRun(activeRun.run_id);
      setActiveRun(updated);
      setActiveSteps([]);
      saveActiveRunId(updated.run_id);
      await refreshRunState(updated.run_id, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rerun the workflow.');
    }
  };

  const progressPercent = useMemo(() => {
    if (!activeRun) {
      if (copilot?.ready_to_plan) {
        return 100;
      }
      return Math.min(90, ((answers.length + 1) / Math.max(1, answers.length + (copilot?.remaining_questions ?? 1) + 1)) * 100);
    }
    if (activeRun.status === 'succeeded') {
      return 100;
    }
    const phase = normalizeRuntimeStep(activeRun.current_step || activeRun.last_completed_step);
    const phaseIndex = RUNTIME_PHASES.indexOf(phase as typeof RUNTIME_PHASES[number]);
    return phaseIndex >= 0 ? Math.round(((phaseIndex + 0.5) / RUNTIME_PHASES.length) * 100) : 12;
  }, [activeRun, answers.length, copilot]);

  const runtimeHeadline = useMemo(() => {
    if (!activeRun) {
      if (copilot?.ready_to_plan) {
        return 'Clarification complete. Ready to start planning.';
      }
      return 'Planner is waiting for your answers.';
    }
    if (activeRun.status === 'succeeded') {
      return 'Workflow complete';
    }
    if (activeRun.status === 'queued' || activeRun.status === 'pending') {
      return 'Workflow queued';
    }
    if (activeRun.status === 'running') {
      return `${formatRuntimeLabel(activeRun.current_step || activeRun.last_completed_step)} is in progress`;
    }
    if (activeRun.status === 'cancelled') {
      return 'Workflow was cancelled';
    }
    return 'Workflow stopped before completion';
  }, [activeRun, copilot]);

  if (!initialRequest) {
    return (
      <div className={styles.page}>
        <Card variant="metric">
          <h2 className={styles.title}>Clarification</h2>
          <div className={styles.placeholder}>No trip data found yet. Start from <Link to="/new-trip">New Trip</Link>.</div>
        </Card>
      </div>
    );
  }

  return (
    <div className={`${styles.page} ${styles.triptych}`}>
      <div className={styles.stack}>
        <Card variant="caution">
          <h2 className={styles.title}>Trip Context</h2>
          <div className={styles.kvList}>
            <div><span className={styles.muted}>Route</span><strong>{initialRequest.origin_city} to {initialRequest.destination}</strong></div>
            <div><span className={styles.muted}>Dates</span><strong>{initialRequest.start_date} to {initialRequest.end_date}</strong></div>
            <div><span className={styles.muted}>Travelers</span><strong>{initialRequest.traveler_count}</strong></div>
            <div><span className={styles.muted}>Purpose</span><strong>{initialRequest.trip_purpose}</strong></div>
          </div>
        </Card>
        <Card>
          <h2 className={styles.title}>Destination Signals</h2>
          {copilot?.destination_signals?.length ? (
            <div className={styles.stackTight}>
              {copilot.destination_signals.map((item) => (
                <div key={item} className={styles.detailCard}>
                  <div className={styles.signalBody}>{item}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.placeholder}>Loading location-specific context for the copilot.</div>
          )}
        </Card>
      </div>

      <div className={styles.stack}>
        <Card variant="review">
          <h2 className={styles.title}>Clarification Copilot</h2>
          <div className={styles.chatShell}>
            <div className={`${styles.chatBubble} ${styles.chatBubbleAgent}`}>
              I’ll ask only the details that materially change the plan. The goal is better routing for stay, food, timing, safety, and memorable moments.
            </div>
            {answers.map((item, index) => (
              <React.Fragment key={`${item.key}-${index}`}>
                {item.question ? <div className={`${styles.chatBubble} ${styles.chatBubbleAgent}`}>{item.question}</div> : null}
                <div className={`${styles.chatBubble} ${styles.chatBubbleUser}`}>{item.answer}</div>
              </React.Fragment>
            ))}
            {copilot?.question ? (
              <div className={`${styles.chatBubble} ${styles.chatBubbleAgent}`}>
                <div className={styles.detailQuestion}>{copilot.question.prompt}</div>
                <div className={styles.detailReason}>{copilot.question.reason}</div>
                {copilot.question.helper_text ? <div className={styles.signalBody}>{copilot.question.helper_text}</div> : null}
              </div>
            ) : null}
          </div>

          {copilot?.question ? (
            <>
              <div className={styles.optionGrid}>
                {copilot.question.options.map((option) => (
                  <button key={option.value} type="button" className={styles.optionButton} onClick={() => void submitAnswer(option.value)} disabled={isLoading}>
                    {option.label}
                  </button>
                ))}
              </div>
              {copilot.question.allow_custom ? (
                <div className={styles.inputRow}>
                  <input
                    type="text"
                    placeholder="Add a custom answer"
                    value={customAnswer}
                    onChange={(event) => setCustomAnswer(event.target.value)}
                  />
                  <button type="button" onClick={() => void submitAnswer(customAnswer)} disabled={isLoading || customAnswer.trim().length === 0}>
                    Send
                  </button>
                </div>
              ) : null}
            </>
          ) : null}

          {!copilot?.question && !copilot?.ready_to_plan ? (
            <div className={styles.inlineActions}>
              <div className={styles.placeholder}>
                {isLoading ? 'Loading the first clarification question.' : 'The copilot is preparing the next question.'}
              </div>
              {!isLoading ? (
                <button type="button" onClick={() => void loadCopilot()}>
                  Retry Question Load
                </button>
              ) : null}
            </div>
          ) : null}

          {copilot?.summary ? <div className={styles.signalBody}>{copilot.summary}</div> : null}
          {isLoading ? <div className={styles.placeholder}>Thinking through the next best question.</div> : null}
        </Card>
      </div>

      <div className={styles.stack}>
        <Card variant={activeRun && ['failed', 'dead_lettered', 'cancelled'].includes(activeRun.status) ? 'caution' : 'metric'}>
          <h2 className={styles.title}>Workflow Panel</h2>
          <div className={styles.kvList}>
            <div><span className={styles.muted}>Status</span><strong>{activeRun?.status || (copilot?.ready_to_plan ? 'ready' : 'waiting')}</strong></div>
            <div><span className={styles.muted}>Job</span><strong>{activeJob?.job_id || '-'}</strong></div>
            <div><span className={styles.muted}>Answered</span><strong>{answers.length}</strong></div>
            <div><span className={styles.muted}>Questions left</span><strong>{copilot?.remaining_questions ?? '-'}</strong></div>
            <div><span className={styles.muted}>Observed steps</span><strong>{activeSteps.length}</strong></div>
          </div>
          <div className={styles.progressMeta}>
            <span>{runtimeHeadline}</span>
            <strong>{Math.round(progressPercent)}%</strong>
          </div>
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: `${progressPercent}%` }} />
          </div>
          <div className={styles.muted}>
            {activeRun ? formatRuntimeLabel(activeRun.current_step || activeRun.last_completed_step) : 'The workflow starts only after clarification is complete.'}
          </div>
          <div className={styles.workflowActions}>
            <button type="button" className={styles.primary} onClick={() => void startPlanning()} disabled={!copilot?.ready_to_plan || isStartingRun}>
              {isStartingRun ? 'Starting...' : 'Start Planning'}
            </button>
            <button type="button" onClick={() => void requestRunCancellation()} disabled={!activeRun || !['queued', 'running', 'pending'].includes(activeRun.status)}>
              Cancel Run
            </button>
            <button type="button" onClick={() => void requestRunRerun()} disabled={!activeRun || !['failed', 'dead_lettered', 'cancelled'].includes(activeRun.status)}>
              Rerun Workflow
            </button>
          </div>
        </Card>
        <Card>
          <h2 className={styles.title}>Why This Step Exists</h2>
          <div className={styles.placeholder}>
            The planner is using this step to replace generic assumptions with guided answers before research and itinerary generation.
          </div>
          <div className={styles.inlineActions}>
            <button
              type="button"
              onClick={() => {
                clearClarificationState();
                clearActiveRunId();
                navigate('/new-trip');
              }}
            >
              Back to New Trip
            </button>
          </div>
        </Card>
      </div>
      {error ? <div className={styles.errorText}>{error}</div> : null}
    </div>
  );
};

export default Clarification;
