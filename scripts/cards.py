#!/usr/bin/env python3
"""Generate README cards (commits, top languages, repo pins) as static SVGs.

Needs GITHUB_TOKEN. With a PAT (repo scope) private commits and languages count too.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = "leonavas"
PINS = [
    "omarchy-calendar", "omarchy-dock", "omarchy-whatsapp",
    "omarchy-astroa50", "omarchy-superstrike", "omarchy-mouse",
    "omarchy-shire-light-theme", "omarchy-shire-night-theme",
]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "cards")
ACCENT = "#2E8B57"
LANG_COLORS = ["#2E8B57", "#3CB371", "#66CDAA", "#8FBC8F", "#20B2AA", "#98FB98"]

STYLE = """<style>
  .bg { fill: #ffffff; stroke: #d0d7de; }
  .t { fill: #1f2328; font: 600 14px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }
  .s { fill: #59636e; font: 400 12px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }
  .n { fill: #1f2328; font: 700 32px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }
  .a { fill: %s; font: 600 14px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #0d1117; stroke: #30363d; }
    .t, .n { fill: #e6edf3; }
    .s { fill: #9198a1; }
  }
</style>""" % ACCENT


def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    body = json.load(urllib.request.urlopen(req))
    if body.get("errors"):
        raise SystemExit(body["errors"])
    return body["data"]


def card(w, h, inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'{STYLE}<rect class="bg" x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="6"/>{inner}</svg>\n'
    )


def total_commits():
    created = gql("query($u:String!){user(login:$u){createdAt}}", u=USER)["user"]["createdAt"]
    total = 0
    for year in range(int(created[:4]), datetime.now(timezone.utc).year + 1):
        c = gql(
            """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
                 contributionsCollection(from:$f,to:$t){totalCommitContributions restrictedContributionsCount}}}""",
            u=USER, f=f"{year}-01-01T00:00:00Z", t=f"{year}-12-31T23:59:59Z",
        )["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
    return total


def top_languages(n=6):
    sizes, cursor = {}, None
    while True:
        page = gql(
            """query($u:String!,$c:String){user(login:$u){repositories(first:100,after:$c,ownerAffiliations:OWNER,isFork:false){
                 pageInfo{hasNextPage endCursor}
                 nodes{languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}""",
            u=USER, c=cursor,
        )["user"]["repositories"]
        for repo in page["nodes"]:
            for e in repo["languages"]["edges"]:
                sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:n]
    total = sum(s for _, s in top) or 1
    return [(name, size / total) for name, size in top]


def commits_svg(total):
    return card(300, 136,
        '<text class="t" x="24" y="32">Total commits</text>'
        f'<text class="n" x="24" y="92">{total:,}</text>')


def langs_svg(langs):
    w, x, bar = 300, 24, ""
    for i, (_, pct) in enumerate(langs):
        seg = 252 * pct
        bar += f'<rect x="{x:.1f}" y="48" width="{seg:.1f}" height="8" fill="{LANG_COLORS[i]}"/>'
        x += seg
    legend = ""
    for i, (name, pct) in enumerate(langs):
        lx, ly = 24 + (i % 2) * 130, 78 + (i // 2) * 18
        legend += (f'<circle cx="{lx + 4}" cy="{ly - 4}" r="4" fill="{LANG_COLORS[i]}"/>'
                   f'<text class="s" x="{lx + 14}" y="{ly}">{escape(name)} {pct:.0%}</text>')
    return card(w, 136,
        '<text class="t" x="24" y="32">Top languages</text>'
        f'<clipPath id="r"><rect x="24" y="48" width="252" height="8" rx="4"/></clipPath>'
        f'<g clip-path="url(#r)">{bar}</g>{legend}')


def wrap(text, width=52):
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][: width - 1] + "…"
    return lines


def pin_svg(repo):
    r = gql(
        """query($u:String!,$r:String!){repository(owner:$u,name:$r){
             name description stargazerCount primaryLanguage{name color}}}""",
        u=USER, r=repo,
    )["repository"]
    desc = "".join(
        f'<text class="s" x="24" y="{58 + i * 18}">{escape(line)}</text>'
        for i, line in enumerate(wrap(r["description"] or ""))
    )
    meta = ""
    if r["primaryLanguage"]:
        lang = r["primaryLanguage"]
        meta += (f'<circle cx="28" cy="100" r="5" fill="{lang["color"] or ACCENT}"/>'
                 f'<text class="s" x="40" y="104">{escape(lang["name"])}</text>')
    meta += f'<text class="s" x="376" y="104" text-anchor="end">★ {r["stargazerCount"]}</text>'
    return card(400, 124, f'<text class="a" x="24" y="34">{escape(r["name"])}</text>{desc}{meta}')


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {"commits.svg": commits_svg(total_commits()), "langs.svg": langs_svg(top_languages())}
    for repo in PINS:
        files[f"{repo}.svg"] = pin_svg(repo)
    for name, svg in files.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)


if __name__ == "__main__":
    main()
