# Ignatious/app.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from database import get_db, Project, Task, TaskStatus, Epic, User, init_db

app = FastAPI()

@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        # force revalidation so edited HTML/CSS/JS aren't served stale from the browser cache
        response.headers["Cache-Control"] = "no-cache"
    return response

app.mount("/static", StaticFiles(directory="static"), name="static")
init_db()

class EpicCreate(BaseModel):
    title: str
    description: Optional[str] = None
    color: Optional[str] = "#48d597"
    project_id: Optional[int] = 1

class EpicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

class EpicRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    color: str
    project_id: int

    class Config:
        from_attributes = True

class UserRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    name: str

class UserUpdate(BaseModel):
    name: str


@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

@app.get("/team")
def team_page():
    return FileResponse("static/team.html")

@app.get("/api/statuses/")
def get_statuses():
    return [status.value for status in TaskStatus]

@app.get("/api/users/", response_model=List[UserRead])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.name).all()

@app.post("/api/users/add/", response_model=UserRead)
def add_user(user: UserCreate, db: Session = Depends(get_db)):
    name = user.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    existing = db.query(User).filter(User.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    new_user = User(name=name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/api/users/{user_id}/", response_model=UserRead)
def update_user(user_id: int, update: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not update.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    existing = db.query(User).filter(User.name == update.name.strip(), User.id != user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user.name = update.name.strip()
    db.commit()
    db.refresh(user)
    return user

@app.delete("/api/users/{user_id}/")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}

from planning import router as planning_router
app.include_router(planning_router)
from followups import router as followups_router
app.include_router(followups_router)

@app.get("/api/epics/", response_model=List[EpicRead])
def get_epics(db: Session = Depends(get_db)):
    return db.query(Epic).order_by(Epic.id).all()

@app.get("/api/epics/{epic_id}", response_model=EpicRead)
def get_epic(epic_id: int, db: Session = Depends(get_db)):
    epic = db.query(Epic).filter(Epic.id == epic_id).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic

@app.post("/api/epics/", response_model=EpicRead)
def create_epic(epic_data: EpicCreate, db: Session = Depends(get_db)):
    project_id = epic_data.project_id or 1
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_epic = Epic(
        title=epic_data.title,
        description=epic_data.description,
        color=epic_data.color,
        project_id=project_id,
    )
    db.add(db_epic)
    db.commit()
    db.refresh(db_epic)
    return db_epic

@app.patch("/api/epics/{epic_id}", response_model=EpicRead)
def update_epic(epic_id: int, epic_update: EpicUpdate, db: Session = Depends(get_db)):
    epic = db.query(Epic).filter(Epic.id == epic_id).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")

    updates = epic_update.dict(exclude_unset=True)
    for field, value in updates.items():
        setattr(epic, field, value)

    db.commit()
    db.refresh(epic)
    return epic

@app.delete("/api/epics/{epic_id}")
def delete_epic(epic_id: int, db: Session = Depends(get_db)):
    epic = db.query(Epic).filter(Epic.id == epic_id).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    db.query(Task).filter(Task.epic_id == epic_id).update({"epic_id": None})
    db.delete(epic)
    db.commit()
    return {"detail": "Epic deleted"}
