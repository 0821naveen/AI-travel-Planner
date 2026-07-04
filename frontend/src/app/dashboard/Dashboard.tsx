import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/Card';
import StatusBadge from '../../components/StatusBadge';
import {
  AdminDashboardResponse,
  AlertsResponse,
  WorkflowRunResponse,
  fetchAdminDashboard,
  fetchAlerts,
  fetchRecentRuns,
} from '../../lib/planner';
import styles from './Dashboard.module.css';

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return 'Unknown';
  }
  return new Date(value).toLocaleString();
};

const dashboardIcons = {
  active: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19h16" />
      <path d="M7 15.5 11 11l3 3 5-6" />
      <circle cx="7" cy="15.5" r="1" />
      <circle cx="11" cy="11" r="1" />
      <circle cx="14" cy="14" r="1" />
      <circle cx="19" cy="8" r="1" />
    </svg>
  ),
  awaiting: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5l3 2" />
    </svg>
  ),
  review: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3h7v7" />
      <path d="m10 14 11-11" />
      <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
    </svg>
  ),
  complete: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.3 2.3 4.7-5.3" />
    </svg>
  ),
};

const Dashboard: React.FC = () => {
  const [dashboard, setDashboard] = useState<AdminDashboardResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [recentRuns, setRecentRuns] = useState<WorkflowRunResponse[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [dashboardData, alertsData, recentRunData] = await Promise.all([
          fetchAdminDashboard(),
          fetchAlerts(),
          fetchRecentRuns(),
        ]);
        if (!active) {
          return;
        }
        setDashboard(dashboardData);
        setAlerts(alertsData);
        setRecentRuns(recentRunData);
        setError('');
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load operator dashboard.');
      }
    };

    void load();
    return () => {
      active = false;
    };
  }, []);

  const summary = [
    {
      label: 'Active Plans',
      value: dashboard?.active_plans ?? 0,
      status: 'active' as const,
      tone: 'blue',
      note: 'Trips currently moving through planning.',
    },
    {
      label: 'Awaiting Clarification',
      value: dashboard?.awaiting_clarification ?? 0,
      status: 'awaiting' as const,
      tone: 'amber',
      note: 'Need traveler answers before orchestration can start.',
    },
    {
      label: 'Ready for Review',
      value: dashboard?.ready_for_review ?? 0,
      status: 'review' as const,
      tone: 'violet',
      note: 'Operator checks required before export.',
    },
    {
      label: 'Completed',
      value: dashboard?.completed ?? 0,
      status: 'complete' as const,
      tone: 'green',
      note: 'Trips successfully delivered to travelers.',
    },
  ];

  const totalTrips = summary.reduce((count, item) => count + item.value, 0);

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}>Operator Control Room</span>
          <h2 className={styles.heroTitle}>Atlas trip flow, review pressure, and live planning activity.</h2>
          <p className={styles.heroText}>
            Track where trips are getting stuck, what is ready for handoff, and which runs need attention without digging through each tab.
          </p>
          <div className={styles.heroActions}>
            <Link to="/new-trip" className={styles.primaryAction}>Create New Trip</Link>
            <div className={styles.generatedAt}>Updated {formatTimestamp(dashboard?.generated_at)}</div>
          </div>
        </div>
        <div className={styles.heroPanel}>
          <div className={styles.heroPanelLabel}>Flow Snapshot</div>
          <div className={styles.heroPanelValue}>{totalTrips}</div>
          <div className={styles.heroPanelText}>Trips visible in the planning funnel right now.</div>
          <div className={styles.pipelineList}>
            {summary.map((item) => {
              const width = totalTrips ? `${Math.max((item.value / totalTrips) * 100, item.value ? 12 : 0)}%` : '0%';
              return (
                <div key={item.label} className={styles.pipelineRow}>
                  <div className={styles.pipelineMeta}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                  <div className={styles.pipelineTrack}>
                    <div className={`${styles.pipelineFill} ${styles[item.tone]}`} style={{ width }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className={styles.metricsGrid}>
        {summary.map((item) => (
          <Card key={item.label} className={`${styles.metricCard} ${styles[item.tone]}`} variant="metric">
            <div className={styles.metricTop}>
              <div>
                <div className={styles.metricLabel}>{item.label}</div>
                <div className={styles.metricValue}>{item.value}</div>
              </div>
              <div className={styles.metricIcon}>{dashboardIcons[item.status]}</div>
            </div>
            <div className={styles.metricBottom}>
              <StatusBadge status={item.status} />
              <span className={styles.metricNote}>{item.note}</span>
            </div>
          </Card>
        ))}
      </section>

      {error ? (
        <Card variant="caution" className={styles.errorCard}>
          <h3 className={styles.sectionTitle}>Operator Dashboard</h3>
          <div className={styles.errorText}>{error}</div>
        </Card>
      ) : null}

      <section className={styles.contentGrid}>
        <div className={styles.primaryColumn}>
          <Card className={styles.largePanel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.sectionTitle}>Recent Trip Plans</h3>
                <p className={styles.sectionText}>Latest traveler plans, review state, and delivery readiness.</p>
              </div>
              <div className={styles.panelCount}>{dashboard?.recent_trips.length ?? 0}</div>
            </div>
            {!dashboard?.recent_trips.length ? (
              <div className={styles.emptyState}>No trips yet. Start a new trip to see it here.</div>
            ) : (
              <div className={styles.listShell}>
                {dashboard.recent_trips.map((trip) => (
                  <Link key={trip.trip_id} to={`/review?tripId=${trip.trip_id}`} className={styles.tripRow}>
                    <div className={styles.tripMain}>
                      <div className={styles.tripDestination}>{trip.destination}</div>
                      <div className={styles.tripMeta}>
                        {trip.traveler_count} travelers • {trip.start_date} to {trip.end_date}
                      </div>
                    </div>
                    <div className={styles.tripStatus}>
                      <StatusBadge status={trip.status === 'completed' ? 'complete' : trip.status === 'ready_for_review' ? 'review' : trip.status === 'awaiting_clarification' ? 'awaiting' : 'active'} />
                      <span className={styles.tripApproval}>{trip.approval.status.replace('_', ' ')}</span>
                      <span className={styles.tripUpdated}>{formatTimestamp(trip.updated_at)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>

          <Card className={styles.largePanel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.sectionTitle}>Recent Workflow Runs</h3>
                <p className={styles.sectionText}>Execution status, current node, and retry pressure across planner runs.</p>
              </div>
              <div className={styles.panelCount}>{recentRuns.length}</div>
            </div>
            {!recentRuns.length ? (
              <div className={styles.emptyState}>No workflow runs are recorded yet.</div>
            ) : (
              <div className={styles.runGrid}>
                {recentRuns.map((run) => (
                  <Link key={run.run_id} to={run.trip_id ? `/review?tripId=${run.trip_id}` : '/review'} className={styles.runCard}>
                    <div className={styles.runCardTop}>
                      <span className={styles.runId}>Run {run.run_id.slice(0, 8)}</span>
                      <StatusBadge
                        status={
                          run.status === 'succeeded'
                            ? 'complete'
                            : run.status === 'waiting'
                              ? 'waiting'
                              : run.status === 'skipped'
                                ? 'skipped'
                                : 'active'
                        }
                      />
                    </div>
                    <div className={styles.runStep}>{run.current_step || run.last_completed_step || 'Queued for execution'}</div>
                    <div className={styles.runMeta}>Retries: {run.retry_count} • Updated {formatTimestamp(run.updated_at)}</div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className={styles.sideColumn}>
          <Card variant="review" className={styles.sidePanel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.sectionTitle}>Review Queue</h3>
                <p className={styles.sectionText}>Trips awaiting operator judgment.</p>
              </div>
            </div>
            {!dashboard?.review_queue.length ? (
              <div className={styles.emptyState}>No trips are currently waiting for operator review.</div>
            ) : (
              <div className={styles.queueList}>
                {dashboard.review_queue.map((trip) => (
                  <Link key={trip.trip_id} to={`/review?tripId=${trip.trip_id}`} className={styles.queueItem}>
                    <div className={styles.queueDestination}>{trip.destination}</div>
                    <div className={styles.queueMeta}>{Math.round(trip.review_confidence * 100)}% confidence</div>
                  </Link>
                ))}
              </div>
            )}
          </Card>

          <Card variant={alerts?.healthy === false ? 'caution' : 'insight'} className={styles.sidePanel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.sectionTitle}>Planning Alerts</h3>
                <p className={styles.sectionText}>Observability and workflow exceptions that may need intervention.</p>
              </div>
            </div>
            {!alerts ? (
              <div className={styles.emptyState}>Loading alerts.</div>
            ) : alerts.healthy ? (
              <div className={styles.healthyCallout}>No active observability alerts.</div>
            ) : (
              <div className={styles.alertList}>
                {alerts.alerts.map((alert) => (
                  <div key={alert.code} className={styles.alertItem}>
                    <div className={styles.alertSeverity}>{alert.severity.toUpperCase()}</div>
                    <div className={styles.alertSummary}>{alert.summary}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
