# FEST Summer 2026 — Student Management System

Desktop Tkinter app for managing student enrollment records, grades, charts, and ID cards.
The interface uses Vanderbilt's official black, flat-gold, cream, sand, gray, sky, oak, and sage palette.

## Setup

Requires Python 3.9+ with **tkinter** (macOS: use `/usr/bin/python3` or python.org installer — Homebrew Python often lacks tkinter).

```bash
cd Python-Project-initial
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Register an account on first launch, then log in to access the sidebar dashboard.
The sidebar provides student-management, class-ranking, GPA, chart, profile, ID-card, and query tools.
The most recent record deletion can be restored with **Undo Delete** during the current app session.

## Data files

| File | Purpose |
|---|---|
| `users.csv` | Login accounts (SHA-256 hashed passwords) |
| `students.csv` | Enrollment roster (one row per student/course) |
| `gpa_scale.json` | Editable grading scale |

## Documentation

See `FEST_Project_Documentation.md` (also available as `.html` and `.pdf`).
