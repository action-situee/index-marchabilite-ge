"""
Module: filter_features
Filtrage ou validation manuelle/semi-automatique des features.
"""
import geopandas as gpd
import os

def filter_features(input_path, output_path, params=None):
    """
    Étape 2 du pipeline : filtrage/validation des features (intervention manuelle ou semi-automatique possible).
    Args:
        input_path (str): Chemin vers les features à filtrer (GeoJSON, Parquet, etc.).
        output_path (str): Dossier de sauvegarde des features filtrées.
        params (dict, optional):
            - 'formats' (list): Formats de sauvegarde ['geojson', 'gpkg', 'parquet', 'csv']
            - 'crs' (str): Code EPSG cible (ex: 'EPSG:2056')
    Returns:
        gpd.GeoDataFrame: Features filtrées/validées.
    """
    import warnings
    crs = params.get('crs', 'EPSG:2056') if params else 'EPSG:2056'
    formats = params.get('formats', ['geojson']) if params else ['geojson']

    # Chargement des features
    if input_path.endswith('.parquet'):
        gdf = gpd.read_parquet(input_path)
    else:
        gdf = gpd.read_file(input_path)
    gdf = gdf.to_crs(crs)

    # Nettoyage géométrie (buffer(0) pour corriger les invalides)
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.buffer(0) if geom is not None and not geom.is_valid else geom)
    warnings.filterwarnings("ignore", category=UserWarning)

    os.makedirs(output_path, exist_ok=True)
    for fmt in formats:
        try:
            if fmt == 'geojson':
                gdf.to_file(os.path.join(output_path, 'features_filtered.geojson'), driver='GeoJSON')
            elif fmt in ['gpkg', 'geopackage']:
                gdf.to_file(os.path.join(output_path, 'features_filtered.gpkg'), driver='GPKG')
            elif fmt == 'parquet':
                gdf.to_parquet(os.path.join(output_path, 'features_filtered.parquet'))
            elif fmt == 'csv':
                gdf.to_csv(os.path.join(output_path, 'features_filtered.csv'), index=False)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde au format {fmt}: {e}")
    return gdf
