"""
Module: prepare_features
Calcule les attributs/features pour chaque segment du réseau piéton.
"""
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import ast
from pathlib import Path
from shapely import area as shp_area, length as shp_length, intersection as shp_intersection, make_valid as shp_make_valid
from shapely.geometry import Point, box
import networkx as nx


def _is_nan_like(value) -> bool:
    try:
        return pd.isna(value)
    except Exception:
        return False


def make_feature_query(filter_column, filter_values):
    if not filter_column or _is_nan_like(filter_column) or filter_values is None or _is_nan_like(filter_values):
        return None
    column = str(filter_column).strip()
    if column == "":
        return None
    if isinstance(filter_values, (list, tuple, set, np.ndarray)):
        return f"`{column}` in {repr(list(filter_values))}"
    if isinstance(filter_values, str):
        candidate = filter_values.strip()
        if candidate == "":
            return None
        lowered = candidate.lower()
        if lowered in ("true", "false"):
            return f"`{column}` == {lowered == 'true'}"
        if candidate.startswith("[") and candidate.endswith("]"):
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, (list, tuple)):
                    return f"`{column}` in {repr(list(parsed))}"
            except Exception:
                pass
        try:
            if "." in candidate or "e" in lowered:
                num = float(candidate)
            else:
                num = int(candidate)
            return f"`{column}` == {num}"
        except Exception:
            return f"`{column}` == {repr(candidate)}"
    if isinstance(filter_values, (bool, int, float, np.integer, np.floating)):
        return f"`{column}` == {filter_values}"
    return f"`{column}` == {repr(str(filter_values))}"


def _resolve_attribute_file(base_dir: Path, source_dir: str | None, file_name: str | None) -> Path:
    base = Path(base_dir)
    if not file_name:
        raise FileNotFoundError("Nom de fichier manquant pour l'attribut.")
    rel = Path(str(source_dir).strip()) if source_dir and not _is_nan_like(source_dir) else Path()
    if not rel.is_absolute():
        rel = (base / rel).resolve()
    if rel.is_dir():
        candidate = rel / file_name
    else:
        candidate = rel
        if rel.name != file_name:
            candidate = rel / file_name
    return candidate


def _load_attribute_layer(base_dir: Path, row, target_crs):
    file_name = row.get('file_name')
    if _is_nan_like(file_name):
        return None
    path = _resolve_attribute_file(base_dir, row.get('attribute_source_path'), file_name)
    if not path.exists():
        return None
    ext = path.suffix.lower()
    if ext == '.parquet':
        layer = gpd.read_parquet(path)
    else:
        layer = gpd.read_file(path)
    declared_crs = row.get('crs')
    if layer.crs is None and not _is_nan_like(declared_crs):
        try:
            layer = layer.set_crs(f"EPSG:{int(declared_crs)}")
        except Exception:
            pass
    if target_crs:
        layer = layer.to_crs(target_crs)
    return layer


