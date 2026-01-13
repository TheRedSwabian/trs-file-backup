import sys
from pathlib import Path

import typer
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger, time_it

from trs_file_backup import __version__
from trs_file_backup.my_app import MyApp

package_name = "trs-file-backup"

app = typer.Typer(name=package_name, help="Script to backup changed filed in a given Folder.", no_args_is_help=True, add_completion=False)


@app.callback(invoke_without_command=True)
def version(version: bool = typer.Option(None, "--version", "-v", is_eager=True, help="Show version and exit.")) -> None:
    if version:
        typer.echo(f"{package_name} {__version__}")
        raise typer.Exit()


@app.command(help="Run command description")
@time_it("run command")
def run(project_dir: Path = typer.Option(Path.cwd().absolute(), help="The project directory")) -> None:  # noqa: B008
    """Run the application."""
    MyApp(project_dir).run()


@app.command(help="Init command description")
@time_it("init command")
def init(
    project_dir: Path = typer.Option(Path.cwd().absolute(), help="The project directory"),  # noqa: B008
    force: bool = False,
) -> None:
    """Init the application."""
    logger.info(f"Running the application in {project_dir} with force={force}")


def main() -> None:
    """Initialize something in the project directory."""
    try:
        setup_logger()
        app()
    except UserNotificationException as e:
        logger.error(f"{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
