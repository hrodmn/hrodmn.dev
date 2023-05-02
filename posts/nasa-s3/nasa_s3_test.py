import os
import timeit

import click
import pystac_client
import rasterio
import requests
import stackstac

EPSG = 5070
HLS_URL_PREFIX = "https://data.lpdaac.earthdatacloud.nasa.gov/"
BBOX = (-121.8238, 38.4921, -121.6018, 38.6671)
COLLECTION = "HLSL30.v2.0"
START_DATE = "2022-04-01"
END_DATE = "2023-03-31"
ASSETS = ["B04", "B03", "B02"]
RESOLUTION = 30
N_ITERATIONS = 10


def default(stac_items):
    """Read the rasters using the links in the STAC item metadata"""
    stackstac.stack(
        stac_items,
        assets=ASSETS,
        bounds_latlon=BBOX,
        epsg=EPSG,
        resolution=RESOLUTION,
        xy_coords="center",
    ).compute()


def get_nasa_s3_creds():
    # get username/password from netrc file
    netrc_creds = {}
    with open(os.path.expanduser("~/.netrc")) as f:
        for line in f:
            key, value = line.strip().split(" ")
            netrc_creds[key] = value

    # request AWS credentials for direct read access
    url = requests.get(
        "https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials",
        allow_redirects=False,
    ).headers["Location"]

    raw_creds = requests.get(
        url, auth=(netrc_creds["login"], netrc_creds["password"])
    ).json()

    return dict(
        aws_access_key_id=raw_creds["accessKeyId"],
        aws_secret_access_key=raw_creds["secretAccessKey"],
        aws_session_token=raw_creds["sessionToken"],
        region_name="us-west-2",
    )


def direct_from_s3(stac_items, nasa_creds):
    """Read the rasters using S3 URIs rather than the links in the STAC item
    metadata
    """

    # replace https:// prefixes with s3:// so rasterio will read directly from S3
    for item in stac_items:
        for asset in item.assets.values():
            if asset.href.startswith(HLS_URL_PREFIX):
                asset.href = asset.href.replace(HLS_URL_PREFIX, "s3://")

    with rasterio.Env(session=rasterio.session.AWSSession(**nasa_creds)) as env:
        stackstac.stack(
            stac_items,
            assets=["B04", "B03", "B02"],
            bounds_latlon=BBOX,
            epsg=EPSG,
            resolution=30,
            xy_coords="center",
            gdal_env=stackstac.DEFAULT_GDAL_ENV.updated(
                always=dict(session=env.session)
            ),
        ).compute()

    return


@click.command()
@click.option("--method")
def run(method):
    # find STAC items
    catalog = pystac_client.Client.open("https://cmr.earthdata.nasa.gov/stac/LPCLOUD")

    stac_items = catalog.search(
        collections=[COLLECTION],
        bbox=BBOX,
        datetime=[START_DATE, END_DATE],
    ).item_collection()

    func = None
    if method == "default":
        func = default
        kwargs = {}
    elif method == "direct_from_s3":
        func = direct_from_s3
        kwargs = {"nasa_creds": get_nasa_s3_creds()}

    assert func

    run_time = timeit.timeit(lambda: func(stac_items, **kwargs), number=N_ITERATIONS)
    print(f"average run time: {run_time / N_ITERATIONS}")


if __name__ == "__main__":
    run()
