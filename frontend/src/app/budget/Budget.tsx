import React from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/Card';
import Checklist from '../../components/Checklist';
import { loadPlannerResponse } from '../../lib/planner';
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

type CostRange = {
  min: number;
  max: number;
};

function parseCurrencyRange(raw: string | undefined): CostRange | null {
  if (!raw) {
    return null;
  }

  const matches = Array.from(raw.matchAll(/\d[\d,]*/g))
    .map((item) => Number(item[0].replace(/,/g, '')))
    .filter((value) => Number.isFinite(value));

  if (!matches.length) {
    return null;
  }

  if (matches.length === 1) {
    return { min: matches[0], max: matches[0] };
  }

  return { min: Math.min(...matches), max: Math.max(...matches) };
}

function formatRange(range: CostRange | null): string {
  if (!range) {
    return '-';
  }
  if (range.min === range.max) {
    return `₹${range.min.toLocaleString('en-IN')}`;
  }
  return `₹${range.min.toLocaleString('en-IN')} - ₹${range.max.toLocaleString('en-IN')}`;
}

function sumRanges(ranges: Array<CostRange | null>): CostRange | null {
  const valid = ranges.filter((item): item is CostRange => Boolean(item));
  if (!valid.length) {
    return null;
  }
  return {
    min: valid.reduce((total, item) => total + item.min, 0),
    max: valid.reduce((total, item) => total + item.max, 0),
  };
}

function mealRangeFromPriceLevel(priceLevel: string | undefined): CostRange | null {
  const normalized = (priceLevel || '').toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes('luxury')) {
    return { min: 2500, max: 4500 };
  }
  if (normalized.includes('premium')) {
    return { min: 1500, max: 2800 };
  }
  if (normalized.includes('mid')) {
    return { min: 700, max: 1500 };
  }
  if (normalized.includes('budget')) {
    return { min: 250, max: 700 };
  }
  return { min: 500, max: 1200 };
}

