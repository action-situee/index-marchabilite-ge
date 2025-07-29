import geopandas as gpd
import pandas as pd
from tqdm import tqdm

def spatial_join_maxoverlap(segments_gdf, attribute_gdf, value_column, segment_id_col="segment_id", feature_name=None):
    """
    Assigns to each segment the value of the zone (polygon) that overlaps the most.

    Uses sjoin for speed, then filters to keep only the dominant (max overlap) zone per segment.

    Parameters:
    - segments_gdf: GeoDataFrame of segments with unique ID.
    - attribute_gdf: GeoDataFrame of polygons with a value column (e.g., vitesse).
    - segment_id_col: Column name for the unique segment ID.
    - value_column: Column in attribute_gdf to assign.
    - feature_name: Desired output column name (str).

    Returns:
    - DataFrame with segment_id and dominant zone value.
    """

    # Ensure CRS match
    if segments_gdf.crs != attribute_gdf.crs:
        attribute_gdf = attribute_gdf.to_crs(segments_gdf.crs)

    # Ensure valid geometries
    segments_gdf = segments_gdf[segments_gdf.is_valid]
    attribute_gdf = attribute_gdf[attribute_gdf.is_valid]

    # Spatial join: all intersecting zones
    joined = gpd.sjoin(
        segments_gdf[[segment_id_col, 'geometry']], 
        attribute_gdf[[value_column, 'geometry']],
        how="left",
        predicate="intersects"
    )

    # For segments with NaN, try 'within'
    missing = joined[joined[value_column].isna()][segment_id_col]
    if not missing.empty:
        missing_segments = segments_gdf[segments_gdf[segment_id_col].isin(missing)]
        joined_within = gpd.sjoin(
            missing_segments[[segment_id_col, 'geometry']],
            attribute_gdf[[value_column, 'geometry']],
            how="left",
            predicate="within"
        )
        # Fill missing values
        joined.loc[joined[segment_id_col].isin(missing), value_column] = joined_within[value_column].values


    # Compute overlap geometries (with tqdm for progress)
    tqdm.pandas(desc="Computing overlaps")
    # Compute overlap geometries
    joined["overlap_geom"] = joined.apply(
        lambda row: row.geometry.intersection(attribute_gdf.loc[row["index_right"]].geometry)
        if pd.notnull(row["index_right"]) else None,
        axis=1
    )
    joined = joined[joined["overlap_geom"].notnull()].copy()
    joined["overlap_area"] = joined["overlap_geom"].area

    # Find the zone with the largest overlap for each segment
    col_name = feature_name if feature_name else value_column
    dominant = (
        joined.loc[joined.groupby(segment_id_col)["overlap_area"].idxmax()]
        [[segment_id_col, value_column]]
        .rename(columns={value_column: col_name})
        .reset_index(drop=True)
    )

    # Merge back to segments_gdf to ensure all segments are present
    result = segments_gdf[[segment_id_col]].merge(dominant, on=segment_id_col, how="left")
    return result