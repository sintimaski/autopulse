---
title: Lumonox Demo
emoji: 🚀
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Live, self-seeding demo of Lumonox observability
---

# Lumonox — live demo 🚀

This Space runs a full, self-contained instance of **[Lumonox](https://github.com/sintimaski/lumonox)** — opinionated observability for **FastAPI** and **Django** apps that answers *what broke, when, and which requests led to it*.

It boots the FastAPI ingest API + dashboard from the published `lumonox` wheel, seeds a demo project with a few hours of synthetic request/error history, and keeps a light live traffic trickle running so the dashboard stays in motion.

## Try it

1. Open the Space — you're **signed in automatically** (a brief "Signing you into the Lumonox demo…" screen) and land straight on the dashboard.
2. Explore: **Overview** (five-second health read), **Diagnosis** (grouped errors), **Requests** (recent traffic with correlation pivots), plus custom widgets.

Everyone shares one demo account (`demo@lumonox.dev`) and one pre-seeded project.

## Good to know

- **Data resets on restart.** The Space's free-tier filesystem is ephemeral; every cold start re-seeds from scratch. That's intentional — the demo self-cleans.
- **It's a shared demo account.** Everyone is signed in as `demo@lumonox.dev`, so settings changes are visible to other visitors until the next restart.
- **Not the product.** Lumonox is an open-source portfolio project you self-host — see the [GitHub repo](https://github.com/sintimaski/lumonox) for the SDK, backend, and dashboard, and `docs/ops/` for real deployment guides.

## How this Space is built

A few files, no monorepo checkout required:

| File | Role |
|------|------|
| `Dockerfile` | `pip install lumonox` (the wheel bundles the API, dashboard UI, and migrations) + demo runtime config |
| `patch_dashboard.py` | build-time: point the bundled UI at the same origin + inject auto sign-in for the shared demo account |
| `entrypoint.sh` | bootstrap tenant → start API → backfill history → run live trickle |
| `seed_demo.py` | `--bootstrap` (org/project/user/key), `--backfill` (recent history), `--live` (ongoing traffic) |

Maintainer setup and update instructions live in [`docs/ops/HUGGINGFACE_SPACE.md`](https://github.com/sintimaski/lumonox/blob/main/docs/ops/HUGGINGFACE_SPACE.md) in the main repo.