const Budget: React.FC = () => {
  const response = loadPlannerResponse();
  const budget = response?.budget_assessment;
  const stays = response?.stay_recommendation_plan;
  const transport = response?.local_transport_plan;
  const food = response?.food_recommendation_plan;
  const transportLegs = transport?.legs || [];
  const foodRecommendations = food?.recommendations || [];
  const transportTotal = sumRanges(transportLegs.map((leg) => parseCurrencyRange(leg.approx_fare)));
  const foodTotal = sumRanges(foodRecommendations.map((item) => mealRangeFromPriceLevel(item.price_level)));

  if (!response || !budget) {
    return (
      <div className={styles.page}>
        <Card>
          <h2 className={styles.title}>Budget</h2>
          <div className={styles.placeholder}>No budget assessment is available yet. Start from <Link to="/new-trip">New Trip</Link>.</div>
        </Card>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={`${styles.row} ${styles.row3}`}>
        <Card variant="metric"><strong>Total Cost</strong><div>{budget.estimated_total_cost}</div></Card>
        <Card variant="metric"><strong>Daily Cost</strong><div>{budget.estimated_daily_cost}</div></Card>
        <Card variant={budget.within_budget ? 'review' : 'caution'}><strong>Budget Fit</strong><div>{budget.within_budget ? 'Within budget' : 'Needs changes'}</div></Card>
      </div>
      <Card variant="insight">
        <SectionTitle
          title="Budget Summary"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="6" width="18" height="12" rx="2" />
              <path d="M7 12h5" />
              <path d="M16 12h.01" />
            </svg>
          }
        />
        <div>{budget.summary}</div>
      </Card>
      <Card variant="review">
        <SectionTitle
          title="Constraint Checklist"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          }
        />
        <Checklist items={[
          { label: 'Max budget not exceeded', checked: budget.within_budget },
          { label: 'Optimization actions available', checked: budget.optimization_actions.length > 0 },
        ]} />
      </Card>
      <div className={`${styles.row} ${styles.row2}`}>
        <Card variant="caution">
          <SectionTitle
            title="Cost Drivers"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20V10" />
                <path d="M18 20V4" />
                <path d="M6 20v-6" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {budget.cost_drivers.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
        <Card variant="insight">
          <SectionTitle
            title="Optimization Suggestions"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v4" />
                <path d="M12 18v4" />
                <path d="M4.93 4.93l2.83 2.83" />
                <path d="M16.24 16.24l2.83 2.83" />
                <path d="M2 12h4" />
                <path d="M18 12h4" />
                <path d="M4.93 19.07l2.83-2.83" />
                <path d="M16.24 7.76l2.83-2.83" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            }
          />
          <ul className={styles.infoList}>
            {budget.optimization_actions.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
      </div>
      <div className={`${styles.row} ${styles.row3}`}>
        {stays && (
          <Card variant="insight">
            <SectionTitle
              title="Stay Cost Context"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 19V9a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10" />
                  <path d="M2 19h20" />
                  <path d="M7 13h4" />
                  <path d="M14 13h3" />
                </svg>
              }
            />
            <div>{stays.recommendations[0]?.price_band || '-'}</div>
            <div className={styles.detailReason}>{stays.summary}</div>
          </Card>
        )}
        {transport && (
          <Card variant="insight">
            <SectionTitle
              title="Transport Cost Context"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 17h14" />
                  <path d="M7 17V9l5-3 5 3v8" />
                  <circle cx="8.5" cy="17.5" r="1.5" />
                  <circle cx="15.5" cy="17.5" r="1.5" />
                </svg>
              }
            />
            <div>{formatRange(transportTotal)}</div>
            <div className={styles.detailReason}>Estimated from {transportLegs.length} planned leg{transportLegs.length === 1 ? '' : 's'}.</div>
          </Card>
        )}
        {food && (
          <Card variant="insight">
            <SectionTitle
              title="Food Cost Context"
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
            <div>{formatRange(foodTotal)}</div>
            <div className={styles.detailReason}>Estimated from {foodRecommendations.length} meal recommendation{foodRecommendations.length === 1 ? '' : 's'}.</div>
          </Card>
        )}
      </div>
      <div className={`${styles.row} ${styles.row2}`}>
        {transport && (
          <Card variant="review">
            <SectionTitle
              title="Transport Split"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 16l4-5h10l4 5" />
                  <path d="M5 16h14" />
                  <circle cx="7.5" cy="17.5" r="1.5" />
                  <circle cx="16.5" cy="17.5" r="1.5" />
                </svg>
              }
            />
            {transportLegs.length === 0 ? (
              <div className={styles.placeholder}>No transport legs were costed.</div>
            ) : (
              <div className={styles.stack}>
                <div className={styles.detailReason}>Subtotal: {formatRange(transportTotal)}</div>
                {transportLegs.map((leg, index) => (
                  <div key={`${leg.day_number}-${leg.from_area}-${index}`} className={styles.detailCard}>
                    <div className={styles.detailQuestion}>Day {leg.day_number}: {leg.from_area} to {leg.to_area}</div>
                    <div className={styles.detailReason}>{leg.recommended_mode} • {leg.approx_duration}</div>
                    <div><strong>Fare:</strong> {leg.approx_fare || '-'}</div>
                    <div className={styles.detailReason}>{leg.notes}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
        {food && (
          <Card variant="review">
            <SectionTitle
              title="Food Split"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 7h16" />
                  <path d="M6 7l1 11h10l1-11" />
                  <path d="M9 11v3" />
                  <path d="M15 11v3" />
                </svg>
              }
            />
            {foodRecommendations.length === 0 ? (
              <div className={styles.placeholder}>No meal recommendations were costed.</div>
            ) : (
              <div className={styles.stack}>
                <div className={styles.detailReason}>Subtotal: {formatRange(foodTotal)}</div>
                {foodRecommendations.map((item, index) => (
                  <div key={`${item.day_number}-${item.meal}-${item.venue_name}-${index}`} className={styles.detailCard}>
                    <div className={styles.detailQuestion}>Day {item.day_number} {item.meal}: {item.venue_name}</div>
                    <div className={styles.detailReason}>{item.area} • {item.cuisine_type}</div>
                    <div><strong>Estimated meal spend:</strong> {formatRange(mealRangeFromPriceLevel(item.price_level))}</div>
                    <div><strong>Price band:</strong> {item.price_level || '-'}</div>
                    <div className={styles.detailReason}>{item.why_fit}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
      <Card variant="caution">
        <SectionTitle
          title="Warnings"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3 2 21h20L12 3Z" />
              <path d="M12 9v4" />
              <path d="M12 17h.01" />
            </svg>
          }
        />
        <ul className={styles.infoList}>
          {budget.warnings.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </Card>
    </div>
  );
};

export default Budget;
