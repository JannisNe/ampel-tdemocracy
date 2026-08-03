from pathlib import Path

import pytest

from ampel.cli.JobCommand import JobCommand
from ampel.kafka.HopskotchAdapter import HopskotchAdapter
from ampel.struct.UnitResult import UnitResult
from ampel.tdemocracy.T2NuclearFilter import T2NuclearFilter


@pytest.mark.schema(remove_adapter=False, iter_max=100)
def test_run_job(test_schema_path: Path, testing_config: Path, monkeypatch) -> None:
    # patch hopskotch stream
    sent_results = []

    def send_patch(ur: UnitResult):
        sent_results.append(ur)

    monkeypatch.setattr(HopskotchAdapter, "send", send_patch)

    # patch lasair annotations
    lasair_annotations = []

    def annotate(*args, **kwargs):
        lasair_annotations.append((args, kwargs))

    monkeypatch.setattr(T2NuclearFilter, "annotate", annotate)

    cmd = JobCommand()
    parser = cmd.get_parser()
    args = vars(
        parser.parse_args(
            ["--schema", str(test_schema_path), "--config", str(testing_config)]
        )
    )
    cmd.run(args, unknown_args=())
