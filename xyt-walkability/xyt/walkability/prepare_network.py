"""
Module: prepare_network
Prépare le réseau piéton à partir des données OSM ou autres sources.
"""
import geopandas as gpd
import osmnx as ox
import os

def prepare_network(input_path, output_path, params=None):
    """
    Étape 0 du pipeline : extraction et préparation du réseau piéton OSM pour une zone d'étude.
    Args:
        input_path (str): Chemin vers le fichier ou nom de la zone (ex: 'Canton de Genève, Switzerland').
        output_path (str): Dossier de sauvegarde du réseau traité.
        params (dict, optional):
            - 'place' (str): Nom de la zone d'étude (prioritaire sur input_path)
            - 'custom_filter' (str): Filtre OSM avancé (optionnel)
            - 'crs' (str): Code EPSG cible (ex: 'EPSG:2056')
    Returns:
        dict: {'edges': GeoDataFrame, 'nodes': GeoDataFrame}
    """
    # Définition de la zone d'étude
    place = params.get('place') if params and 'place' in params else input_path
    crs = params.get('crs', 'EPSG:2056') if params else 'EPSG:2056'
    custom_filter = params.get('custom_filter') if params else None

    print(f"🗺️ Téléchargement des limites de la zone '{place}'...")
    area_gdf = ox.geocode_to_gdf(place)
    polygon = area_gdf.geometry.iloc[0]

    # Filtre OSM par défaut (adapté à la marche)
    if not custom_filter:
        custom_filter = (
            '["area"!~"yes"]'
            '["highway"!~"motorway|motorway_link|trunk|trunk_link|construction|proposed"]'
            '["highway"~"footway|path|pedestrian|steps|living_street|residential|service|unclassified|tertiary|secondary|primary|platform"]'
        )

    print("🌍 Téléchargement du réseau piéton OSM…")
    G = ox.graph_from_polygon(
        polygon=polygon,
        custom_filter=custom_filter,
        simplify=True,
        retain_all=True
    )

    print("🔄 Conversion en GeoDataFrames…")
    nodes_gdf = ox.graph_to_gdfs(G, edges=False)
    edges_gdf = ox.graph_to_gdfs(G, nodes=False, fill_edge_geometry=True).reset_index(drop=True)

    # Projection
    nodes_gdf = nodes_gdf.to_crs(crs)
    edges_gdf = edges_gdf.to_crs(crs)

    print(f"📊 Nœuds: {len(nodes_gdf)} | Arêtes: {len(edges_gdf)}")
    os.makedirs(output_path, exist_ok=True)
    nodes_gdf.to_file(os.path.join(output_path, 'network_nodes.geojson'), driver='GeoJSON')
    edges_gdf.to_file(os.path.join(output_path, 'network_edges.geojson'), driver='GeoJSON')
    return {'edges': edges_gdf, 'nodes': nodes_gdf}
    # Exemple minimal : extraction OSM par bbox ou place
    if params and 'place' in params:
        G = ox.graph_from_place(params['place'], network_type='walk')
    elif params and 'bbox' in params:
        G = ox.graph_from_bbox(*params['bbox'], network_type='walk')
    else:
        raise ValueError("Spécifier 'place' ou 'bbox' dans params pour l'extraction OSM.")
    gdf = ox.graph_to_gdfs(G, nodes=False)
    os.makedirs(output_path, exist_ok=True)
    out_file = os.path.join(output_path, 'network.geojson')
    gdf.to_file(out_file, driver='GeoJSON')
    return gdf
