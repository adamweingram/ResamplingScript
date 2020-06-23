import os
import sys
import click
import copy
from rasterio.enums import Resampling
from rasterio import Affine
from scipy.ndimage import zoom
import numpy as np
import rasterio as rio


def resample_band(dataset: rio.io.DatasetReader,
                  target_resolution: float,
                  resampling_method: Resampling,
                  resampler: str) -> dict:
    """Resample a Band (2D NDArray)

    :param dataset: Input dataset
    :param target_resolution: Resolution of the output dataset: what you want to resample to
    :param resampling_method: Which method to use for resampling (only applicable to rasterio!)
    :param resampler: Which resampling function to use (e.g. Rasterio vs SciPy zoom)
    :return: Dictionary containing resampled data ("data") and the resampled profile ("profile")
    """

    # Calculate scale factor
    scaling = int(dataset.res[0]) / float(target_resolution)

    # Calculate profile and transfor elements
    profile = copy.deepcopy(dataset.profile)
    trans = copy.deepcopy(dataset.transform)
    transform = Affine(trans.a / scaling, trans.b, trans.c, trans.d, trans.e / scaling, trans.f)
    height = copy.deepcopy(dataset.height) * scaling
    width = copy.deepcopy(dataset.width) * scaling
    profile.update(
        res=(float(target_resolution), float(target_resolution)),
        transform=transform,
        height=height,
        width=width
    )

    # Resample data to target resolution
    if resampler is "rasterio":
        print("[INFO] Using Rasterio resampler...")
        resampled = dataset.read(
            out_shape=(
                dataset.count,
                int(height),
                int(width)
            ),
            resampling=resampling_method
        )
    else:
        print("[INFO] Using scipy zoom resampler...")
        print("[WARNING] Zoom resampler does not honor resampling methods! Use the Rasterio resampler for this!")
        raw_read = dataset.read()
        resampled = np.array(list(map(
            lambda layer: zoom(layer, scaling, order=0, mode='nearest'),
            raw_read
        )))

    # Create output dictionary
    output = {
        "data": resampled,
        "profile": profile
    }

    return output


def write_resampled(data: np.ndarray, path: str, profile: rio.profiles.Profile) -> None:
    """Write a Dataset to Disk

    :param data: Dataset to be written
    :param path: Path of the output file
    :param profile: Profile of the dataset
    """

    with rio.open(path.encode('unicode-escape').decode(), 'w', **profile) as dst:
        for band_num, data_arr in enumerate(data, start=1):
            # print("Would have written to band {} in file {}".format(band_num, output_path))
            dst.write_band(band_num, data_arr.astype(rio.uint16))
        print("[INFO] Raster written to {}".format(path))


def load_and_resample(file: str,
                      output_path: str,
                      naming_scheme: str,
                      target_res: int,
                      resampling_method: Resampling,
                      resampler: str) -> list:
    """Load and Resample Raster File

    :param file: Path of input raster data
    :param output_path: Path to write output rasters to
    :param naming_scheme: Base unit of output file names (e.g. "foo" in "foo_104.tiff")
    :param target_res: Resolution to resample to (e.g. "10" for "10 meters")
    :param resampling_method: Which resampling method to use (e.g. nearest-neighbor or bilinear)
    :param resampler: Which resampling function set to use (e.g. Rasterio or SciPy zoom)
    :return: A list of resampled datasets formatted as directories containing data and profiles
    """

    if not os.path.isfile(file):
        print('File ' + file + ' not found.')
        sys.exit()

    with rio.open(file) as raw_ds:
        sds_paths = raw_ds.subdatasets

    resampled_subdatasets = list(map(
        lambda sds: resample_band(
            rio.open(sds),
            float(target_res),
            resampling_method=resampling_method,
            resampler=resampler
        ),
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
            to_create = "/{}/{}_{}.tiff".format(output_path, naming_scheme, ds_num)
            ds_dict["profile"].update(driver="GTiff", dtype=rio.uint16)
            write_resampled(ds_dict["data"], to_create, ds_dict["profile"])

    return resampled_subdatasets


@click.command()
@click.option("--source-path", '-s', required=True, help="Path of source file to resample")
@click.option("--output-path", '-o', required=True, help="Path of the intended output directory")
@click.option("--naming-scheme", '-n',
              required=False,
              default="output",
              help="The 'base' of the filename (e.g. 'foo' in 'foo_1.tiff')"
              )
@click.option("--target-resolution", '-t', required=True, default=10, help="The resolution to resample to")
@click.option('--resampling-method',
              required=False,
              type=click.Choice(['nearest', 'bilinear', 'cubic', 'cubicspline'], case_sensitive=False),
              default='nearest',
              help="Which resampling method to use when resampling. Default is nearest-neighbor."
              )
@click.option('--select-resampler',
              required=False,
              type=click.Choice(['rasterio', 'zoom'], case_sensitive=False),
              default='zoom'
              )
def main(source_path: str,
         output_path: str,
         naming_scheme: str,
         target_resolution: str,
         resampling_method: str,
         select_resampler: str):
    print("[INFO] --- Starting Resample... ---")

    rs_methods = {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
        "cubicspline": Resampling.cubic_spline
    }

    out = load_and_resample(
        file=source_path,
        output_path=output_path,
        naming_scheme=naming_scheme,
        target_res=int(target_resolution),
        resampling_method=rs_methods[resampling_method],
        resampler=select_resampler
    )

    print("[INFO] --- Done. ---")


if __name__ == '__main__':
    main()
