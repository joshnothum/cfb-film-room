# Football KB Sources

This file tracks candidate external sources for future football strategy KB ingestion.
No automated ingestion is enabled yet.

Machine-readable allowlist:

- `docs/kb_allowlist.json`

## Candidate Sources

- URL: https://www.youtube.com/watch?v=gBHQZOulvIY
- Source label: YouTube - Receiver Route Concepts (User Stash)
- Added: 2026-03-06
- Status: deferred
- Notes: user-stashed for future strategy/coach-feedback phase; not used in current play-review workflow.

- URL: https://www.gripboost.com/blogs/news/football-receiver-route-tree
- Source label: Grip Boost - Football Receiver Route Tree
- Added: 2026-03-06
- Status: deferred
- Notes: user-stashed for future strategy/coach-feedback phase; not used in current play-review workflow.

- URL: https://throwdeeppublishing.com/blogs/football-glossary/football-pass-routes-complete-guide
- Source label: Throw Deep Publishing - Football Pass Routes Guide
- Added: 2026-03-06
- Status: deferred
- Notes: user-stashed for future strategy/coach-feedback phase; not used in current play-review workflow.

- URL: https://www.360player.com/blog/football-101-breaking-down-the-basics-of-the-route-tree
- Source label: 360Player - Route Tree Basics
- Added: 2026-03-06
- Status: deferred
- Notes: user-stashed for future strategy/coach-feedback phase; not used in current play-review workflow.

- URL: https://www.thephinsider.com/2016/6/20/11975890/football-101-wide-receiver-route-tree
- Source label: The Phinsider - WR Route Tree
- Added: 2026-03-06
- Status: deferred
- Notes: user-stashed for future strategy/coach-feedback phase; not used in current play-review workflow.

- URL: https://footballpipelines.com/ultimate-guide-to-wide-receiver-routes/
- Source label: Football Pipelines - Ultimate Guide to Wide Receiver Routes
- Added: 2026-03-06
- Status: deferred
- Notes: user-stashed for future strategy/coach-feedback phase; not used in current play-review workflow.

- URL: https://www.cfblabs.com/cfb-play-art-guide
- Source label: CFB Labs Play Art Guide
- Added: 2026-03-01
- Status: planned
- Notes: user-requested reference for future football-only knowledge base context.

- URL: https://footballplaycard.com/blog/mastering-the-stick-concept-football
- Source label: Football Play Card - Stick Concept
- Added: 2026-03-01
- Status: planned
- Notes: user-requested concept reference for passing game strategy context.

- URL: https://footballplaycard.com/blog/the-complete-guide-to-the-mesh-concept
- Source label: Football Play Card - Mesh Concept Guide
- Added: 2026-03-01
- Status: planned
- Notes: user-requested concept reference for mesh-specific coaching context.

- URL: https://www.littlelegendsfootball.com/post/what-is-a-mesh-concept
- Source label: Little Legends Football - Mesh Concept
- Added: 2026-03-01
- Status: planned
- Notes: user-requested explanatory reference for mesh concept framing.

- URL: https://www.reddit.com/r/footballstrategy/comments/1kinr43/what_does_a_modern_mike_leach_offense_look_like/
- Source label: Reddit r/footballstrategy - Modern Mike Leach Offense Discussion
- Added: 2026-03-01
- Status: planned
- Notes: user-requested community perspective source; lower-authority than coaching/technical references.

## Ingestion Policy (Planned)

- Use explicit source allowlisting before crawling or scraping.
- Store retrieval metadata for each chunk:
  - source URL
  - retrieval timestamp
  - source label
- Keep this KB football-domain-focused.
