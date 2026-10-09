# Raid Outside

Raid Outside is a mobile-first co-op adventure prototype for turning a short break into an outdoor quest. Create a mission, invite a party, explore a public place, and unlock a story ending and badge.

## Features

- Solo demo flow for creating, briefing, playing, and completing a raid
- Mystery, nature, silly, and fantasy mission vibes; 15, 30, or 45 minute sessions
- Optional OpenStreetMap place lookup for a user-entered landmark
- Mission generation through a configurable, locally hosted open-weight model
- Hand-written mission fallback when the model is disabled or unavailable
- Local browser storage for settings and collected badges

## Run locally

Requirements: Node.js and npm.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. To create a production build, run `npm run build`; to preview it, run `npm run preview`.

## Connect a local open model

The app sends mission-generation requests from the browser to an OpenAI-compatible chat-completions endpoint. For example, run a local inference server with Ollama, llama.cpp, LM Studio, or another compatible runtime, then configure **Settings** in the app with its base URL and model name.

For Vite defaults, copy `.env.example` to `.env.local` and set:

```env
VITE_OPENAI_BASE_URL=http://localhost:11434/v1
VITE_OPENAI_MODEL_NAME=your-local-model-name
VITE_OPENAI_API_KEY=ollama
```

Restart Vite after changing environment variables. The model must support chat completions and JSON response formatting. The API key is stored in browser settings and is not a secret-management mechanism; use a local-only endpoint and do not enter a key for a hosted service if you want requests to stay on your device. A model download may require internet access, but inference can be local after the model is installed.

If the endpoint is unavailable or returns an invalid mission, the app uses a hand-written fallback mission.

## Location data and safety

The app sends the landmark text entered by the player to OpenStreetMap's Nominatim service for place lookup. It does not request GPS. Completed raids and badges, including their place names, are saved in the browser's local storage; the prototype does not send this history to a Raid Outside server. The lookup can identify a mapped place and its broad OSM classification; it does **not** verify that benches, trees, paths, or other small features are currently present or accessible. Treat map results as suggestions, check the place yourself, and only play in public areas where you are allowed to be.

Mission prompts are intended to be observational and low-risk. Stop somewhere safe before reading or interacting with the app. Do not enter private or restricted property, approach traffic, disturb wildlife, climb, or collect items.

## Tech stack

React, TypeScript, Vite, Tailwind CSS, and Lucide icons. The frontend prototype uses browser local storage and does not currently provide a hosted multiplayer backend; party codes are for the demo flow.

## OpenStreetMap attribution

Place search uses OpenStreetMap data via Nominatim. Map data is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
