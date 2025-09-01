import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

def extract_buffer_feature(
    segments_gdf: gpd.GeoDataFrame,
    feature_gdf: gpd.GeoDataFrame,
    feature_name: str,
    *,
    geom_kind: str,                    # "point" | "line" | "polygon"
    how: str,                          # "presence" | "count" | "sum" | "length_ratio" | "area_ratio"
    buffer_radius: float = 50.0,
    value_column: str | None = None,   # utilisé si how="sum"
    crs_meter_epsg: int | None = None, # ex. 2056
    predicate: str | None = None,      # None => choix par défaut adapté au type
    feature_query: str | None = None,  # ex: "OBJET == 'fontaine'"
    segment_length_col: str | None = None,  # si déjà calculée (ex. "length_m")
    zero_for_missing: bool = True      # True: segments sans match = 0/False
) -> pd.DataFrame:
    """
    Calcule un indicateur local pour chaque segment en fonction d'une couche de points/lignes/polygones.

    - presence: booléen (au moins un objet intersecte le buffer)
    - count: nombre d'objets dans le buffer
    - sum: somme d'une colonne numérique (value_column) pour les objets dans le buffer
    - length_ratio (geom_kind='line'):  sum(length(layer ∩ buffer)) / length(segment)
    - area_ratio   (geom_kind='polygon'): sum(area(layer ∩ buffer)) / area(buffer)

    Retour: DataFrame ["segment_id", feature_name]
    """

    if geom_kind not in {"point", "line", "polygon"}:
        raise ValueError("geom_kind must be 'point', 'line', or 'polygon'")
    if how not in {"presence", "count", "sum", "length_ratio", "area_ratio"}:
        raise ValueError("how must be 'presence', 'count', 'sum', 'length_ratio', or 'area_ratio'")
    if how == "length_ratio" and geom_kind != "line":
        raise ValueError("length_ratio requires geom_kind='line'")
    if how == "area_ratio" and geom_kind != "polygon":
        raise ValueError("area_ratio requires geom_kind='polygon'")
    if how == "sum" and not value_column:
        raise ValueError("how='sum' requires value_column")

    # Sélection du prédicat par défaut
    if predicate is None:
        predicate = "intersects"

    seg = segments_gdf[["segment_id", "geometry"]].copy()
    feat = feature_gdf.copy()

    # Filtre optionnel de la couche
    if feature_query:
        feat = feat.query(feature_query)

    # CRS métrique
    if crs_meter_epsg is not None:
        if seg.crs is None or not seg.crs.is_projected:
            seg = seg.to_crs(crs_meter_epsg)
        if feat.crs is None or feat.crs != seg.crs:
            feat = feat.to_crs(seg.crs)
    elif seg.crs is None or not seg.crs.is_projected:
        raise ValueError("Segments must be in a projected CRS (meters) or pass crs_meter_epsg.")

    # Longueur segment si besoin
    if segment_length_col and segment_length_col in segments_gdf.columns:
        seg = seg.merge(segments_gdf[["segment_id", segment_length_col]], on="segment_id", how="left")
        seg_len_col = segment_length_col
    else:
        seg["_seg_len"] = seg.geometry.length
        seg_len_col = "_seg_len"

    # Construire buffers
    seg_buf = seg.copy()
    seg_buf["geometry"] = seg_buf.geometry.buffer(buffer_radius)
    if how == "area_ratio":
        seg_buf["_buf_area"] = seg_buf.geometry.area

    # Nettoyage géometries invalides
    if not feat.geometry.is_valid.all():
        feat = feat.set_geometry(feat.geometry.buffer(0))

    # 1) Cas simples: presence / count / sum  (vectorisé via sjoin)
    if how in {"presence", "count", "sum"}:
        # pour sum, on a besoin de la colonne de valeur dans le join
        right_cols = ["geometry"] if how in {"presence", "count"} else ["geometry", value_column]
        joined = gpd.sjoin(
            seg_buf[["segment_id", "geometry"]],
            feat[right_cols],
            how="inner",
            predicate=predicate
        )

        if how == "presence":
            agg = joined[["segment_id"]].drop_duplicates().assign(**{feature_name: 1})
            out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
            out[feature_name] = out[feature_name].fillna(0).astype(int) if zero_for_missing else out[feature_name]
            return out[["segment_id", feature_name]]

        if how == "count":
            agg = (joined.groupby("segment_id")
                         .size()
                         .rename(feature_name)
                         .reset_index())
            out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
            out[feature_name] = out[feature_name].fillna(0).astype(float) if zero_for_missing else out[feature_name]
            return out[["segment_id", feature_name]]

        # how == "sum"
        # sécurité: convertir en numérique (coerce -> NaN) puis sommer
        joined[value_column] = pd.to_numeric(joined[value_column], errors="coerce")
        agg = (joined.groupby("segment_id")[value_column]
                     .sum(min_count=1)  # NaN si aucun num valide
                     .rename(feature_name)
                     .reset_index())
        out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
        out[feature_name] = out[feature_name].fillna(0.0) if zero_for_missing else out[feature_name]
        return out[["segment_id", feature_name]]

    # 2) Ratios: length_ratio (lines) / area_ratio (polygons)
    # Pré-filtrage spatial pour limiter overlay
    joined = gpd.sjoin(
        seg_buf[["segment_id", "geometry"]],
        feat[["geometry"]],
        how="inner",
        predicate=predicate
    )
    if joined.empty:
        out = seg[["segment_id"]].copy()
        out[feature_name] = 0.0 if zero_for_missing else pd.NA
        return out

    # Overlay pour obtenir l'intersection géométrique exacte
    buf_for_overlay = gpd.GeoDataFrame(joined[["segment_id", "geometry"]], geometry="geometry", crs=seg_buf.crs)
    inter = gpd.overlay(buf_for_overlay, feat[["geometry"]], how="intersection", keep_geom_type=False)

    if inter.empty:
        out = seg[["segment_id"]].copy()
        out[feature_name] = 0.0 if zero_for_missing else pd.NA
        return out

    if how == "length_ratio":
        inter["_val"] = inter.length
        length_sum = (inter.groupby("segment_id")["_val"]
                           .sum()
                           .rename("_len_in_buf")
                           .reset_index())
        out = seg[["segment_id", seg_len_col]].merge(length_sum, on="segment_id", how="left")
        out["_len_in_buf"] = out["_len_in_buf"].fillna(0.0)
        out[feature_name] = out["_len_in_buf"] / out[seg_len_col].replace({0: pd.NA})
        out[feature_name] = out[feature_name].fillna(0.0) if zero_for_missing else out[feature_name]
        return out[["segment_id", feature_name]]

    # how == "area_ratio"
    inter["_val"] = inter.area
    area_sum = (inter.groupby("segment_id")["_val"]
                       .sum()
                       .rename("_area_in_buf")
                       .reset_index())
    out = seg_buf[["segment_id", "_buf_area"]].merge(area_sum, on="segment_id", how="left")
    out["_area_in_buf"] = out["_area_in_buf"].fillna(0.0)
    out[feature_name] = out["_area_in_buf"] / out["_buf_area"].replace({0: pd.NA})
    out[feature_name] = out[feature_name].fillna(0.0) if zero_for_missing else out[feature_name]
    return out[["segment_id", feature_name]]


