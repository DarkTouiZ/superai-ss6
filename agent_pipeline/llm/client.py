"""Provider-agnostic LLM client.

Providers (selected via ``SS6_LLM_PROVIDER`` or auto-detected):

  * **anthropic** — Claude via the official SDK (paid; needs ``ANTHROPIC_API_KEY``).
  * **ollama**    — a local model on ``localhost:11434`` (free, private, offline).
                    Best fit for a no-cost PoC and the "no data leak" requirement.
  * **gemini**    — Google Gemini free tier (cloud). Free within quota; needs
                    ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``).
  * **mock**      — deterministic, grounded stand-in so the pipeline + evals run
                    with zero setup. Not a model; it templates output from the
                    grounding facts each agent injects.

``auto`` (default) picks anthropic (key) → gemini (key) → ollama (reachable) →
mock. All providers return the same ``LLMResponse`` and honor ``SS6_STRICT`` (no
silent downgrade when a provider is explicitly requested).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

from agent_pipeline import config


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    is_live: bool  # True for a real model call, False for the deterministic mock


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class AnthropicClient:
    """Thin wrapper over the Anthropic Messages API."""

    def __init__(self, model: str = config.LLM_MODEL) -> None:
        import anthropic  # local import: optional dep

        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.provider = "anthropic"
        self.is_live = True

    def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return LLMResponse(text, self.provider, self.model, is_live=True)


class OllamaClient:
    """Local Ollama server (free). Uses /api/chat with JSON-forced output."""

    def __init__(self, host: str = config.OLLAMA_HOST, model: str = config.OLLAMA_MODEL) -> None:
        import httpx  # already a transitive dep (chromadb/anthropic)

        self._httpx = httpx
        self.host = host.rstrip("/")
        self.model = model
        self.provider = "ollama"
        self.is_live = True
        # Fail fast if the server/model isn't there, so get_llm can fall back.
        tags = httpx.get(f"{self.host}/api/tags", timeout=2.0).json()
        names = {m.get("name", "") for m in tags.get("models", [])}
        # Accept exact or family match (e.g. "qwen2.5-coder:7b" vs "qwen2.5-coder").
        if names and not any(self.model.split(":")[0] in n for n in names):
            raise RuntimeError(
                f"Ollama is running but model '{self.model}' is not pulled. "
                f"Run: ollama pull {self.model}"
            )

    def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        resp = self._httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": "json",  # force valid JSON output
                "options": {"temperature": 0.2, "num_predict": max_tokens},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        text = resp.json()["message"]["content"]
        return LLMResponse(text, self.provider, self.model, is_live=True)


class GeminiClient:
    """Google Gemini free-tier via the REST API, with JSON-forced output."""

    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, model: str = config.GEMINI_MODEL) -> None:
        import httpx

        self._httpx = httpx
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")
        self.model = model
        self.provider = "gemini"
        self.is_live = True

    def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
            },
        }
        resp = self._httpx.post(
            f"{self._BASE}/{self.model}:generateContent",
            params={"key": self.api_key},
            json=body,
            timeout=120.0,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return LLMResponse(text, self.provider, self.model, is_live=True)


class MockLLM:
    """Deterministic offline stand-in. Branches on the ``<<GROUNDING:{...}>>`` block
    the agents inject: ``task=="plans"`` -> three archetype plans; ``task=="design"``
    -> design artifacts (UML, API spec, test cases). Keeps planning logic in the
    agents; the mock only assembles deterministic JSON from supplied grounding.
    """

    provider = "mock"
    model = "deterministic-mock-v1"
    is_live = False

    def complete(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        g = self._extract_grounding(user)
        if g is None:
            return LLMResponse(user, self.provider, self.model, is_live=False)
        task = g.get("task", "plans")
        builder = {
            "design": self._build_design,
            "code": self._build_code,
        }.get(task, self._build_plans)
        return LLMResponse(json.dumps(builder(g), indent=2), self.provider, self.model, False)

    @staticmethod
    def _extract_grounding(user: str) -> Optional[dict]:
        marker = "<<GROUNDING:"
        if marker not in user:
            return None
        start = user.index(marker) + len(marker)
        end = user.index(">>", start)
        try:
            return json.loads(user[start:end])
        except json.JSONDecodeError:
            return None

    # ---- plan generation (Phase 2) ----
    @staticmethod
    def _build_plans(g: dict) -> dict:
        req = g.get("requirement", "the requirement")
        prims = g.get("primitives", [])
        services = g.get("services", [])
        new_screen = "target_repo/frontend/src/app/features/top-customers/top-customers.component.ts"
        return {
            "plans": [
                {
                    "id": "A", "title": "Performance-optimized", "priority_focus": "performance",
                    "summary": f"Satisfy '{req}' with a server-side aggregate endpoint and a cached selector.",
                    "steps": [
                        "Add a top-customers SQL aggregate in the order repository.",
                        "Expose it via a dashboard controller route; paginate results.",
                        "Cache/memoize the response in ApiService so re-renders don't refetch.",
                        "Render the list with trackBy to minimize Angular re-renders.",
                    ],
                    "files_touched": [new_screen] + services[:1],
                    "primitives_reused": prims[:2],
                    "tradeoffs": {"pros": ["Fast with thousands of customers", "Less data over the wire"],
                                  "cons": ["More backend code", "Cache invalidation to manage"]},
                },
                {
                    "id": "B", "title": "Maintainability / component reuse", "priority_focus": "reuse",
                    "summary": f"Satisfy '{req}' by composing existing primitives and the ApiService.",
                    "steps": [
                        "Compose the new screen from the canonical Card + MetricTile + Badge primitives.",
                        "Fetch data through ApiService only; add no new HTTP code.",
                        "Format money with the existing MoneyPipe; reference design tokens only.",
                        "Add a unit test for the spend-sorting logic in a service.",
                    ],
                    "files_touched": [new_screen],
                    "primitives_reused": prims,
                    "tradeoffs": {"pros": ["Maximal reuse", "Strong context.md adherence", "Easy to review"],
                                  "cons": ["Not tuned for very large lists"]},
                },
                {
                    "id": "C", "title": "Pragmatic / fastest", "priority_focus": "speed",
                    "summary": f"Ship '{req}' fastest with a minimal component over the existing orders endpoint.",
                    "steps": ["Call the existing orders endpoint via ApiService and aggregate client-side.",
                              "Reuse the Card primitive; skip extra abstraction."],
                    "files_touched": [new_screen],
                    "primitives_reused": prims[:1],
                    "tradeoffs": {"pros": ["Quickest to deliver", "Few moving parts"],
                                  "cons": ["Client-side aggregation", "Less optimized"]},
                },
            ]
        }

    # ---- design artifacts (Phase 2 enrichment) ----
    @staticmethod
    def _build_design(g: dict) -> dict:
        req = g.get("requirement", "the requirement")
        prims = [p.split("/")[-1].replace(".component.ts", "").replace(".ts", "")
                 for p in g.get("primitives", [])]
        services = [s.split("/")[-1].replace(".ts", "") for s in g.get("services", [])]
        feature = "TopCustomersComponent"
        uml = "\n".join([
            "classDiagram",
            f"    class {feature} {{",
            "        +rows: TopCustomerRow[]",
            "        +ngOnInit() void",
            "    }",
            "    class ApiService {",
            "        +getTopCustomers() Observable~TopCustomerRow[]~",
            "    }",
            f"    {feature} --> CardComponent : composes",
            f"    {feature} --> MetricTileComponent : composes",
            f"    {feature} --> ApiService : uses",
            f"    {feature} --> MoneyPipe : formats",
        ])
        return {
            "design": {
                "requirement": req,
                "uml_mermaid": uml,
                "api_spec": [
                    "ApiService.getTopCustomers(): Observable<TopCustomerRow[]>",
                    "GET /api/v1/dashboard/top-customers -> { rows: TopCustomerRow[] }",
                    "interface TopCustomerRow { customer_id: number; full_name: string; spend_satang: number }",
                    "TopCustomersComponent.ngOnInit(): void",
                ],
                "test_cases": [
                    {"type": "functional", "name": "renders one Card per customer with spend formatted by MoneyPipe"},
                    {"type": "functional", "name": "sorts customers by total spend descending"},
                    {"type": "non_functional", "name": "empty state shows a message, does not crash (context.md §6)"},
                    {"type": "non_functional", "name": "spend totals use integer satang, no float drift (context.md §4/§5)"},
                    {"type": "non_functional", "name": "data fetched only via ApiService, not HttpClient/fetch (context.md §4)"},
                    {"type": "functional", "name": "interactive elements carry an aria-label (context.md §6)"},
                ],
                "ux_notes": "Compose canonical primitives; reference tokens.scss CSS variables only; no inline hex.",
                "architecture_notes": "Aggregation in a backend service/repository; component fetches via ApiService only.",
                "primitives_reused": prims,
                "services_used": services,
            }
        }

    # ---- code generation (Phase 3b) ----
    @staticmethod
    def _build_code(g: dict) -> dict:
        """Deterministic, context.md-compliant eleven-7 Angular feature for the winner."""
        path = "frontend/src/app/features/top-customers/top-customers.component.ts"
        content = (
            "// Generated by the SS6 Developer agent for the winning plan.\n"
            "// context.md: composes canonical primitives (Card, MetricTile, Badge),\n"
            "// fetches via ApiService only (no fetch/HttpClient), money as integer\n"
            "// satang formatted by MoneyPipe, design tokens only (no inline hex).\n"
            "import { Component, OnInit, inject } from '@angular/core';\n"
            "import { NgFor, NgIf } from '@angular/common';\n"
            "import { ApiService } from '../../core/services/api.service';\n"
            "import { MoneyPipe } from '../../core/services/money.pipe';\n"
            "import { CardComponent } from '../../shared/components/card/card.component';\n"
            "import { MetricTileComponent } from '../../shared/components/metric-tile/metric-tile.component';\n"
            "import { BadgeComponent } from '../../shared/components/badge/badge.component';\n\n"
            "interface TopCustomerRow {\n"
            "  customer_id: number;\n"
            "  full_name: string;\n"
            "  loyalty_tier: string;\n"
            "  spend_satang: number;\n"
            "}\n\n"
            "@Component({\n"
            "  selector: 'e7-top-customers',\n"
            "  standalone: true,\n"
            "  imports: [NgFor, NgIf, MoneyPipe, CardComponent, MetricTileComponent, BadgeComponent],\n"
            "  template: `\n"
            "    <h1>Top Customers by Spend</h1>\n"
            "    <e7-metric-tile label=\"Customers\" [value]=\"rows.length\"></e7-metric-tile>\n"
            "    <e7-card *ngIf=\"rows.length; else empty\">\n"
            "      <div class=\"row\" *ngFor=\"let r of rows\">\n"
            "        <span>{{ r.full_name }}</span>\n"
            "        <e7-badge variant=\"brand\">{{ r.loyalty_tier }}</e7-badge>\n"
            "        <span class=\"num\">{{ r.spend_satang | thb }}</span>\n"
            "      </div>\n"
            "    </e7-card>\n"
            "    <ng-template #empty><p class=\"muted\">No customer spend yet.</p></ng-template>\n"
            "  `,\n"
            "  styles: [`\n"
            "    .row { display: flex; justify-content: space-between; gap: var(--space-sm);\n"
            "           padding: var(--space-sm) 0; border-bottom: 1px solid var(--color-border); }\n"
            "    .num { color: var(--color-text-secondary); }\n"
            "    .muted { color: var(--color-text-secondary); }\n"
            "  `],\n"
            "})\n"
            "export class TopCustomersComponent implements OnInit {\n"
            "  private readonly api = inject(ApiService);\n"
            "  rows: TopCustomerRow[] = [];\n\n"
            "  ngOnInit(): void {\n"
            "    // ApiService is the only HTTP entry point (context.md §4).\n"
            "    this.api.getOrders().subscribe((r) => {\n"
            "      const byCustomer = new Map<number, TopCustomerRow>();\n"
            "      for (const o of r.orders as any[]) {\n"
            "        const row = byCustomer.get(o.customer_id) ?? {\n"
            "          customer_id: o.customer_id, full_name: o.order_no,\n"
            "          loyalty_tier: 'standard', spend_satang: 0,\n"
            "        };\n"
            "        row.spend_satang += o.total_satang;\n"
            "        byCustomer.set(o.customer_id, row);\n"
            "      }\n"
            "      this.rows = [...byCustomer.values()].sort((a, b) => b.spend_satang - a.spend_satang);\n"
            "    });\n"
            "  }\n"
            "}\n"
        )
        return {"files": [{"path": path, "content": content}]}


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
def _ollama_reachable() -> bool:
    try:
        import httpx

        httpx.get(f"{config.OLLAMA_HOST.rstrip('/')}/api/tags", timeout=1.5)
        return True
    except Exception:
        return False


def get_llm():
    """Resolve a provider per SS6_LLM_PROVIDER, honoring SS6_STRICT."""
    provider = config.LLM_PROVIDER
    strict = config.STRICT

    def _fail(msg: str):
        if strict:
            raise RuntimeError(f"SS6_STRICT: {msg}")
        print(f"[llm] {msg}; using deterministic MockLLM.", file=sys.stderr)
        return MockLLM()

    if provider == "mock":
        return MockLLM()

    if provider in ("anthropic", "auto") and os.getenv("ANTHROPIC_API_KEY"):
        try:
            return AnthropicClient()
        except Exception as exc:
            if provider == "anthropic":
                return _fail(f"Anthropic requested but unavailable ({exc.__class__.__name__})")

    if provider in ("gemini", "auto") and (
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    ):
        try:
            return GeminiClient()
        except Exception as exc:
            if provider == "gemini":
                return _fail(f"Gemini requested but unavailable ({exc.__class__.__name__})")

    if provider in ("ollama", "auto"):
        try:
            return OllamaClient()
        except Exception as exc:
            if provider == "ollama":
                return _fail(f"Ollama requested but unavailable ({exc})")
            print(f"[llm] Ollama not available ({exc.__class__.__name__}); ", end="", file=sys.stderr)

    if provider == "anthropic":
        return _fail("ANTHROPIC_API_KEY not set")
    if provider == "gemini":
        return _fail("GEMINI_API_KEY not set")
    return _fail("no live provider available")
