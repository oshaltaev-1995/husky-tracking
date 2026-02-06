HUSKY TRACKING DEMO

Streamlit demo for monitoring sled dog workload, detecting workload alerts,
and generating team layouts using explainable rule-based logic.

REQUIREMENTS
- Python 3.11+ (recommended)
- Git

QUICK START (RECOMMENDED: UV)

1) Clone the repository

git clone git@github.com:oshaltaev-1995/husky-tracking.git
cd husky-tracking

2) Install uv (if not installed)

macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

Windows (PowerShell):
irm https://astral.sh/uv/install.ps1 | iex

Restart your terminal if uv is not found.

3) Create virtual environment and install dependencies

uv sync

NOTE:
The .venv directory is local and is not shared via Git.
Each user must create their own virtual environment.

4) Run the application

uv run streamlit run app/main.py

Open in browser:
http://localhost:8501

ALTERNATIVE SETUP (pip + venv)

python -m venv .venv
source .venv/bin/activate        (macOS / Linux)
.venv\Scripts\activate           (Windows)

pip install -r requirements.txt
streamlit run app/main.py

DATA

The demo can run on sample / fake data.
To use your own kennel data, prepare an Excel file with the required columns
and upload it in the app, or place it in the configured data folder
(see demo.md).

PROJECT STATUS

This is a baseline rule-based version.
ML extensions are planned as a next step.

NOTES

- Streamlit entrypoint: app/main.py
- If no public demo link is available, run the application locally
  using the instructions above.
