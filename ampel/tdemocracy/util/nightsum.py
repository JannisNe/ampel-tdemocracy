from datetime import UTC, datetime
from urllib.error import HTTPError

import numpy as np
import pandas as pd
from astropy.time import Time, TimeDelta
from cachier import cachier

BASE_URL = "http://s3df.slac.stanford.edu/data/rubin/sim-data/completed/simonyi"
NON_SCIENCE_OBS_REASON = [
    "tmacheckout",
    "infocus_initial_alignment",
    "infocus_sweep_cam_m2_dz",
    "intra_alternating_elevation_stability",
    "extra_alternating_elevation_stability",
    "infocus_alternating_elevation_stability",
]


@cachier()
def get_nightly_summary(time: Time) -> pd.DataFrame:
    t = time.to_datetime()
    assert t < datetime.now(tz=UTC), "Can only query summaries from past nights!"
    url = f"{BASE_URL}/{t.year}/{t.strftime('%Y-%m-%d')}.parquet"
    try:
        return pd.read_parquet(url)
    except HTTPError as e:
        if "404: Not Found" not in str(e):
            raise e
        return pd.DataFrame([])


def get_obs_log(start_time: Time, end_time: Time) -> pd.DataFrame:
    # get nightly summary logs
    dt = end_time - start_time
    n_days = int(np.ceil(dt.to_value("d")))
    start_time_day = Time(np.floor(start_time.mjd), format="mjd")
    dates = start_time_day + TimeDelta(np.arange(-1, n_days + 2), format="jd")
    obs = pd.concat([get_nightly_summary(date) for date in dates])  # type: pd.DataFrame

    # select observations in required time
    obs_start = pd.to_datetime(obs["obs_start"], format="mixed")
    obs_end = pd.to_datetime(obs["obs_end"], format="mixed")
    m = (obs_end >= start_time.to_datetime()) & (obs_start <= end_time.to_datetime())
    obs = obs[m]  # type: pd.DataFrame

    # mark science observations
    obs["science"] = ~obs["observation_reason"].isin(NON_SCIENCE_OBS_REASON)

    return obs
