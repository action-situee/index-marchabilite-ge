import geopandas as gpd
import pandas as pd
import numpy as np
from tqdm import tqdm

def compute_zonal_stat(segments_gdf, features_gdf, buffer_radius=15, value_column=None, stat="mean", segment_id_col="segment_id"):
    """
    Compute zonal statistics (mean, sum, etc.) of attribute values from feature layer within a buffer around network segments.

    Parameters:
    - segments_gdf: GeoDataFrame with segment geometries and unique ID.
    - features_gdf: GeoDataFrame with vector "pixels" or features (points or polygons) with values.
    - buffer_radius: Radius (in meters) for buffer around each segment.
    - value_column: Column in features_gdf to compute statistics on.
    - stat: Which statistic to compute: 'mean', 'sum', 'median', 'std', or 'count'.
    - segment_id_col: Unique ID column in segments_gdf.

    Returns:
    - DataFrame with segment_id and computed statistic.
    """

    results = []
    
    # Ensure same CRS
    if segments_gdf.crs != features_gdf.crs:
        features_gdf = features_gdf.to_crs(segments_gdf.crs)

    for _, row in tqdm(segments_gdf.iterrows(), total=len(segments_gdf)):
        segment_id = row[segment_id_col]
        buffer_geom = row.geometry.buffer(buffer_radius)

        # Find intersecting features
        within = features_gdf[features_gdf.intersects(buffer_geom)]

        if len(within) == 0:
            value = np.nan
        else:
            if stat == "count":
                value = len(within)
            elif value_column is not None:
                values = within[value_column].dropna()
                if values.empty:
                    value = np.nan
                elif stat == "mean":
                    value = values.mean()
                elif stat == "sum":
                    value = values.sum()
                elif stat == "median":
                    value = values.median()
                elif stat == "std":
                    value = values.std()
                elif stat == "max":
                    value = values.max()
                else:
                    raise ValueError(f"Unsupported stat: {stat}")
            else:
                raise ValueError("value_column is required for stat other than 'count'.")

        results.append({segment_id_col: segment_id, f"zonal_{stat}": value})

    return pd.DataFrame(results)
