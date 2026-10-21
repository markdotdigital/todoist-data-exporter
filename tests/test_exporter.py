import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd
from todoist_api_python.models import Comment, Label, Project, Section, Task

from exporter import ENTITIES, TodoistExporter, main, parse_args, selected_entities

TIMESTAMP = "2026-01-01T09:00:00Z"


def make_project(**overrides) -> Project:
    data = {
        "id": "p1", "name": "Test Project", "description": "", "order": 1, "color": "blue",
        "is_collapsed": False, "is_shared": False, "is_favorite": False, "is_archived": False,
        "can_assign_tasks": False, "view_style": "list", "created_at": TIMESTAMP, "updated_at": TIMESTAMP,
    }
    return Project.from_dict({**data, **overrides})


def make_task(**overrides) -> Task:
    data = {
        "id": "t1", "content": "Test Task", "description": "", "project_id": "p1", "section_id": None,
        "parent_id": None, "labels": [], "priority": 1, "due": None, "deadline": None, "duration": None,
        "is_collapsed": False, "order": 1, "assignee_id": None, "assigner_id": None, "completed_at": None,
        "creator_id": "u1", "created_at": TIMESTAMP, "updated_at": TIMESTAMP,
    }
    return Task.from_dict({**data, **overrides})


def make_label(**overrides) -> Label:
    data = {"id": "l1", "name": "Test Label", "color": "red", "order": 1, "is_favorite": False}
    return Label.from_dict({**data, **overrides})


def make_section(**overrides) -> Section:
    data = {"id": "s1", "name": "Test Section", "project_id": "p1", "is_collapsed": False, "order": 1}
    return Section.from_dict({**data, **overrides})


def make_comment(**overrides) -> Comment:
    data = {"id": "c1", "content": "Test Comment", "poster_id": "u1", "posted_at": TIMESTAMP}
    return Comment.from_dict({**data, **overrides})


def pages(*page_items):
    """Mimics the SDK's paginated results: an iterator of lists."""
    return iter([list(items) for items in page_items])


