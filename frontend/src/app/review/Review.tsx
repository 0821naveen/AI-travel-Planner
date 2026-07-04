import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Card from '../../components/Card';
import ExportPanel from '../../components/ExportPanel';
import {
  AdminTripListItem,
  ApprovalDecisionRequest,
  TripReviewDetailResponse,
  WorkflowRunTraceResponse,
  decideTripApproval,
  fetchReviewQueue,
  fetchRunTrace,
  fetchTripReviewDetail,
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

function humanizeToken(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatGovernanceFlag(flag: string): string {
  const readableFlags: Record<string, string> = {
    budget_exceeds_target: 'Over budget',
    review_reported_issues: 'Review issues found',
    itinerary_outside_researched_areas: 'Outside researched areas',
    'low_confidence:destination_research': 'Weak destination research',
    'low_confidence:itinerary_plan': 'Weak itinerary draft',
    'low_confidence:stay_recommendation': 'Weak stay guidance',
    'low_confidence:local_transport': 'Weak transport guidance',
    'low_confidence:food_recommendation': 'Weak food guidance',
    'low_confidence:budget_assessment': 'Weak budget estimate',
    'low_confidence:review_assessment': 'Weak final review',
  };

  return readableFlags[flag] || flag.replace(/[_:]+/g, ' ');
}

function formatWorkflowStep(stepName: string): string {
  const readableSteps: Record<string, string> = {
    clarification_validator: 'Clarification Check',
    research_signal_agent: 'Planning Signals',
    destination_research_agent: 'Destination Research',
    itinerary_planning_agent: 'Itinerary Planning',
    stay_recommendation_agent: 'Stay Recommendations',
    local_transport_agent: 'Local Transport',
    food_recommendation_agent: 'Food Recommendations',
    budget_optimization_agent: 'Budget Review',
    solo_women_safety_advisor_agent: 'Safety Review',
    review_and_consistency_agent: 'Consistency Review',
    governance_gate_agent: 'Governance Check',
  };

  return readableSteps[stepName] || humanizeToken(stepName);
}

function formatEvidenceTitle(title: string): string {
  const normalized = title.trim().toLowerCase();
  if (normalized === 'review issue') {
    return 'Review warning';
  }
  if (normalized === 'governance flag') {
    return 'Plan warning';
  }
  return humanizeToken(title);
}

function formatEvidenceDetail(detail: string): string {
  const normalized = detail.trim();
  if (!normalized) {
    return '-';
  }

  if (normalized.startsWith('low_confidence:')) {
    return formatGovernanceFlag(normalized);
  }

  if (normalized === 'budget_exceeds_target') {
    return formatGovernanceFlag(normalized);
  }

  if (normalized === 'review_reported_issues') {
    return formatGovernanceFlag(normalized);
  }

  return normalized;
}

function formatTimelineTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
}

const Review: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [queue, setQueue] = useState<AdminTripListItem[]>([]);
  const [detail, setDetail] = useState<TripReviewDetailResponse | null>(null);
  const [trace, setTrace] = useState<WorkflowRunTraceResponse | null>(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [pendingAction, setPendingAction] = useState('');

  const tripId = searchParams.get('tripId');

  useEffect(() => {
    let active = true;
    const loadQueue = async () => {
      try {
        const items = await fetchReviewQueue();
        if (!active) {
          return;
        }
        setQueue(items);
        if (!tripId && items[0]?.trip_id) {
          setSearchParams({ tripId: items[0].trip_id }, { replace: true });
        }
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load review queue.');
      }
    };

    void loadQueue();
    return () => {
      active = false;
    };
  }, [setSearchParams, tripId]);

  useEffect(() => {
    let active = true;
    const loadDetail = async () => {
      if (!tripId) {
        setDetail(null);
        setTrace(null);
        return;
      }

      try {
        const detailResponse = await fetchTripReviewDetail(tripId);
        if (!active) {
          return;
        }
        setDetail(detailResponse);
        setNote(detailResponse.approval.note || '');
        if (detailResponse.trip.run_id) {
          const traceResponse = await fetchRunTrace(detailResponse.trip.run_id);
          if (active) {
            setTrace(traceResponse);
          }
        } else {
          setTrace(null);
        }
        setError('');
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load review detail.');
      }
    };

    void loadDetail();
    return () => {
      active = false;
    };
  }, [tripId]);

  const handleDecision = async (payload: ApprovalDecisionRequest) => {
    if (!tripId) {
      return;
    }
    setPendingAction(payload.action);
    try {
      const updated = await decideTripApproval(tripId, { ...payload, note });
      setDetail(updated);
      const items = await fetchReviewQueue();
      setQueue(items);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply approval decision.');
    } finally {
      setPendingAction('');
    }
  };

  if (!queue.length && !detail) {
    return (
      <div className={styles.page}>
        <Card variant="review">
          <SectionTitle
            title="Review Queue"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 6h13" />
                <path d="M8 12h13" />
                <path d="M8 18h13" />
                <path d="M3 6h.01" />
                <path d="M3 12h.01" />
                <path d="M3 18h.01" />
              </svg>
            }
          />
          <div className={styles.placeholder}>No review assessment is available yet. Start from <Link to="/new-trip">New Trip</Link>.</div>
        </Card>
      </div>
    );
  }

  return (
    <div className={`${styles.page} ${styles.mainSidebar}`}>
      <div className={styles.stack}>
        <Card variant="review">
          <SectionTitle
            title="Pending Operator Review"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 6h13" />
                <path d="M8 12h13" />
                <path d="M8 18h13" />
                <path d="M3 6h.01" />
                <path d="M3 12h.01" />
                <path d="M3 18h.01" />
              </svg>
            }
          />
          {!queue.length ? (
            <div className={styles.placeholder}>No trips are currently awaiting approval.</div>
          ) : (
            <ul className={styles.infoList}>
              {queue.map((item) => (
                <li key={item.trip_id}>
                  <button type="button" onClick={() => setSearchParams({ tripId: item.trip_id })}>
                    {item.destination} · {item.approval.status}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {trace ? (
          <Card>
            <SectionTitle
              title="Run Trace"
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
              <div><span className={styles.muted}>Run</span><strong>{trace.run.run_id}</strong></div>
              <div><span className={styles.muted}>Status</span><strong>{trace.run.status}</strong></div>
              <div><span className={styles.muted}>Retries</span><strong>{trace.run.retry_count}</strong></div>
            </div>
            <h3 className={styles.title}>Workflow Steps</h3>
            <ul className={styles.infoList}>
              {trace.steps.map((step) => (
                <li key={step.step_id}>
                  {step.sequence}. {formatWorkflowStep(step.step_name)} · {humanizeToken(step.status)}
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        {detail ? (
          <Card variant="insight">
            <SectionTitle
              title="Evidence"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 4h9l3 3v13H6z" />
                  <path d="M15 4v4h4" />
                  <path d="M9 12h6" />
                  <path d="M9 16h6" />
                </svg>
              }
            />
            {!detail.evidence_items.length ? (
              <div className={styles.placeholder}>No evidence items were stored for this run.</div>
            ) : (
              <ul className={styles.infoList}>
                {detail.evidence_items.map((item, index) => (
                  <li key={`${item.category}-${index}`}>
                    <strong>{formatEvidenceTitle(item.title)}:</strong>{' '}
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noreferrer">{formatEvidenceDetail(item.detail)}</a>
                    ) : (
                      formatEvidenceDetail(item.detail)
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ) : null}
      </div>

      <div className={styles.stack}>
        {error ? (
          <Card variant="caution">
            <SectionTitle
              title="Review Error"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3 2 21h20L12 3Z" />
                  <path d="M12 9v4" />
                  <path d="M12 17h.01" />
                </svg>
              }
            />
            <div className={styles.errorText}>{error}</div>
          </Card>
        ) : null}

        {detail ? (
          <>
            {trace?.decision_timeline?.length ? (
              <Card variant="insight">
                <SectionTitle
                  title="How Decisions Were Made"
                  icon={
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2v4" />
                      <path d="m16.24 7.76 2.83-2.83" />
                      <path d="M18 12h4" />
                      <path d="m16.24 16.24 2.83 2.83" />
                      <path d="M12 18v4" />
                      <path d="m4.93 19.07 2.83-2.83" />
                      <path d="M2 12h4" />
                      <path d="m4.93 4.93 2.83 2.83" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  }
                />
                <ul className={styles.infoList}>
                  {trace.decision_timeline.map((item, index) => (
                    <li key={`${item.occurred_at}-${index}`}>
                      <strong>{item.headline}</strong>
                      <div>{item.detail}</div>
                      <div className={styles.muted}>
                        {item.actor} · {formatTimelineTime(item.occurred_at)}
                        {typeof item.confidence === 'number' ? ` · ${Math.round(item.confidence * 100)}% confidence` : ''}
                      </div>
                      {item.evidence.length ? (
                        <div className={styles.muted}>Evidence: {item.evidence.join(' · ')}</div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}

            <Card>
              <SectionTitle
                title="Final Plan Review"
                icon={
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 4h9l3 3v13H6z" />
                    <path d="M15 4v4h4" />
                    <path d="M9 12h6" />
                    <path d="M9 16h4" />
                  </svg>
                }
              />
              <div className={styles.kvList}>
                <div><span className={styles.muted}>Destination</span><strong>{detail.trip.trip.destination}</strong></div>
                <div><span className={styles.muted}>Trip Status</span><strong>{detail.trip.trip.status}</strong></div>
                <div><span className={styles.muted}>Approval</span><strong>{detail.approval.status}</strong></div>
              </div>
              <div>{detail.trip.review_assessment?.summary || 'No review summary available.'}</div>
              <div className={styles.inlineActions}>
                <button
                  type="button"
                  onClick={() => void handleDecision({ action: 'approve', note })}
                  disabled={pendingAction !== ''}
                >
                  {pendingAction === 'approve' ? 'Approving...' : 'Approve Plan'}
                </button>
                <button
                  type="button"
                  onClick={() => void handleDecision({ action: 'reject', note })}
                  disabled={pendingAction !== ''}
                >
                  {pendingAction === 'reject' ? 'Rejecting...' : 'Reject for Rework'}
                </button>
              </div>
              <label className={styles.form}>
                <span className={styles.muted}>Operator note</span>
                <textarea
                  rows={4}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Capture approval rationale, required changes, or escalation notes."
                />
              </label>
            </Card>

            <div className={styles.row}>
              <Card variant="caution">
                <SectionTitle
                  title="Governance Flags"
                  icon={
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 21V5" />
                      <path d="M5 5h10l-2 4 2 4H5" />
                    </svg>
                  }
                />
                {!detail.governance_flags.length ? (
                  <div className={styles.okText}>No active governance flags.</div>
                ) : (
                  <ul className={styles.infoList}>
                    {detail.governance_flags.map((flag) => <li key={flag}>{formatGovernanceFlag(flag)}</li>)}
                  </ul>
                )}
              </Card>
            </div>

            <ExportPanel>
              <SectionTitle
                title="Approval Summary"
                icon={
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 11l3 3L22 4" />
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                  </svg>
                }
              />
              <div className={styles.stackTight}>
                <div><strong>Consistency Score:</strong> {detail.trip.review_assessment ? `${(detail.trip.review_assessment.consistency_score * 100).toFixed(0)}%` : '-'}</div>
                <div><strong>Confidence:</strong> {detail.trip.review_assessment ? `${(detail.trip.review_assessment.confidence * 100).toFixed(0)}%` : '-'}</div>
              </div>
              <h3 className={styles.title}>Review Notes</h3>
              <ul className={styles.infoList}>
                {detail.review_notes.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <h3 className={styles.title}>Recent Audit Events</h3>
              <ul className={styles.infoList}>
                {(trace?.audit_events || []).slice(-6).map((event) => (
                  <li key={event.event_id}>
                    {humanizeToken(event.event_type)} · {event.status || 'n/a'}
                  </li>
                ))}
              </ul>
            </ExportPanel>
          </>
        ) : (
          <Card variant="review">
            <SectionTitle
              title="Review Detail"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 4h9l3 3v13H6z" />
                  <path d="M15 4v4h4" />
                  <path d="M9 12h6" />
                  <path d="M9 16h4" />
                </svg>
              }
            />
            <div className={styles.placeholder}>Select a trip from the review queue.</div>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Review;
