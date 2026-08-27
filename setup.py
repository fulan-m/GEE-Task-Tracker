from setuptools import setup, find_packages

setup(
    name="gee-dashboard",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "earthengine-api",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "gee-dashboard=gee_dashboard.cli:main",
        ],
    },
    author="Mateus H. Fulan",
    description="CLI para monitoramento de tarefas do Google Earth Engine",
)