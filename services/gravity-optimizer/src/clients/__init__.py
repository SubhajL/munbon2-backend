"""Service clients for inter-service communication"""

from .gis_client import GISClient
from .ros_client import ROSClient
from .scada_client import SCADAClient
from .weather_client import WeatherClient
from .sensor_client import SensorDataClient
from .service_registry import ServiceRegistry

__all__ = [
    'GISClient',
    'ROSClient', 
    'SCADAClient',
    'WeatherClient',
    'SensorDataClient',
    'ServiceRegistry'
]