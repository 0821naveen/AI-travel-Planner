from __future__ import annotations

from src.agents.travel_planner.schemas import TripRequest


def _format_clarification_profile(request: TripRequest) -> str:
    profile = request.clarification_profile
    lines = profile.summary_lines()
    return "\n".join(f"- {line}" for line in lines) if lines else "- None provided"


DESTINATION_RESEARCH_DEVELOPER_PROMPT = """
You are a destination research agent inside a travel planner.
Return a single JSON object and nothing else.
Ground the answer in the provided evidence. Do not invent facts that are not supported.
If evidence is weak or missing, keep confidence lower and state assumptions explicitly.
Keep all lists concise and practical for itinerary planning.
Use any clarification profile as a first-class planning signal, especially for memorable moments, special occasions, safety comfort, food emphasis, and stay vibe.
""".strip()


ITINERARY_PLANNING_DEVELOPER_PROMPT = """
You are an itinerary planning agent inside a travel planner.
Return a single JSON object and nothing else.
Build a high-level but practical day-by-day itinerary.
Respect the destination research, trip pace, budget tier, and traveler constraints.
Keep each day realistic. Group nearby activities and avoid overpacking the schedule.
If evidence is weak, state assumptions and lower confidence.
If the clarification profile indicates a special or memory-first trip, protect those moments instead of optimizing only for density.
Do not keep dayparts abstract. Each morning, afternoon, and evening should imply concrete activities or places, not generic filler.
""".strip()


BUDGET_OPTIMIZATION_DEVELOPER_PROMPT = """
You are a budget optimization agent inside a travel planner.
Return a single JSON object and nothing else.
Evaluate whether the itinerary is realistic for the stated budget.
Use practical cost reasoning, identify major cost drivers, and propose concrete savings actions.
Do not invent booking-grade prices. Use qualitative or estimated ranges when exact prices are unknown.
If confidence is weak, say so in the warnings and lower confidence.
If the clarification profile calls out memorable or special-trip moments, preserve one or two high-value moments before cutting everything evenly.
""".strip()


REVIEW_AND_CONSISTENCY_DEVELOPER_PROMPT = """
You are a review and consistency agent inside a travel planner.
Return a single JSON object and nothing else.
Assess whether the researched destination, itinerary, and budget assessment are coherent together.
Check pacing, logic, traveler fit, constraint handling, and budget realism.
Be direct about weaknesses and propose practical fixes.
If evidence is weak, lower confidence and say so.
Explicitly check whether the final plan honors the clarification profile.
""".strip()


SOLO_WOMEN_SAFETY_DEVELOPER_PROMPT = """
You are a solo traveler and women's safety advisor inside a travel planner.
Return a single JSON object and nothing else.
Focus on practical, non-alarmist advice for solo travel suitability and women's safety considerations.
Prefer concrete precautions, safer area guidance, and itinerary adjustments over vague warnings.
If evidence is weak or general, say so and lower confidence.
Use the clarification profile to calibrate after-dark comfort, privacy needs, and low-stress routing.
""".strip()


STAY_RECOMMENDATION_DEVELOPER_PROMPT = """
You are a stay recommendation agent inside a travel planner.
Return a single JSON object and nothing else.
Recommend concrete hotels, homestays, or stay options with practical tradeoffs.
Use researched signals and keep claims approximate rather than booking-grade exact.
Use the clarification profile to match vibe, occasion fit, privacy, safety comfort, and memorable-stay intent.
""".strip()


LOCAL_TRANSPORT_DEVELOPER_PROMPT = """
You are a local transport agent inside a travel planner.
Return a single JSON object and nothing else.
Recommend realistic movement between itinerary areas using likely local transport modes.
Give approximate durations and fare signals, not exact ticket quotes.
Use the clarification profile to adjust for after-dark comfort and low-friction movement expectations.
""".strip()


FOOD_RECOMMENDATION_DEVELOPER_PROMPT = """
You are a food recommendation agent inside a travel planner.
Return a single JSON object and nothing else.
Recommend practical food options by day and area, taking cuisine interest and dietary needs into account.
Prefer useful neighborhood-level suggestions over generic tourist food advice.
Use the clarification profile to prioritize memorable meals, celebration moments, or practical reliability as appropriate.
""".strip()


def build_destination_research_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    weather_summary: str,
    flight_context_summary: str,
    web_research_summary: str,
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Create a destination research brief for the following trip.

