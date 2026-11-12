#!/usr/bin/env python3
"""Collect every scanner's output for one build into a single report.

Job logs age out, and a log is not evidence anyone can hand to an auditor six
months later. This writes one durable record per build answering: what was
scanned, by what, with what result, and what is inside the image.

Two renderings of the same data: Markdown to download, HTML for GitLab Pages,
because GitLab will not render a Markdown artifact in the browser.

Reads whatever is present in reports/ and fails if a scanner produced nothing,
rather than quietly publishing a clean-looking report built from missing data.
"""

import html
import json
import os
import pathlib
import sys
from collections import Counter

REPORTS = pathlib.Path("reports")
SEVERE = ("High", "Critical", "HIGH", "CRITICAL")
LICENCE_ROWS = 15


def load(name):
    path = REPORTS / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def job_urls():
    """Map job name to its URL, so every gate links to the run that produced it.

    A job cannot know another job's id, so this asks the API for the current
    pipeline's jobs. Any failure falls back to linking the pipeline itself,
    which is one click further but never wrong.
    """
    api = os.environ.get("CI_API_V4_URL")
    project = os.environ.get("CI_PROJECT_ID")
    pipeline = os.environ.get("CI_PIPELINE_ID")
    token = os.environ.get("CI_JOB_TOKEN")
    if not all((api, project, pipeline, token)):
        return {}

    import urllib.error
    import urllib.request

    url = f"{api}/projects/{project}/pipelines/{pipeline}/jobs?per_page=100"
    request = urllib.request.Request(url, headers={"JOB-TOKEN": token})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            jobs = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        print(f"note: could not resolve job links ({exc})", file=sys.stderr)
        return {}
    return {j["name"]: j["web_url"] for j in jobs if j.get("web_url")}


def collect():
    """Read every scanner report into one structure."""
    data = {
        "sha": os.environ.get("CI_COMMIT_SHORT_SHA", "local"),
        "ref": os.environ.get("CI_COMMIT_REF_NAME", "unknown"),
        "pipeline": os.environ.get("CI_PIPELINE_ID", "-"),
        "pipeline_url": os.environ.get("CI_PIPELINE_URL", ""),
        "image": os.environ.get("IMAGE", "shop-api"),
        "jobs": job_urls(),
        "infra_pipelines": os.environ.get(
            "INFRA_PIPELINES_URL",
            "https://gitlab.com/inga-group2/"
            "devops_technion_final_project_infra/-/pipelines",
        ),
        "missing": [],
    }

    trivy = load("trivy.json")
    if trivy is None:
        data["missing"].append("trivy")
        data["trivy"] = (None, "report not produced")
    else:
        findings = [
            v
            for result in trivy.get("Results", [])
            for v in (result.get("Vulnerabilities") or [])
        ]
        by_sev = Counter(v["Severity"] for v in findings)
        detail = ", ".join(f"{n} {s.lower()}" for s, n in by_sev.most_common())
        data["trivy"] = (len(findings), f"{detail or 'none'} (fixable only)")

    grype = load("grype.json")
    if grype is None:
        data["missing"].append("grype")
        data["grype"] = (None, "report not produced")
    else:
        matches = grype.get("matches", [])
        blocking = [
            m
            for m in matches
            if (m["vulnerability"].get("fix") or {}).get("state") == "fixed"
            and m["vulnerability"]["severity"] in SEVERE
        ]
        # `only-fixed` in .grype.yaml applies to the JSON output too, so these
        # counts already exclude vulnerabilities with no available fix.
        lower = len(matches) - len(blocking)
        data["grype"] = (len(blocking), f"{lower} further fixable findings below high")

    sbom = load("sbom.cdx.json")
    if sbom is None:
        data["missing"].append("sbom")
        data["sbom"] = None
    else:
        components = sbom.get("components", [])
        kinds = Counter(c.get("type") for c in components)
        licences = Counter()
        for component in components:
            for entry in component.get("licenses") or []:
                licence = entry.get("license") or {}
                name = (
                    licence.get("id")
                    or licence.get("name")
                    or entry.get("expression")
                )
                if name:
                    licences[name] += 1
        data["sbom"] = {
            "count": len(components),
            "kinds": ", ".join(f"{n} {k}" for k, n in kinds.most_common()),
            "licences": licences,
        }

    return data


