#!/usr/bin/env python3
"""Execution/Review evaluation — proves the compliance gate actually discriminates.

A gate that always passes is worthless. So this eval checks BOTH directions:

  * a compliant reference file PASSES, and
  * each deliberately non-compliant fixture FAILS on the expected rule
    (inline hex, direct fetch, no primitive reuse, no export).

If the gate passes the good file and fails every bad fixture on the right rule, the
Review phase is a real gate, not a rubber stamp. Exit non-zero on any surprise.

Run:
    python eval/execution_quality.py
    python eval/execution_quality.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline.review import check_file  # noqa: E402

# Compliant eleven-7 reference: composes a canonical primitive (CardComponent),
# fetches via ApiService, uses design-token CSS variables, has an export + return type.
GOOD = (
    "import { Component } from '@angular/core';\n"
    "import { ApiService } from '../../core/services/api.service';\n"
    "import { CardComponent } from '../../shared/components/card/card.component';\n"
    "@Component({ selector: 'e7-x', standalone: true, imports: [CardComponent],\n"
    "  template: `<e7-card>ok</e7-card>`, styles: [`.x{ color: var(--color-brand); }`] })\n"
    "export class XComponent { constructor(private api: ApiService) {} load(): void {} }\n"
)

BAD_FIXTURES = {
    "inline_hex": (
        "import { CardComponent } from '../../shared/components/card/card.component';\n"
        "@Component({ template: `<e7-card></e7-card>`, styles: [`.x{ color: #ff0000; }`] })\n"
        "export class S { c = CardComponent; }\n",
        "inline hex",
    ),
    "direct_fetch": (
        "import { CardComponent } from '../../shared/components/card/card.component';\n"
        "export class S { c = CardComponent; load(): void { fetch('/api/x'); } }\n",
        "fetch()",
    ),
    "httpclient_in_component": (
        "import { HttpClient } from '@angular/common/http';\n"
        "import { CardComponent } from '../../shared/components/card/card.component';\n"
        "@Component({ template: `<e7-card></e7-card>` })\n"
        "export class S { c = CardComponent; constructor(private http: HttpClient) {} }\n",
        "HttpClient",
    ),
    "no_primitive_reuse": (
        "import { Component } from '@angular/core';\n"
        "@Component({ template: `<div>x</div>`, styles: [`.x{ color: var(--color-brand); }`] })\n"
        "export class S {}\n",
        "canonical primitive",
    ),
    "no_export": (
        "import { CardComponent } from '../../shared/components/card/card.component';\n"
        "class S { c = CardComponent; }\n",
        "no export",
    ),
}


def evaluate() -> dict:
    good = check_file("Good.tsx", GOOD)
    good_ok = good.passed

    fixtures = {}
    all_bad_caught = True
    for name, (content, expect_substr) in BAD_FIXTURES.items():
        fr = check_file(f"{name}.tsx", content)
        caught = (not fr.passed) and any(expect_substr in v for v in fr.violations)
        all_bad_caught = all_bad_caught and caught
        fixtures[name] = {
            "expected_violation_contains": expect_substr,
            "failed_as_expected": caught,
            "violations": fr.violations,
        }

    return {
        "good_file_passes": good_ok,
        "good_warnings": good.warnings,
        "bad_fixtures": fixtures,
        "pass": good_ok and all_bad_caught,
    }


def _print_human(r: dict) -> None:
    print("\n=== SS6 Execution/Review quality report ===")
    print(f"[{'PASS' if r['good_file_passes'] else 'FAIL'}] compliant reference file passes")
    for name, f in r["bad_fixtures"].items():
        mark = "PASS" if f["failed_as_expected"] else "FAIL"
        print(f"[{mark}] bad fixture '{name}' caught (expects '{f['expected_violation_contains']}')")
    print(f"\nOVERALL: {'PASS' if r['pass'] else 'FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Review compliance gate.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    print(json.dumps(report, indent=2) if args.json else "", end="")
    if not args.json:
        _print_human(report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
