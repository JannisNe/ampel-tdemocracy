from bson import encode

from ampel.abstract.AbsAlertFilter import AbsAlertFilter
from ampel.abstract.AbsAlertSupplier import AbsAlertSupplier
from ampel.base.AuxUnitRegister import AuxUnitRegister
from ampel.dev.DevAmpelContext import DevAmpelContext
from ampel.log import DEBUG, AmpelLogger
from ampel.lsst.ingest.LSSTDataPointShaper import LSSTDataPointShaper
from ampel.model.AlertConsumerModel import AlertConsumerModel
from ampel.model.ingest.FilterModel import FilterModel
from ampel.model.UnitModel import UnitModel
from ampel.util.hash import hash_payload


def shaper_hash(d: dict) -> bytes:
    return hash_payload(
        encode(dict(sorted(d["body"].items()))),
        size=-8 * 8,
    )


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

    passed_dps = []
    for ctr, alert in enumerate(supplier):
        if ctr > iter_max:
            break
        if filter_inst.process(alert):
            for dp in shaper.process(alert.datapoints, alert.stock):
                if dp["id"] not in dp_ids:
                    h = shaper_hash(dp)
                    h_from_t0 = shaper_hash(
                        next(
                            idp
                            for idp in collections["t0"][alert.stock]
                            if idp["body"].get("diaSourceId")
                            == idp["body"]["diaSourceId"]
                        )
                    )

                    raise AssertionError(
                        f"Error for alert {alert.id} of {alert.stock}, now hash is {h}, from shaper: {dp['id']}, manual: {h_from_t0}, shaper.digest_size: {shaper.digest_size}"
                    )
                passed_dps.append(dp["id"])

    assert all([sid in passed_dps for sid in dp_ids])
