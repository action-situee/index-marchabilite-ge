import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
import rasterio
from rasterstats import zonal_stats
from shapely import intersection, area, length

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
    zero_for_missing: bool = True,      # True: segments sans match = 0/False
    raster_stats: str = "mean"         # "mean" | "max" | "min" | "sum" | "std" | "count"
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
    if how not in {"presence", "count", "sum", "length_ratio", "area_ratio", "raster"}:
        raise ValueError("how must be 'presence', 'count', 'sum', 'length_ratio', 'area_ratio' or 'raster")
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
    invalid_mask = ~feat.geometry.is_valid
    if invalid_mask.any():
        print(f"Correcting {invalid_mask.sum()} invalid geometries in feature layer using buffer(0).")
        feat.loc[invalid_mask, 'geometry'] = feat.loc[invalid_mask, 'geometry'].buffer(0)


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

        if how == "count":
            agg = (joined.groupby("segment_id")
                         .size()
                         .rename(feature_name)
                         .reset_index())
            out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
            out[feature_name] = out[feature_name].fillna(0).astype(float) if zero_for_missing else out[feature_name]
            return out[["segment_id", feature_name]]

        if how == "sum":
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

    if how == "area_ratio":
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

    # 3) Raster analysis
    if how == "raster":
        if value_column is None:
            raise ValueError("how='raster' requires value_column (e.g. 'temperature')")

        # Spatial join: points inside each buffer
        print("Starting spatial join ...")
        joined = gpd.sjoin(
            seg_buf[["segment_id", "geometry"]],
            feat[["geometry", value_column]],
            how="left",
            predicate="intersects"
        )
        print("Chek in joined is empty...")
        if joined.empty:
            out = seg[["segment_id"]].copy()
            out[feature_name] = 0.0 if zero_for_missing else pd.NA
            return out
        print("Joined is not empty.")
        # Aggregate according to raster_stats
        print("Starting aggregation ...")
        if raster_stats == "mean":
            agg = joined.groupby("segment_id")[value_column].mean()
        else:
            raise ValueError(f"Unsupported raster_stats: {raster_stats}")
        print("Aggregation done.")
        agg = agg.rename(feature_name).reset_index()
        out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")

        if zero_for_missing:
            if raster_stats in {"mean", "max", "min", "sum", "std"}:
                out[feature_name] = out[feature_name].fillna(0.0)
            elif raster_stats == "count":
                out[feature_name] = out[feature_name].fillna(0).astype(int)

        return out[["segment_id", feature_name]]