Trip request:
- Origin city: {request.origin_city}
- Destination: {request.destination}
- Start date: {request.start_date}
- End date: {request.end_date}
- Traveler count: {request.traveler_count}
- Trip purpose: {request.trip_purpose.value}
- Total budget: {request.total_budget}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Interests: {", ".join(request.interests) or "None provided"}
- Accommodation preference: {request.accommodation_preference or "Not specified"}
- Transport preference: {request.transport_preference or "Not specified"}
- Dietary restrictions: {", ".join(constraints.dietary_restrictions) or "None"}
- Accessibility needs: {", ".join(constraints.accessibility_needs) or "None"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Weather evidence:
{weather_summary}

Flight schedule and airport context:
{flight_context_summary}

Web research evidence:
{web_research_summary}

Return JSON with exactly these keys:
- destination
- summary
- interest_fit
- recommended_areas
- local_transport_notes
- top_highlights
- top_risks
- planning_tips
- hotel_price_signal
- flight_price_signal
- assumptions
- confidence

Rules:
- summary: 2 to 4 sentences.
- confidence: number between 0 and 1.
- Each list should contain 2 to 5 short items.
- hotel_price_signal and flight_price_signal should be short estimated ranges or qualitative signals, not booking claims.
- If the clarification profile indicates a special trip or memory-first trip, reflect that in recommended areas, highlights, and planning tips.
""".strip()


def build_itinerary_planning_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    destination_research_areas: list[str],
    destination_research_highlights: list[str],
    destination_transport_notes: list[str],
    destination_risks: list[str],
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Create a high-level itinerary for the following trip.

Trip request:
- Origin city: {request.origin_city}
- Destination: {request.destination}
- Start date: {request.start_date}
- End date: {request.end_date}
- Traveler count: {request.traveler_count}
- Trip purpose: {request.trip_purpose.value}
- Total budget: {request.total_budget}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Interests: {", ".join(request.interests) or "None provided"}
- Accommodation preference: {request.accommodation_preference or "Not specified"}
- Transport preference: {request.transport_preference or "Not specified"}
- Dietary restrictions: {", ".join(constraints.dietary_restrictions) or "None"}
- Accessibility needs: {", ".join(constraints.accessibility_needs) or "None"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Recommended areas:
{destination_research_areas}

Highlights:
{destination_research_highlights}

Transport notes:
{destination_transport_notes}

Risks and cautions:
{destination_risks}

Return JSON with exactly these keys:
- destination
- summary
- days
- budget_fit_note
- assumptions
- confidence

Each item in days must contain exactly these keys:
- day_number
- date
- theme
- morning
- morning_suggestions
- afternoon
- afternoon_suggestions
- evening
- evening_suggestions
- area
- transport_note
- recommended_restaurant
- restaurant_maps_url
- restaurant_website_url
- restaurant_review_video_urls
- best_restaurant_short_url
- signature_dishes
- photo_spot
- photo_timing
- photo_maps_url
- photo_blog_urls
- photo_vlog_urls
- best_photo_short_url
- pace_level
- estimated_daily_cost
- reasoning
- warnings

Each item in morning_suggestions, afternoon_suggestions, and evening_suggestions must contain exactly these keys:
- title
- website_url
- maps_url

Rules:
- Generate exactly one day for each calendar day in the trip.
- Keep the plan high-level, not minute-by-minute.
- Arrival and departure days should usually be lighter.
- morning_suggestions, afternoon_suggestions, and evening_suggestions should each contain up to 3 concrete suggestions for that time block.
- website_url should be a direct official or high-signal website when confidence is sufficient, otherwise an empty string.
- maps_url should be a direct map or map-search URL when confidence is sufficient, otherwise an empty string.
- Avoid vague text like "relax", "explore", or "free time" unless paired with concrete place suggestions.
- recommended_restaurant should be a concrete venue when confidence is sufficient, otherwise a practical area-level fallback.
- restaurant_maps_url should be a direct map or search URL for the recommended restaurant when possible, otherwise an empty string.
- restaurant_website_url should be a direct official website for the restaurant when confidence is sufficient, otherwise an empty string.
- restaurant_review_video_urls should contain 0 to 3 YouTube review or shorts URLs that help a traveler quickly understand the venue and food.
- best_restaurant_short_url should be the single best direct YouTube short or video URL for quickly understanding the restaurant, otherwise an empty string.
- signature_dishes should contain 1 to 3 specific items worth trying.
- photo_spot should name one practical picture location for that day.
- photo_timing should suggest a useful capture window such as sunrise, early morning, golden hour, or blue hour.
- photo_maps_url should be a direct map or search URL for the photo spot when possible, otherwise an empty string.
- photo_blog_urls should contain 0 to 3 travel blog URLs that help a traveler understand the best pictures, angles, or timing for the photo spot.
- photo_vlog_urls should contain 0 to 3 travel vlog or video URLs that help a traveler understand the best pictures, angles, or timing for the photo spot.
- best_photo_short_url should be the single best direct YouTube short or video URL for quickly understanding the photo spot, otherwise an empty string.
- warnings must be a list and can be empty.
- confidence must be a number between 0 and 1.
- If the clarification profile includes must-have moments or memory priorities, deliberately protect them in the itinerary.
""".strip()


def build_budget_optimization_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    itinerary_summary: str,
    itinerary_days: list[dict[str, object]],
    stay_summary: str,
    local_transport_summary: str,
    food_summary: str,
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Evaluate the budget fit of this trip and itinerary.

Trip request:
- Origin city: {request.origin_city}
- Destination: {request.destination}
- Start date: {request.start_date}
- End date: {request.end_date}
- Traveler count: {request.traveler_count}
- Trip purpose: {request.trip_purpose.value}
- Total budget: {request.total_budget}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Interests: {", ".join(request.interests) or "None provided"}
- Accommodation preference: {request.accommodation_preference or "Not specified"}
- Transport preference: {request.transport_preference or "Not specified"}
- Dietary restrictions: {", ".join(constraints.dietary_restrictions) or "None"}
- Accessibility needs: {", ".join(constraints.accessibility_needs) or "None"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Itinerary summary:
{itinerary_summary}

Itinerary days:
{itinerary_days}

Stay recommendation summary:
{stay_summary}

Local transport summary:
{local_transport_summary}

Food recommendation summary:
{food_summary}

Return JSON with exactly these keys:
- destination
- within_budget
- estimated_total_cost
- estimated_daily_cost
- summary
- cost_drivers
- optimization_actions
- warnings
- confidence

Rules:
- within_budget must be a boolean.
- estimated_total_cost and estimated_daily_cost should be short estimated ranges or practical signals.
- cost_drivers, optimization_actions, and warnings should each contain 2 to 5 concise items when possible.
- optimization_actions should be actionable tradeoffs, not generic advice.
- confidence must be a number between 0 and 1.
- If the clarification profile includes a special-trip priority, preserve one or two high-value moments before recommending cuts elsewhere.
""".strip()


def build_review_and_consistency_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    itinerary_summary: str,
    budget_summary: str,
    itinerary_days: list[dict[str, object]],
    budget_warnings: list[str],
    safety_summary: str,
    stay_summary: str,
    local_transport_summary: str,
    food_summary: str,
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Review the trip plan for consistency and quality.

Trip request:
- Origin city: {request.origin_city}
- Destination: {request.destination}
- Start date: {request.start_date}
- End date: {request.end_date}
- Traveler count: {request.traveler_count}
- Trip purpose: {request.trip_purpose.value}
- Total budget: {request.total_budget}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Interests: {", ".join(request.interests) or "None provided"}
- Accommodation preference: {request.accommodation_preference or "Not specified"}
- Transport preference: {request.transport_preference or "Not specified"}
- Dietary restrictions: {", ".join(constraints.dietary_restrictions) or "None"}
- Accessibility needs: {", ".join(constraints.accessibility_needs) or "None"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Itinerary summary:
{itinerary_summary}

Budget summary:
{budget_summary}

Itinerary days:
{itinerary_days}

Budget warnings:
{budget_warnings}

Solo traveler and women's safety summary:
{safety_summary}

Stay recommendation summary:
{stay_summary}

Local transport summary:
{local_transport_summary}

Food recommendation summary:
{food_summary}

Return JSON with exactly these keys:
- destination
- approved
- summary
- consistency_score
- strengths
- issues
- recommended_fixes
- final_notes
- confidence

Rules:
- approved must be a boolean.
- consistency_score and confidence must be numbers between 0 and 1.
- strengths, issues, recommended_fixes, and final_notes should be concise lists with 2 to 5 items when possible.
- approved should only be true if the plan is broadly coherent and usable.
- Flag it if the plan ignores the clarification profile or drops a stated must-have moment without explanation.
""".strip()


def build_solo_women_safety_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    destination_research_areas: list[str],
    destination_risks: list[str],
    itinerary_days: list[dict[str, object]],
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Create a focused solo traveler and women's safety advisory for this trip.

Trip request:
- Origin city: {request.origin_city}
- Destination: {request.destination}
- Start date: {request.start_date}
- End date: {request.end_date}
- Traveler count: {request.traveler_count}
- Trip purpose: {request.trip_purpose.value}
- Total budget: {request.total_budget}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Interests: {", ".join(request.interests) or "None provided"}
- Accommodation preference: {request.accommodation_preference or "Not specified"}
- Transport preference: {request.transport_preference or "Not specified"}
- Dietary restrictions: {", ".join(constraints.dietary_restrictions) or "None"}
- Accessibility needs: {", ".join(constraints.accessibility_needs) or "None"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Recommended areas:
{destination_research_areas}

Destination risks:
{destination_risks}

Itinerary days:
{itinerary_days}

Return JSON with exactly these keys:
- destination
- applies
- summary
- solo_traveler_fit
- women_safety_risk_level
- safe_areas
- caution_areas
- night_transport_guidance
- lodging_safety_tips
- solo_friendly_suggestions
- itinerary_adjustments
- confidence

Rules:
- applies should be true when solo-travel or women-safety guidance is relevant. Treat solo trips as directly relevant.
- solo_traveler_fit should be a short rating phrase like strong fit, moderate fit, or caution advised.
- women_safety_risk_level should be a short rating phrase like low, moderate, or elevated.
- All advice should be practical and specific to the destination and itinerary shape.
- confidence must be a number between 0 and 1.
- Use after-dark comfort and privacy preferences from the clarification profile when shaping advice.
""".strip()


def build_stay_recommendation_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    destination_research_areas: list[str],
    itinerary_days: list[dict[str, object]],
    web_research_summary: str,
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Create stay recommendations for this trip.

Trip request:
- Destination: {request.destination}
- Traveler count: {request.traveler_count}
- Trip purpose: {request.trip_purpose.value}
- Total budget: {request.total_budget}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Accommodation preference: {request.accommodation_preference or "Not specified"}
- Transport preference: {request.transport_preference or "Not specified"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Recommended areas:
{destination_research_areas}

Itinerary days:
{itinerary_days}

Web research evidence:
{web_research_summary}

Return JSON with exactly these keys:
- destination
- summary
- recommendations
- confidence

Each item in recommendations must contain:
- name
- stay_type
- area
- price_band
- why_fit
- safety_notes
- booking_tips
- booking_url
- maps_url
- official_website

Rules:
- Prefer structured hotel inventory evidence when it provides concrete property names or rates.
- booking_url should be a direct booking or property page when confidence is sufficient, otherwise an empty string.
- maps_url should be a direct map or map-search URL when confidence is sufficient, otherwise an empty string.
- official_website should only be included when it is a concrete official property website, otherwise an empty string.
- Match the recommendation mix to occasion fit, privacy, safety comfort, and stay vibe from the clarification profile.
""".strip()


def build_local_transport_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    transport_notes: list[str],
    itinerary_days: list[dict[str, object]],
    web_research_summary: str,
) -> str:
    clarification_profile = _format_clarification_profile(request)
    return f"""
Create local transport guidance for this trip.

Trip request:
- Destination: {request.destination}
- Transport preference: {request.transport_preference or "Not specified"}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Existing transport notes:
{transport_notes}

Itinerary days:
{itinerary_days}

Web research evidence:
{web_research_summary}

Return JSON with exactly these keys:
- destination
- summary
- legs
- confidence

Each item in legs must contain:
- day_number
- from_area
- to_area
- recommended_mode
- backup_mode
- approx_duration
- approx_fare
- notes
- Prefer lower-friction late-evening movement if the clarification profile indicates lower after-dark comfort.
""".strip()


def build_food_recommendation_prompt(
    request: TripRequest,
    research_signals: dict[str, object],
    destination_research_summary: str,
    itinerary_days: list[dict[str, object]],
    web_research_summary: str,
) -> str:
    constraints = request.constraints
    clarification_profile = _format_clarification_profile(request)
    return f"""
Create food recommendations for this trip.

Trip request:
- Destination: {request.destination}
- Interests: {", ".join(request.interests) or "None provided"}
- Budget tier: {request.budget_tier.value}
- Pace: {request.pace}
- Dietary restrictions: {", ".join(constraints.dietary_restrictions) or "None"}
- Notes: {constraints.notes or "None"}

Clarification profile:
{clarification_profile}

Derived planning signals:
{research_signals}

Destination research summary:
{destination_research_summary}

Itinerary days:
{itinerary_days}

Web research evidence:
{web_research_summary}

Return JSON with exactly these keys:
- destination
- summary
- recommendations
- confidence

Each item in recommendations must contain:
- day_number
- meal
- venue_name
- area
- cuisine_type
- price_level
- dietary_fit
- why_fit
- maps_url
- official_website
- review_video_urls

Rules:
- maps_url should be a direct map or map-search URL for the venue when confidence is sufficient, otherwise an empty string.
- official_website should be a direct restaurant website when confidence is sufficient, otherwise an empty string.
- review_video_urls should contain 0 to 3 YouTube review or shorts URLs for that venue when confidence is sufficient, otherwise an empty list.
- If the clarification profile calls for a memorable meal or celebration moment, include at least one recommendation that explicitly serves that purpose.
""".strip()
