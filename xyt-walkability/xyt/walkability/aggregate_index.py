"""
Module: aggregate_index
Agrège les features et calcule l’indice de marchabilité.
"""
import geopandas as gpd
import os

def aggregate_index(input_path, output_path, params=None):
    """
    Étape 3 du pipeline : agrégation des features et calcul de l’indice de marchabilité.
    Args:
        input_path (str): Chemin vers les features filtrées (GeoJSON, Parquet, etc.).
        output_path (str): Dossier de sauvegarde de l’index agrégé.
        params (dict, optional):
            - 'zones_girec' (str): Chemin vers le fichier GIREC (shp/gpkg)
            - 'agglo_carreau' (str): Chemin vers le fichier Carreau 200 (shp/gpkg)
            - 'target_crs' (str): Code EPSG cible (ex: 'EPSG:2056')
    Returns:
        dict: {'girec': GeoDataFrame, 'carreau': GeoDataFrame}
    """
    import os
    import geopandas as gpd
    target_crs = params.get('target_crs', 'EPSG:2056') if params else 'EPSG:2056'
    zones_girec_path = params.get('zones_girec') if params else None
    agglo_carreau_path = params.get('agglo_carreau') if params else None
    if not zones_girec_path or not agglo_carreau_path:
        raise ValueError("Les chemins vers zones_girec et agglo_carreau doivent être fournis dans params.")

    # Chargement des features filtrées
    if input_path.endswith('.parquet'):
        index_walkability = gpd.read_parquet(input_path)
    else:
        index_walkability = gpd.read_file(input_path)
    index_walkability = index_walkability.to_crs(target_crs)

    # GIREC
    zones_girec = gpd.read_file(zones_girec_path).to_crs(target_crs)
    segments_girec = gpd.sjoin(index_walkability, zones_girec, how="inner", predicate="within")
    cols = index_walkability.columns.to_list()
    cols_to_agg = cols[3:]  # à adapter selon la structure
    girec_stats = (
        segments_girec
        .groupby("OBJECTID")[cols_to_agg]
        .mean()
        .reset_index()
    )
    zones_girec = zones_girec.merge(girec_stats, on="OBJECTID", how="left")
    zones_girec = zones_girec.dropna(subset=["indice_marchabilite"]) if "indice_marchabilite" in zones_girec.columns else zones_girec

    # Carreau 200
    agglo_carreau = gpd.read_file(agglo_carreau_path).to_crs(target_crs)
    segments_carreau = gpd.sjoin(index_walkability, agglo_carreau, how="inner", predicate="within")
    carreau_stats = (
        segments_carreau
        .groupby("GRID_ID")[cols_to_agg]
        .mean()
        .reset_index()
    )
    agglo_carreau = agglo_carreau.merge(carreau_stats, on="GRID_ID", how="left")
    agglo_carreau = agglo_carreau.dropna(subset=["indice_marchabilite"]) if "indice_marchabilite" in agglo_carreau.columns else agglo_carreau

    os.makedirs(output_path, exist_ok=True)
    zones_girec.to_file(os.path.join(output_path, "step3_aggregated_index_girec.gpkg"), driver="GPKG")
    zones_girec.to_parquet(os.path.join(output_path, "step3_aggregated_index_girec.parquet"))
    agglo_carreau.to_file(os.path.join(output_path, "step3_aggregated_index_carreau200.gpkg"), driver="GPKG")
    agglo_carreau.to_parquet(os.path.join(output_path, "step3_aggregated_index_carreau200.parquet"))
    return {'girec': zones_girec, 'carreau': agglo_carreau}
