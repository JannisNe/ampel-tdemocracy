import json
from collections import defaultdict

import numpy as np
from matplotlib import pyplot as plt

from ampel.tdemocracy.util.cutout import (
    NO_CUTOUT,
    create_stamp_plot,
    download_lsst_cutout,
)
from tests.conftest import load_collection


def load_data():
    col = sorted(load_collection("t0"), key=lambda c: c["stock"], reverse=True)
    sorted_col = defaultdict(list)
    for c in col:
        for stock in np.atleast_1d(c["stock"]):
            sorted_col[stock].append(c)
    return sorted_col


def find_multiple_sources_per_visit():
    col = load_data()
    multiple_sources = {}
    for stock, dps in col.items():
        visits = defaultdict(list)
        for dp in dps:
            if dp["body"].get("diaSourceId"):
                dp.pop("_id")
                dp.pop("expiry")
                visits[dp["body"]["visit"]].append(dp)
        multiple_source_per_visit = [v for k, v in visits.items() if len(v) > 1]
        if any(multiple_source_per_visit):
            multiple_sources[int(stock)] = multiple_source_per_visit

    print(f"Found {len(multiple_sources)} objects with multiple sources per visit")  # noqa: T201
    max_n_sources = max([len(iv) for v in multiple_sources.values() for iv in v])
    print(f"Up to {max_n_sources} sources per visit")  # noqa: T201
    return multiple_sources


def plot_multiple_sources_per_visit():
    multiple_sources = find_multiple_sources_per_visit()
    for stock, dps_list in multiple_sources.items():
        for dps in dps_list:
            mjd = dps[0]["body"]["midpointMjdTai"]
            fig, axs = plt.subplots(
                nrows=len(dps),
                ncols=3,
                figsize=(15, 5 * len(dps)),
                sharex="all",
                sharey="all",
            )
            for i, dp in enumerate(dps):
                cutouts = download_lsst_cutout(
                    dia_source_id=dp["body"]["diaSourceId"],
                )
                if cutouts == NO_CUTOUT:
                    continue
                for ax, st in zip(
                    axs[i], ["Science", "Template", "Difference"], strict=False
                ):
                    create_stamp_plot(
                        {"cutouts": cutouts},
                        ax,
                        st,
                        ra=dp["body"]["ra"],
                        dec=dp["body"]["dec"],
                    )
                    for idp in dps:
                        x = idp["body"]["ra"]
                        y = idp["body"]["dec"]
                        ax.scatter(x, y)
                        ax.annotate(
                            idp["body"]["diaSourceId"],
                            (x, y),
                            xytext=(0, 2),
                            textcoords="offset points",
                            ha="center",
                            va="bottom",
                            color="white",
                        )
                    ax.grid(ls=":")
                axs[i][1].set_title(dp["body"]["diaSourceId"])
            try:
                fig.tight_layout()
                fn = f"./{stock}_{mjd}.pdf"
                print(f"Saving {fn}")  # noqa: T201
                fig.savefig(fn)
            except ValueError:
                pass
            plt.close()
    return multiple_sources


if __name__ == "__main__":
    multiple_sources = plot_multiple_sources_per_visit()
    with open("mutliple_sources_per_visit.json", "w") as f:
        json.dump(multiple_sources, f)
