Render deployment steps for OSINT backend

Prerequisites:
- A Render account (https://render.com) with access to create a Web Service.
- Your GitHub repo `shadabahmed786/OSINT_tool` is connected to Render (OAuth or via deploy key).

Quick steps:
1. Sign in to Render and click "New" → "Web Service".
2. Select "Connect a repository" and choose `shadabahmed786/OSINT_tool`.
3. For "Environment", choose "Docker".
4. Set the "Dockerfile Path" to `backend/Dockerfile`.
5. Set the "Name" to `osint-backend` and plan to your preference (Free/Starter).
6. Add environment variables required by your app (for example `OLLAMA_BASE_URL` if using local Ollama, or other API keys). You can add them in Render UI under Environment.
7. Click "Create Web Service" — Render will build the Docker image and deploy it.

Notes:
- If the build fails due to missing system libraries for WeasyPrint or Playwright, Render's Docker environment will allow you to adjust the `Dockerfile` until it builds.
- After successful deployment, note the service URL (e.g., `https://osint-backend.onrender.com`).

Next: update Netlify to proxy `/api/*` to this backend URL (see Netlify steps below).
