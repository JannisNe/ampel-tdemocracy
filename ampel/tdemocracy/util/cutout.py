import base64
import gzip
import io
import os
from collections.abc import Mapping
from contextlib import suppress
from gzip import BadGzipFile

import backoff
import numpy as np
import requests
from astropy import visualization
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from cachier import cachier
from matplotlib.colors import Normalize
from scipy import ndimage

ARCHIVE_URL = "https://lsst-archive.ampel.zeuthen.desy.de/api/lsst/archive/v1/"


@backoff.on_exception(
    backoff.expo,
    (requests.ConnectionError, requests.Timeout),
    max_tries=5,
    factor=2,
)
@backoff.on_exception(
    backoff.expo,
    requests.HTTPError,
    giveup=lambda e: (
        not isinstance(e, requests.HTTPError)
        or e.response is None
        or e.response.status_code not in {502, 503, 504, 429, 408}
    ),
    max_time=60,
)
@cachier()
def download_lsst_cutout(dia_source_id: int) -> dict[str, bytes] | None:
    """
    Download a cutout from the LSST archive.

    Behavior:
    - 404 -> no cutout available -> return None
    - temporary network / server problems -> retry
    - persistent timeout / server failure -> raise and stop job
    """
    response = requests.get(
        f"{ARCHIVE_URL.rstrip('/')}/alert/{dia_source_id}/cutouts",
        verify=False,
        timeout=20,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()
    json = response.json()
    return {
        k: base64.b64decode(json[k])
        for k in ["cutoutScience", "cutoutTemplate", "cutoutDifference"]
    }


def load_cutout_image(
    data_bytes: bytes,
    *,
    return_header: bool = False,
) -> np.ndarray | tuple[np.ndarray, fits.Header]:
    """
    Decode a cutout FITS image from bytes and return a 2D float array.

    Supports both:
      - ZTF cutouts: gzip-compressed FITS payload
      - LSST cutouts: plain FITS payload

    If return_header=True, also return the FITS header of the chosen 2D HDU.
    """
    # 1) Decompress if needed (ZTF), otherwise treat as plain FITS (LSST)
    try:
        with gzip.open(io.BytesIO(data_bytes), "rb") as f:
            payload = f.read()
    except BadGzipFile:
        payload = data_bytes

    with fits.open(io.BytesIO(payload), ignore_missing_simple=True) as hdul:
        # 2) Find first 2D image HDU
        data2d: np.ndarray | None = None
        hdr: fits.Header | None = None

        for hdu in hdul:
            if getattr(hdu, "data", None) is None:
                continue
            arr = np.squeeze(hdu.data)
            if isinstance(arr, np.ndarray) and arr.ndim == 2:
                data2d = arr.astype(float, copy=False)
                hdr = hdu.header
                break

        if data2d is None or hdr is None:
            raise ValueError("No 2D image HDU found in cutout FITS payload")

        if return_header:
            return data2d, hdr
        return data2d


def cutout_fov_arcsec(data2d: np.ndarray, hdr: fits.Header) -> float | None:
    """
    Calculate the Field of View (FoV) in arcseconds for a given cutout FITS image.
    """
    ny, nx = data2d.shape[-2], data2d.shape[-1]

    try:
        w = WCS(hdr)
        # pixel scales in deg/pix (for each axis)
        scales_deg = proj_plane_pixel_scales(w)  # ndarray, len>=2
        pixscale_arcsec = float(np.mean(scales_deg[:2]) * 3600.0)
        return pixscale_arcsec * float(max(nx, ny))
    except Exception:
        return None


def get_cached_cutout_image(
    data_bytes: bytes,
    *,
    cache_dir: str | None,
    cache_key: str,
    cutout_type: str,
) -> tuple[np.ndarray, float | None]:
    """
    Return a display-ready 2D cutout image and its FoV in arcsec.

    The cache stores the already processed image after:
      - FITS decoding
      - optional rotation
      - stretch / normalization for imshow
    """
    cache_path = None
    if cache_dir is not None:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{cache_key}_{cutout_type}.npz")
        if os.path.isfile(cache_path):
            try:
                cached = np.load(cache_path, allow_pickle=True)
                data = np.asarray(cached["data"], dtype=float)
                fov = cached["fov"]
                fov_val: float | None
                if np.ndim(fov) == 0:
                    fov_scalar = float(fov)
                    fov_val = fov_scalar if np.isfinite(fov_scalar) else None
                else:
                    fov_val = None
                return data, fov_val
            except Exception:
                pass

    data, hdr = load_cutout_image(data_bytes, return_header=True)
    cutout_fov = cutout_fov_arcsec(data, hdr)

    rotpa = hdr.get("ROTPA", None)
    if rotpa is not None:
        try:
            angle = -float(rotpa)
            data = ndimage.rotate(
                data,
                angle=angle,
                reshape=False,
                order=1,
                mode="constant",
                cval=np.nan,
                prefilter=False,
            )
        except Exception:
            pass

    finite = np.isfinite(data)
    if not np.any(finite):
        data_ = np.full_like(data, np.nan, dtype=float)
    else:
        vmin, vmax = np.percentile(data[finite], [50, 99.5])
        denom = vmax - vmin
        if not np.isfinite(denom) or denom <= 0:
            denom = 1.0
        data_ = visualization.AsinhStretch()((data - vmin) / denom)

    if cache_path is not None:
        with suppress(Exception):
            np.savez(
                cache_path,
                data=np.asarray(data_, dtype=float),
                fov=np.nan if cutout_fov is None else float(cutout_fov),
            )

    return np.asarray(data_, dtype=float), cutout_fov


def create_stamp_plot(
    cutouts: Mapping[str, Mapping[str, bytes]],
    ax,
    cutout_type: str,
    *,
    cache_dir: str | None = None,
    cache_key: str | None = None,
) -> float | None:
    """
    Render a Science/Template/Difference cutout into the provided axes and
    return an FOV in arcseconds to use as the finder FOV.
    """
    data_bytes = next(iter(cutouts.values()))[f"cutout{cutout_type}"]

    if cache_key is not None:
        data_, cutout_fov = get_cached_cutout_image(
            data_bytes,
            cache_dir=cache_dir,
            cache_key=cache_key,
            cutout_type=cutout_type,
        )
    else:
        data, hdr = load_cutout_image(data_bytes, return_header=True)
        cutout_fov = cutout_fov_arcsec(data, hdr)

        rotpa = hdr.get("ROTPA", None)
        if rotpa is not None:
            try:
                angle = -float(rotpa)
                data = ndimage.rotate(
                    data,
                    angle=angle,
                    reshape=False,
                    order=1,
                    mode="constant",
                    cval=np.nan,
                    prefilter=False,
                )
            except Exception:
                pass

        finite = np.isfinite(data)
        if not np.any(finite):
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(cutout_type, fontdict={"fontsize": "small"})
            return None

        vmin, vmax = np.percentile(data[finite], [50, 99.5])
        denom = vmax - vmin
        if not np.isfinite(denom) or denom <= 0:
            denom = 1.0
        data_ = visualization.AsinhStretch()((data - vmin) / denom)

    finite2 = np.isfinite(data_)
    if not np.any(finite2):
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(cutout_type, fontdict={"fontsize": "small"})
        return cutout_fov

    ax.imshow(
        data_,
        norm=Normalize(*np.percentile(data_[finite2], [0.5, 99.5])),
        aspect="equal",
        cmap="viridis",
        origin="lower",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(cutout_type, fontdict={"fontsize": "small"})
    return cutout_fov
