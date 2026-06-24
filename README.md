# EduSync Portal — MVP

Offline-first school result management system for private secondary schools in Niger State, Nigeria.

## Project Structure

```
edusync/
├── backend/                  # FastAPI Python backend
│   ├── main.py               # App entry point
│   ├── models.py             # Database tables (SQLAlchemy)
│   ├── database.py           # DB connection (SQLite dev / PostgreSQL prod)
│   ├── auth.py               # JWT + bcrypt auth utilities
│   ├── seed.py               # Bootstrap script (run once)
│   ├── requirements.txt
│   └── routes/
│       ├── auth.py           # Login, /me
│       ├── schools.py        # School, sections, classes, subjects, sessions, grading config
│       ├── teachers.py       # Teacher account management
│       ├── students.py       # Student registration, listing
│       └── results.py        # Score entry, calculation, submit, approve
│
└── frontend/                 # Plain HTML/CSS/JS — runs in any phone browser
    ├── index.html            # Login page (email + role)
    ├── teacher.html          # Teacher dashboard — subject list
    ├── scores.html           # Score entry with auto-save every 30s
    ├── principal.html        # Principal dashboard — approvals, results, students
    ├── result-card.html      # Result card viewer + print
    ├── register-student.html # Student registration form
    └── assets/
        ├── style.css         # Design system — all shared styles
        └── api.js            # API client, Auth, OfflineQueue, helpers
```

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python seed.py          # Creates DB, test school, and accounts
uvicorn main:app --reload
# API runs at http://localhost:8000
# Docs at  http://localhost:8000/docs
```

### Frontend
Open `frontend/index.html` directly in a browser, or serve with:
```bash
cd frontend
npx serve .
# Then visit http://localhost:3000
```

Point `API_BASE` in `index.html` and `assets/api.js` to your server URL.

## Login Credentials (after seed)

| Role       | Email                         | Password        |
|------------|-------------------------------|-----------------|
| Super Admin| admin@edusync.ng              | Admin@1234      |
| Principal  | principal@brightfuture.ng     | Principal@1234  |
| Teacher    | teacher@brightfuture.ng       | Teacher@1234    |

## MVP Features (Phase 1 Complete)

- [x] School setup — sections, classes, subjects, sessions, grading config
- [x] Role-based login — Super Admin / Principal / Teacher
- [x] Teacher dashboard — subject list, session info
- [x] Score entry — CA1 (20) + CA2 (20) + Exam (60) = 100
- [x] Auto-save every 30 seconds (offline queue if no internet)
- [x] Auto-calculation — total score, grade, remark
- [x] Submit results for principal approval
- [x] Principal approval workflow
- [x] Result card — full table with summary block + print
- [x] Student registration with auto-generated ID
- [x] Offline-first — OfflineQueue syncs when connection returns
- [x] JWT authentication with 7-day token cache for offline login
- [x] Audit log on all critical actions
- [x] Subscription suspend/activate (Super Admin)

## Next — Phase 2
- SQLite on-device via sql.js (full offline)
- Background sync queue with retry
- PostgreSQL cloud setup on Render/Railway
- Conflict resolution on sync

## Phase 3
- WhatsApp result delivery (WhatsApp Business API)
- SMS fallback via Termii / Africa's Talking
- Result correction workflow with parent notification