# import geopandas as gpd

# def extract_buffer_feature(segments_gdf, feature_gdf, feature_name, buffer_radius=30, how='count', value_column=None):

#     """
#     Extracts a buffer-based feature (Method A) for each segment.
    
#     Parameters:
#     - segments_gdf: GeoDataFrame of street segments with unique ID.
#     - feature_gdf: GeoDataFrame of points or polygons to count (e.g., lights, benches).
#     - feature_name: name of the new column to be added (e.g., 'lighting_count').
#     - buffer_radius: buffer distance around segments (in meters).
#     - how: 'count' or 'presence' for binary presence.
#     - value_column: name of the column to aggregate on if using "sum"
    
#     Returns:
#     - DataFrame with 'segment_id' and new feature column.
#     """

#     # Ensure both are in the same CRS
#     if segments_gdf.crs != feature_gdf.crs:
#         feature_gdf = feature_gdf.to_crs(segments_gdf.crs)

#     # Buffer the segments
#     segments_buffered = segments_gdf.copy()
#     segments_buffered["geometry"] = segments_buffered.buffer(buffer_radius)

#     # Spatial join to count how many features fall into each buffer
#     joined = gpd.sjoin(segments_buffered[["segment_id", "geometry"]], feature_gdf, how="left", predicate="intersects")

