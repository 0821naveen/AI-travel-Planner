import React from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/Card';
import ItineraryDayCard from '../../components/ItineraryDayCard';
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

const IconFrame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className={styles.titleIcon}>{children}</span>
);

const SectionTitle: React.FC<{ title: string; icon: React.ReactNode }> = ({ title, icon }) => (
  <div className={styles.cardHeader}>
    <IconFrame>{icon}</IconFrame>
    <h2 className={styles.title}>{title}</h2>
  </div>
);

const Itinerary: React.FC = () => {
  const response = loadPlannerResponse();
  const itinerary = response?.itinerary_plan;
  const stays = response?.stay_recommendation_plan;
  const food = response?.food_recommendation_plan;

  if (!response || !itinerary) {
    return (
      <div className={styles.page}>
        <Card variant="metric">
          <h2 className={styles.title}>Itinerary</h2>
          <div className={styles.placeholder}>No itinerary is available yet. Start from <Link to="/new-trip">New Trip</Link>.</div>
        </Card>
      </div>
    );
  }

  return (
    <div className={`${styles.page} ${styles.row} ${styles.row2}`}>
      <div className={styles.stack}>
        <Card variant="insight">
          <SectionTitle
            title="Trip Summary"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19h16" />
                <path d="M5 19V9l7-4 7 4v10" />
                <path d="M9 19v-4h6v4" />
              </svg>
            }
          />
          <div className={styles.kvList}>
            <div><span className={styles.muted}>Destination</span><strong>{itinerary.destination}</strong></div>
            <div><span className={styles.muted}>Status</span><strong>{response.trip.status}</strong></div>
            <div><span className={styles.muted}>Confidence</span><strong>{(itinerary.confidence * 100).toFixed(0)}%</strong></div>
          </div>
          <div>{itinerary.summary}</div>
        </Card>
        <Card variant="review">
          <SectionTitle
            title="Budget Fit Note"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="6" width="18" height="12" rx="2" />
                <path d="M16 12h.01" />
                <path d="M7 12h5" />
              </svg>
            }
          />
          <div>{itinerary.budget_fit_note}</div>
        </Card>
        <Card>
          <SectionTitle
            title="Assumptions"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3Z" />
                <path d="M12 8v5" />
                <path d="M12 16h.01" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {itinerary.assumptions.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
        {stays && (
          <Card variant="insight">
            <SectionTitle
              title="Recommended Stay Base"
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
              {stays.recommendations.slice(0, 2).map((stay) => (
                <div key={`${stay.name}-${stay.area}`} className={styles.detailCard}>
                  <div className={styles.detailQuestion}>{stay.name}</div>
                  <div className={styles.detailReason}>{stay.stay_type} • {stay.area} • {stay.price_band}</div>
                  <div>{stay.why_fit}</div>
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
                      href={stay.maps_url || buildGoogleMapsUrl(`${stay.name} ${stay.area}`)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View on map
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
        {food && (
          <Card variant="review">
            <SectionTitle
              title="Food Direction"
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
              {food.recommendations.slice(0, 3).map((item, index) => (
                <div key={`${item.day_number}-${item.meal}-${index}`} className={styles.detailCard}>
                  <div className={styles.detailQuestion}>Day {item.day_number} {item.meal}</div>
                  <div className={styles.detailReason}>{item.venue_name} • {item.area}</div>
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
                      href={item.maps_url || buildGoogleMapsUrl(`${item.venue_name} ${item.area} ${itinerary.destination}`)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Find on map
                    </a>
                    <a
                      className={styles.actionLink}
                      href={item.review_video_urls?.[0] || buildYouTubeSearchUrl(`${item.venue_name} ${itinerary.destination} food review shorts`)}
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
      <div>
        {itinerary.days.map((day) => (
          <ItineraryDayCard
            key={day.day_number}
            day={`Day ${day.day_number} • ${day.date} • ${day.theme}`}
            morning={day.morning}
            morningSuggestions={day.morning_suggestions}
            afternoon={day.afternoon}
            afternoonSuggestions={day.afternoon_suggestions}
            evening={day.evening}
            eveningSuggestions={day.evening_suggestions}
            notes={`${day.area}. ${day.reasoning} ${day.warnings.join(' ')}`.trim()}
            transport={
              response?.local_transport_plan?.legs.find((leg) => leg.day_number === day.day_number)
                ? `${response.local_transport_plan.legs.find((leg) => leg.day_number === day.day_number)?.recommended_mode} • ${response.local_transport_plan.legs.find((leg) => leg.day_number === day.day_number)?.approx_duration} • ${response.local_transport_plan.legs.find((leg) => leg.day_number === day.day_number)?.approx_fare}`
                : day.transport_note
            }
            spend={day.estimated_daily_cost}
            restaurant={day.recommended_restaurant}
            restaurantUrl={
              day.restaurant_maps_url || buildGoogleMapsUrl(`${day.recommended_restaurant} ${day.area} ${itinerary.destination}`)
            }
            restaurantWebsiteUrl={day.restaurant_website_url}
            restaurantReviewUrl={
              day.best_restaurant_short_url
              || day.restaurant_review_video_urls?.[0]
              || buildYouTubeSearchUrl(`${day.recommended_restaurant} ${itinerary.destination} food review shorts`)
            }
            restaurantVideoUrls={[
              day.best_restaurant_short_url,
              ...(day.restaurant_review_video_urls || []),
            ].filter((url, index, all) => Boolean(url) && all.indexOf(url) === index)}
            signatureItems={day.signature_dishes}
            photoSpot={day.photo_spot}
            photoTiming={day.photo_timing}
            photoBlogUrl={
              day.photo_blog_urls?.[0] || buildGoogleSearchUrl(`${day.photo_spot} ${itinerary.destination} best photo spot travel blog`)
            }
            photoVlogUrl={
              day.best_photo_short_url
              || day.photo_vlog_urls?.[0]
              || buildYouTubeSearchUrl(`${day.photo_spot} ${itinerary.destination} travel vlog photography`)
            }
            photoVideoUrls={[
              day.best_photo_short_url,
              ...(day.photo_vlog_urls || []),
            ].filter((url, index, all) => Boolean(url) && all.indexOf(url) === index)}
          />
        ))}
      </div>
    </div>
  );
};

export default Itinerary;