def extract_buffer_feature(
    segments_gdf,
    feature_gdf,
    feature_name,
    *,
    geom_kind,
    how,
    buffer_radius=50.0,
    value_column=None,
    crs_meter_epsg=None,
    predicate=None,
    feature_query=None,
    segment_length_col=None,
    zero_for_missing=True,
    raster_stats="mean",
    buffer_resolution=8,
):
    if geom_kind not in {"point", "line", "polygon"}:
        raise ValueError("geom_kind must be 'point', 'line', or 'polygon'")
    if how not in {"presence", "count", "sum", "mean", "length_ratio", "area_ratio", "length_area_ratio", "raster"}:
        raise ValueError("Unsupported aggregation mode.")
    if how == "length_ratio" and geom_kind != "line":
        raise ValueError("length_ratio requires line geometries.")
    if how == "area_ratio" and geom_kind != "polygon":
        raise ValueError("area_ratio requires polygon geometries.")
    if how in {"sum", "mean", "raster"} and not value_column:
        raise ValueError(f"how='{how}' requires value_column.")
    if predicate is None:
        predicate = "intersects"

    seg = segments_gdf[["segment_id", "geometry"]].copy()
    feat = feature_gdf.copy()

    if feature_query:
        try:
            feat = feat.query(feature_query)
        except Exception:
            pass

    if crs_meter_epsg is not None:
        if seg.crs is None or not seg.crs.is_projected or seg.crs.to_epsg() != crs_meter_epsg:
            seg = seg.to_crs(crs_meter_epsg)
        if feat.crs is None or feat.crs != seg.crs:
            feat = feat.to_crs(seg.crs)
    elif seg.crs is None or not seg.crs.is_projected:
        raise ValueError("Segments must be projected or crs_meter_epsg must be provided.")

    if segment_length_col and segment_length_col in segments_gdf.columns:
        seg = seg.merge(segments_gdf[["segment_id", segment_length_col]], on="segment_id", how="left")
        seg_len = seg[segment_length_col].to_numpy()
    else:
        seg_len = seg.geometry.length.to_numpy()

    seg_buf_geom = seg.geometry.buffer(buffer_radius, resolution=buffer_resolution)
    buf_area = seg_buf_geom.area.to_numpy()

    if not feat.geometry.is_valid.all():
        feat["geometry"] = shp_make_valid(feat.geometry.values)

    if how in {"presence", "count", "sum", "mean"}:
        right_cols = ["geometry"] if how in {"presence", "count"} else ["geometry", value_column]
        left = gpd.GeoDataFrame(seg[["segment_id"]].copy(), geometry=seg_buf_geom, crs=seg.crs)
        joined = gpd.sjoin(left, feat[right_cols], how="inner", predicate=predicate)
        if joined.empty:
            out = seg[["segment_id"]].copy()
            out[feature_name] = 0 if how == "presence" else 0.0
            return out
        if how == "presence":
            agg = (joined.groupby("segment_id").size().gt(0).astype(int)
                   .rename(feature_name).reset_index())
            out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
            out[feature_name] = out[feature_name].fillna(0).astype(int)
            return out
        if how == "count":
            agg = joined.groupby("segment_id").size().rename(feature_name).reset_index()
            out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
            out[feature_name] = out[feature_name].fillna(0.0)
            return out
        joined[value_column] = pd.to_numeric(joined[value_column], errors="coerce")
        if how == "sum":
            agg = (joined.groupby("segment_id")[value_column]
                         .sum(min_count=1)
                         .rename(feature_name)
                         .reset_index())
        else:
            agg = (joined.groupby("segment_id")[value_column]
                         .mean()
                         .rename(feature_name)
                         .reset_index())
        out = seg[["segment_id"]].merge(agg, on="segment_id", how="left")
        if zero_for_missing:
            out[feature_name] = out[feature_name].fillna(0.0)
        return out

    def _pairwise_intersections(seg_buffers, feat_geom, metric):
        sidx = feat_geom.sindex
        totals = np.zeros(len(seg_buffers), dtype="float64")
        for idx, buffer_geom in enumerate(seg_buffers):
            if buffer_geom is None or buffer_geom.is_empty:
                continue
            cand_idx = list(sidx.intersection(buffer_geom.bounds))
            if not cand_idx:
                continue
            buffers = np.repeat(buffer_geom, len(cand_idx))
            feats = feat_geom.values[np.array(cand_idx)]
            inter = shp_intersection(buffers, feats)
            if metric == "area":
                vals = shp_area(inter)
            else:
                vals = shp_length(inter)
            totals[idx] = np.nansum(np.asarray(vals, dtype="float64"))
        return totals

    if how in {"area_ratio", "length_area_ratio"}:
        out = seg[["segment_id"]].copy()
        inter_area = _pairwise_intersections(seg_buf_geom.values, feat.geometry, "area")
        denom = buf_area.copy()
        denom[denom == 0] = np.nan
        ratio = np.divide(inter_area, denom)
        ratio = np.clip(ratio, 0.0, 1.0)
        if zero_for_missing:
            ratio = np.nan_to_num(ratio, nan=0.0)
        out[feature_name] = ratio
        return out

    if how == "length_ratio":
        out = seg[["segment_id"]].copy()
        inter_len = _pairwise_intersections(seg_buf_geom.values, feat.geometry, "length")
        denom = seg_len.copy().astype("float64")
        denom[denom == 0] = np.nan
        ratio = np.divide(inter_len, denom)
        ratio = np.clip(ratio, 0.0, 1.0)
        if zero_for_missing:
            ratio = np.nan_to_num(ratio, nan=0.0)
        out[feature_name] = ratio
        return out

    if how == "raster":
        left = gpd.GeoDataFrame(seg[["segment_id"]].copy(), geometry=seg_buf_geom, crs=seg.crs)
        joined = gpd.sjoin(left, feat[["geometry", value_column]], how="left", predicate="intersects")
        out = seg[["segment_id"]].copy()
        if joined.empty:
            out[feature_name] = 0.0 if zero_for_missing else pd.NA
            return out
        joined[value_column] = pd.to_numeric(joined[value_column], errors="coerce")
        if raster_stats == "mean":
            agg = joined.groupby("segment_id")[value_column].mean()
        else:
            raise ValueError("Unsupported raster_stats.")
        out = out.merge(agg.rename(feature_name).reset_index(), on="segment_id", how="left")
        if zero_for_missing:
            out[feature_name] = out[feature_name].fillna(0.0)
        return out

    raise RuntimeError("Unhandled aggregation branch.")


