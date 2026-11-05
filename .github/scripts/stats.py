"""Generate GitHub stats cards (SVG) for the profile README.

Runs in GitHub Actions with the default GITHUB_TOKEN. Only public data is read.
Usage: python stats.py <login> <out_dir>
"""
import json
import os
import sys
import urllib.request
from html import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
    repositoriesContributedTo(first: 50, includeUserRepositories: true,
        contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {
      totalCount
      nodes {
        nameWithOwner isFork isPrivate stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Languages that are mostly config, notebooks or generated files.
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS", "SCSS", "Dockerfile", "Makefile"}

STYLE = """
<style>
  .bg { fill: #ffffff; stroke: #d0d7de; }
  .title { font: 600 15px 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; fill: #1f2328; }
  .label { font: 400 13px 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; fill: #59636e; }
  .value { font: 600 13px 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; fill: #1f2328; }
  .track { fill: #eff2f5; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #0d1117; stroke: #30363d; }
    .title, .value { fill: #e6edf3; }
    .label { fill: #9198a1; }
    .track { fill: #21262d; }
  }
</style>
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def stats_card(user):
    cc = user["contributionsCollection"]
    repos = [r for r in user["repositoriesContributedTo"]["nodes"] if not r["isPrivate"]]
    rows = [
        ("Contributions (last year)", cc["contributionCalendar"]["totalContributions"]),
        ("Commits", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
        ("Pull requests", cc["totalPullRequestContributions"]),
        ("Public repos contributed to", len(repos)),
        ("Stars on those repos", sum(r["stargazerCount"] for r in repos)),
    ]
    w, h = 360, 52 + 26 * len(rows)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           STYLE,
           f'<rect class="bg" x="0.5" y="0.5" rx="6" width="{w-1}" height="{h-1}"/>',
           '<text class="title" x="20" y="32">GitHub activity</text>']
    for i, (label, value) in enumerate(rows):
        y = 64 + 26 * i
        out.append(f'<text class="label" x="20" y="{y}">{escape(label)}</text>')
        out.append(f'<text class="value" x="{w-20}" y="{y}" text-anchor="end">{value:,}</text>')
    out.append("</svg>")
    return "\n".join(out)


def langs_card(user, top=6):
    totals, colors = {}, {}
    for r in user["repositoriesContributedTo"]["nodes"]:
        if r["isPrivate"] or r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in SKIP_LANGS:
                continue
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#8b949e"
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:top]
    total = sum(v for _, v in ranked) or 1
    w, h = 360, 182  # same height as the stats card so they line up
    bar_w = w - 40
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           STYLE,
           f'<rect class="bg" x="0.5" y="0.5" rx="6" width="{w-1}" height="{h-1}"/>',
           '<text class="title" x="20" y="32">Languages</text>',
           f'<rect class="track" x="20" y="48" rx="4" width="{bar_w}" height="8"/>']
    x = 20.0
    for name, size in ranked:
        seg = bar_w * size / total
        out.append(f'<rect x="{x:.1f}" y="48" width="{seg:.1f}" height="8" fill="{colors[name]}"/>')
        x += seg
    for i, (name, size) in enumerate(ranked):
        cx = 20 + (i % 2) * (bar_w / 2)
        cy = 96 + 30 * (i // 2)
        out.append(f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{colors[name]}"/>')
        out.append(f'<text class="value" x="{cx+16}" y="{cy}">{escape(name)}</text>')
        out.append(f'<text class="label" x="{cx+bar_w/2-12}" y="{cy}" text-anchor="end">'
                   f'{100*size/total:.1f}%</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    user = fetch(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "stats.svg"), "w") as f:
        f.write(stats_card(user))
    with open(os.path.join(out_dir, "langs.svg"), "w") as f:
        f.write(langs_card(user))


if __name__ == "__main__":
    main()
