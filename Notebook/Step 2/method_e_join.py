import geopandas as gpd
import pandas as pd
from tqdm import tqdm

def spatial_join_maxoverlap(segments_gdf, attribute_gdf, value_column, segment_id_col="segment_id", feature_name=None):
    """
    Assigns zone type to segments based on which zone contains the largest portion of each segment.
    
    Parameters:
    -----------
    segments_gdf : GeoDataFrame
        The 50m road segments
    attribute_gdf : GeoDataFrame
        The speed zone polygons
    value_column : str
        Name of column containing zone type (e.g. 'TYPE_ZONE')
    segment_id_col : str
        Name of segment ID column
    feature_name : str
        Output column name
        
    Returns:
    --------
    GeoDataFrame with segment IDs and their assigned zone types
    """
    # Ensure CRS match
    if segments_gdf.crs != attribute_gdf.crs:
        attribute_gdf = attribute_gdf.to_crs(segments_gdf.crs)

    # First try direct spatial join with 'within'
    joined = gpd.sjoin(
        segments_gdf[[segment_id_col, 'geometry']], 
        attribute_gdf[[value_column, 'geometry']],
        how="left",
        predicate="within"
    )

    # For segments that cross zone boundaries, compute overlap
    if joined[value_column].isna().any():
        # Get segments without a zone assignment
        missing_segments = segments_gdf[
            ~segments_gdf[segment_id_col].isin(
                joined[~joined[value_column].isna()][segment_id_col]
            )
        ]
        
        # For these segments, intersect with zones and take the one with max overlap
        for idx, segment in missing_segments.iterrows():
            # Find intersecting zones
            intersecting = attribute_gdf[attribute_gdf.intersects(segment.geometry)]
            if len(intersecting) > 0:
                # Calculate overlap lengths
                overlaps = [(
                    zone[value_column],
                    segment.geometry.intersection(zone.geometry).length
                ) for _, zone in intersecting.iterrows()]
                
                # Take zone with maximum overlap
                max_zone = max(overlaps, key=lambda x: x[1])[0]
                
                # Assign to joined DataFrame
                joined.loc[joined[segment_id_col] == segment[segment_id_col], value_column] = max_zone

    # Prepare output
    col_name = feature_name if feature_name else value_column
    result = (
        joined[[segment_id_col, value_column]]
        .rename(columns={value_column: col_name})
    )
    
    return result