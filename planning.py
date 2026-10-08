"""Monthly planning and recursive task boards. Children inherit their branch's sprint."""
from collections import defaultdict
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Epic, Project, Sprint, Subtask, Task, TaskStatus, NeededTask, get_db

router = APIRouter()
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


ResolutionState = Literal["Unresolved", "Partially resolved", "Resolved", "Deferred"]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: str | None = None
    resolution_state: ResolutionState = "Unresolved"
    review_notes: str | None = None
    title: Title
    description: str | None = None
    assignee: str | None = None
    status: TaskStatus = TaskStatus.BACKLOG
    project_id: int = 1
    epic_id: int | None = None
    parent_id: int | None = None
    sprint_id: int | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: str | None = None
    resolution_state: ResolutionState | None = None
    review_notes: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    title: Title | None = None
    description: str | None = None
    assignee: str | None = None
    status: TaskStatus | None = None
    epic_id: int | None = None
    parent_id: int | None = None
    sprint_id: int | None = None


class TaskRead(TaskCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    revision: int = 1
    needed_task_count: int = 0
    open_needed_task_count: int = 0
    child_count: int = 0
    completed_children: int = 0
    descendant_count: int = 0
    completed_descendants: int = 0


class SprintCreate(BaseModel):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    goal: str = Field(default='', max_length=3000)
    project_id: int = 1

    @field_validator('month')
    @classmethod
    def valid_month(cls, value):
        date.fromisoformat(value + '-01')
        return value


class SprintUpdate(BaseModel):
    goal: str = Field(max_length=3000)


class SprintRead(SprintCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_count: int = 0
    completed_tasks: int = 0


class SprintAssignment(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=500)
    sprint_id: int | None = None


def require(db, model, object_id, name):
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(404, f'{name} not found')
    return obj


def same_project(db, model, object_id, project_id, name):
    if object_id is None:
        return None
    obj = require(db, model, object_id, name)
    if obj.project_id != project_id:
        raise HTTPException(400, f'{name} must belong to the same project')
    return obj


def child_map(tasks):
    children = defaultdict(list)
    for task in tasks:
        children[task.parent_id].append(task)
    return children


def branch(task, children):
    """Iterative traversal supports arbitrary depth without Python recursion limits."""
    stack, seen, result = [task], set(), []
    while stack:
        current = stack.pop()
        if current.id in seen:
            raise HTTPException(409, 'Task hierarchy contains a cycle')
        seen.add(current.id)
        result.append(current)
        stack.extend(children[current.id])
    return result


def serialize(task, children, needs=None):
    result = TaskRead.model_validate(task)
    related = (needs or {}).get(task.id, [])
    result.needed_task_count = len(related)
    result.open_needed_task_count = sum(n.state in ("Open", "Linked") for n in related)
    direct = children[task.id]
    descendants = branch(task, children)[1:]
    result.child_count = len(direct)
    result.completed_children = sum(t.status == TaskStatus.COMPLETE for t in direct)
    result.descendant_count = len(descendants)
    result.completed_descendants = sum(t.status == TaskStatus.COMPLETE for t in descendants)
    return result


def needs_map(db):
    result = defaultdict(list)
    for need in db.query(NeededTask).all():
        result[need.task_id].append(need)
    return result


def read_task(db, task):
    return serialize(task, child_map(db.query(Task).filter(Task.project_id == task.project_id).all()), needs_map(db))


def check_resolution(state, resolution):
    if state != 'Unresolved' and not (resolution or '').strip():
        raise HTTPException(422, 'Explain the decision or deferral in Resolution')



@router.get('/api/sprints/', response_model=list[SprintRead])
def list_sprints(project_id: int = 1, db: Session = Depends(get_db)):
    roots = db.query(Task).filter(Task.project_id == project_id, Task.parent_id.is_(None)).all()
    result = []
    for sprint in db.query(Sprint).filter(Sprint.project_id == project_id).order_by(Sprint.month).all():
        row = SprintRead.model_validate(sprint)
        tasks = [t for t in roots if t.sprint_id == sprint.id]
        row.task_count = len(tasks)
        row.completed_tasks = sum(t.status == TaskStatus.COMPLETE for t in tasks)
        result.append(row)
    return result


@router.post('/api/sprints/', response_model=SprintRead, status_code=201)
def create_sprint(data: SprintCreate, db: Session = Depends(get_db)):
    require(db, Project, data.project_id, 'Project')
    sprint = Sprint(**data.model_dump())
    db.add(sprint)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A sprint already exists for this month')
    db.refresh(sprint)
    return sprint


@router.patch('/api/sprints/{sprint_id}', response_model=SprintRead)
def update_sprint(sprint_id: int, data: SprintUpdate, db: Session = Depends(get_db)):
    sprint = require(db, Sprint, sprint_id, 'Sprint')
    sprint.goal = data.goal
    db.commit()
    return next(s for s in list_sprints(sprint.project_id, db) if s.id == sprint_id)


@router.delete('/api/sprints/{sprint_id}')
def delete_sprint(sprint_id: int, db: Session = Depends(get_db)):
    db.execute(text('BEGIN IMMEDIATE'))
    sprint = require(db, Sprint, sprint_id, 'Sprint')
    if db.query(Task).filter(Task.sprint_id == sprint_id).first():
        raise HTTPException(409, 'Move the tasks out of this sprint before deleting it')
    db.delete(sprint)
    db.commit()
    return {'detail': 'Sprint deleted'}


@router.get('/api/tasks/', response_model=list[TaskRead])
def get_tasks(status: TaskStatus | None = None, epic_id: int | None = None,
              sprint_id: int | None = None, unscheduled: bool = False,
              parent_id: int | None = None, roots_only: bool = False,
              project_id: int | None = None, resolution_state: ResolutionState | None = None,
              needs_attention: bool = False, db: Session = Depends(get_db)):
    if unscheduled and sprint_id is not None:
        raise HTTPException(400, 'Choose a sprint or unscheduled, not both')
    if roots_only and parent_id is not None:
        raise HTTPException(400, 'Choose a parent board or root tasks, not both')
    query = db.query(Task)
    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    all_tasks = query.order_by(Task.id).all()
    children = child_map(all_tasks)
    needs = needs_map(db)
    return [serialize(t, children, needs) for t in all_tasks
            if (resolution_state is None or t.resolution_state == resolution_state)
            and (not needs_attention or any(n.state in ("Open", "Linked") for n in needs[t.id]))
            and (status is None or t.status == status)
            and (epic_id is None or t.epic_id == epic_id)
            and (sprint_id is None or t.sprint_id == sprint_id)
            and (not unscheduled or t.sprint_id is None)
            and (parent_id is None or t.parent_id == parent_id)
            and (not roots_only or t.parent_id is None)]


@router.post('/api/tasks/assign-sprint')
def assign_sprint(data: SprintAssignment, db: Session = Depends(get_db)):
    db.execute(text('BEGIN IMMEDIATE'))
    roots = [require(db, Task, i, 'Task') for i in set(data.task_ids)]
    for root in roots:
        if root.parent_id is not None:
            raise HTTPException(400, 'Assign the top-level task; subtasks inherit its sprint')
        same_project(db, Sprint, data.sprint_id, root.project_id, 'Sprint')
    children = child_map(db.query(Task).all())
    changed = []
    for root in roots:
        for task in branch(root, children):
            task.sprint_id = data.sprint_id
            task.revision += 1
            changed.append(task.id)
    db.commit()
    return {'updated_task_ids': sorted(changed)}


@router.get('/api/tasks/{task_id}/ancestors')
def ancestors(task_id: int, db: Session = Depends(get_db)):
    task = require(db, Task, task_id, 'Task')
    trail, seen = [], {task_id}
    while task.parent_id is not None:
        task = require(db, Task, task.parent_id, 'Parent task')
        if task.id in seen:
            raise HTTPException(409, 'Task hierarchy contains a cycle')
        seen.add(task.id)
        trail.append({'id': task.id, 'title': task.title})
    return list(reversed(trail))


@router.get('/api/tasks/{task_id}', response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return read_task(db, require(db, Task, task_id, 'Task'))


@router.post('/api/tasks/', response_model=TaskRead)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    db.execute(text('BEGIN IMMEDIATE'))
    require(db, Project, data.project_id, 'Project')
    same_project(db, Epic, data.epic_id, data.project_id, 'Epic')
    parent = same_project(db, Task, data.parent_id, data.project_id, 'Parent task')
    values = data.model_dump()
    if parent:
        if 'sprint_id' in data.model_fields_set and data.sprint_id != parent.sprint_id:
            raise HTTPException(400, 'Subtasks inherit their parent sprint')
        values['sprint_id'] = parent.sprint_id
        if 'epic_id' not in data.model_fields_set:
            values['epic_id'] = parent.epic_id
    same_project(db, Sprint, values['sprint_id'], data.project_id, 'Sprint')
    check_resolution(data.resolution_state, data.resolution)
    task = Task(**values)
    db.add(task)
    db.commit()
    db.refresh(task)
    return read_task(db, task)


@router.patch('/api/tasks/{task_id}', response_model=TaskRead)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    # Serialize hierarchy mutations, so concurrent moves cannot introduce cycles
    # or leave a newly created child in a different sprint from its parent.
    db.execute(text('BEGIN IMMEDIATE'))
    task = require(db, Task, task_id, 'Task')
    updates = data.model_dump(exclude_unset=True)
    expected = updates.pop('expected_revision', None)
    if expected is not None and expected != task.revision:
        raise HTTPException(409, 'Task changed since you opened it. Reload and merge your changes.')
    for field in ('title', 'status', 'resolution_state'):
        if field in updates and updates[field] is None:
            raise HTTPException(422, f'{field} cannot be null')
    check_resolution(updates.get('resolution_state', task.resolution_state), updates.get('resolution', task.resolution))
    if 'epic_id' in updates:
        same_project(db, Epic, updates['epic_id'], task.project_id, 'Epic')
    parent_id = updates.get('parent_id', task.parent_id)
    parent = same_project(db, Task, parent_id, task.project_id, 'Parent task')
    children = child_map(db.query(Task).filter(Task.project_id == task.project_id).all())
    subtree = branch(task, children)
    if parent and parent.id in {t.id for t in subtree}:
        raise HTTPException(400, 'A task cannot be placed inside itself or a descendant')
    sprint_id = updates.get('sprint_id', task.sprint_id)
    if parent:
        if 'sprint_id' in updates and sprint_id != parent.sprint_id:
            raise HTTPException(400, 'Subtasks inherit their parent sprint')
        sprint_id = parent.sprint_id
    same_project(db, Sprint, sprint_id, task.project_id, 'Sprint')
    for field, value in updates.items():
        if field != 'sprint_id':
            setattr(task, field, value)
    task.revision += 1
    for descendant in subtree:
        if descendant.sprint_id != sprint_id and descendant.id != task.id:
            descendant.revision += 1
        descendant.sprint_id = sprint_id
    db.commit()
    return read_task(db, task)


@router.delete('/api/tasks/{task_id}')
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db.execute(text('BEGIN IMMEDIATE'))
    task = require(db, Task, task_id, 'Task')
    if db.query(Task).filter(Task.parent_id == task_id).first():
        raise HTTPException(409, 'This task has subtasks. Move or delete them first.')
    if db.query(NeededTask).filter((NeededTask.task_id == task_id) | (NeededTask.linked_task_id == task_id)).first():
        raise HTTPException(409, 'This task has decision/follow-up records. Keep it for the audit trail.')
    # Do not resurrect a migrated legacy checklist item on the next startup.
    if task.legacy_subtask_id is not None:
        db.query(Subtask).filter(Subtask.id == task.legacy_subtask_id).delete()
    db.delete(task)
    db.commit()
    return {'detail': 'Task deleted'}
