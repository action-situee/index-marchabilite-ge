import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from tqdm import tqdm  # Optional for progress bar

def extract_catchment_feature(segments_gdf, points_gdf, buffer_radius=350, feature_name="catchment_count"):
    """
    Count how many feature buffers (e.g. amenities) contain each street segment centroid.

    Parameters:
    - segments_gdf: GeoDataFrame with segment geometries (must contain 'segment_id').
    - points_gdf: GeoDataFrame of points of interest (e.g. amenities).
    - buffer_radius: Radius in meters for catchment area (default 350m).
    - feature_name: Name of output column with the count.

    Returns:
    - DataFrame with 'segment_id' and count column.
    """

    # Ensure same CRS
    if segments_gdf.crs != points_gdf.crs:
        points_gdf = points_gdf.to_crs(segments_gdf.crs)

    # Step 1: Create catchment areas around each point
    print(f"Buffering {len(points_gdf)} features by {buffer_radius}m...")
    catchments = points_gdf.copy()
    catchments["geometry"] = catchments.buffer(buffer_radius)

    # Step 2: Get midpoints (centroids) of each segment
    print("Extracting segment centroids...")
    centroids = segments_gdf.copy()
    centroids["geometry"] = centroids.geometry.interpolate(0.5, normalized=True)
    centroids = centroids[["segment_id", "geometry"]]

    # Step 3: Spatial join: which centroids fall inside which catchments
    print("Performing spatial join...")
    joined = gpd.sjoin(centroids, catchments[["geometry"]], how="left", predicate="within")

    # Step 4: Count how many catchments each segment is inside
    print("Counting overlaps...")
    count_series = joined.groupby("segment_id").size()

    # Step 5: Merge back with full list (fill 0 if no overlap)
    result = pd.DataFrame({feature_name: count_series}).reset_index()
    result = segments_gdf[["segment_id"]].drop_duplicates().merge(result, on="segment_id", how="left")
    result[feature_name] = result[feature_name].fillna(0).astype(int)

    return result