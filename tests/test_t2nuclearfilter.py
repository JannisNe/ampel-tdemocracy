import numpy as np
import pytest

from ampel.content.DataPoint import DataPoint
from ampel.content.T1Document import T1Document
from ampel.log.AmpelLogger import DEBUG, AmpelLogger
from ampel.model.DPSelection import DPSelection
from ampel.struct.UnitResult import UnitResult
from ampel.tdemocracy.T2NuclearFilter import T2NuclearFilter
from ampel.util.mappings import get_by_path
from ampel.view.T2DocView import T2DocView

REF_T2_DEPENDENCY = [
    {
        "config": "%T2CatalogMatch_TDEmocracy",
        "unit": "T2CatalogMatch",
        "link_override": {
            "filter": "LSSTObjFilter",
            "select": "last",
            "sort": "diaObjectId",
        },
    },
    {
        "config": {
            "datalab_user": {"label": "datalab/user"},
            "datalab_pwd": {"label": "datalab/password"},
            "match_radius": 1,
            "query": "SELECT ra, dec, photo_z.z_phot_median, photo_z.z_phot_mean, photo_z.z_phot_std, photo_z.z_phot_l68, z_phot_u68, photo_z.z_spec, tractor.type, tractor.w1_w2, tractor.w2_w3, tractor.w3_w4, tractor.dered_mag_g, tractor.dered_mag_r, tractor.dered_mag_z, tractor.dered_mag_w1, tractor.dered_mag_w2 , tractor.dered_mag_w3, tractor.dered_mag_w4, tractor.snr_g, tractor.snr_r, tractor.snr_z, tractor.snr_w1, tractor.snr_w2, tractor.snr_w3, tractor.snr_w4 FROM ls_dr10.tractor as tractor LEFT JOIN ls_dr10.photo_z as photo_z on photo_z.ls_id = tractor.ls_id WHERE 't' = Q3C_RADIAL_QUERY(ra, dec,%.6f,%.6f,%.6f)",
        },
        "unit": "T2LSPhotoZTap",
    },
    {
        "config": {
            "max_redshift_category": 7,
            "t2_dependency": [
                {
                    "config": "%T2CatalogMatch_TDEmocracy",
                    "link_override": {
                        "filter": "LSSTObjFilter",
                        "select": "last",
                        "sort": "diaObjectId",
                    },
                    "unit": "T2CatalogMatch",
                },
                {
                    "config": {
                        "datalab_user": {"label": "datalab/user"},
                        "datalab_pwd": {"label": "datalab/password"},
                        "match_radius": 1,
                        "query": "SELECT ra, dec, photo_z.z_phot_median, photo_z.z_phot_mean, photo_z.z_phot_std, photo_z.z_phot_l68, z_phot_u68, photo_z.z_spec, tractor.type, tractor.w1_w2, tractor.w2_w3, tractor.w3_w4, tractor.dered_mag_g, tractor.dered_mag_r, tractor.dered_mag_z, tractor.dered_mag_w1, tractor.dered_mag_w2 , tractor.dered_mag_w3, tractor.dered_mag_w4, tractor.snr_g, tractor.snr_r, tractor.snr_z, tractor.snr_w1, tractor.snr_w2, tractor.snr_w3, tractor.snr_w4 FROM ls_dr10.tractor as tractor LEFT JOIN ls_dr10.photo_z as photo_z on photo_z.ls_id = tractor.ls_id WHERE 't' = Q3C_RADIAL_QUERY(ra, dec,%.6f,%.6f,%.6f)",
                    },
                    "link_override": {
                        "filter": "LSSTObjFilter",
                        "select": "last",
                        "sort": "diaObjectId",
                    },
                    "unit": "T2LSPhotoZTap",
                },
            ],
        },
        "unit": "T2DigestRedshifts",
    },
]


