# Tournament Engine

Tournament Engine is a web app for creating and running bracket tournaments. Organizers of esports and community events usually track brackets in spreadsheets or on paper, which gets messy fast, especially with Swiss stages where pairings depend on every team's record. Tournament Engine handles the bookkeeping so the organizer can focus on running the event, and gives players and spectators a live public page to follow results.

> **Status:** Planning stage (Unit 11). This README describes the planned app and will be updated as features are built.

## Planned Features

- **Single-elimination brackets** with automatic seeding placement and byes
- **Swiss stages** with record-based pairings, rematch avoidance, and Buchholz tiebreakers
- **Score reporting** that automatically advances winners
- **Live public tournament page** that updates as results come in (Server-Sent Events)
- **Public or private tournaments**, shareable with a link or QR code
- **Best-of-1/3/5 series** support

Organizers manage a tournament through a private admin link, so no account is needed to run an event.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React (JavaScript) |
| Backend | Python, FastAPI |
| Database | PostgreSQL (hosted on Neon free plan) |
| Live updates | Server-Sent Events (SSE) |
| Containerization | Docker |
| CI/CD | GitHub Actions |
| Hosting | Google Cloud Run (via Artifact Registry) |
| Project management | Jira + Confluence |
| AI tools (development only) | GitHub Copilot, Claude Code |

### Why these choices

- **FastAPI** handles async streaming well, which SSE needs, and it generates API docs automatically.
- **PostgreSQL** fits the data: matches reference teams and feed winners into later matches, and Swiss standings are aggregate queries that SQL handles well.
- **Neon** has a permanent free plan, and its compute scales to zero when idle and wakes back up on the next request, so the demo link keeps working without paying for an always-on database.
- **Cloud Run** runs the Docker container directly and has a free tier.

## Planned Project Structure

```
Tournament-Engine/
├── backend/          # FastAPI app, bracket + Swiss logic, tests
├── frontend/         # React app
├── .github/workflows # CI/CD pipelines
├── Dockerfile
└── README.md
```

## Getting Started

Setup instructions will be added once the MVP is built (Unit 12). The planned flow is:

1. Clone the repo: `git clone https://github.com/JDD310/Tournament-Engine.git`
2. Copy the environment file and add a Postgres connection string: `cp .env.example .env`
3. Build and run with Docker: `docker build -t tournament-engine .` then `docker run -p 8080:8080 --env-file .env tournament-engine`

## Project Management

- **Jira:** [Tournament-Engine board](https://jdd310.atlassian.net/jira/software/projects/TE/boards/2) (epics, user stories, and sprints)
- **Confluence:** [Project Overview](https://jdd310.atlassian.net/wiki/spaces/TE/pages/229377/Project+Overview) (proposal, tech decisions, and reasoning)

| Sprint | Dates | Goal |
|---|---|---|
| Sprint 1: MVP Core | Nov 14 – Nov 22 | Single-elimination tournament working end to end, first deploy to Cloud Run |
| Sprint 2: Swiss & Production Ready | Nov 23 – Dec 6 | Swiss pairings and standings, automated tests, automatic deployment |
| Sprint 3: Polish & Launch | Dec 7 – Dec 13 | Live updates, sharing/QR codes, series play, final documentation |

## AI Assistance

This project is built with AI-assisted development. The app itself has no AI features. AI tools are used during development for:

- Generating boilerplate (FastAPI routes, React components)
- Writing and expanding unit tests
- Generating Dockerfile and GitHub Actions YAML
- Debugging and learning new APIs (SSE, Cloud Run deployment)

Specific examples of how each tool helped will be documented here as features are completed.

## License

MIT, see [LICENSE](LICENSE).
