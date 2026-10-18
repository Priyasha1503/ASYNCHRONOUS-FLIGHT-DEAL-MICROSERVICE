# SkyScout AI — Design Decisions

Log of design decisions, newest first. Visual-identity decisions are deferred until references arrive.

| Date | Decision | Rationale |
|---|---|---|
| 2026-10-18 | Defer palette/typography until user references are inspected | Addendum §A: references are the source of truth; don't invent preferences |
| 2026-10-18 | Tokens live in `frontend/src/styles/tokens.css` as CSS variables, mapped into Tailwind theme | Single source for all screens; swappable once references land |
| 2026-10-18 | Fare source shown as icon + text badge | Addendum §B: never communicate status by colour alone |
