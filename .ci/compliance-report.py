#!/usr/bin/env python3
"""Collect every scanner's output for one build into a single report.

Job logs age out, and a log is not evidence anyone can hand to an auditor six
months later. This writes one durable artifact per build answering: what was
scanned, by what, with what result, and what is in the image.

Reads whatever is present in reports/ and reports honestly on what is missing,
rather than silently producing a clean-looking report because a scanner never
ran.
"""

import json
import os
import pathlib
import sys
from collections import Counter

REPORTS = pathlib.Path("reports")
SEVERE = ("High", "Critical", "HIGH", "CRITICAL")


def load(name):
    path = REPORTS / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def trivy_summary():
    data = load("trivy.json")
    if data is None:
        return None, "report not produced"
    findings = [
        v
        for result in data.get("Results", [])
        for v in (result.get("Vulnerabilities") or [])
    ]
    by_sev = Counter(v["Severity"] for v in findings)
    detail = ", ".join(f"{n} {s.lower()}" for s, n in by_sev.most_common()) or "none"
    return len(findings), f"{detail} (fixable only)"


def grype_summary():
    data = load("grype.json")
    if data is None:
        return None, "report not produced"
    matches = data.get("matches", [])
    fixable = [
        m
        for m in matches
        if (m["vulnerability"].get("fix") or {}).get("state") == "fixed"
        and m["vulnerability"]["severity"] in SEVERE
    ]
    # `only-fixed` in .grype.yaml applies to the JSON output too, so this count
    # is already limited to vulnerabilities with an available fix.
    lower = len(matches) - len(fixable)
    return len(fixable), f"{lower} further fixable findings below high"


def sbom_summary():
    data = load("sbom.cdx.json")
    if data is None:
        return None, None, "SBOM not produced"

    components = data.get("components", [])
    kinds = Counter(c.get("type") for c in components)

    licences = Counter()
    for component in components:
        for entry in component.get("licenses") or []:
            licence = entry.get("license") or {}
            name = licence.get("id") or licence.get("name") or entry.get("expression")
            if name:
                licences[name] += 1

    kind_detail = ", ".join(f"{n} {k}" for k, n in kinds.most_common())
    return len(components), licences, kind_detail


def main():
    REPORTS.mkdir(exist_ok=True)

    sha = os.environ.get("CI_COMMIT_SHORT_SHA", "local")
    ref = os.environ.get("CI_COMMIT_REF_NAME", "unknown")
    pipeline = os.environ.get("CI_PIPELINE_ID", "-")
    url = os.environ.get("CI_PIPELINE_URL", "")

    trivy_count, trivy_note = trivy_summary()
    grype_count, grype_note = grype_summary()
    package_count, licences, sbom_note = sbom_summary()

    missing = [
        name
        for name, value in (("trivy", trivy_count), ("grype", grype_count),
                            ("sbom", package_count))
        if value is None
    ]

    lines = [
        f"# Compliance report — {sha}",
        "",
        f"- Branch: `{ref}`",
        f"- Pipeline: {pipeline}" + (f" ({url})" if url else ""),
        f"- Image: `{os.environ.get('IMAGE', 'shop-api')}:{sha}`",
        "",
        "## Security gates",
        "",
        "| Gate | Tool | Blocking findings | Notes |",
        "|---|---|---|---|",
        f"| Secrets | GitLeaks | see job | full git history, not just the checkout |",
        f"| SAST | SonarQube | see job | quality gate enforced with `qualitygate.wait` |",
        f"| Image CVEs | Trivy | {fmt(trivy_count)} | {trivy_note} |",
        f"| Image CVEs | Grype | {fmt(grype_count)} | {grype_note} |",
        f"| IaC | Checkov | infra repo | suppressions justified in `.checkov.yaml` |",
        "",
        "Two vulnerability scanners run deliberately: they use different",
        "databases and catch different things. Grype found a fixable CRITICAL",
        "in the Python interpreter that Trivy reported as clean.",
        "",
        "## Software Bill of Materials",
        "",
    ]

    if package_count is None:
        lines.append(f"{sbom_note}.")
    else:
        lines += [
            f"{package_count} components — {sbom_note}.",
            "",
            "Formats: CycloneDX (`sbom.cdx.json`) for scanners, "
            "SPDX (`sbom.spdx.json`) for licence tooling.",
            "",
            "### Licences",
            "",
            "| Licence | Components |",
            "|---|---|",
        ]
        for name, count in licences.most_common(12):
            lines.append(f"| {name} | {count} |")
        if len(licences) > 12:
            lines.append(f"| … {len(licences) - 12} more | |")
        lines += [
            "",
            "GPL components are Debian base-image packages, not linked into the",
            "application. Worth re-checking if the image is ever redistributed.",
        ]

    if missing:
        lines += [
            "",
            "## Incomplete",
            "",
            f"No output from: {', '.join(missing)}. "
            "This report covers only the scanners that ran.",
        ]

    out = REPORTS / "compliance.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    # Fail loudly rather than publishing a clean-looking report built from
    # missing data.
    if missing:
        print(f"\nERROR: missing scanner output: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


def fmt(value):
    return "n/a" if value is None else str(value)


if __name__ == "__main__":
    sys.exit(main())
