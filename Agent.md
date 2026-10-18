## 1. Deployment Configuration

### Target Space
- **Profile:** `Leon4gr45`
- **Space:** `openweb-v2-staging`
- **Full Identifier:** `Leon4gr45/openweb-v2-staging`
- **Frontend Port:** `7860` (mandatory for all Hugging Face Spaces)

### Deployment Method
Choose the correct SDK based on the app type based on the codebase language:

- **Gradio SDK** — for Gradio applications
- **Streamlit SDK** — for Streamlit applications
- **Docker SDK** — for all other applications (recommended default for flexibility)

### HF Token
- The environment variable **`HF_TOKEN` will always be provided at execution time**.
- Never hardcode the token. Always read it from the environment.
- All monitoring and log‑streaming commands rely on `HF_TOKEN`.

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
### /api/stats
- Method: GET
- Purpose: Stats

### /api/videos
- Method: GET
- Purpose: Videos

### /api/videos/{video_id}
- Method: GET
- Purpose: Video

### /api/search
- Method: GET
- Purpose: Search

### /api/search/image
- Method: POST
- Purpose: Search Image

### /api/compare
- Method: GET
- Purpose: Compare

### /api/compare-views
- Method: GET
- Purpose: Compare Views

### /api/ask
- Method: POST
- Purpose: Ask

### /api/answers
- Method: GET
- Purpose: Answers

### /api/experiments
- Method: GET
- Purpose: Experiments

### /api/health
- Method: GET
- Purpose: Health

### /api/providers
- Method: GET
- Purpose: Providers

### /api/config
- Method: GET
- Purpose: Get Config

### /api/config/template
- Method: GET
- Purpose: Template

### /api/config/profiles
- Method: GET
- Purpose: Profiles

### /api/config/validate
- Method: POST
- Purpose: Validate Config

### /api/config/apply
- Method: POST
- Purpose: Apply Config

### /api/config/rollback
- Method: POST
- Purpose: Rollback

### /api/providers/{pid}/test
- Method: POST
- Purpose: Test Provider

### /api/routing/dry-run
- Method: POST
- Purpose: Dry Run

### /api/live/sessions
- Method: POST
- Purpose: Create Session

### /api/live/sessions/{sid}
- Method: DELETE
- Purpose: Delete Session

### /api/live/sessions/{sid}/frames
- Method: POST
- Purpose: Analyze Frame

### /api/live/sessions/{sid}/events
- Method: GET
- Purpose: Events

### /api/live/sessions/{sid}/transcribe
- Method: POST
- Purpose: Transcribe

### /api/live/sessions/{sid}/guidance
- Method: POST
- Purpose: Guidance

### /api/live/sessions/{sid}/task
- Method: PUT
- Purpose: Task State

### /api/access
- Method: POST
- Purpose: Media Access

### /api/access
- Method: DELETE
- Purpose: Clear Media Access

### /api/admin/backup-status
- Method: GET
- Purpose: Backup Status

### /api/admin/backup
- Method: POST
- Purpose: Backup Trigger

### /api/admin/backup/recovery-test
- Method: POST
- Purpose: Backup Recovery Test

### /api/live/sessions/{sid}/routing
- Method: PUT
- Purpose: Session Routing

### /api/demo/videos
- Method: GET
- Purpose: Library

### /api/demo/videos/{vid}
- Method: GET
- Purpose: Detail

### /api/demo/stats
- Method: GET
- Purpose: Stats

### /api/demo/search
- Method: GET
- Purpose: Search

### /api/demo/ask
- Method: POST
- Purpose: Ask

### /api/demo/answers
- Method: GET
- Purpose: History

### /api/demo/compare
- Method: GET
- Purpose: Compare

### /api/demo/compare-views
- Method: GET
- Purpose: Compare Views

### /api/demo/experiments
- Method: GET
- Purpose: Experiments

### /api/jobs
- Method: GET
- Purpose: Jobs

### /api/ingest
- Method: POST
- Purpose: Upload

### /api/jobs/{jid}
- Method: POST
- Purpose: Action

All endpoints listed here **must** appear in `/api-docs`.

---

## 3. Deployment Workflow

### Standard Deployment Command
Upload to the private staging space using the Python script provided in `docs/deployment-hf.md`:

```python
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ['HF_TOKEN'])
repo = 'Leon4gr45/openweb-v2-staging'
api.upload_folder(
    repo_id=repo, repo_type='space', folder_path='.',
    allow_patterns=['README.md', 'Dockerfile', 'requirements-runtime.txt',
                    'vrag/**', 'config/**', 'scripts/cloud-start.py', 'web/**'],
    ignore_patterns=['**/.env*', '**/*.pem', '**/*.key', '**/*.agekey', '**/*.age',
                     '**/__pycache__/**', '**/node_modules/**', '**/.next/**',
                     'web/tests/**', 'web/test-results/**', 'web/playwright-report/**'],
    commit_message='Stage reviewed Video RAG Visual Mentor v2'
)
```

Scan build and run logs using the Hugging Face API or UI to verify the deployment.
