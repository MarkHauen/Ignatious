from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Enum, Boolean, UniqueConstraint, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, timezone
import enum
import os

Base = declarative_base()

class TaskStatus(enum.Enum):
    BACKLOG = "Backlog"
    READY_FOR_ACTION = "Ready for Action"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    COMPLETE = "Complete"

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    def __repr__(self):
        return f"<User id={self.id} name={self.name}>"

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    tasks = relationship("Task", back_populates="project")
    epics = relationship("Epic", back_populates="project")

class Epic(Base):
    __tablename__ = 'epics'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    color = Column(String, default="#48d597")

    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project", back_populates="epics")

    stories = relationship("Task", back_populates="epic")

class Sprint(Base):
    __tablename__ = 'sprints'
    __table_args__ = (UniqueConstraint('project_id', 'month', name='uq_sprint_month'),)

    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False)
    goal = Column(String, nullable=False, default='')
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(Enum(TaskStatus), default=TaskStatus.BACKLOG, nullable=False)
    assignee = Column(String)
    resolution = Column(String)
    resolution_state = Column(String, nullable=False, default="Unresolved", server_default="Unresolved")
    review_notes = Column(String)
    revision = Column(Integer, nullable=False, default=1, server_default="1")

    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project", back_populates="tasks")

    epic_id = Column(Integer, ForeignKey('epics.id'), nullable=True)
    epic = relationship("Epic", back_populates="stories")

    parent_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    sprint_id = Column(Integer, ForeignKey('sprints.id'), nullable=True)
    legacy_subtask_id = Column(Integer, nullable=True, unique=True)

    subtasks = relationship("Subtask", back_populates="task")

class NeededTask(Base):
    __tablename__ = 'needed_tasks'
    __table_args__ = (UniqueConstraint('task_id', 'source_key', name='uq_needed_source'),)

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    kind = Column(String, nullable=False, default='Action')
    state = Column(String, nullable=False, default='Open')
    resolution = Column(String)
    linked_task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True, index=True)
    source_key = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())

class Subtask(Base):
    __tablename__ = 'subtasks'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    is_complete = Column(Boolean, default=False)

    task_id = Column(Integer, ForeignKey('tasks.id'))
    task = relationship("Task", back_populates="subtasks")

DATABASE_URL = os.environ.get('IGNATIOUS_DATABASE_URL', "sqlite:///./ignatious.db")
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False}, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    db = SessionLocal()
    try:
        if db.query(Project).count() == 0:
            db.add(Project(name="Default Project"))
        if db.query(User).count() == 0:
            db.add_all([
                User(name="Alice"),
                User(name="Bob"),
                User(name="Clara"),
                User(name="Jordan")
            ])
        db.commit()
    finally:
        db.close()


def _migrate_schema():
    """Add columns introduced after the initial release to an existing sqlite file."""
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    additions = {
        'resolution': 'TEXT',
        'resolution_state': "TEXT NOT NULL DEFAULT 'Unresolved'",
        'review_notes': 'TEXT',
        'revision': 'INTEGER NOT NULL DEFAULT 1',
        'epic_id': 'INTEGER REFERENCES epics(id)',
        'parent_id': 'INTEGER REFERENCES tasks(id)',
        'sprint_id': 'INTEGER REFERENCES sprints(id)',
        'legacy_subtask_id': 'INTEGER',
    }
    with engine.begin() as connection:
        for column, definition in additions.items():
            if column not in task_columns:
                connection.execute(text(f'ALTER TABLE tasks ADD COLUMN {column} {definition}'))
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_tasks_parent ON tasks(parent_id)'))
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_tasks_sprint ON tasks(sprint_id)'))
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_tasks_legacy_subtask ON tasks(legacy_subtask_id)'))
        # Preserve old checklist records as full nested tasks, once per original ID.
        connection.execute(text('''
            INSERT INTO tasks (title, status, project_id, epic_id, parent_id, sprint_id, legacy_subtask_id)
            SELECT s.title, CASE WHEN s.is_complete THEN 'COMPLETE' ELSE 'BACKLOG' END,
                   p.project_id, p.epic_id, p.id, p.sprint_id, s.id
            FROM subtasks s JOIN tasks p ON p.id = s.task_id
            WHERE NOT EXISTS (SELECT 1 FROM tasks t WHERE t.legacy_subtask_id = s.id)
        '''))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
