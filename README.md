# GenomePipe Pro

This repository contains a GenomePipe Pro static frontend and a FastAPI Python backend. The project is configured for deployment on Vercel with the frontend served from `project/frontend` and the backend exposed through `/api/*`.

## Deployment

- Frontend: `project/frontend`
- Backend: `project/backend/app/main.py`
- Vercel configuration: `vercel.json`

## How to deploy

1. Add a GitHub remote:
   ```bash
   git remote add origin <your-github-repo-url>
   git push -u origin master
   ```
2. Import the repository in Vercel.
3. Vercel will serve the frontend and route API calls under `/api/*`.
