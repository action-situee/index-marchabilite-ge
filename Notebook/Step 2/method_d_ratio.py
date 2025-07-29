

import geopandas as gpd
import pandas as pd

def ratio_by_surface_type(segments_gdf, attribute_gdf, buffer_radius=100, value_column="OBJET", min_area=1):
    """
    Assigns to each segment the ratio of surface types (e.g., 't', 'c') within a buffer around the segment.

    Parameters:
    - segments_gdf: GeoDataFrame of line segments.
    - attribute_gdf: GeoDataFrame of polygon surfaces with surface type column.
    - buffer_radius: Buffer radius around segments (in meters).
    - value_column: Column in attribute_gdf indicating surface type (e.g., 'OBJET').
    - min_area: Minimum area threshold to keep surface polygons.

    Returns:
    - GeoDataFrame with added columns for area ratios (e.g., 'ratio_trottoir', 'ratio_chaussée') and surface areas.
    """

    lines = segments_gdf.copy()
    surfaces = attribute_gdf.copy()

    print(f"{len(lines)} lignes chargées")
    print(f"{len(surfaces)} surfaces chargées")

    # Clean geometries
    surfaces = surfaces[surfaces.is_valid & surfaces.geometry.notnull()]
    surfaces = surfaces[surfaces.geometry.area > min_area]

    # Create buffer around lines
    if not lines.empty:
        lines = lines.reset_index(drop=True).reset_index().rename(columns={"index": "line_index"})
        lines["buffer"] = lines.geometry.buffer(buffer_radius)
        lines_buffered = lines.set_geometry("buffer")
    else:
        print("Pas de lignes dans la zone, skip buffer")
        return lines  # return unchanged if empty

    # Intersect buffers with surfaces
    print("Calcul de l’intersection entre surfaces et buffers de lignes…")
    if not lines_buffered.empty and not surfaces.empty:
        intersected = gpd.overlay(surfaces, lines_buffered, how="intersection")
        intersected["area"] = intersected.geometry.area
    else:
        print("Intersection non réalisée : une des couches est vide")
        return lines.set_geometry("geometry").drop(columns="buffer", errors="ignore")

    # Aggregate surface areas by line and surface type
    print("Agrégation des surfaces par tronçon…")
    intersected = intersected[intersected["area"] > 0]
    grouped = intersected.groupby(["line_index", value_column])["area"].sum().unstack(fill_value=0).reset_index()

    # Total and ratios
    grouped["total"] = grouped.drop(columns=["line_index"]).sum(axis=1)
    if "t" in grouped.columns:
        grouped["ratio_trottoir"] = grouped["t"] / grouped["total"]
    if "c" in grouped.columns:
        grouped["ratio_chaussée"] = grouped["c"] / grouped["total"]

    # Merge with original segments
    print("Fusion avec les données linéaires originales…")
    lines = lines.merge(grouped, on="line_index", how="left")
    lines = lines.set_geometry("geometry").drop(columns="buffer", errors="ignore")

    return lines
