from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SITE_PACKAGES = Path(
    "/Users/naveen.kumar.p/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages"
)
if str(RUNTIME_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SITE_PACKAGES))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer


OUTPUT_PDF = REPO_ROOT / "CODE_EXPLAINER_MANUAL.pdf"
CODE_ROOTS = [
    "backend/src",
    "backend/tests",
    "backend/scripts",
    "frontend/src",
]
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".css", ".d.ts"}


def styles():
    sheet = getSampleStyleSheet()
    sheet.add(
        ParagraphStyle(
            name="ManualTitle",
            parent=sheet["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#12344D"),
            spaceAfter=16,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="ManualSubtitle",
            parent=sheet["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#486581"),
            spaceAfter=10,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="ChapterTitle",
            parent=sheet["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=24,
            textColor=colors.HexColor("#102A43"),
            spaceBefore=6,
            spaceAfter=10,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=sheet["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="Body",
            parent=sheet["BodyText"],
            fontName="Helvetica",
            fontSize=10.6,
            leading=15.2,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#243B53"),
            spaceAfter=7,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="Path",
            parent=sheet["BodyText"],
            fontName="Courier-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0B3954"),
            spaceAfter=3,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="ManualBullet",
            parent=sheet["BodyText"],
            fontName="Helvetica",
            fontSize=10.2,
            leading=14.4,
            leftIndent=16,
            firstLineIndent=-10,
            textColor=colors.HexColor("#243B53"),
            spaceAfter=5,
        )
    )
    sheet.add(
        ParagraphStyle(
            name="Small",
            parent=sheet["BodyText"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=11,
            textColor=colors.HexColor("#486581"),
            spaceAfter=4,
        )
    )
    return sheet


def list_code_files() -> list[Path]:
    files: list[Path] = []
    for root in CODE_ROOTS:
        for path in (REPO_ROOT / root).rglob("*"):
            if path.is_file() and path.suffix in CODE_EXTENSIONS:
                files.append(path.relative_to(REPO_ROOT))
    return sorted(files)


def group_by_parent(files: list[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for file_path in files:
        grouped[file_path.parent.as_posix()].append(file_path)
    return dict(sorted(grouped.items()))


def package_summary(parent: str) -> str:
    if parent == "backend/src":
        return "Backend source root. This is the main Python application tree. It holds the HTTP layer, orchestration runtime, services, provider clients, repositories, domain contracts, and worker entrypoints."
    if parent.startswith("backend/src/agents/travel_planner/multi_agent"):
        return "Coordinator-led multi-agent runtime. These modules define agent roles, coordination state, delegation rules, runtime scheduling, and adapter logic that reuses the older specialist implementations."
    if parent.startswith("backend/src/agents/travel_planner/tooling"):
        return "Planner tool abstraction layer. These files keep provider-facing capabilities organized as planner-owned tools rather than scattering raw external API logic into every specialist."
    if parent.startswith("backend/src/agents/travel_planner"):
        return "Planner core. This is where trip-planning state, specialist nodes, prompts, routing helpers, governance checks, and the original sequential graph are implemented."
    if parent.startswith("backend/src/api"):
        return "Backend HTTP boundary. Modules here accept requests, enforce auth, call services or use cases, and return typed responses."
    if parent.startswith("backend/src/application"):
        return "Application-layer contracts and mappers. These modules shape internal state into API-safe schemas and isolate transport-facing representations from storage and domain models."
    if parent.startswith("backend/src/core"):
        return "Cross-cutting backend infrastructure. Settings, logging, request context, redaction, response shaping, and security live here."
    if parent.startswith("backend/src/db"):
        return "SQLAlchemy database setup. These modules create the engine and sessions and define the ORM tables."
    if parent.startswith("backend/src/domain"):
        return "Domain model layer. Business concepts such as trips, jobs, workflows, and audit records are defined here without tying them directly to FastAPI or SQLAlchemy routes."
    if parent.startswith("backend/src/evals"):
        return "Evaluation helpers used to compare planner behavior against expected outcomes or golden cases."
    if parent.startswith("backend/src/messaging"):
        return "Async execution plumbing. These modules connect the application to Redis-backed queue behavior and background jobs."
    if parent.startswith("backend/src/persistence/memory"):
        return "In-memory repository implementations for tests or lightweight flows."
    if parent.startswith("backend/src/persistence/postgres"):
        return "Postgres-backed repository implementations used by the real backend runtime."
    if parent.startswith("backend/src/providers"):
        return "External provider client layer. These modules know how to talk to OpenAI, Tavily, SerpApi, WeatherAPI, and Aviationstack."
    if parent.startswith("backend/src/services"):
        return "Service layer. This is where orchestration-aware business operations are coordinated across repositories, runtimes, and policies."
    if parent.startswith("backend/src/workers"):
        return "Worker-process entrypoints that run queued workflow jobs outside the web server."
    if parent == "backend/tests":
        return "Backend automated tests. These modules describe the intended behavior of configuration, orchestration, providers, observability, security, and resilience."
    if parent == "backend/scripts":
        return "Backend operational utility scripts used for probes or load checks."
    if parent == "frontend/src":
        return "Frontend source root. It contains the application router, global CSS, route-level pages, reusable components, shared layouts, and the client-side planner integration layer."
    if parent.startswith("frontend/src/app/login"):
        return "Authentication screens. These files implement user login and signup flows in the browser."
    if parent.startswith("frontend/src/app"):
        return "Route-level React pages. Each module corresponds to a major user-facing screen such as new trip, clarification, itinerary, budget, review, or research."
    if parent.startswith("frontend/src/components"):
        return "Reusable UI building blocks shared across multiple pages."
    if parent.startswith("frontend/src/layouts"):
        return "Shared application layout modules that provide page chrome and structural consistency."
    if parent.startswith("frontend/src/lib"):
        return "Frontend integration library. This is where API calls, local storage helpers, and shared frontend types live."
    return f"Code package `{parent}`. This directory groups closely related modules so the repository remains navigable and layered instead of flat."


def describe_module(path: Path) -> str:
    value = path.as_posix()
    name = path.name

    explicit = {
        "backend/src/main.py": "FastAPI process entrypoint. It assembles the web application and mounts the API router.",
        "backend/src/bootstrap.py": "Dependency composition root. This module wires settings, repositories, services, runtimes, provider clients, queue support, and dependency-injection helpers.",
        "backend/src/api/main.py": "Main route module for the backend API. It exposes health, auth, trip creation, clarification, runtime inspection, admin review, and observability endpoints.",
        "backend/src/agents/travel_planner/graph.py": "Original sequential LangGraph workflow. It registers the step order for clarification, research, itinerary, stay, transport, food, budget, safety, review, and governance.",
        "backend/src/agents/travel_planner/nodes.py": "Primary specialist implementation module. This is where most planner artifacts are actually produced.",
        "backend/src/agents/travel_planner/schemas.py": "Core planner contract file. It defines trip requests, clarification models, and structured output artifacts used across backend and frontend.",
        "backend/src/agents/travel_planner/state.py": "Planner runtime state definitions shared by orchestration and specialists.",
        "backend/src/agents/travel_planner/governance.py": "Governance rules for confidence checks, early routing, and policy-oriented review signals.",
        "backend/src/agents/travel_planner/routing.py": "Small routing helper module that decides how the workflow moves after clarification or other checkpoints.",
        "backend/src/agents/travel_planner/prompts.py": "Prompt templates used by planner specialists.",
        "backend/src/agents/travel_planner/research_prompts.py": "Prompt templates focused on research-oriented planner behavior.",
        "backend/src/agents/travel_planner/research_clients.py": "Helper integrations for travel research tasks.",
        "backend/src/agents/travel_planner/contracts.py": "Typed input/output contract helpers for specialist nodes.",
        "backend/src/agents/travel_planner/tools.py": "Planner-level tool entry module tying tool abstractions into the travel planner subsystem.",
        "backend/src/agents/travel_planner/multi_agent/runtime.py": "Custom coordinator runtime that supports selective parallel specialist execution and explicit coordination state.",
        "backend/src/agents/travel_planner/multi_agent/coordinator.py": "Coordinator decision logic for choosing which specialist or specialist batch runs next.",
        "backend/src/agents/travel_planner/multi_agent/topology.py": "Role topology and delegation policy. It seeds the coordination ledger and defines allowed communication patterns.",
        "backend/src/agents/travel_planner/multi_agent/schemas.py": "Coordination ledger data contracts: roles, tasks, messages, artifacts, and runtime metadata.",
        "backend/src/agents/travel_planner/multi_agent/adapters.py": "Adapter layer that lets the new coordinator runtime reuse the older specialist node logic.",
        "backend/src/services/workflow_runtime_service.py": "Workflow execution service for job creation, run tracking, step tracking, cancellation, rerun, and queue submission.",
        "backend/src/services/travel_planner_service.py": "Main synchronous trip-planning service that bridges trip requests, planner runtime, and persistence.",
        "backend/src/services/clarification_copilot_service.py": "Clarification copilot service that asks focused follow-up questions before heavy workflow execution begins.",
        "backend/src/services/observability_service.py": "Run-trace and metrics service used for admin and operator visibility.",
        "backend/src/services/operator_review_service.py": "Service for review queues, approval decisions, and operator-facing trip inspection.",
        "backend/src/services/audit_service.py": "Durable audit-event recording and lookup service.",
        "backend/src/services/auth_service.py": "Authentication service for registration, login, and user-profile lookups.",
        "backend/src/services/readiness_service.py": "Dependency readiness service for startup and health reporting.",
        "backend/src/messaging/redis_queue.py": "Redis-backed queue builder used by asynchronous workflow execution.",
        "backend/src/messaging/background_jobs.py": "Background-job helpers used to bridge business logic into queued execution.",
        "backend/src/providers/factory.py": "Central factory that builds provider clients from configured settings.",
        "backend/src/providers/llm.py": "OpenAI client abstractions for model-backed structured generation.",
        "backend/src/providers/search.py": "Search-provider clients, including Tavily and SerpApi-style web lookups.",
        "backend/src/providers/travel.py": "Travel-provider clients such as weather and flight-enrichment access.",
        "backend/src/core/config.py": "Typed settings resolution for the backend runtime.",
        "backend/src/core/security.py": "Actor-context extraction, role checks, and rate-limiting support.",
        "backend/src/core/request_context.py": "Per-request metadata support such as request ids and contextual logging hooks.",
        "backend/src/core/response_shaping.py": "Response normalization helpers used before data leaves the backend.",
        "backend/src/core/logging.py": "Logger configuration helpers.",
        "backend/src/core/redaction.py": "Helpers for hiding or minimizing sensitive information.",
        "backend/src/db/models.py": "SQLAlchemy ORM table definitions for trips, jobs, workflow runs, workflow steps, users, and audit-related records.",
        "backend/src/db/session.py": "Database engine and session-factory setup.",
        "backend/src/db/base.py": "Declarative SQLAlchemy base model setup.",
        "backend/src/db/bootstrap.py": "Database bootstrap utilities.",
        "frontend/src/App.tsx": "Top-level React router and page composition module.",
        "frontend/src/index.tsx": "React browser entrypoint that mounts the app.",
        "frontend/src/index.css": "Global frontend styles and visual tokens.",
        "frontend/src/lib/planner.ts": "Frontend planner client layer. It centralizes HTTP calls, local persistence, runtime polling helpers, and shared UI-facing types.",
        "frontend/src/lib/planner.test.ts": "Frontend tests for the planner client and storage helpers.",
        "frontend/src/app/new-trip/NewTrip.tsx": "Trip intake screen where the user enters the base request.",
        "frontend/src/app/clarification/Clarification.tsx": "Clarification and workflow-launch screen that drives the guided copilot and shows runtime progress.",
        "frontend/src/app/research/Research.tsx": "Research artifact screen for destination context and evidence.",
        "frontend/src/app/itinerary/Itinerary.tsx": "Itinerary artifact screen for day-by-day trip plans.",
        "frontend/src/app/budget/Budget.tsx": "Budget artifact screen for spend analysis and optimization notes.",
        "frontend/src/app/review/Review.tsx": "Review and governance artifact screen.",
        "frontend/src/app/dashboard/Dashboard.tsx": "Landing dashboard for the frontend experience.",
        "frontend/src/app/login/Login.tsx": "Browser login screen.",
        "frontend/src/app/login/Signup.tsx": "Browser signup screen.",
        "frontend/src/layouts/AppLayout.tsx": "Shared layout and page-chrome wrapper for the frontend.",
        "backend/scripts/load_test.py": "Backend load-test utility for quick endpoint pressure checks.",
    }
    if value in explicit:
        return explicit[value]

    if value.startswith("backend/tests/"):
        stem = name.replace(".py", "").replace("_", " ")
        return f"Automated backend test module for {stem}. It captures intended behavior for one risk-prone area of the system."
    if value.startswith("backend/src/application/") and name.endswith("schemas.py"):
        return "Application-layer schema module. It defines response or transport contracts used outside the core domain layer."
    if value.startswith("backend/src/application/") and name.endswith("mappers.py"):
        return "Application-layer mapper module. It converts persistence or domain objects into API-facing schemas."
    if value.startswith("backend/src/application/") and name.endswith("use_cases.py"):
        return "Application-layer use-case module. It packages one coherent operation behind a narrow execution interface."
    if value.startswith("backend/src/application/"):
        return "Application-layer support module used to keep transport contracts and use cases separate from core runtime logic."
    if value.startswith("backend/src/domain/"):
        return "Domain contract module defining stable business concepts independently of web or database plumbing."
    if value.startswith("backend/src/persistence/memory/"):
        return "In-memory repository implementation used where lightweight storage behavior is sufficient."
    if value.startswith("backend/src/persistence/postgres/"):
        return "Postgres repository implementation that persists business and runtime records durably."
    if value.startswith("backend/src/agents/travel_planner/tooling/"):
        return "Planner tooling module that helps register, validate, or execute planner-owned tools."
    if value.startswith("backend/src/providers/"):
        return "Provider client module that wraps an external API behind repository-owned code."
    if value.startswith("backend/src/services/"):
        return "Service-layer module coordinating multiple dependencies into one backend capability."
    if value.startswith("backend/src/core/"):
        return "Cross-cutting backend utility module."
    if value.startswith("backend/src/db/"):
        return "Database infrastructure module."
    if value.startswith("backend/src/evals/"):
        return "Evaluation helper module for regressions, scoring, or golden-case execution."
    if value.startswith("backend/src/messaging/"):
        return "Async messaging module that supports queue-based execution."
    if value.startswith("backend/src/workers/"):
        return "Worker-side module that runs queued workflow tasks."
    if value.startswith("frontend/src/app/") and value.endswith(".tsx"):
        return "Route-level React page module that renders one major user workflow or artifact view."
    if value.startswith("frontend/src/app/") and value.endswith(".css"):
        return "Page-specific CSS module controlling one route's layout and visual treatment."
    if value.startswith("frontend/src/components/") and value.endswith(".tsx"):
        return "Reusable React component shared across one or more screens."
    if value.startswith("frontend/src/components/") and value.endswith(".css"):
        return "Component-scoped CSS module for a reusable UI building block."
    if value.startswith("frontend/src/layouts/"):
        return "Layout module for shared frontend structure."
    if value.startswith("frontend/src/react-app-env"):
        return "TypeScript environment declaration module for the React toolchain."
    return f"Code module `{value}`. It belongs to the repository-owned implementation surface and contributes to runtime behavior, UI rendering, or automated verification."


def pathless_name(path: str) -> str:
    return path if path else "root"


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#486581"))
    canvas.drawString(doc.leftMargin, 0.45 * inch, "Code Explainer Manual")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def add_bullets(story, style, items: list[str]) -> None:
    for item in items:
        story.append(Paragraph(f"• {item}", style))


def build_story():
    s = styles()
    files = list_code_files()
    grouped = group_by_parent(files)
    story = []

    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("Code Explainer Manual", s["ManualTitle"]))
    story.append(Paragraph("Travel Planner Agent", s["ManualTitle"]))
    story.append(
        Paragraph(
            "A module-by-module guide to the backend, frontend, and test code in the repository.",
            s["ManualSubtitle"],
        )
    )
    story.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} from {REPO_ROOT}.",
            s["ManualSubtitle"],
        )
    )
    story.append(
        Paragraph(
            "Scope note: this manual explains repo-owned code modules under backend source, backend tests, backend scripts, and frontend source. Generated assets, caches, third-party packages, and docs-only files are intentionally excluded.",
            s["Body"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("How To Use This Manual", s["ChapterTitle"]))
    for paragraph in [
        "This manual is organized around code packages rather than user stories. Read it when you need to understand where logic lives, which modules own specific responsibilities, and how backend and frontend pieces fit together.",
        "The backend should be read from the outside inward: entrypoint, API, services, orchestration, providers, persistence, and tests. The frontend should be read from the outside inward as well: router, page modules, shared components, layout, and client integration layer.",
        "A good reading rhythm is package summary first, then the file-level entries in that package, then the corresponding tests. That gives you both architecture intent and executable proof of behavior.",
    ]:
        story.append(Paragraph(paragraph, s["Body"]))

    story.append(Paragraph("Manual Outline", s["SectionTitle"]))
    add_bullets(
        story,
        s["ManualBullet"],
        [
            "Backend package map",
            "Frontend package map",
            "Test-suite explanations",
            "Module-by-module appendix",
        ],
    )

    story.append(Paragraph("Code Inventory Snapshot", s["SectionTitle"]))
    story.append(
        Preformatted(
            "\n".join(
                [
                    "backend/src: 101 modules",
                    "backend/tests: 16 modules",
                    "backend/scripts: 1 module",
                    "frontend/src: 46 modules",
                    f"total code modules documented: {len(files)}",
                ]
            ),
            s["Path"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("Backend Overview", s["ChapterTitle"]))
    for paragraph in [
        "The backend is a layered Python application built around FastAPI, LangGraph, a custom coordinator-led runtime, Redis-backed asynchronous execution, and Postgres persistence. The important design decision is that orchestration, provider access, storage, and API contracts are kept in distinct packages rather than being mixed into one file or one service.",
        "Two orchestration models exist side by side. The older sequential graph is still present because it provides a simple, understandable workflow baseline. The newer coordinator runtime adds explicit roles, task ledgers, selective parallelism, and more agent-like behavior. Both are worth understanding because the repository's current design has evolved through that transition.",
        "The backend tests are not an afterthought. They document intended behavior for configuration, providers, runtime coordination, observability, review flows, and resilience. Use them as a second form of architecture documentation.",
    ]:
        story.append(Paragraph(paragraph, s["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("Frontend Overview", s["ChapterTitle"]))
    for paragraph in [
        "The frontend is a React and TypeScript application organized around route-level pages and a central planner client. Each major screen corresponds to a backend artifact family or user workflow stage: new trip, clarification, research, itinerary, budget, review, dashboard, and auth.",
        "The most important frontend file is `frontend/src/lib/planner.ts` because it is the contract bridge between browser pages and backend APIs. It owns fetch helpers, runtime-polling helpers, local storage state, and shared frontend types. Route modules then consume that library rather than inventing their own transport logic.",
        "Reusable UI modules under `frontend/src/components` keep the pages from collapsing into giant single-file implementations. CSS modules remain near the components or pages they style, which keeps visual concerns local and discoverable.",
    ]:
        story.append(Paragraph(paragraph, s["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("Package Explanations", s["ChapterTitle"]))
    for parent, items in grouped.items():
        story.append(Paragraph(pathless_name(parent), s["SectionTitle"]))
        story.append(Paragraph(package_summary(parent), s["Body"]))
        story.append(Paragraph(f"Modules in this package: {len(items)}", s["Small"]))

    story.append(PageBreak())
    story.append(Paragraph("Module Appendix", s["ChapterTitle"]))
    for parent, items in grouped.items():
        story.append(Paragraph(pathless_name(parent), s["SectionTitle"]))
        story.append(Paragraph(package_summary(parent), s["Body"]))
        for item in items:
            story.append(Paragraph(item.as_posix(), s["Path"]))
            story.append(Paragraph(describe_module(item), s["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("Reading Sequence Recommendation", s["ChapterTitle"]))
    add_bullets(
        story,
        s["ManualBullet"],
        [
            "Start with `backend/src/main.py`, `backend/src/bootstrap.py`, and `backend/src/api/main.py` to understand process assembly and HTTP surface area.",
            "Move to `backend/src/agents/travel_planner/schemas.py`, `state.py`, `graph.py`, and `multi_agent/runtime.py` to understand planner contracts and orchestration.",
            "Then read `backend/src/services/workflow_runtime_service.py` and the persistence repositories to understand how async runs become durable records.",
            "After that, read `frontend/src/lib/planner.ts`, `frontend/src/app/new-trip/NewTrip.tsx`, and `frontend/src/app/clarification/Clarification.tsx` to understand the browser-side integration flow.",
            "Finally, read the backend tests alongside the corresponding modules to see what the code promises to preserve.",
        ],
    )

    story.append(Paragraph("Closing Note", s["SectionTitle"]))
    story.append(
        Paragraph(
            "This manual is meant to reduce search cost. A strong engineering manual does not replace reading the code; it makes reading the code more efficient by telling you where each responsibility lives before you dive into implementation detail.",
            s["Body"],
        )
    )

    return story


def main() -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.7 * inch,
        title="Code Explainer Manual",
        author="OpenAI Codex",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    print(f"Generated {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