GATES_INTRO = (
    "Two vulnerability scanners run deliberately: they use different databases "
    "and catch different things. Grype found a fixable CRITICAL in the Python "
    "interpreter that Trivy reported as clean, which is why the base image "
    "moved to 3.14.10."
)
LICENCE_NOTE = (
    "GPL components are Debian base-image packages, not linked into the "
    "application. Worth re-checking if the image is ever redistributed."
)


def gate_rows(data):
    """One row per gate: (gate, tool, result, link, note).

    `link` may be None, in which case the result renders as plain text.
    """
    trivy_count, trivy_note = data["trivy"]
    grype_count, grype_note = data["grype"]
    jobs = data["jobs"]
    # Without the API the pipeline page is still one click from every job.
    fallback = data["pipeline_url"] or None

    def job(name):
        return jobs.get(name, fallback)

    def fmt(value):
        return "n/a" if value is None else str(value)

    return [
        ("Secrets", "GitLeaks", "see job", job("gitleaks"),
         "full git history, not just the checkout"),
        ("SAST", "SonarQube", "see job", job("sonarqube"),
         "quality gate enforced with qualitygate.wait"),
        ("Image CVEs", "Trivy", fmt(trivy_count), job("trivy"), trivy_note),
        ("Image CVEs", "Grype", fmt(grype_count), job("grype"), grype_note),
        ("IaC", "Checkov", "infra repo", data["infra_pipelines"],
         "suppressions justified in .checkov.yaml"),
    ]


def render_markdown(data):
    out = [
        f"# Compliance report — {data['sha']}",
        "",
        f"- Branch: `{data['ref']}`",
        f"- Pipeline: {data['pipeline']}"
        + (f" ({data['pipeline_url']})" if data["pipeline_url"] else ""),
        f"- Image: `{data['image']}:{data['sha']}`",
        "",
        "## Security gates",
        "",
        "| Gate | Tool | Blocking findings | Notes |",
        "|---|---|---|---|",
    ]
    for gate, tool, count, link, note in gate_rows(data):
        cell = f"[{count}]({link})" if link else count
        out.append(f"| {gate} | {tool} | {cell} | {note} |")
    out += ["", GATES_INTRO, "", "## Software Bill of Materials", ""]

    sbom = data["sbom"]
    if sbom is None:
        out.append("SBOM not produced.")
    else:
        out += [
            f"{sbom['count']} components — {sbom['kinds']}.",
            "",
            "Formats: CycloneDX (`sbom.cdx.json`) for scanners, "
            "SPDX (`sbom.spdx.json`) for licence tooling.",
            "",
            "### Licences",
            "",
            "| Licence | Components |",
            "|---|---|",
        ]
        for name, count in sbom["licences"].most_common(LICENCE_ROWS):
            out.append(f"| {name} | {count} |")
        extra = len(sbom["licences"]) - LICENCE_ROWS
        if extra > 0:
            out.append(f"| … {extra} more | |")
        out += ["", LICENCE_NOTE]

    if data["missing"]:
        out += [
            "",
            "## Incomplete",
            "",
            f"No output from: {', '.join(data['missing'])}. "
            "This report covers only the scanners that ran.",
        ]
    return "\n".join(out) + "\n"


HTML_STYLE = """
:root{--bg:#fbfaf8;--fg:#1a1a18;--muted:#6f6c66;--line:#e5e2db;--surface:#fff;
      --ok:#1f5f4b;--bad:#a32d26}
@media(prefers-color-scheme:dark){:root{--bg:#151517;--fg:#eceae6;--muted:#9a978f;
      --line:#2d2d32;--surface:#1d1d20;--ok:#5fb795;--bad:#e8827c}}
*{box-sizing:border-box}
body{margin:0;padding:40px 20px 80px;background:var(--bg);color:var(--fg);
     font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto}
h1{font-size:26px;letter-spacing:-.02em;margin:0 0 6px}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
   margin:40px 0 12px;font-weight:650}
h3{font-size:15px;margin:26px 0 10px;font-weight:600}
.meta{color:var(--muted);font-size:14px;margin:0 0 4px}
.meta code{background:var(--surface);border:1px solid var(--line);
           padding:1px 6px;border-radius:5px;font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--surface);
      border:1px solid var(--line);border-radius:10px;overflow:hidden}
th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;
   color:var(--muted);font-weight:650;padding:11px 14px;border-bottom:1px solid var(--line)}
td{padding:11px 14px;border-bottom:1px solid var(--line);font-size:14.5px}
tr:last-child td{border-bottom:0}
td.n{font-variant-numeric:tabular-nums;text-align:right}
.ok{color:var(--ok);font-weight:650}
.bad{color:var(--bad);font-weight:650}
p{margin:14px 0;font-size:15px}
.note{color:var(--muted);font-size:14px}
.files{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.files a{display:inline-block;padding:8px 13px;border:1px solid var(--line);
         border-radius:8px;background:var(--surface);color:var(--fg);
         text-decoration:none;font-size:13.5px}
.files a:hover{border-color:var(--ok);color:var(--ok)}
.warn{border:1px solid var(--bad);border-radius:10px;padding:14px;color:var(--bad)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
"""


