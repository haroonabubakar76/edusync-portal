from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import create_tables
from routes import auth, students, results, schools, teachers

app = FastAPI(
    title="EduSync Portal API",
    description="Offline-first school result management system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://edusync-portal.haroonabubakar76.workers.dev",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(schools.router)
app.include_router(teachers.router)
app.include_router(students.router)
app.include_router(results.router)


@app.on_event("startup")
def startup():
    create_tables()
    print("EduSync Portal API started. Tables ready.")


@app.get("/")
def root():
    return {"message": "EduSync Portal API", "version": "1.0.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
