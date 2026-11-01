import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from src.spatial_integration import _validate_spatial_result


def _spatial(geometry):
    rows = 735
    return gpd.GeoDataFrame(
        {"boundary_fid": range(rows)},
        geometry=[geometry] * rows,
        crs="EPSG:4326",
    ).rename_geometry("geom")


def test_valid_full_boundary_result_passes():
    valid_polygon = Polygon(
        [(0, 0), (1, 0), (1, 1), (0, 0)]
    )
    _validate_spatial_result(_spatial(valid_polygon))


def test_invalid_geometry_is_rejected():
    invalid_polygon = Polygon(
        [(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)]
    )
    with pytest.raises(ValueError, match="invalid geometries"):
        _validate_spatial_result(_spatial(invalid_polygon))
