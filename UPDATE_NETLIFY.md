Update Netlify to proxy API requests to backend

1. In Netlify dashboard for your site, go to "Site settings" → "Build & deploy" → "Deploy contexts".
2. Alternatively, update your `netlify.toml` in the repo to set the backend host URL.

If you deployed backend to Render and received `https://osint-backend.onrender.com`, update `netlify.toml` like:

[[redirects]]
  from = "/api/*"
  to = "https://osint-backend.onrender.com/:splat"
  status = 200
  force = false

Then push the change to GitHub and Netlify will redeploy the site.

If you prefer setting the redirect in Netlify UI, go to "Redirects" and add the same rule, using the deployed backend URL.