def render_html(data):
    e = html.escape
    sbom = data["sbom"]

    rows = []
    for gate, tool, count, link, note in gate_rows(data):
        cls = ""
        if count.isdigit():
            cls = ' class="ok"' if count == "0" else ' class="bad"'
        cell = f"<span{cls}>{e(count)}</span>"
        if link:
            cell = f'<a href="{e(link)}">{cell}</a>'
        rows.append(
            f"<tr><td>{e(gate)}</td><td>{e(tool)}</td>"
            f"<td class='n'>{cell}</td>"
            f"<td class='note'>{e(note)}</td></tr>"
        )

    pipeline = e(data["pipeline"])
    if data["pipeline_url"]:
        pipeline = f'<a href="{e(data["pipeline_url"])}">{pipeline}</a>'

    parts = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>",
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>Compliance report — {e(data['sha'])}</title>",
        f"<style>{HTML_STYLE}</style></head><body><main>",
        f"<h1>Compliance report</h1>",
        f"<p class=meta>Commit <code>{e(data['sha'])}</code> on "
        f"<code>{e(data['ref'])}</code> &middot; pipeline {pipeline}</p>",
        f"<p class=meta>Image <code>{e(data['image'])}:{e(data['sha'])}</code></p>",
        "<h2>Security gates</h2>",
        "<table><thead><tr><th>Gate</th><th>Tool</th>"
        "<th style='text-align:right'>Blocking</th><th>Notes</th></tr></thead>",
        f"<tbody>{''.join(rows)}</tbody></table>",
        f"<p class=note>{e(GATES_INTRO)}</p>",
        "<h2>Software Bill of Materials</h2>",
    ]

    if sbom is None:
        parts.append("<p>SBOM not produced.</p>")
    else:
        lic_rows = "".join(
            f"<tr><td>{e(name)}</td><td class=n>{n}</td></tr>"
            for name, n in sbom["licences"].most_common(LICENCE_ROWS)
        )
        extra = len(sbom["licences"]) - LICENCE_ROWS
        if extra > 0:
            lic_rows += (
                f"<tr><td class=note>… {extra} more</td><td class=n></td></tr>"
            )
        parts += [
            f"<p><strong>{sbom['count']} components</strong> — {e(sbom['kinds'])}.</p>",
            "<div class=files>"
            '<a href="sbom.txt">sbom.txt</a>'
            '<a href="sbom.cdx.json">CycloneDX</a>'
            '<a href="sbom.spdx.json">SPDX</a>'
            '<a href="trivy.json">trivy.json</a>'
            '<a href="grype.json">grype.json</a>'
            '<a href="compliance.md">compliance.md</a>'
            "</div>",
            "<h3>Licences</h3>",
            "<table><thead><tr><th>Licence</th>"
            "<th style='text-align:right'>Components</th></tr></thead>"
            f"<tbody>{lic_rows}</tbody></table>",
            f"<p class=note>{e(LICENCE_NOTE)}</p>",
        ]

    if data["missing"]:
        parts.append(
            f"<h2>Incomplete</h2><p class=warn>No output from: "
            f"{e(', '.join(data['missing']))}. This report covers only the "
            "scanners that ran.</p>"
        )

    parts.append("</main></body></html>")
    return "".join(parts)


def main():
    REPORTS.mkdir(exist_ok=True)
    data = collect()

    (REPORTS / "compliance.md").write_text(render_markdown(data))
    (REPORTS / "index.html").write_text(render_html(data))
    print(render_markdown(data))

    if data["missing"]:
        print(
            f"\nERROR: missing scanner output: {', '.join(data['missing'])}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
