# Meal Planner Web Interface — Design Spec

**Date:** 2026-06-14  
**Status:** Approved

## Goal

Local web UI for weekly meal planning with rotation history, recipe instructions/images, and Amazon grocery ordering via the existing Python CLI.

## Stack

- **Server:** Node.js + Express (JavaScript only)
- **UI:** Preact + HTM (no build step, no TypeScript)
- **Data:** JSON files (`data/planning.json`, `recipes/week-*.json`)
- **Amazon:** Python CLI subprocess only (`python -m purchasing auth login` / `run`)

## Data

- **Catalog:** Union of all meals from `recipes/week-*.json`, deduped by slug
- **Planning:** `data/planning.json` — settings + week history
- **Purchase input:** `recipes/current-week.json` — selected meals only

## Meal Selection

1. Cooldown: exclude meals cooked within N weeks (default 4)
2. Rotation score: weeks since last cooked
3. Diversity: penalize same protein/starch within a week
4. Grouping bonus: reward shared staple ingredients (onion, garlic, lemon, etc.)

## UI Screens

1. **Week planner** — suggest/swap meals, confirm week
2. **Recipe detail** — instructions, ingredients, images
3. **History** — past weeks
4. **Purchase** — Amazon session status, auth trigger, order subprocess

## Amazon Integration

- Auth stays in Python CLI (Playwright browser login)
- Web shows session valid/expired/missing
- Purchase spawns `python -m purchasing run`; CLI approval in terminal (v1)

## Deferred

- Web-based ingredient approval
- Cross-meal ingredient quantity aggregation in purchasing pipeline
- Automatic checkout from web UI
