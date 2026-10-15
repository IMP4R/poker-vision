#!/usr/bin/env python3
"""Веб-поиск через ddgs — тот же бэкенд, что у NousResearch/hermes-agent (plugins/web/ddgs).
Usage: websearch.py "query" [limit] [--backend NAME] [--json]
"""
import json, sys
from ddgs import DDGS

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    if not args:
        print("usage: websearch.py \"query\" [limit]"); sys.exit(1)
    query = args[0]
    limit = int(args[1]) if len(args) > 1 else 6
    backend = "auto"
    for f in flags:
        if f.startswith('--backend='):
            backend = f.split('=', 1)[1]
    out = []
    with DDGS(timeout=10) as client:
        try:
            it = client.text(query, max_results=limit, backend=backend)
        except TypeError:
            it = client.text(query, max_results=limit)
        for i, hit in enumerate(it):
            out.append({
                "position": i + 1,
                "title": str(hit.get("title", "")),
                "url": str(hit.get("href") or hit.get("url") or ""),
                "body": str(hit.get("body", "")),
            })
    if '--json' in flags:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for r in out:
            print(f"[{r['position']}] {r['title']}\n    {r['url']}\n    {r['body'][:220]}\n")

if __name__ == "__main__":
    main()
