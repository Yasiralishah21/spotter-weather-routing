import truststore

truststore.inject_into_ssl()

import requests

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "SpotterWeatherRouting/1.0 (fullstack assessment)",
        "Accept": "application/json",
    }
)