def add_uv_columns(gdf):
    result = gdf.copy()
    result["u"] = result.geometry.apply(lambda geom: hash(geom.coords[0]))
    result["v"] = result.geometry.apply(lambda geom: hash(geom.coords[-1]))
    result["key"] = result["segment_id"]
    return result


def compute_connectivity_metrics(
    segmented_net,
    buffer_m=50,
    compute_betweenness=False,
    betweenness_k=None,
    crs_meter_epsg=None,
):
    gdf = segmented_net.copy()
    if crs_meter_epsg is not None and (gdf.crs is None or not gdf.crs.is_projected):
        gdf = gdf.to_crs(crs_meter_epsg)
    if "length_m" not in gdf.columns:
        gdf["length_m"] = gdf.geometry.length
    graph = nx.MultiGraph()
    for row in gdf.itertuples(index=False):
        graph.add_edge(getattr(row, "u"), getattr(row, "v"),
                       key=getattr(row, "key"),
                       segment_id=getattr(row, "segment_id"),
                       length=getattr(row, "length_m"))
    node_degree = dict(graph.degree())
    nx.set_node_attributes(graph, node_degree, "degree")
    node_rows = []
    for row in gdf.itertuples(index=False):
        geom = getattr(row, "geometry")
        x0, y0 = geom.coords[0]
        x1, y1 = geom.coords[-1]
        node_rows.append({"node": getattr(row, "u"), "geometry": Point(x0, y0)})
        node_rows.append({"node": getattr(row, "v"), "geometry": Point(x1, y1)})
    nodes_gdf = gpd.GeoDataFrame(node_rows, geometry="geometry", crs=gdf.crs)
    nodes_gdf = nodes_gdf.drop_duplicates(subset="node", keep="first").reset_index(drop=True)
    nodes_gdf["degree"] = nodes_gdf["node"].map(node_degree).fillna(0).astype(int)

    node_bet = None
    if compute_betweenness:
        simple_graph = nx.Graph()
        for u, v, data in graph.edges(data=True):
            weight = data.get("length", 1.0)
            if simple_graph.has_edge(u, v):
                if weight < simple_graph[u][v]["weight"]:
                    simple_graph[u][v]["weight"] = weight
            else:
                simple_graph.add_edge(u, v, weight=weight)
        node_bet = nx.betweenness_centrality(
            simple_graph,
            k=betweenness_k,
            weight="weight",
            normalized=True,
            endpoints=False,
            seed=42
        )

    edge_sindex = gdf.sindex
    node_sindex = nodes_gdf.sindex
    metrics = {
        "segment_id": [],
        "conn_mean_degree": [],
        "conn_deadend_flag": [],
        "conn_intersection_flag": [],
        "conn_nodes_in_buffer": [],
        "conn_edges_in_buffer": [],
        "conn_intersections_in_buffer": [],
        "conn_deadends_in_buffer": [],
        "conn_branching_in_buffer": [],
        "conn_beta_local": [],
    }

    for row in gdf.itertuples(index=False):
        seg_id = getattr(row, "segment_id")
        geom = getattr(row, "geometry")
        buffer_geom = geom.buffer(buffer_m)
        minx, miny, maxx, maxy = buffer_geom.bounds
        query_geom = box(minx, miny, maxx, maxy)

        u_node = getattr(row, "u")
        v_node = getattr(row, "v")
        deg_u = node_degree.get(u_node, 0)
        deg_v = node_degree.get(v_node, 0)
        mean_degree = (deg_u + deg_v) / 2
        deadend_flag = deg_u == 1 or deg_v == 1
        intersection_flag = deg_u >= 3 or deg_v >= 3

        candidate_nodes_idx = list(node_sindex.query(query_geom, predicate="intersects"))
        nodes_in_buffer = nodes_gdf.iloc[candidate_nodes_idx]
        nodes_in_buffer = nodes_in_buffer[nodes_in_buffer.geometry.intersects(buffer_geom)]

        nb_nodes = len(nodes_in_buffer)
        nb_intersections = int((nodes_in_buffer["degree"] >= 3).sum())
        nb_deadends = int((nodes_in_buffer["degree"] == 1).sum())
        branching = int(((nodes_in_buffer["degree"] - 2).clip(lower=0)).sum())

        candidate_edges_idx = list(edge_sindex.query(query_geom, predicate="intersects"))
        edges_in_buffer = gdf.iloc[candidate_edges_idx]
        edges_in_buffer = edges_in_buffer[edges_in_buffer.geometry.intersects(buffer_geom)]
        nb_edges = int(len(edges_in_buffer) - 1)

        beta_local = nb_edges / max(1, nb_nodes)

        metrics["segment_id"].append(seg_id)
        metrics["conn_mean_degree"].append(mean_degree)
        metrics["conn_deadend_flag"].append(bool(deadend_flag))
        metrics["conn_intersection_flag"].append(bool(intersection_flag))
        metrics["conn_nodes_in_buffer"].append(int(nb_nodes))
        metrics["conn_edges_in_buffer"].append(int(nb_edges))
        metrics["conn_intersections_in_buffer"].append(int(nb_intersections))
        metrics["conn_deadends_in_buffer"].append(int(nb_deadends))
        metrics["conn_branching_in_buffer"].append(int(branching))
        metrics["conn_beta_local"].append(float(beta_local))

    metrics_df = pd.DataFrame(metrics)

    if compute_betweenness and node_bet is not None:
        betweenness = []
        for row in gdf.itertuples(index=False):
            u_node = getattr(row, "u")
            v_node = getattr(row, "v")
            betweenness.append(0.5 * (node_bet.get(u_node, 0.0) + node_bet.get(v_node, 0.0)))
        gdf["conn_betweenness"] = betweenness

    gdf = gdf.merge(metrics_df, on="segment_id", how="left")
    return gdf