#     # Aggregate
#     if how == "presence":
#         feature_stats = joined.groupby("segment_id").size().gt(0).astype(int).reset_index(name=feature_name)
#     elif how == "sum" and value_column:
#         feature_stats = joined.groupby("segment_id")[value_column].sum().reset_index(name=feature_name)    
#     elif how == "count":
#         feature_stats = joined.groupby("segment_id").size().reset_index(name=feature_name)
#     else:
#         raise ValueError("Invalid 'how' parameter. Use 'count', 'presence', or 'sum' with value_column.")

#     return feature_stats


# V1 sans STRtree
# import geopandas as gpd
# import pandas as pd

# def extract_buffer_feature(
#     segments_gdf,
#     feature_gdf,
#     feature_name,
#     buffer_radius=30,
#     how='count',
#     value_column=None,
#     geometry_type="point"  # "point", "linestring", "polygon"
# ):
#     """
#     Extracts a buffer-based feature (Method A) for each segment.

#     Parameters:
#     - segments_gdf: GeoDataFrame of street segments with unique ID.
#     - feature_gdf: GeoDataFrame of points, lines or polygons to count or aggregate.
#     - feature_name: name of the new column to be added (e.g., 'lighting_count').
#     - buffer_radius: buffer distance around segments (in meters).
#     - how: 'count', 'presence', 'sum' (with value_column), or 'ratio' (for polygons).
#     - value_column: name of the column to aggregate on if using "sum"
#     - geometry_type: "point", "linestring", or "polygon"

#     Returns:
#     - DataFrame with 'segment_id' and new feature column.
#     """

#     # Ensure both are in the same CRS
#     if segments_gdf.crs != feature_gdf.crs:
#         feature_gdf = feature_gdf.to_crs(segments_gdf.crs)

#     # Buffer the segments
#     segments_buffered = segments_gdf.copy()
#     segments_buffered["geometry"] = segments_buffered.buffer(buffer_radius)

#     print("Invalid buffers:", segments_buffered[~segments_buffered.is_valid])
#     print("Invalid features:", feature_gdf[~feature_gdf.is_valid])

#     # Juste après le buffer :
#     segments_buffered["geometry"] = segments_buffered["geometry"].apply(lambda geom: geom.buffer(0) if not geom.is_valid else geom)
#     feature_gdf["geometry"] = feature_gdf["geometry"].apply(lambda geom: geom.buffer(0) if not geom.is_valid else geom)

#     # Spatial join
#     joined = gpd.sjoin(
#         segments_buffered[["segment_id", "geometry"]],
#         feature_gdf,
#         how="left",
#         predicate="intersects"
#     )

#     # Traitement selon le type de géométrie et la méthode demandée
#     if geometry_type == "polygon" and how == "ratio":
#         # Calculer l'aire du buffer pour chaque segment
#         buffer_area = segments_buffered.set_index("segment_id")["geometry"].area

#         # Récupérer la géométrie du buffer et de la feature pour chaque ligne jointe
#         joined = joined.rename(columns={"geometry": "buffer_geom", "index_right": "feature_idx"})
#         feature_geom_map = feature_gdf.geometry.reset_index(drop=True)
#         joined["feature_geom"] = joined["feature_idx"].apply(
#             lambda idx: feature_geom_map.iloc[int(idx)] if pd.notnull(idx) else None
#         )

#         # Calcul de l'intersection
#         joined["intersection"] = joined.apply(
#             lambda row: row["buffer_geom"].intersection(row["feature_geom"]) if row["feature_geom"] is not None else None,
#             axis=1
#         )
#         joined["intersect_area"] = joined["intersection"].area

#         # Agréger la surface d'intersection par segment
#         intersect_sum = joined.groupby("segment_id")["intersect_area"].sum().fillna(0)

#         # Calculer le ratio
#         ratio = (intersect_sum / buffer_area).fillna(0).reset_index(name=feature_name)
#         feature_stats = ratio

