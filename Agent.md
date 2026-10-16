## 1. Deployment Configuration

### Target Space
- **Profile:** `Leon4gr45`
- **Space:** `openweb`
- **Full Identifier:** `Leon4gr45/openweb`
- **Frontend Port:** `7860` (mandatory for all Hugging Face Spaces)

### Deployment Method
Choose the correct SDK based on the app type based on the codebase language:

- **Gradio SDK** — for Gradio applications
- **Streamlit SDK** — for Streamlit applications
- **Docker SDK** — for all other applications (recommended default for flexibility)

### HF Token
- The environment variable **`hf_your_token_here` will always be provided at execution time**.
- Never hardcode the token. Always read it from the environment.
- All monitoring and log‑streaming commands rely on `hf_your_token_here`.

### Required Files
- `Dockerfile` (or `app.py` for Gradio/Streamlit SDKs)
- `README.md` with Hugging Face YAML frontmatter:
  ```yaml
  ---
  title: <APP NAME>
  sdk: docker | gradio | streamlit
  app_port: 7860
  ---
  ```
- `.hfignore` to exclude unnecessary files
- This `Agent.md` file (must be committed before deployment)

---

## 2. API Exposure and Documentation

### Mandatory Endpoints
Every deployment **must** expose:

- **`/health`**
  - Returns HTTP 200 when the app is ready.
  - Required for Hugging Face to transition the Space from *starting* → *running*.

- **`/api-docs`**
  - Documents **all** available API endpoints.
  - Must be reachable at:
    `https://HF_PROFILE-openweb.hf.space/api-docs`

### Functional Endpoints
Document each endpoint here. For every endpoint, include:

- **Method:** GET/POST/PUT/DELETE
- **Path:** `/predict`, `/generate`, `/upload`, etc.
- **Purpose:** What the endpoint does
- **Request Example:** JSON or query parameters
- **Response Example:** JSON schema or example payload

### /api/stats
- Method: GET
- Purpose: Get index statistics and manifest details
- Request: {}
- Response: {"views_built": {}, "limitations": "...", "dims": [768], "views": ["text"], "view_descriptions": {}, "storage": [], "total_duration_s": 0}

### /api/videos
- Method: GET
- Purpose: List all indexed videos
- Request: {}
- Response: [{"video_id": "xyz", "title": "...", "duration": 120}]

### /api/videos/{video_id}
- Method: GET
- Purpose: Get details, segments and transcripts for a specific video
- Request: video_id path param
- Response: {"video_id": "xyz", "title": "...", "duration": 120, "segments": [], "transcript": [], "transcripts": {}}

### /api/search
- Method: GET
- Purpose: Search across embedded segments
- Request: `?q=query&view=text&dim=768&k=10`
- Response: {"query": "...", "view": "...", "dim": 768, "hits": [], "timing": {}}

### /api/compare
- Method: GET
- Purpose: Compare MRL dims for a specific view
- Request: `?q=query&view=text&k=5`
- Response: {"query": "...", "view": "...", "k": 5, "columns": []}

### /api/compare-views
- Method: GET
- Purpose: Compare across views for a specific dim
- Request: `?q=query&dim=768&k=5`
- Response: {"query": "...", "dim": 768, "k": 5, "columns": []}

### /api/ask
- Method: POST
- Purpose: Ask a question based on retrieved clips
- Request: {"question": "...", "view": "text", "dim": 768, "k": 4, "use_video": true, "use_audio": false}
- Response: {"answer": "...", "clips": []}

### /api/answers
- Method: GET
- Purpose: List answer history
- Request: `?limit=50`
- Response: [{"question": "...", "answer": "...", "clips": []}]

### /api/experiments
- Method: GET
- Purpose: Get experiment results
- Request: `?transcripts=whisper` (optional)
- Response: {"variants": [], "per_query": []}

All endpoints listed here **must** appear in `/api-docs`.

---

## 3. Deployment Workflow

Precondition: Use the huggingface hub cli hf to check that the space is empty of files nd delete any which are still in there and not belonging to the project to be uploaded

### Standard Deployment Command
After any code change, run:

```bash
hf upload Leon4gr45/openweb --repo-type=space
---

Scan build and run logs # Get build logs (SSE) curl -N
-H "Authorization: Bearer hf_your_token_here"
"https://huggingface.co/api/spaces/Leon4gr45/openweb/logs/build"

Get run logs (SSE) once the build logs succeed
curl -N
-H "Authorization: Bearer hf_your_token_here"
"https://huggingface.co/api/spaces/Leon4gr45/openweb/logs/run"

after 300 seconds to see if the deployment has been successful, and if not, fix the errors of deployment, and redeploy and monitor in a cycle until the space is running and reacts to the api endpoints you created.