def prepare_features(input_path, output_path, params=None):
    """
    Étape 1 du pipeline : calcul et enrichissement des attributs/features pour chaque segment du réseau piéton.
    Args:
        input_path (str): Chemin vers le fichier des segments (GeoJSON, Parquet, etc.).
        output_path (str): Dossier de sauvegarde des features enrichis.
        params (dict, optional):
            - 'attributs_info' (str): Chemin vers le fichier attributs_info.xlsx
            - 'crs' (str): Code EPSG cible (ex: 'EPSG:2056')
    Returns:
        gpd.GeoDataFrame: Réseau enrichi des attributs/features.
    """
    crs = params.get('crs', 'EPSG:2056') if params else 'EPSG:2056'
    attributs_info_path = params.get('attributs_info') if params else None
    if attributs_info_path is None:
        raise ValueError("Le chemin vers attributs_info.xlsx doit être fourni dans params['attributs_info'].")

    # Chargement des segments
    if input_path.endswith('.parquet'):
        gdf = gpd.read_parquet(input_path)
    else:
        gdf = gpd.read_file(input_path)
    gdf = gdf.to_crs(crs)
    if 'segment_id' not in gdf.columns:
        gdf = gdf.reset_index(drop=True)
        gdf['segment_id'] = gdf.index.astype(int)

    # Chargement et filtrage des attributs à inclure
    attributs_info = pd.read_excel(attributs_info_path, sheet_name="attributs_info")
    attributs_info = attributs_info[attributs_info['include_in_index'] != False]

    # Exemple d'enrichissement : calcul de la longueur
    if 'length_m' not in gdf.columns:
        gdf['length_m'] = gdf.geometry.length

    attributs_root = Path(attributs_info_path).resolve().parent
    epsg_code = None
    if isinstance(crs, str) and crs.lower().startswith("epsg:"):
        try:
            epsg_code = int(crs.split(":")[1])
        except (ValueError, IndexError):
            epsg_code = None
    elif isinstance(crs, int):
        epsg_code = crs

    connectivity_cache = None

    for _, row in attributs_info.iterrows():
        attribute_name = row.get('attribute')
        if not attribute_name or _is_nan_like(attribute_name):
            continue
        attribute_name = str(attribute_name)

        geom_kind = str(row.get('geometry_type') or '').strip().lower()
        how = str(row.get('how') or '').strip().lower()
        if not geom_kind or not how:
            continue

        buffer_size = row.get('buffer_size')
        buffer_radius = float(buffer_size) if not _is_nan_like(buffer_size) else 0.0
        value_column = row.get('value_column')
        value_column = None if _is_nan_like(value_column) else str(value_column)
        clip_value = row.get('clip')
        filter_query = make_feature_query(row.get('filter_column'), row.get('filter_values'))

        feature_layer = _load_attribute_layer(attributs_root, row, gdf.crs)
        if feature_layer is None and attribute_name.lower() == 'connectivite':
            if connectivity_cache is None:
                metrics_source = add_uv_columns(gdf)
                metrics_source = compute_connectivity_metrics(
                    metrics_source,
                    buffer_m=50,
                    compute_betweenness=False,
                    crs_meter_epsg=epsg_code
                )
                metrics_source['filtered'] = 1
                connectivity_cache = metrics_source
            feature_layer = connectivity_cache

        if feature_layer is None or feature_layer.empty:
            print(f"⚠️ Impossible de charger la couche pour l'attribut '{attribute_name}', attribut ignoré.")
            continue

        if how in {'sum', 'mean', 'raster'} and not value_column:
            print(f"⚠️ L'attribut '{attribute_name}' nécessite une colonne valeur, attribut ignoré.")
            continue

        attribute_df = extract_buffer_feature(
            segments_gdf=gdf,
            feature_gdf=feature_layer,
            feature_name=attribute_name,
            geom_kind=geom_kind,
            how=how,
            buffer_radius=buffer_radius,
            value_column=value_column,
            crs_meter_epsg=epsg_code,
            feature_query=filter_query,
            segment_length_col='length_m'
        )

        current_crs = gdf.crs
        gdf = gpd.GeoDataFrame(
            gdf.merge(attribute_df, on='segment_id', how='left'),
            geometry='geometry',
            crs=current_crs
        )
        if not _is_nan_like(clip_value):
            gdf[attribute_name] = gdf[attribute_name].clip(upper=clip_value)

    os.makedirs(output_path, exist_ok=True)
    out_file = os.path.join(output_path, 'features_enriched.geojson')
    gdf.to_file(out_file, driver='GeoJSON')
    return gdf