def test_t2_nuclear_filter(collections, test_schema, mock_context):  # noqa: ARG001
    t2_config = get_by_path(
        test_schema,
        "task.0.config.directives.0.ingest.mux.combine.0.state_t2.1.config",
    )
    # remove t2_dependencies, they are already included in the test data
    assert t2_config["t2_dependency"] == REF_T2_DEPENDENCY, (
        "Catalog matching config changed and can not be tested!"
    )
    t2_config["t2_dependency"] = []
    logger = AmpelLogger.get_logger(console=dict(level=DEBUG))
    t2_nuclear_filter = T2NuclearFilter(logger=logger, **t2_config)
    unique_stocks = [d["stock"] for d in collections["stock"]]
    links_in_t2 = {
        s: np.unique(
            [d["link"] for d in collections["t2"][s] if d.get("col", "") != "t0"]
        )
        for s in unique_stocks
    }
    dp_fltr, dp_sort, dp_slc = DPSelection(
        filter="LSSTObjFilter", select="last", sort="id"
    ).tools()
    for stock, stock_links in links_in_t2.items():
        t1_doc = sorted(
            [
                T1Document(
                    **next(d for d in collections["t1"][stock] if d["link"] == link)
                )
                for link in stock_links
            ],
            key=lambda d: len(d["dps"]),
        )[-1]

        link = t1_doc["link"]

        # prepare T1Document
        t1_doc = T1Document(
            **next(d for d in collections["t1"][stock] if d["link"] == link)
        )
        dps = [
            DataPoint(**dp)
            for dp in collections["t0"][stock]
            if (dp["id"] in t1_doc["dps"])
        ]

        st2 = collections["t2"][stock]
        t0_links = np.unique([d["link"] for d in st2 if d.get("col", "") == "t0"])
        if len(t0_links) == 1:
            t0_link = t0_links[0]
        else:
            # emulate link override in T2Worker
            selected_dps = dp_sort(dp_fltr.apply(dps))[dp_slc]
            assert len(selected_dps) == 1
            t0_link = selected_dps[0]["id"]

        t2_views = []
        for t2 in st2:
            if t2["link"] in [link, t0_link]:
                for k in ["_id", "channel", "col", "expiry"]:
                    t2.pop(k, None)
                t2["confid"] = -1
                t2["t2_type"] = 1
                t2_views.append(T2DocView(**t2))

        result = t2_nuclear_filter.process(
            compound=t1_doc, datapoints=dps, t2_views=t2_views
        )
        reference = next(
            d["body"]
            for d in st2
            if (d["link"] == link) and (d["unit"] == "T2NuclearFilter")
        )
        assert len(reference) == 1
        reference = reference[0]
        assert isinstance(result, UnitResult)
        assert isinstance(result.body, dict)
        resb = result.body
        assert resb["passed"] == reference["passed"]
        for attr in [
            "version",
            "model_version",
            "object",
            "mean_position",
            "template_fluxes",
            "host",
        ]:
            if isinstance(resd := resb["report"][attr], dict):
                for k, resv in resd.items():
                    refv = reference["report"][attr][k]
                    msg = f"{attr}.{k} failed!"
                    if (attr == "host") and (k in ["sources", "info"]):
                        assert sorted(resv) == sorted(refv), msg
                    else:
                        assert resv == pytest.approx(
                            reference["report"][attr][k], rel=1e-8
                        ), msg

        # check alsop photometry
        res_phot = sorted(resb["report"]["photometry"], key=lambda x: x["id"])
        ref_phot = sorted(reference["report"]["photometry"], key=lambda x: x["id"])
        assert len(res_phot) == len(ref_phot)
        for i, (res, ref) in enumerate(zip(res_phot, ref_phot, strict=False)):
            for k, resv in res.items():
                refv = ref[k]
                if k == "time":
                    refv -= 2400000.5  # test data was created with convert2jd: true
                assert resv == pytest.approx(refv, rel=1e-8), (
                    f"Stock: {stock}, Epoch {i}: {k} failed!"
                )
