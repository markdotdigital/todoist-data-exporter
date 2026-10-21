import pandas as pd
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Comment, Label, Project, Section, Task
import argparse
import dataclasses
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator, Optional, TypeVar

T = TypeVar("T")

# The completed-tasks endpoint only accepts a limited since/until range, so history is fetched in windows.
COMPLETED_TASKS_WINDOW = timedelta(days=30)

ENTITIES = ["projects", "tasks", "completed_tasks", "labels", "sections", "comments"]


def flatten(pages: Iterable[list[T]]) -> Iterator[T]:
    """Yields the items from the paginated results returned by the Todoist SDK."""
    for page in pages:
        yield from page


class TodoistExporter:
    """Exports data from Todoist into CSV files for projects, tasks, labels, sections, and comments."""

    def __init__(self, token: str, output_dir: str = "data"):
        self.api = TodoistAPI(token)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)  # Create the output directory if it doesn't exist
        logging.info(f"Data will be exported to directory: {self.output_dir}")

    def _write_csv(self, items: list, model: type, filename: str) -> None:
        """Writes dataclass models to a CSV, flattening nested objects (e.g. due -> due.date, due.string)."""
        if items:
            rows = [dataclasses.asdict(item) for item in items]
            df = pd.json_normalize(rows, sep=".")
            # Store lists (e.g. task labels) as JSON so they stay unambiguous in a single cell
            for column in df.columns:
                df[column] = df[column].map(lambda v: json.dumps(v) if isinstance(v, list) else v)
        else:
            df = pd.DataFrame(columns=[f.name for f in dataclasses.fields(model)])
        path = os.path.join(self.output_dir, filename)
        df.to_csv(path, index=False)
        logging.info(f"Exported {len(items)} rows to {path}")

    def export_projects(self) -> None:
        """Exports all projects to a CSV file."""
        projects = list(flatten(self.api.get_projects()))
        self._write_csv(projects, Project, "projects.csv")

    def export_tasks(self) -> None:
        """Exports all active tasks to a CSV file."""
        tasks = list(flatten(self.api.get_tasks()))
        self._write_csv(tasks, Task, "tasks.csv")

    def export_completed_tasks(self, since: datetime, until: Optional[datetime] = None) -> None:
        """Exports tasks completed between since and until (default: now) to a CSV file."""
        until = until or datetime.now(timezone.utc)
        tasks = []
        window_start = since
        while window_start < until:
            window_end = min(window_start + COMPLETED_TASKS_WINDOW, until)
            logging.debug(f"Fetching tasks completed between {window_start} and {window_end}")
            tasks.extend(flatten(self.api.get_completed_tasks_by_completion_date(since=window_start, until=window_end)))
            window_start = window_end
        self._write_csv(tasks, Task, "tasks_completed.csv")

    def export_labels(self) -> None:
        """Exports all personal labels to a CSV file."""
        labels = list(flatten(self.api.get_labels()))
        self._write_csv(labels, Label, "labels.csv")

    def export_sections(self) -> None:
        """Exports all sections across all projects to a CSV file."""
        sections = list(flatten(self.api.get_sections()))
        self._write_csv(sections, Section, "sections.csv")

    def export_comments(self) -> None:
        """Exports all comments on projects and active tasks to a CSV file."""
        comments = []
        for project in flatten(self.api.get_projects()):
            comments.extend(flatten(self.api.get_comments(project_id=project.id)))
        for task in flatten(self.api.get_tasks()):
            comments.extend(flatten(self.api.get_comments(task_id=task.id)))
        self._write_csv(comments, Comment, "comments.csv")


def parse_date(value: str) -> datetime:
    """Parses a YYYY-MM-DD command-line argument as midnight UTC."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date '{value}', expected YYYY-MM-DD")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Todoist data to CSV files.")
    parser.add_argument("--projects", action="store_true", help="Export projects")
    parser.add_argument("--tasks", action="store_true", help="Export active tasks")
    parser.add_argument("--completed_tasks", action="store_true", help="Export completed tasks")
    parser.add_argument("--labels", action="store_true", help="Export labels")
    parser.add_argument("--sections", action="store_true", help="Export sections")
    parser.add_argument("--comments", action="store_true", help="Export comments")
    parser.add_argument("--all", action="store_true", help="Export all data types (the default if no entity flags are given)")
    parser.add_argument(
        "--completed_since",
        type=parse_date,
        default=datetime.now(timezone.utc) - timedelta(days=365),
        help="Export tasks completed on or after this date, YYYY-MM-DD (default: one year ago)",
    )
    parser.add_argument("--output_dir", type=str, default="data", help="Directory to save CSV files")
    parser.add_argument("--config", type=str, default="config.json", help="Path to the config file holding TOKEN")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    return parser.parse_args(argv)


def selected_entities(args: argparse.Namespace) -> list[str]:
    """Returns the entities to export: those flagged, or all of them if none (or --all) are flagged."""
    chosen = [entity for entity in ENTITIES if getattr(args, entity)]
    return ENTITIES if args.all or not chosen else chosen


def load_token(config_path: str) -> str:
    with open(config_path) as f:
        return json.load(f)["TOKEN"]


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    try:
        token = load_token(args.config)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        logging.critical(f"{args.config} not found, invalid, or missing a TOKEN entry.")
        return 1

    exporter = TodoistExporter(token, output_dir=args.output_dir)
    exports = {
        "projects": exporter.export_projects,
        "tasks": exporter.export_tasks,
        "completed_tasks": lambda: exporter.export_completed_tasks(since=args.completed_since),
        "labels": exporter.export_labels,
        "sections": exporter.export_sections,
        "comments": exporter.export_comments,
    }

    for entity in selected_entities(args):
        try:
            exports[entity]()
        except Exception:
            logging.exception(f"Failed to export {entity}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
