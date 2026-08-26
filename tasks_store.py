"""
Task board persistence. tasks.json lives in PROJECT_DIR alongside projects.json.

Schema:
{
  "tasks": [
    {
      "id": str,                    # uuid4
      "project_id": str,            # matches projects.json id, or "none"
      "title": str,
      "status": "not_started" | "in_progress" | "done",
      "assignee": str | null,
      "deadline": str | null,
      "priority": "high" | "medium" | "low" | null,
      "parent_id": str | null,      # null = top-level task
      "source": "meeting" | "manual",
      "meeting_path": str | null,
      "meeting_action_index": int | null,
      "created_at": str             # ISO datetime
    }
  ],
  "migrated": bool
}
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_DIR

log = logging.getLogger(__name__)

TASKS_FILE = PROJECT_DIR / 'tasks.json'


def _load() -> dict:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'tasks': [], 'migrated': False}


def _save(data: dict) -> None:
    TASKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get_tasks() -> list:
    return _load().get('tasks', [])


def create_task(
    project_id: str,
    title: str,
    parent_id: str | None = None,
    status: str = 'not_started',
    assignee: str | None = None,
    deadline: str | None = None,
    priority: str | None = None,
    source: str = 'manual',
    meeting_path: str | None = None,
    meeting_action_index: int | None = None,
    claude_executable: bool = False,
) -> dict:
    data = _load()
    task = {
        'id': str(uuid.uuid4()),
        'project_id': project_id or 'none',
        'title': title,
        'status': status,
        'assignee': assignee,
        'deadline': deadline,
        'priority': priority,
        'parent_id': parent_id,
        'source': source,
        'meeting_path': meeting_path,
        'meeting_action_index': meeting_action_index,
        'claude_executable': claude_executable,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    data['tasks'].append(task)
    _save(data)
    return task


def update_task(task_id: str, fields: dict) -> bool:
    allowed = {'title', 'status', 'assignee', 'deadline', 'priority', 'parent_id', 'project_id'}
    data = _load()
    for task in data['tasks']:
        if task['id'] == task_id:
            for k, v in fields.items():
                if k in allowed:
                    task[k] = v
            _save(data)
            return True
    return False


def delete_task(task_id: str) -> bool:
    """Deletes the task and all its direct sub-items."""
    data = _load()
    before = len(data['tasks'])
    data['tasks'] = [t for t in data['tasks']
                     if t['id'] != task_id and t.get('parent_id') != task_id]
    if len(data['tasks']) < before:
        _save(data)
        return True
    return False


def migrate_panel_actions() -> int:
    """One-time import of all in_panel=True actions from meeting JSONs into tasks.json.
    Safe to call on every startup — no-op after first run."""
    data = _load()
    if data.get('migrated'):
        return 0

    from config import MINUTES_DIR

    seen = {
        (t.get('meeting_path'), t.get('meeting_action_index'))
        for t in data['tasks']
    }
    count = 0

    for actions_json in sorted(MINUTES_DIR.glob('*_actions.json')):
        try:
            adata = json.loads(actions_json.read_text(encoding='utf-8'))
            meeting_path = adata.get('minutes', str(actions_json))
            project_id = adata.get('project_id') or 'none'
            for a in adata.get('actions', []):
                if not a.get('in_panel'):
                    continue
                key = (meeting_path, a['index'])
                if key in seen:
                    continue
                task = {
                    'id': str(uuid.uuid4()),
                    'project_id': project_id,
                    'title': a.get('title', ''),
                    'status': 'done' if a.get('executed') else 'not_started',
                    'assignee': a.get('assignee'),
                    'deadline': a.get('deadline'),
                    'priority': None,
                    'parent_id': None,
                    'source': 'meeting',
                    'meeting_path': meeting_path,
                    'meeting_action_index': a['index'],
                    'claude_executable': bool(a.get('claude_executable')),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                }
                data['tasks'].append(task)
                seen.add(key)
                count += 1
        except Exception as e:
            log.warning(f"migrate_panel_actions {actions_json.name}: {e}")

    data['migrated'] = True
    _save(data)
    log.info(f"Task migration: {count} actions imported to tasks.json")
    return count
