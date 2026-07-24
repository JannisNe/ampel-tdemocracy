import argparse
import logging
import re
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel

from ampel.cli.JobCommand import JobCommand

LOGGER = logging.getLogger()
JOB_FILE_PATH = Path(__file__).parent.parent.parent / "job_files" / "nuclear_stream.yml"
DATA_DIR = Path(__file__).parent
INPUT_DATA = DATA_DIR / "lsst-alerts-2026-07-05--2026-07-06-r0.8.parquet"
MONGO_PREFIX = "nuclear_stream_test_data"
RESULT_ADAPTER_CONFIG = (
    "                  result_adapter:\n"
    "                    unit: HopskotchAdapter\n"
    "                    config:\n"
    "                      broker: kafka.scimma.org\n"
    "                      auth:\n"
    "                        username:\n"
    "                          label: scimma/neckerja/user\n"
    "                        password:\n"
    "                          label: scimma/neckerja/password\n"
    "                      topic: Ampel-TDEmocracy.nucelar-stream-dev\n"
    "                      model: tdemocracy.model.NuclearTransientReport\n"
    "                      message_path: report\n"
    "                      condition_path: passed\n"
)


def patch_schema(
    fin: TextIOWrapper,
    fout: TextIOWrapper,
    remove_adapter: bool = True,
    iter_max: int | None = None,
) -> None:
    text_in = fin.read()
    if remove_adapter:
        text_in = text_in.replace(RESULT_ADAPTER_CONFIG, "")

    # More targeted replacement: only change iter_max in the AlertConsumer task config
    if iter_max is not None:
        pattern = re.compile(
            r"(unit:\s*AlertConsumer\s*\n\s*config:\s*\n.*?iter_max:\s*)(\d+)",
            flags=re.S,
        )
        text_in = pattern.sub(lambda m: m.group(1) + str(int(iter_max)), text_in)

    fout.write(
        re.sub(
            r"(unit:\s*ParquetAlertLoader\s*\n\s*config:\s*\n\s*path:\s*)\S+",
            rf"\1{INPUT_DATA!s}",
            re.sub(
                r"(mongo:\s*\n\s*prefix:\s*)\S+",
                rf"\1{MONGO_PREFIX}",
                re.sub(r"(do_lasair_annotation:\s*)\S+", r"\1false", text_in),
            ),
        )
    )


@contextmanager
def test_job_file() -> Generator[Path]:
    with tempfile.NamedTemporaryFile("w") as fmod:
        with open(JOB_FILE_PATH) as f:
            patch_schema(f, fmod)
        fmod.seek(0)
        yield Path(fmod.name)


def run_job(ampel_config_path: str, secrets_file: str):
    LOGGER.info("Running job")
    with test_job_file() as fmod_path:
        LOGGER.debug(f"config: {ampel_config_path}, job: {fmod_path}")
        cmd = JobCommand()
        parser = cmd.get_parser()
        args = vars(
            parser.parse_args(
                [
                    "--schema",
                    str(fmod_path),
                    "--config",
                    str(ampel_config_path),
                    "--reset-db",
                    "--task",
                    "0",
                    "1",
                    "--secrets",
                    str(secrets_file),
                ]
            )
        )
        LOGGER.debug(args)
        cmd.run(args, unknown_args=())


def export_collection(ampel_config_path: str, collection_name: str):
    LOGGER.info(f"Exporting collection {collection_name}")
    with open(ampel_config_path) as f:
        config = yaml.safe_load(f)
    uri = config["resource"]["mongo"]
    cmd = [
        "mongodump",
        "-d",
        MONGO_PREFIX,
        "-c",
        collection_name,
        f"--uri={uri}",
        "-o",
        str(DATA_DIR.absolute()),
        "--gzip",
    ]
    LOGGER.debug(" ".join(cmd))
    subprocess.check_output(cmd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="Path to ampel config")
    parser.add_argument("secrets", type=Path, help="Path to secrets file")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)

    console = Console()
    console.print(
        Panel(
            "[bold yellow]⚠ Make sure new test data is needed! [/]\n\n"
            "• Do not make test data just to pass the unit tests!\n"
            "• Make sure you understand why the tests fail and which change makes the old test data obsolete!\n"
            "• Make sure any relevant changes are documented in CHANGELOG.md!",
            title="[bold red]CAUTION[/]",
            border_style="bright_red",
            padding=(1, 2),
            expand=False,
        )
    )
    input("If you have done the above, press enter to continue...")
    config_path = str(args.config.absolute())
    run_job(args.config, args.secrets)
    for i in range(3):
        export_collection(args.config, f"t{i}")
    export_collection(args.config, "stock")
