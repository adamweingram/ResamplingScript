import os
import sys
import fnmatch
import click
import copy
from scipy.ndimage import zoom
from osgeo import gdal
import rasterio as rio
import numpy as np


# from acolite.sentinel import get_rtoa

def resample_band(dataset, target_resolution):
    scaling = int(dataset.res[0]) / float(target_resolution)
    profile = dataset.profile.copy()

    profile.update(
        res=(float(target_resolution), float(target_resolution))
    )

    raw_read = dataset.read()

    resampled = np.array(list(map(
        lambda layer: zoom(layer, scaling, order=0, mode='nearest'),
        raw_read
    )))

    # Calculate Profile Changes
    # transform = dataset.transform * dataset.transform.scale(
    #     (resampled.width / data.shape[-1]),
    #     (resampled.height / data.shape[-2])
    # )

    # Create output dictionary
    output = {
        "data": resampled,
        "profile": profile
    }

    return output


def write_resampled(data, path, profile):
    with rio.open(path.encode('unicode-escape').decode(), 'w', **profile) as dst:
        for band_num, data_arr in enumerate(data, start=1):
            # print("Would have written to band {} in file {}".format(band_num, output_path))
            dst.write_band(band_num, data_arr.astype(rio.uint16))
            print("--- Outputted to {} ---".format(path))


def load_and_resample(file, output_path, target_res=10):
    if not os.path.isfile(file):
        print('File ' + file + ' not found.')
        sys.exit()

    # gdal.UseExceptions()
    # raw_ds = gdal.Open(file)
    # datasets = raw_ds.GetSubdatasets()

    with rio.open(file) as raw_ds:
        sds_paths = raw_ds.subdatasets

    # WARNING In its current implementation, this using a spline interpolation approach to resampling!
    # Note In the original code, the sds resolution was bing divided by the target res. This is required
    # because we're rescaling the bounds of the image, NOT THE PIXELS THEMSELVES! Therefore, the operation
    # is essentially the inverse of the naive approach.
    resampled_subdatasets = list(map(
        lambda sds: resample_band(rio.open(sds), float(10.0)),
        sds_paths
    ))

    # New instance of GDAL/Rasterio
    with rio.Env():
        # Write an array as a raster band to a new 8-bit file. For
        # the new file's profile, we start with the profile of the source
        # profile = src.profile

        # if len(resampled_subdatasets) > 0:
        #     all_profile = resampled_subdatasets[0]["profile"]
        #     all_profile.update(
        #         driver="GTiff",
        #         count=len(resampled_subdatasets)
        #     )
        # else:
        #     raise RuntimeError("No resampled datasets returned! Check your script!")

            # Read each resampled band and write it to stack
        for ds_num, ds_dict in enumerate(resampled_subdatasets):
            to_create = "/{}/test_{}.tiff".format(output_path, ds_num)
            ds_dict["profile"].update(driver="GTiff", dtype=rio.uint16)
            write_resampled(ds_dict["data"], to_create, ds_dict["profile"])

    return resampled_subdatasets


@click.command()
@click.option("--source-path", '-s', required=True, help="Path of source file to resample")
@click.option("--output-path", '-o', required=True, help="Path of the intended output file")
def main(source_path, output_path):
    out = load_and_resample(source_path, output_path, target_res=10)
    print("Done.")


if __name__ == '__main__':
    main()
