import React from 'react';
import styles from './ItineraryDayCard.module.css';

interface ItineraryDayCardProps {
  day: string;
  morning?: string;
  morningSuggestions?: Array<{ title: string; website_url: string; maps_url: string }>;
  afternoon?: string;
  afternoonSuggestions?: Array<{ title: string; website_url: string; maps_url: string }>;
  evening?: string;
  eveningSuggestions?: Array<{ title: string; website_url: string; maps_url: string }>;
  notes?: string;
  transport?: string;
  spend?: string;
  restaurant?: string;
  restaurantUrl?: string;
  restaurantWebsiteUrl?: string;
  restaurantReviewUrl?: string;
  restaurantVideoUrls?: string[];
  signatureItems?: string[];
  photoSpot?: string;
  photoTiming?: string;
  photoBlogUrl?: string;
  photoVlogUrl?: string;
  photoVideoUrls?: string[];
  isEdited?: boolean;
  isRegenerating?: boolean;
}

function extractYouTubeVideoId(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes('youtu.be')) {
      return parsed.pathname.replace('/', '').split('/')[0] || '';
    }
    if (parsed.pathname.startsWith('/shorts/')) {
      return parsed.pathname.replace('/shorts/', '').split('/')[0] || '';
    }
    if (parsed.pathname === '/watch') {
      return parsed.searchParams.get('v') || '';
    }
  } catch {
    return '';
  }
  return '';
}

function buildYouTubeThumbnailUrl(url: string): string {
  const videoId = extractYouTubeVideoId(url);
  return videoId ? `https://img.youtube.com/vi/${videoId}/hqdefault.jpg` : '';
}

function openExternalUrl(url: string): void {
  if (!url) {
    return;
  }
  const opened = window.open(url, '_blank', 'noopener,noreferrer');
  if (!opened) {
    window.location.assign(url);
  }
}

