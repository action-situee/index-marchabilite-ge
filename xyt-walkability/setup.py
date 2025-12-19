from setuptools import setup, find_packages

setup(
    name='xyt-walkability',
    version='0.1.0',
    description='ETL pipeline for walkability index',
    author='Votre Nom',
    packages=find_packages(),
    install_requires=[
        'geopandas', 'pandas', 'numpy', 'shapely', 'matplotlib', 'folium',
        'osmnx', 'networkx', 'branca', 'rasterio', 'scikit-learn', 'scipy', 'plotly', 'pyarrow', 'click'
    ],
    entry_points={
        'console_scripts': [
            'xyt-walkability=xyt.walkability.cli:cli',
        ],
    },
    python_requires='>=3.8',
)
