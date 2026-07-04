import React from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/Card';
import FilterBar from '../../components/FilterBar';
import { loadPlannerResponse } from '../../lib/planner';
import styles from '../AppPage.module.css';

function buildGoogleSearchUrl(query: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(query)}`;
}

function buildGoogleMapsUrl(query: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

function buildYouTubeSearchUrl(query: string): string {
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}

function cleanProviderMessage(value?: string | null, fallback = 'No structured provider signal is available yet.'): string {
  if (!value || !value.trim()) {
    return fallback;
  }

  const normalized = value.replace(/\s+/g, ' ').trim();
  const lower = normalized.toLowerCase();

  if (lower.includes('aviationstack') || lower.includes('serpapi') || lower.includes('http 4') || lower.includes('function_access_restricted')) {
    return 'Live provider enrichment was unavailable for this run, so flight availability details could not be verified.';
  }

  if (lower.includes('no tripadvisor results returned')) {
    return 'No recent Tripadvisor review summaries were available for this run.';
  }

  if (lower.includes('tripadvisor') && lower.includes('not configured')) {
    return 'Traveler review enrichment is not configured in this environment.';
  }

  if (lower.includes('lookup failed') || lower.includes('returned http') || lower.includes('error')) {
    return 'Structured provider enrichment failed for this run. Planning continued with fallback research.';
  }

  return normalized;
}

function formatHotelInventorySummary(value?: string | null): string {
  if (!value || !value.trim()) {
    return 'No structured hotel inventory signal is available yet.';
  }

  const normalized = value.replace(/\s+/g, ' ').trim();
  const lower = normalized.toLowerCase();

  if (lower.includes('lookup failed') || lower.includes('returned http') || lower.includes('error')) {
    return 'Hotel inventory pricing could not be enriched from the provider during this run.';
  }

  const matchedHotels = Array.from(
    normalized.matchAll(/([^|]+?)\s*\|\s*\{[^}]*'lowest':\s*'([^']+)'/g),
  ).map((match) => `${match[1].trim()} from ${match[2].trim()}`);

  if (matchedHotels.length > 0) {
    return matchedHotels.join(' • ');
  }

  return normalized;
}

const IconFrame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className={styles.titleIcon}>{children}</span>
);

const SectionTitle: React.FC<{ title: string; icon: React.ReactNode }> = ({ title, icon }) => (
  <div className={styles.cardHeader}>
    <IconFrame>{icon}</IconFrame>
    <h2 className={styles.title}>{title}</h2>
  </div>
);

const Research: React.FC = () => {
  const response = loadPlannerResponse();
  const research = response?.destination_research;
  const stays = response?.stay_recommendation_plan;
  const transport = response?.local_transport_plan;
  const food = response?.food_recommendation_plan;
  const hasProviderSignals = Boolean(
    research?.flight_context_summary || stays?.hotel_inventory_summary || stays?.traveler_review_summary || food?.traveler_review_summary,
  );
  const flightContextSummary = cleanProviderMessage(
    research?.flight_context_summary,
    'No structured flight signal is available yet.',
  );
  const hotelInventorySummary = formatHotelInventorySummary(stays?.hotel_inventory_summary);
  const stayReviewSummary = cleanProviderMessage(
    stays?.traveler_review_summary,
    'No stay review signal is available yet.',
  );
  const foodReviewSummary = cleanProviderMessage(
    food?.traveler_review_summary,
    'No food review signal is available yet.',
  );

  if (!response || !research) {
    return (
      <div className={styles.page}>
        <Card variant="insight">
          <h2 className={styles.title}>Research</h2>
          <div className={styles.placeholder}>No destination research is available yet. Start from <Link to="/new-trip">New Trip</Link>.</div>
        </Card>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <FilterBar>
        <strong>{research.destination}</strong> research summary with confidence {(research.confidence * 100).toFixed(0)}%
      </FilterBar>
      <div className={`${styles.row} ${styles.row3}`}>
        <Card variant="insight">
          <SectionTitle
            title="Summary"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 5h14v14H5z" />
                <path d="M8 9h8" />
                <path d="M8 13h8" />
              </svg>
            }
          />
          <div>{research.summary}</div>
        </Card>
        <Card variant="metric">
          <SectionTitle
            title="Weather"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 15a4 4 0 1 1 1-7.9A5 5 0 0 1 17.5 9 3.5 3.5 0 1 1 18 16H6Z" />
              </svg>
            }
          />
          <div>{research.weather?.summary || 'No weather data returned.'}</div>
        </Card>
        <Card variant="insight">
          <SectionTitle
            title="Price Signals"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="6" width="18" height="12" rx="2" />
                <path d="M7 12h5" />
                <path d="M16 12h.01" />
              </svg>
            }
          />
          <div className={styles.stackTight}>
            <div><strong>Flight:</strong> {research.flight_price_signal || '-'}</div>
            <div><strong>Hotel:</strong> {research.hotel_price_signal || '-'}</div>
            <div><strong>Budget / Day:</strong> {research.budget_per_day_estimate ?? '-'}</div>
          </div>
        </Card>
      </div>
      {hasProviderSignals && (
        <div className={`${styles.row} ${styles.row3}`}>
          <Card variant="insight">
            <SectionTitle
              title="Flight Context"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 16l20-5-20-5 5 5-5 5Z" />
                </svg>
              }
            />
            <div className={styles.signalBody}>
              {flightContextSummary}
            </div>
          </Card>
          <Card variant="review">
            <SectionTitle
              title="Hotel Inventory"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 19V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v13" />
                  <path d="M10 19V9" />
                  <path d="M2 19h20" />
                  <path d="M7 8h.01" />
                  <path d="M7 11h.01" />
                  <path d="M13 8h.01" />
                  <path d="M13 11h.01" />
                </svg>
              }
            />
            <div className={styles.signalBody}>
              {hotelInventorySummary}
            </div>
          </Card>
          <Card variant="metric">
            <SectionTitle
              title="Traveler Reviews"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 12h8" />
                  <path d="M8 16h5" />
                  <path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
                </svg>
              }
            />
            <div className={styles.stackTight}>
              <div className={styles.signalLabel}>Stay reviews</div>
              <div className={styles.signalBody}>
                {stayReviewSummary}
              </div>
              <div className={styles.signalLabel}>Food reviews</div>
              <div className={styles.signalBody}>
                {foodReviewSummary}
              </div>
            </div>
          </Card>
        </div>
      )}
      <div className={`${styles.row} ${styles.row2}`}>
        <Card variant="caution">
          <SectionTitle
            title="Highlights"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.8-5.4 2.8 1-6L3.2 9.4l6.1-.9L12 3Z" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {research.top_highlights.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
        <Card variant="insight">
          <SectionTitle
            title="Risks"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3 2 21h20L12 3Z" />
                <path d="M12 9v4" />
                <path d="M12 17h.01" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {research.top_risks.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
      </div>
      <div className={`${styles.row} ${styles.row2}`}>
        <Card variant="review">
          <SectionTitle
            title="Recommended Areas"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 21s7-4.4 7-11a7 7 0 1 0-14 0c0 6.6 7 11 7 11Z" />
                <circle cx="12" cy="10" r="2.5" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {research.recommended_areas.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
        <Card variant="review">
          <SectionTitle
            title="Transport Notes"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 16l4-5h10l4 5" />
                <path d="M5 16h14" />
                <circle cx="7.5" cy="17.5" r="1.5" />
                <circle cx="16.5" cy="17.5" r="1.5" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {research.local_transport_notes.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
      </div>
      {stays && (
        <Card>
          <SectionTitle
            title="Stay Options"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19V9a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10" />
                <path d="M2 19h20" />
                <path d="M7 13h4" />
                <path d="M14 13h3" />
              </svg>
            }
          />
          <div className={styles.stack}>
            <div className={styles.placeholder}>{stays.summary}</div>
            <div className={styles.cardGrid}>
              {stays.recommendations.map((stay) => (
                <div key={`${stay.name}-${stay.area}`} className={styles.detailCard}>
                  <div className={styles.detailQuestion}>{stay.name}</div>
                  <div className={styles.detailReason}>{stay.stay_type} • {stay.area} • {stay.price_band}</div>
                  <div>{stay.why_fit}</div>
                  <div className={styles.detailReason}>Safety: {stay.safety_notes.join(' ') || '-'}</div>
                  <div className={styles.detailReason}>Booking: {stay.booking_tips.join(' ') || '-'}</div>
                  <div className={styles.detailLinks}>
                    <a
                      className={styles.actionLink}
                      href={stay.booking_url || buildGoogleSearchUrl(`${stay.name} ${stay.area} booking`)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Booking search
                    </a>
                    <a
                      className={styles.actionLink}
                      href={stay.maps_url || buildGoogleMapsUrl(`${stay.name} ${stay.area} ${research.destination}`)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View on map
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}
      <div className={`${styles.row} ${styles.row2}`}>
        {transport && (
          <Card variant="insight">
            <SectionTitle
              title="Local Transport Snapshot"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 17h14" />
                  <path d="M7 17V9l5-3 5 3v8" />
                  <circle cx="8.5" cy="17.5" r="1.5" />
                  <circle cx="15.5" cy="17.5" r="1.5" />
                </svg>
              }
            />
            <div className={styles.stack}>
              <div className={styles.placeholder}>{transport.summary}</div>
              {transport.legs.slice(0, 4).map((leg, index) => (
                <div key={`${leg.day_number}-${index}`} className={styles.detailCard}>
                  <div className={styles.detailQuestion}>Day {leg.day_number}: {leg.from_area} to {leg.to_area}</div>
                  <div className={styles.detailReason}>{leg.recommended_mode} • {leg.approx_duration} • {leg.approx_fare}</div>
                  <div>{leg.notes}</div>
                </div>
              ))}
            </div>
          </Card>
        )}
        {food && (
          <Card variant="review">
            <SectionTitle
              title="Food Snapshot"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 4v8" />
                  <path d="M12 4v8" />
                  <path d="M10 12v8" />
                  <path d="M17 4c1.7 2.2 1.7 5.8 0 8" />
                  <path d="M17 12v8" />
                </svg>
              }
            />
            <div className={styles.stack}>
              <div className={styles.placeholder}>{food.summary}</div>
              {food.recommendations.slice(0, 4).map((item, index) => (
                <div key={`${item.day_number}-${item.meal}-${index}`} className={styles.detailCard}>
                  <div className={styles.detailQuestion}>Day {item.day_number} {item.meal}: {item.venue_name}</div>
                  <div className={styles.detailReason}>{item.area} • {item.cuisine_type} • {item.price_level}</div>
                  <div>{item.why_fit}</div>
                  <div className={styles.detailLinks}>
                    {item.official_website ? (
                      <a
                        className={styles.actionLink}
                        href={item.official_website}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Website
                      </a>
                    ) : null}
                    <a
                      className={styles.actionLink}
                      href={item.maps_url || buildGoogleMapsUrl(`${item.venue_name} ${item.area} ${research.destination}`)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Find on map
                    </a>
                    <a
                      className={styles.actionLink}
                      href={item.review_video_urls?.[0] || buildYouTubeSearchUrl(`${item.venue_name} ${research.destination} food review shorts`)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Video reviews
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
      {response.itinerary_plan && (
        <Card variant="insight">
          <SectionTitle
            title="Photo Spot Discovery"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 7h4l2-2h4l2 2h4v10H4z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            }
          />
          <div className={styles.stack}>
            {response.itinerary_plan.days.slice(0, 4).map((day) => (
              <div key={`${day.day_number}-${day.photo_spot}`} className={styles.detailCard}>
                <div className={styles.detailQuestion}>Day {day.day_number}: {day.photo_spot || day.area}</div>
                <div className={styles.detailReason}>{day.photo_timing || 'Best timing not available yet'}</div>
                <div className={styles.detailLinks}>
                  <a
                    className={styles.actionLink}
                    href={
                      day.photo_blog_urls?.[0]
                      || buildGoogleSearchUrl(`${day.photo_spot || day.area} ${research.destination} travel blog best pictures`)
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    Travel blogs
                  </a>
                  <a
                    className={styles.actionLink}
                    href={
                      day.photo_vlog_urls?.[0]
                      || buildYouTubeSearchUrl(`${day.photo_spot || day.area} ${research.destination} travel vlog photography`)
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    Travel vlogs
                  </a>
                  <a
                    className={styles.actionLink}
                    href={day.photo_maps_url || buildGoogleMapsUrl(`${day.photo_spot || day.area} ${research.destination}`)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open in map
                  </a>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <Card variant="default">
        <SectionTitle
          title="Research Sources"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 4h9l3 3v13H6z" />
              <path d="M15 4v4h4" />
              <path d="M9 12h6" />
              <path d="M9 16h6" />
            </svg>
          }
        />
        <ul className={styles.infoList}>
          {research.sources.map((source) => (
            <li key={source.url}>
              <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>: {source.snippet}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
};

export default Research;
