import os
import sys
import click
import copy
from rasterio.enums import Resampling
from rasterio import Affine
import rasterio as rio


def resample_band(dataset, target_resolution, resampling_method):
    scaling = int(dataset.res[0]) / float(target_resolution)

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

    # resample data to target shape
    resampled = dataset.read(
        out_shape=(
            dataset.count,
            int(height),
            int(width)
        ),
        resampling=resampling_method
    )

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
        print("[INFO] Raster written to {}".format(path))


def load_and_resample(file, output_path, naming_scheme, target_res, resampling_method):
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
        lambda sds: resample_band(rio.open(sds), float(target_res), resampling_method=resampling_method),
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
@click.option('--resamping-method',
              required=False,
              type=click.Choice(['nearest', 'bilinear', 'cubic', 'cubicspline'], case_sensitive=False),
              default=Resampling.nearest,
              help="Which resampling method to use when resampling. Default is nearest-neighbor."
              )
def main(source_path, output_path, naming_scheme, target_resolution, resampling_method):
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
        resampling_method=rs_methods[resampling_method]
    )

    print("[INFO] --- Done. ---")


if __name__ == '__main__':
    main()