const ItineraryDayCard: React.FC<ItineraryDayCardProps> = ({
  day,
  morning,
  morningSuggestions,
  afternoon,
  afternoonSuggestions,
  evening,
  eveningSuggestions,
  notes,
  transport,
  spend,
  restaurant,
  restaurantUrl,
  restaurantWebsiteUrl,
  restaurantReviewUrl,
  restaurantVideoUrls,
  signatureItems,
  photoSpot,
  photoTiming,
  photoBlogUrl,
  photoVlogUrl,
  photoVideoUrls,
  isEdited,
  isRegenerating,
}) => {
  const renderSuggestions = (items?: Array<{ title: string; website_url: string; maps_url: string }>) => {
    if (!items || items.length === 0) {
      return null;
    }
    return (
      <div className={styles.suggestionList}>
        {items.slice(0, 3).map((item) => (
          <div key={`${item.title}-${item.website_url}-${item.maps_url}`} className={styles.suggestionItem}>
            <div className={styles.suggestionTitle}>{item.title}</div>
            <div className={styles.linkRow}>
              {item.website_url ? (
                <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(item.website_url)}>
                  Website
                </button>
              ) : null}
              {item.maps_url ? (
                <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(item.maps_url)}>
                  Map
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
  <div className={`${styles.card} ${isEdited ? styles.edited : ''} ${isRegenerating ? styles.regenerating : ''}`}>
    <div className={styles.header}>
      <div className={styles.dayBadge}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M8 2v4" />
          <path d="M16 2v4" />
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M3 10h18" />
        </svg>
      </div>
      <div className={styles.headerText}>{day}</div>
    </div>

    <div className={styles.timeline}>
      <div className={styles.timelineItem}>
        <div className={styles.timelineMarker}>AM</div>
        <div className={styles.timelineContent}>
          <div className={styles.timelineLabel}>Morning</div>
          <div>{morning || '-'}</div>
          {renderSuggestions(morningSuggestions)}
        </div>
      </div>
      <div className={styles.timelineItem}>
        <div className={styles.timelineMarker}>PM</div>
        <div className={styles.timelineContent}>
          <div className={styles.timelineLabel}>Afternoon</div>
          <div>{afternoon || '-'}</div>
          {renderSuggestions(afternoonSuggestions)}
        </div>
      </div>
      <div className={styles.timelineItem}>
        <div className={styles.timelineMarker}>EV</div>
        <div className={styles.timelineContent}>
          <div className={styles.timelineLabel}>Evening</div>
          <div>{evening || '-'}</div>
          {renderSuggestions(eveningSuggestions)}
        </div>
      </div>
    </div>

    <div className={styles.grid}>
      <div className={styles.panel}>
        <div className={styles.panelLabel}>Restaurant</div>
        <div className={styles.panelValue}>{restaurant || '-'}</div>
        {(restaurantUrl || restaurantWebsiteUrl || restaurantReviewUrl) ? (
          <div className={styles.linkRow}>
            {restaurantUrl ? (
              <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(restaurantUrl)}>
                Find this place
              </button>
            ) : null}
            {restaurantWebsiteUrl ? (
              <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(restaurantWebsiteUrl)}>
                Website
              </button>
            ) : null}
            {restaurantReviewUrl ? (
              <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(restaurantReviewUrl)}>
                Video reviews
              </button>
            ) : null}
          </div>
        ) : null}
        {restaurantVideoUrls && restaurantVideoUrls.length > 0 ? (
          <div className={styles.thumbnailGrid}>
            {restaurantVideoUrls.slice(0, 3).map((url, index) => {
              const thumbnailUrl = buildYouTubeThumbnailUrl(url);
              if (!thumbnailUrl) {
                return null;
              }
              return (
                <a
                  key={`${url}-${index}`}
                  className={styles.thumbnailLink}
                  href={url}
                  onClick={(event) => {
                    event.preventDefault();
                    openExternalUrl(url);
                  }}
                  title={`Open restaurant video ${index + 1}`}
                >
                  <img className={styles.thumbnailImage} src={thumbnailUrl} alt={`Restaurant video ${index + 1}`} />
                </a>
              );
            })}
          </div>
        ) : null}
      </div>
      <div className={styles.panel}>
        <div className={styles.panelLabel}>Must-Try Items</div>
        <div className={styles.panelValue}>{signatureItems && signatureItems.length > 0 ? signatureItems.join(', ') : '-'}</div>
      </div>
      <div className={styles.panel}>
        <div className={styles.panelLabel}>Photo Spot</div>
        <div className={styles.panelValue}>{photoSpot || '-'}</div>
        {photoSpot ? (
          <div className={styles.linkRow}>
            {photoBlogUrl ? (
              <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(photoBlogUrl)}>
                Travel blogs
              </button>
            ) : null}
            {photoVlogUrl ? (
              <button type="button" className={styles.panelLinkButton} onClick={() => openExternalUrl(photoVlogUrl)}>
                Travel vlogs
              </button>
            ) : null}
          </div>
        ) : null}
        {photoVideoUrls && photoVideoUrls.length > 0 ? (
          <div className={styles.thumbnailGrid}>
            {photoVideoUrls.slice(0, 3).map((url, index) => {
              const thumbnailUrl = buildYouTubeThumbnailUrl(url);
              if (!thumbnailUrl) {
                return null;
              }
              return (
                <a
                  key={`${url}-${index}`}
                  className={styles.thumbnailLink}
                  href={url}
                  onClick={(event) => {
                    event.preventDefault();
                    openExternalUrl(url);
                  }}
                  title={`Open photo video ${index + 1}`}
                >
                  <img className={styles.thumbnailImage} src={thumbnailUrl} alt={`Photo video ${index + 1}`} />
                </a>
              );
            })}
          </div>
        ) : null}
      </div>
      <div className={styles.panel}>
        <div className={styles.panelLabel}>Best Photo Time</div>
        <div className={styles.panelValue}>{photoTiming || '-'}</div>
      </div>
      <div className={styles.panel}>
        <div className={styles.panelLabel}>Transport</div>
        <div className={styles.panelValue}>{transport || '-'}</div>
      </div>
      <div className={styles.panel}>
        <div className={styles.panelLabel}>Estimated Spend</div>
        <div className={styles.panelValue}>{spend || '-'}</div>
      </div>
    </div>

    <div className={styles.notesBlock}>
      <div className={styles.panelLabel}>Notes</div>
      <div className={styles.panelValue}>{notes || '-'}</div>
    </div>
    {isEdited && <div className={styles.badge}>Edited</div>}
    {isRegenerating && <div className={styles.badge}>Regenerating...</div>}
  </div>
);
};

export default ItineraryDayCard;
