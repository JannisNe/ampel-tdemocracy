from ampel.abstract.AbsAlertFilter import AbsAlertFilter
from ampel.abstract.AbsAlertSupplier import AbsAlertSupplier
from ampel.base.AuxUnitRegister import AuxUnitRegister
from ampel.dev.DevAmpelContext import DevAmpelContext
from ampel.log import DEBUG, AmpelLogger
from ampel.lsst.ingest.LSSTDataPointShaper import LSSTDataPointShaper
from ampel.model.AlertConsumerModel import AlertConsumerModel
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
    assert filter_inst.min_reliability >= 0.8, (
        "Test data only contains alerts with reliability >= 0.8! Lower values can not be verified!"
    )

    supplier_model = UnitModel(**test_schema["task"][0]["config"]["supplier"])
    supplier = AuxUnitRegister.new_unit(model=supplier_model, sub_type=AbsAlertSupplier)

    shaper_model = UnitModel(**test_schema["task"][0]["config"]["shaper"])
    shaper = mock_context.loader.new_logical_unit(
        model=shaper_model,
        sub_type=LSSTDataPointShaper,
        logger=logger,
    )

    iter_max = test_schema["task"][0]["config"].get(
        "iter_max", AlertConsumerModel.model_fields["iter_max"].default
    )
    dp_ids = set([dp["id"] for dps in collections["t0"].values() for dp in dps])

    passed_alerts = []
    for ctr, alert in enumerate(supplier):
        if ctr > iter_max:
            break
        if filter_inst.process(alert):
            for dp in shaper.process(alert.datapoints, alert.stock):
                assert dp["id"] in dp_ids, (
                    f"Error for alert {alert.id} of {alert.stock}"
                )
            passed_alerts.append(alert.id)

    assert all([sid in passed_alerts for sid in dp_ids])
