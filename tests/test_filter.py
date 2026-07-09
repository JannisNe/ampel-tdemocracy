from ampel.abstract.AbsAlertFilter import AbsAlertFilter
from ampel.abstract.AbsAlertSupplier import AbsAlertSupplier
from ampel.base.AuxUnitRegister import AuxUnitRegister
from ampel.dev.DevAmpelContext import DevAmpelContext
from ampel.log import DEBUG, AmpelLogger
from ampel.model.ingest.FilterModel import FilterModel
from ampel.model.UnitModel import UnitModel


def test_filtering(
    collections: dict[str, dict],
    test_schema: dict,
    mock_context: DevAmpelContext,
):
    logger = AmpelLogger.get_logger(console=DEBUG)
    filter_model = FilterModel(
        **test_schema["task"][0]["config"]["directives"][0]["filter"]
    )
    filter_inst = mock_context.loader.new_logical_unit(
        model=filter_model,
        sub_type=AbsAlertFilter,
        logger=logger,
    )

    supplier_model = UnitModel(**test_schema["task"][0]["config"]["supplier"])
    supplier = AuxUnitRegister.new_unit(model=supplier_model, sub_type=AbsAlertSupplier)

    source_ids = set(
        [dp["body"]["diaSourceId"] for dps in collections["t0"].values() for dp in dps]
    )
    passed_alerts = []
    for alert in supplier:
        if filter_inst.process(alert):
            assert alert.id in source_ids
            passed_alerts.append(alert.id)

    assert all([sid in passed_alerts for sid in passed_alerts])
