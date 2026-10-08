"""Decisions and follow-up work are distinct from task completion."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import NeededTask, Task, TaskStatus, get_db
from planning import Title, require, same_project

router = APIRouter()
Kind = Literal['Decision', 'Investigation', 'Action']
State = Literal['Open', 'Linked', 'Resolved', 'Dismissed']


class NeedCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: Title
    description: str | None = None
    kind: Kind = 'Action'
    source_key: str | None = Field(default=None, min_length=1, max_length=200)


class NeedUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: Title | None = None
    description: str | None = None
    kind: Kind | None = None
    state: State | None = None
    resolution: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class NeedRead(NeedCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    state: State
    resolution: str | None
    linked_task_id: int | None
    linked_task_status: TaskStatus | None = None
    revision: int
    created_at: str
    updated_at: str


class Materialize(BaseModel):
    model_config = ConfigDict(extra='forbid')
    existing_task_id: int | None = None
    assignee: str | None = None
    status: TaskStatus = TaskStatus.BACKLOG


def serialize_need(db, need):
    result = NeedRead.model_validate(need)
    if need.linked_task_id:
        linked = db.get(Task, need.linked_task_id)
        result.linked_task_status = linked.status if linked else None
    return result


def touch(need):
    need.revision += 1
    need.updated_at = datetime.now(timezone.utc).isoformat()


@router.get('/api/needed-tasks/', response_model=list[NeedRead])
def list_needs(task_id: int | None = None, project_id: int | None = None,
               epic_id: int | None = None, state: State | None = None,
               kind: Kind | None = None, open_only: bool = False,
               db: Session = Depends(get_db)):
    query = db.query(NeededTask).join(Task, Task.id == NeededTask.task_id)
    if task_id is not None:
        require(db, Task, task_id, 'Task')
        query = query.filter(NeededTask.task_id == task_id)
    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    if epic_id is not None:
        query = query.filter(Task.epic_id == epic_id)
    if kind is not None:
        query = query.filter(NeededTask.kind == kind)
    if state is not None:
        query = query.filter(NeededTask.state == state)
    if open_only:
        query = query.filter(NeededTask.state.in_(['Open', 'Linked']))
    return [serialize_need(db, n) for n in query.order_by(NeededTask.id).all()]


@router.post('/api/tasks/{task_id}/needed-tasks', response_model=NeedRead)
def create_need(task_id: int, data: NeedCreate, db: Session = Depends(get_db)):
    db.execute(text('BEGIN IMMEDIATE'))
    require(db, Task, task_id, 'Task')
    if data.source_key:
        existing = db.query(NeededTask).filter_by(task_id=task_id, source_key=data.source_key).first()
        if existing:
            # Retry must not silently reinterpret an already imported suggestion.
            if any(getattr(existing, key) != value for key, value in data.model_dump().items()):
                raise HTTPException(409, 'This source key already exists with different content')
            return serialize_need(db, existing)
    need = NeededTask(task_id=task_id, **data.model_dump())
    db.add(need)
    db.commit()
    db.refresh(need)
    return serialize_need(db, need)


@router.patch('/api/needed-tasks/{need_id}', response_model=NeedRead)
def update_need(need_id: int, data: NeedUpdate, db: Session = Depends(get_db)):
    db.execute(text('BEGIN IMMEDIATE'))
    need = require(db, NeededTask, need_id, 'Needed task')
    updates = data.model_dump(exclude_unset=True)
    expected = updates.pop('expected_revision', None)
    if expected is not None and expected != need.revision:
        raise HTTPException(409, 'Needed task changed. Reload and merge your changes.')
    for field in ('title', 'kind', 'state'):
        if field in updates and updates[field] is None:
            raise HTTPException(422, f'{field} cannot be null')
    state = updates.get('state', need.state)
    resolution = updates.get('resolution', need.resolution)
    if state in ('Resolved', 'Dismissed') and not (resolution or '').strip():
        raise HTTPException(422, 'Record an outcome before resolving or dismissing this item')
    if state == 'Linked' and not need.linked_task_id:
        raise HTTPException(422, 'Create or link a task first')
    if state == 'Open' and need.linked_task_id:
        raise HTTPException(422, 'Reopen linked work as Linked to preserve its task association')
    for field, value in updates.items():
        setattr(need, field, value)
    touch(need)
    db.commit()
    return serialize_need(db, need)


@router.post('/api/needed-tasks/{need_id}/materialize', response_model=NeedRead)
def materialize(need_id: int, data: Materialize, db: Session = Depends(get_db)):
    """Atomic, retry-safe conversion; link existing work instead of duplicating it."""
    db.execute(text('BEGIN IMMEDIATE'))
    need = require(db, NeededTask, need_id, 'Needed task')
    source = require(db, Task, need.task_id, 'Source task')
    if need.linked_task_id:
        if data.existing_task_id is not None and data.existing_task_id != need.linked_task_id:
            raise HTTPException(409, 'This item is already linked to a different task')
        return serialize_need(db, need)
    if need.state != 'Open':
        raise HTTPException(409, 'Reopen this item before creating a task')
    if data.existing_task_id is not None:
        linked = same_project(db, Task, data.existing_task_id, source.project_id, 'Linked task')
        if linked.id == source.id:
            raise HTTPException(400, 'Link a separate follow-up task, not the source itself')
    else:
        linked = Task(title=need.title, description=(need.description or '') +
                      f'\n\nFollow-up to task #{source.id}, needed item #{need.id} ({need.kind}).',
                      status=data.status, assignee=data.assignee,
                      project_id=source.project_id, epic_id=source.epic_id,
                      parent_id=source.id, sprint_id=source.sprint_id)
        db.add(linked)
        db.flush()
    need.linked_task_id = linked.id
    need.state = 'Linked'
    touch(need)
    db.commit()
    return serialize_need(db, need)
