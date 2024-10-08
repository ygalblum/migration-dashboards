""" Set allocation settings for ElasticSearch """
import os

from elasticsearch import Elasticsearch


TRUE_STRINGS = ("true", "1", "yes", "on")


def _get_elastic_client() -> Elasticsearch:
    url = os.getenv("ELASTICSEARCH_URL")
    if url is None:
        print("ELASTICSEARCH_URL must be set")
        return None

    password = os.getenv("ELASTICSEARCH_PASSWORD")
    if password is None:
        print("ELASTICSEARCH_PASSWORD must be set")
        return None

    client_kwargs = {
        'basic_auth': ("elastic", password)
    }
    cert_fingerprint = os.getenv("ELASTICSEARCH_CERT_FINGERPRINT")
    if cert_fingerprint is not None:
        client_kwargs['ssl_assert_fingerprint'] = cert_fingerprint

    ca_certs = os.getenv("ELASTICSEARCH_CA_CERT")
    if ca_certs is not None:
        client_kwargs['ca_certs'] = ca_certs

    return Elasticsearch(url, **client_kwargs)


number_fields = [
    ("ALLOCATION_WATERMARK_LOW", 'cluster.routing.allocation.disk.watermark.low'),
    ("ALLOCATION_WATERMARK_HIGH", 'cluster.routing.allocation.disk.watermark.high'),
    ("ALLOCATION_WATERMARK_FLOOD_STAGE", 'cluster.routing.allocation.disk.watermark.flood_stage'),
]

boolean_fields = [
    ("ALLOCATION_THRESHOLD_ENABLED", 'cluster.routing.allocation.disk.threshold_enabled')
]

def _get_allocation_disk_params() -> dict[str] :
    params = {}
    for var, field in boolean_fields:
        val = os.getenv(var)
        if val is not None:
            params[field] = val.lower() in TRUE_STRINGS

    for var, field in number_fields:
        val = os.getenv(var)
        if val is not None:
            params[field] = val

    return params


def _main():
    elastic_client = _get_elastic_client()
    elastic_client.cluster.put_settings(persistent=_get_allocation_disk_params())


if __name__ == "__main__":
    _main()
