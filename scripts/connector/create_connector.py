""" Create a ElasticSearch Connector
Set the following Environment Variables
ELASTICSEARCH_URL - URL of the elastic service
ELASTICSEARCH_PASSWORD - Password of the `elastic` user
ELASTICSEARCH_CERT_FINGERPRINT - Fingerprint of the server certificate (provide either this or ELASTICSEARCH_CA_CERT)
ELASTICSEARCH_CA_CERT - Path to the server's CA certificate (provide either this or ELASTICSEARCH_CERT_FINGERPRINT)
ELASTICSEARCH_CONNECTOR_ID - ID for the new connector
ELASTICSEARCH_CONNECTOR_NAME - Name for the new connector
ELASTICSEARCH_INDEX_NAME - Index for the new connector
GEN_SECRET_NAMESPACE - Namespace of the secret to store the connector configuration
GEN_SECRET_NAME - Name of the secret to store the connector configuration
CONNECTOR_CA_CERTS_LOCATION - location of the elastic CA certificate in the connector container
"""

import base64
import os

from elasticsearch import Elasticsearch
from jinja2 import Template
from kubernetes import client, config


class MissingEnvVar(Exception):
    """ Exception for missing Environment Variables """


class CreateConnector():  # pylint:disable=R0903
    """ Class for Connector create operation """

    TRUE_STRINGS = ("true", "1", "yes", "on")
    CONNECTOR_CONFIG_TEMPLATE = """
elasticsearch:
    host: {{ url }}
    api_key: {{ api_key }}
    ca_certs: {{ ca_certs_location }}

connectors:
  - connector_id: {{ connector_id }}
    service_type: postgresql

"""

    def __init__(self) -> None:
        self._url = self._get_env_var("ELASTICSEARCH_URL")
        self._elastic_client = self._get_elastic_client()
        self._connector_params = self._get_connector_parameters()
        self._secret_name = self._get_env_var("GEN_SECRET_NAME")
        self._secret_namespace = self._get_env_var("GEN_SECRET_NAMESPACE")
        self._ca_certs_location = self._get_env_var("CONNECTOR_CA_CERTS_LOCATION")

    @staticmethod
    def _get_env_var(var_name: str, optional=False) -> str:
        val = os.getenv(var_name)
        if not optional and val is None:
            raise MissingEnvVar(f"{var_name} is not defined")
        return val

    def _get_elastic_client(self) -> Elasticsearch:
        client_kwargs = {
            'basic_auth': ("elastic", self._get_env_var("ELASTICSEARCH_PASSWORD"))
        }
        cert_fingerprint = self._get_env_var("ELASTICSEARCH_CERT_FINGERPRINT", True)
        if cert_fingerprint is not None:
            client_kwargs['ssl_assert_fingerprint'] = cert_fingerprint

        ca_certs = self._get_env_var("ELASTICSEARCH_CA_CERT", True)
        if ca_certs is not None:
            client_kwargs['ca_certs'] = ca_certs

        return Elasticsearch(self._url, **client_kwargs)

    @staticmethod
    def _get_connector_parameters() -> dict[str] :
        fields = [
            ("ELASTICSEARCH_CONNECTOR_ID", 'connector_id'),
            ("ELASTICSEARCH_CONNECTOR_NAME", 'name'),
            ("ELASTICSEARCH_INDEX_NAME", "index_name")
        ]

        params = {
            'service_type': 'postgresql'
        }

        for var, field in fields:
            params[field] = CreateConnector._get_env_var(var)

        return params

    def run(self):
        """ Run the operation """
        # Make sure the connection to K8S is on before starting
        try:
            config.load_kube_config()
        except config.config_exception.ConfigException:
            config.load_incluster_config()

        self._elastic_client.connector.put(**self._connector_params)
        self._create_connector_config_secret(
            self._generate_connector_config(
                self._create_api_key()
            )
        )

    def _create_api_key(self) -> str:
        response = self._elastic_client.security.create_api_key(
            name=f"{self._connector_params['name']}-connector-api-key",
            role_descriptors={
                f"{self._connector_params['name']}-connector-role": {
                    "cluster": [
                        "monitor",
                        "manage_connector"
                    ],
                    "indices": [
                        {
                            "names": [
                                f"{self._connector_params['index_name']}",
                                f".search-acl-filter-{self._connector_params['index_name']}",
                                ".elastic-connectors*"
                            ],
                            "privileges": [
                                "all"
                            ],
                            "allow_restricted_indices": False
                        }
                    ]
                }
            }
        )
        return response['encoded']

    def _generate_connector_config(self, api_key: str) -> str :
        context = {
            'url': self._url,
            'connector_id': self._connector_params['connector_id'],
            'api_key': api_key,
            'ca_certs_location': self._ca_certs_location,
        }
        template = Template(CreateConnector.CONNECTOR_CONFIG_TEMPLATE)
        return template.render(context)

    def _create_connector_config_secret(self, data: str):
        secret = client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=client.V1ObjectMeta(name=self._secret_name),
            type="Opaque",
            data={
                "config.yml": base64.b64encode(data.encode()).decode()
            }
        )
        try:
            client.CoreV1Api().create_namespaced_secret(namespace=self._secret_namespace, body=secret)
        except client.ApiException as e:
            print(f"An error occurred: {e}")


def _main():
    CreateConnector().run()


if __name__ == "__main__":
    _main()