class ExporterTestCase(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.mkdtemp()
        patcher = patch("exporter.TodoistAPI")
        self.addCleanup(patcher.stop)
        self.api = patcher.start().return_value
        self.exporter = TodoistExporter(token="mock-token", output_dir=self.output_dir)

    def tearDown(self):
        for filename in os.listdir(self.output_dir):
            os.unlink(os.path.join(self.output_dir, filename))
        os.rmdir(self.output_dir)

    def read_csv(self, filename: str) -> pd.DataFrame:
        return pd.read_csv(os.path.join(self.output_dir, filename), keep_default_na=False, dtype=str)


class TestTodoistExporter(ExporterTestCase):
    def test_export_projects_across_pages(self):
        self.api.get_projects.return_value = pages([make_project(id="p1")], [make_project(id="p2", name="Second")])

        self.exporter.export_projects()

        df = self.read_csv("projects.csv")
        self.assertEqual(list(df["id"]), ["p1", "p2"])
        self.assertEqual(list(df["name"]), ["Test Project", "Second"])

    def test_export_tasks_flattens_nested_fields(self):
        due = {"date": "2026-10-20", "string": "today", "lang": "en", "is_recurring": False, "timezone": None}
        self.api.get_tasks.return_value = pages([
            make_task(id="t1", labels=["home", "urgent"], due=due),
            make_task(id="t2"),
        ])

        self.exporter.export_tasks()

        df = self.read_csv("tasks.csv")
        self.assertEqual(list(df["id"]), ["t1", "t2"])
        self.assertEqual(json.loads(df["labels"][0]), ["home", "urgent"])
        self.assertEqual(list(df["due.date"]), ["2026-10-20", ""])
        self.assertEqual(df["due.string"][0], "today")

    def test_export_completed_tasks_in_windows(self):
        until = datetime(2026, 10, 20, tzinfo=timezone.utc)
        since = until - timedelta(days=75)
        self.api.get_completed_tasks_by_completion_date.side_effect = [
            pages([make_task(id="t1", completed_at=TIMESTAMP)]),
            pages([]),
            pages([make_task(id="t2", completed_at=TIMESTAMP)]),
        ]

        self.exporter.export_completed_tasks(since=since, until=until)

        calls = [c.kwargs for c in self.api.get_completed_tasks_by_completion_date.call_args_list]
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["since"], since)
        self.assertEqual(calls[-1]["until"], until)
        for previous, current in zip(calls, calls[1:]):
            self.assertEqual(previous["until"], current["since"])
        self.assertEqual(list(self.read_csv("tasks_completed.csv")["id"]), ["t1", "t2"])

    def test_export_labels(self):
        self.api.get_labels.return_value = pages([make_label()])

        self.exporter.export_labels()

        self.assertEqual(list(self.read_csv("labels.csv")["name"]), ["Test Label"])

    def test_export_sections(self):
        self.api.get_sections.return_value = pages([make_section(id="s1"), make_section(id="s2", project_id="p2")])

        self.exporter.export_sections()

        df = self.read_csv("sections.csv")
        self.assertEqual(list(df["id"]), ["s1", "s2"])
        self.assertEqual(list(df["project_id"]), ["p1", "p2"])

    def test_export_comments_on_projects_and_tasks(self):
        self.api.get_projects.return_value = pages([make_project(id="p1")])
        self.api.get_tasks.return_value = pages([make_task(id="t1")])

        def get_comments(project_id=None, task_id=None):
            if project_id:
                return pages([make_comment(id="c1", project_id=project_id)])
            return pages([make_comment(id="c2", task_id=task_id)])

        self.api.get_comments.side_effect = get_comments

        self.exporter.export_comments()

        df = self.read_csv("comments.csv")
        self.assertEqual(list(df["id"]), ["c1", "c2"])
        self.assertEqual(list(df["project_id"]), ["p1", ""])
        self.assertEqual(list(df["task_id"]), ["", "t1"])

    def test_empty_export_writes_header(self):
        self.api.get_labels.return_value = pages([])

        self.exporter.export_labels()

        df = self.read_csv("labels.csv")
        self.assertTrue(df.empty)
        self.assertEqual(list(df.columns), ["id", "name", "color", "order", "is_favorite"])

    def test_api_errors_propagate(self):
        self.api.get_projects.side_effect = RuntimeError("401 Unauthorized")

        with self.assertRaises(RuntimeError):
            self.exporter.export_projects()
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "projects.csv")))


class TestSelectedEntities(unittest.TestCase):
    def test_no_flags_exports_everything(self):
        self.assertEqual(selected_entities(parse_args([])), ENTITIES)

    def test_all_flag_exports_everything(self):
        self.assertEqual(selected_entities(parse_args(["--all", "--labels"])), ENTITIES)

    def test_specific_flags(self):
        self.assertEqual(selected_entities(parse_args(["--tasks", "--projects"])), ["projects", "tasks"])


class TestMain(ExporterTestCase):
    def write_config(self, contents: dict) -> str:
        path = os.path.join(self.output_dir, "config.json")
        with open(path, "w") as f:
            json.dump(contents, f)
        return path

    def run_main(self, *args: str) -> int:
        with self.assertLogs(level="INFO"):
            return main(["--output_dir", self.output_dir, *args])

    def test_missing_token_fails(self):
        config = self.write_config({})
        self.assertEqual(self.run_main("--config", config), 1)

    def test_exports_selected_entities(self):
        config = self.write_config({"TOKEN": "mock-token"})
        self.api.get_labels.return_value = pages([make_label()])

        self.assertEqual(self.run_main("--config", config, "--labels"), 0)

        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "labels.csv")))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "projects.csv")))

    def test_export_failure_returns_error(self):
        config = self.write_config({"TOKEN": "mock-token"})
        self.api.get_projects.side_effect = RuntimeError("401 Unauthorized")

        self.assertEqual(self.run_main("--config", config, "--projects"), 1)


if __name__ == "__main__":
    unittest.main()