#     elif how == "presence":
#         feature_stats = joined.groupby("segment_id").size().gt(0).astype(int).reset_index(name=feature_name)
#     elif how == "sum" and value_column:
#         feature_stats = joined.groupby("segment_id")[value_column].sum().reset_index(name=feature_name)
#     elif how == "count":
#         feature_stats = joined.groupby("segment_id").size().reset_index(name=feature_name)
#     else:
#         raise ValueError(
#             "Invalid combination: "
#             "For geometry_type='polygon', use how='ratio', 'count', 'sum', or 'presence'. "
#             "For geometry_type='point' or 'linestring', use how='count', 'sum', or 'presence'."
#         )

#     return feature_stats



# V2 avec STRtree
# import geopandas as gpd
# import pandas as pd
# from shapely.strtree import STRtree

# def extract_buffer_feature(
#     segments_gdf,
#     feature_gdf,
#     feature_name,
#     buffer_radius=30,
#     how='count',
#     value_column=None,
#     geometry_type="point"  # "point", "linestring", "polygon"
# ):
#     """
#     Extracts a buffer-based feature (Method A) for each segment.

#     Parameters:
#     - segments_gdf: GeoDataFrame of street segments with unique ID.
#     - feature_gdf: GeoDataFrame of points, lines or polygons to count or aggregate.
#     - feature_name: name of the new column to be added (e.g., 'lighting_count').
#     - buffer_radius: buffer distance around segments (in meters).
#     - how: 'count', 'presence', 'sum' (with value_column), or 'ratio' (for polygons).
#     - value_column: name of the column to aggregate on if using "sum"
#     - geometry_type: "point", "linestring", or "polygon"

#     Returns:
#     - DataFrame with 'segment_id' and new feature column.
#     """

#     # CRS
#     if segments_gdf.crs != feature_gdf.crs:
#         feature_gdf = feature_gdf.to_crs(segments_gdf.crs)

#     # Buffer and clean geometry
#     segments_buffered = segments_gdf[["segment_id", "geometry"]].copy()
#     segments_buffered["geometry"] = segments_buffered["geometry"].buffer(buffer_radius)
#     segments_buffered["geometry"] = segments_buffered["geometry"].apply(lambda geom: geom.buffer(0) if not geom.is_valid else geom)
#     feature_gdf = feature_gdf[["geometry"]].copy()
#     feature_gdf["geometry"] = feature_gdf["geometry"].apply(lambda geom: geom.buffer(0) if not geom.is_valid else geom)

#     if geometry_type == "polygon" and how == "ratio":
#         # Spatial index sur les features
#         feature_geoms = feature_gdf.geometry.values
#         tree = STRtree(feature_geoms)

#         # Calcul du ratio de couverture pour chaque buffer
#         def coverage_ratio(buffer_geom):
#             candidates = [geom for geom in tree.query(buffer_geom) if geom is not None and hasattr(geom, "area")]
#             intersect_area = sum(
#                 buffer_geom.intersection(geom).area
#                 for geom in candidates
#                 if buffer_geom.is_valid and geom.is_valid and buffer_geom.intersects(geom)
#             )
#             return intersect_area

#         buffer_area = segments_buffered.set_index("segment_id")["geometry"].area
#         segments_buffered["intersect_area"] = segments_buffered["geometry"].apply(coverage_ratio)
#         ratio = (segments_buffered["intersect_area"] / buffer_area).fillna(0).reset_index()
#         ratio.columns = ["segment_id", feature_name]
#         feature_stats = ratio

#     else:
#         # Spatial join optimisé (colonnes minimales)
#         joined = gpd.sjoin(
#             segments_buffered,
#             feature_gdf,
#             how="left",
#             predicate="intersects"
#         )

#         if how == "presence":
#             feature_stats = joined.groupby("segment_id").size().gt(0).astype(int).reset_index(name=feature_name)
#         elif how == "sum" and value_column:
#             feature_stats = joined.groupby("segment_id")[value_column].sum().reset_index(name=feature_name)
#         elif how == "count":
#             feature_stats = joined.groupby("segment_id").size().reset_index(name=feature_name)
#         else:
#             raise ValueError(
#                 "Invalid combination: "
#                 "For geometry_type='polygon', use how='ratio', 'count', 'sum', or 'presence'. "
#                 "For geometry_type='point' or 'linestring', use how='count', 'sum', or 'presence'."
#             )

#     return feature_stats