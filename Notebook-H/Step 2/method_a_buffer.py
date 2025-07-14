import geopandas as gpd



def extract_buffer_feature(segments_gdf, feature_gdf, feature_name, buffer_radius=30, how='count', value_column=None):

    """
    Extracts a buffer-based feature (Method A) for each segment.
    
    Parameters:
    - segments_gdf: GeoDataFrame of street segments with unique ID.
    - feature_gdf: GeoDataFrame of points or polygons to count (e.g., lights, benches).
    - feature_name: name of the new column to be added (e.g., 'lighting_count').
    - buffer_radius: buffer distance around segments (in meters).
    - how: 'count' or 'presence' for binary presence.
    - value_column: name of the column to aggregate on if using "sum"
    
    Returns:
    - DataFrame with 'segment_id' and new feature column.
    """

    # Ensure both are in the same CRS
    if segments_gdf.crs != feature_gdf.crs:
        feature_gdf = feature_gdf.to_crs(segments_gdf.crs)

    # Buffer the segments
    segments_buffered = segments_gdf.copy()
    segments_buffered["geometry"] = segments_buffered.buffer(buffer_radius)

    # Spatial join to count how many features fall into each buffer
    joined = gpd.sjoin(feature_gdf, segments_buffered[["segment_id", "geometry"]], how="inner", predicate="intersects")

    # Aggregate
    if how == "presence":
        feature_stats = joined.groupby("segment_id").size().gt(0).astype(int).reset_index(name=feature_name)
    elif how == "sum" and value_column:
        feature_stats = joined.groupby("segment_id")[value_column].sum().reset_index(name=feature_name)    
    else:
        feature_stats = joined.groupby("segment_id").size().reset_index(name=feature_name)

    return feature_stats

