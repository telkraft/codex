# Promptever App

Enterprise Experience Analytics - React Frontend

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **UI Components**: shadcn/ui + Radix UI
- **Styling**: Tailwind CSS
- **State Management**: Zustand (client) + TanStack Query (server)
- **Charts**: Recharts
- **Language**: TypeScript

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  FRONTEND                        │
│  app.promptever.com (This App)                  │
├─────────────────────────────────────────────────┤
│  Next.js 14 + React 18                          │
│  ├── Dashboard (Stats, Activity, Status)        │
│  ├── Chat Interface (RAG + LLM)                 │
│  ├── Analytics (Charts, Reports)                │
│  └── Settings (Model, RAG config)               │
├─────────────────────────────────────────────────┤
│                   API                            │
├─────────────────────────────────────────────────┤
│  RAG API (FastAPI) - rag-api:8000               │
│  ├── /chat - Chat endpoint                      │
│  ├── /health - Health check                     │
│  └── /lrs/stats/* - LRS statistics              │
└─────────────────────────────────────────────────┘
```

## Project Structure

```
promptever-app/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Dashboard
│   │   ├── chat/page.tsx       # Chat interface
│   │   └── api/                # API routes
│   ├── components/
│   │   ├── ui/                 # Base components (shadcn)
│   │   ├── layout/             # Layout components
│   │   ├── dashboard/          # Dashboard widgets
│   │   └── chat/               # Chat components
│   └── lib/
│       ├── api.ts              # RAG API client
│       ├── store.ts            # Zustand stores
│       └── utils.ts            # Utilities
├── public/                     # Static assets
├── nginx/                      # Nginx config
├── docker-compose.yml
├── Dockerfile
└── deploy.sh
```

## Deployment

### Quick Start

```bash
# 1. Setup (directories, SSL, DNS check)
./deploy.sh setup

# 2. Build Docker images
./deploy.sh build

# 3. Start services
./deploy.sh start

# 4. Check status
./deploy.sh status
```

### Available Commands

```bash
./deploy.sh setup    # Initial setup
./deploy.sh build    # Build Docker images
./deploy.sh start    # Start services
./deploy.sh stop     # Stop services
./deploy.sh restart  # Restart services
./deploy.sh logs     # View logs
./deploy.sh status   # Health check
./deploy.sh dev      # Development mode
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_RAG_API_URL` | `http://rag-api:8000` | RAG API URL (client) |
| `RAG_API_INTERNAL_URL` | `http://rag-api:8000` | RAG API URL (server) |
| `NODE_ENV` | `production` | Environment |

### Network

The app connects to `xapia_net` Docker network to communicate with:
- `rag-api` (FastAPI backend)
- `rag-qdrant` (Vector database)
- MongoDB LRS

## Development

### Local Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

### Docker Development

```bash
# Start with hot reload
./deploy.sh dev
```

## Features

- 📊 **Dashboard**: Real-time stats, activity feed, system status
- 💬 **Chat**: AI-powered chat with intent detection
- 📈 **Analytics**: Interactive charts and data visualization
- ⚙️ **Settings**: Model selection, RAG configuration
- 🎨 **Modern UI**: shadcn/ui components with dark mode support

## Related Projects

- **RAG Stack**: Backend API (`/opt/rag-stack`)
- **xAPI UI Stack**: Streamlit frontend (`/opt/xapi-ui-stack`)
- **LRS Stack**: MongoDB LRS (`/opt/lrs`)

## License

Proprietary - Promptever © 2024
