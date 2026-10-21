
# Todoist Data Exporter

The **Todoist Data Exporter** is a Python script that exports data from Todoist, including projects, tasks, labels, sections, and comments, into CSV files. This tool enables users to analyze and visualize their Todoist data independently.

## Features

- Exports **Projects** with metadata like project names, IDs, and colors.
- Exports **Tasks** (both active and completed) with details like content, due dates, labels, and project association. Nested fields are flattened into columns (e.g. `due.date`, `due.string`) and lists such as `labels` are stored as JSON.
- Exports **Labels** created in Todoist.
- Exports **Sections** within projects.
- Exports **Comments** associated with tasks and projects.

## Installation

### Prerequisites

- Python 3.10 or above
- `todoist-api-python` 4.x (the SDK for Todoist API v1)
- A Todoist API token (obtainable from your Todoist account under **Settings > Integrations**)

### Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/todoist-data-exporter.git
   cd todoist-data-exporter
   ```

2. **Install the package and its dependencies:**

   ```bash
   pip install -e .
   ```

   This also installs a `todoist-exporter` command, equivalent to `python src/exporter.py`.

3. **Configure your API token**:

   - Create a `config.json` file in the project root with your Todoist API token:

   ```json
   {
     "TOKEN": "your_todoist_api_token_here"
   }
   ```

## Usage

Run the exporter script to export data to CSV files:

```bash
python src/exporter.py
```

This will generate CSV files in the default `data` directory:

- `projects.csv` – list of all projects
- `tasks.csv` – list of all active tasks
- `tasks_completed.csv` – list of tasks completed in the last year (see `--completed_since`)
- `labels.csv` – list of labels
- `sections.csv` – list of sections per project
- `comments.csv` – list of comments on projects and active tasks

### Optional Command-Line Arguments

You can specify which entities to export using command-line arguments. Here are some examples:

- Export only projects and tasks:

  ```bash
  python src/exporter.py --projects --tasks
  ```

- Export all entities with `--all` flag:

  ```bash
  python src/exporter.py --all
  ```

- Specify an output directory other than the default `data/`:

  ```bash
  python src/exporter.py --all --output_dir="custom_data"
  ```

- Export completed tasks going back further than the default of one year:

  ```bash
  python src/exporter.py --completed_tasks --completed_since=2020-01-01
  ```

- Enable verbose output for debugging:

  ```bash
  python src/exporter.py --all --verbose
  ```

Use `--help` for a full list of options:

```bash
python src/exporter.py --help
```

### Arguments Summary

- `--all`: Export all entities (projects, tasks, completed tasks, labels, sections, and comments). This is also the default when no entity flags are given.
- `--output_dir`: Specify a custom directory to save CSV files.
- `--config`: Path to the config file holding `TOKEN` (default: `config.json`).
- `--completed_since`: Export tasks completed on or after this date, `YYYY-MM-DD` (default: one year ago).
- `--projects`: Export only projects.
- `--tasks`: Export only active tasks.
- `--completed_tasks`: Export only completed tasks.
- `--labels`: Export only labels.
- `--sections`: Export only sections.
- `--comments`: Export only comments (one API request per project and per active task, so this can be slow on large accounts).
- `--verbose`: Enable detailed logging output.

## Development

### Testing

After installing with `pip install -e .`, run the tests using `unittest`:

```bash
python -m unittest discover -s tests
```

The tests mock the Todoist API, so they need no token or network access, and write their CSV files to a temporary directory.

If the exporter fails (for example, an invalid token), it logs the error, stops, and exits with status 1. CSVs already written by earlier exports in that run are left in place.

### Contributing

1. Fork this repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Create a new Pull Request.

## License

This project is licensed under the MIT License. See `LICENSE` for more information.

## Acknowledgments

- Thanks to [Doist](https://doist.com/) for providing the [Todoist API](https://developer.todoist.com/).

## Contact

Feel free to contact me for questions or suggestions!
