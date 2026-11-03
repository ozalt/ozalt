# Maintenance

This repository is the source for the profile README and the work log at
<https://ozalt.github.io/ozalt/>.

## Local preview

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build.py --render
.venv/bin/python scripts/serve.py
```

Open <http://127.0.0.1:8000/> for the work log and
<http://127.0.0.1:8000/lab/> for the Evidence Lab explorer.

`scripts/build.py --cached --render` reuses `docs/data.json` and skips GitHub
API calls, which is useful when iterating on the design.

## What to edit

| File | Purpose |
| --- | --- |
| `scripts/profile.json` | Headline, current role, focus areas, credentials, project titles, summaries, and categories. |
| `scripts/template.html` | The work-log page (HTML/CSS/JS). |
| `scripts/vendor_lab.py` | Refreshes the vendored Evidence Lab explorer from `ozalt/evidence-lab`. |
| `README.md` | The profile README shown on <https://github.com/ozalt>. |

## GitHub setup (one time)

1. Create a **public** repository named `ozalt` with no README, `.gitignore`,
   or license.
2. Push this repository to `git@github.com:ozalt/ozalt.git`.
3. Open **Settings → Pages → Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/docs**
4. Open **Actions → Refresh profile monitor → Run workflow** once. After that the
   schedule at 04:17 UTC refreshes the data, the page, and the animated preview
   daily.

The workflow commits with `GITHUB_TOKEN`, so it needs **Read and write
permissions** under **Settings → Actions → General → Workflow permissions**.
Set it to “Read and write permissions” if it isn't already.

## Adding a project

Add an entry to `scripts/profile.json` using the repository name as the key.
If you omit `title`, `summary`, or `category`, the builder falls back to the
GitHub description and a generic `PROJECT` label.

New public repositories also appear automatically; configured projects simply
keep their order and copy.
