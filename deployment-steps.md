# Steps for Deployment

## Installing ElasticSearch and Kibana

### Using app-interface

In the long run we should consider moving the deployment to the responsability of the AppSRE by using the [app-interface](https://gitlab.cee.redhat.com/service/app-interface/).

### Using ECK

#### Installing the Operator

Install the operator based on their [documentation](https://www.elastic.co/guide/en/cloud-on-k8s/current/k8s-openshift.html).

#### Installing ElasticSearch

Deploy an `Elasticsearch` CRD

Base sample:
```yaml
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: elasticsearch-sample
spec:
  version: 8.15.2
  nodeSets:
  - name: default
    count: 1
    config:
      node.store.allow_mmap: false
# This is needed if the endpoint is to be exposed via a route and needs to predict the route's name
  http:
    tls:
      selfSignedCertificate:
        subjectAltNames:
        - dns: elasticsearch-sample-elastic.apps.my-cluster.example.com
```

See the [sample manifest](./resources/elasticsearch.yml)

#### Installing Kibana
Deploy an `Kibana` CRD

Base sample:
```yaml
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: kibana-sample
spec:
  version: 8.15.2
  count: 1
  elasticsearchRef:
    name: "elasticsearch-sample"
  podTemplate:
    spec:
      containers:
      - name: kibana
        resources:
          limits:
            memory: 1Gi
            cpu: 1
```

See the [sample manifest](./resources/kibana.yml)

#### Expose the Kibana Web Interface

Expose `Kibana` using a `route`:

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: kibana-sample
spec:
  tls:
    termination: passthrough # Kibana is the TLS endpoint
    insecureEdgeTerminationPolicy: Redirect
  to:
    kind: Service
    name: kibana-sample-kb-http
```

## ElasticSearch Configuration

### Using NFS-based Storage

The default disk allocation settings are set in percentage ([see](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-cluster.html#disk-based-shard-allocation)).
However, when using NFS the size of the volume and its free space are the sizes of the entire NFS server. As a result, percentage calculation are incorrect and may lead to a failed cluster.

To avoid this error, either disable the protection or set the values to absolute sizes.

#### Set the values using a Tekton Pipeline

The [tekton pipeline](./tekton/allocation-settings/allocation-settings-pipeline.yml) may be used to disable the allocation threashold.
See the [pipelinerun](./tekton/allocation-settings/allocation-settings-pipelinerun.yml) for reference

## Elastic PostgreSQL connector

### Prerequisites

#### PostgreSQL

TBD - should these steps take place when deploying the DB or when deploying the connector?

##### Commit time recording

To avoid a case in which all data is index in every sync, `track_commit_timestamp` must be set to `on`:
```
ALTER SYSTEM SET track_commit_timestamp = on;
```

##### User

Create a user for the connector.
According the the [documentation](https://www.elastic.co/guide/en/enterprise-search/current/postgresql-connector-client-tutorial.html#postgresql-connector-client-tutorial-postgresql-prerequisites) the user should have `superuser` if the connector is to index all database tables.
But, I think we should find a way to use a less priviliged role.

The DB connection details should be stored in a K8S secret.

#### ElasticSearch

The steps below require a user with the cluster privileges `manage_api_key`, `manage_connector` and `write_connector_secrets`.

If using [ECK](#using-eck), the user `elastic` with the password stored in the secret `<ElasticSearch CRD Name>-es-elastic-user` can be used.

##### Create a PostgreSQL connector

Create a connector using the [API](https://www.elastic.co/guide/en/elasticsearch/reference/8.15/create-connector-api.html)

Sample Parameters:
```
PUT _connector/assisted-migration-db
{
  "index_name": "assisted-migration",
  "name": "Assisted Migration Content",
  "service_type": "postgresql"
}
```

##### Create an API Key

Use the API to create an API key for the connector. See [Doc](https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-create-api-key.html)

Sample parameters:
```
POST /_security/api_key
{
  "name": "<connector_name>-connector-api-key",
  "role_descriptors": {
    "<connector_name>-connector-role": {
      "cluster": [
        "monitor",
        "manage_connector"
      ],
      "indices": [
        {
          "names": [
            "<index_name>",
            ".search-acl-filter-<index_name>",
            ".elastic-connectors*"
          ],
          "privileges": [
            "all"
          ],
          "allow_restricted_indices": false
        }
      ]
    }
  }
}
```

From the returned JSON, the field `encoded` should be used in the connector's configuration

#### Tekton Pipeline

The [tekton pipeline](./tekton/create-connector/pipeline.yml) may be used to create the connector and API key and save the connector configuration in a secret.
See the [pipelinerun](./tekton/create-connector/pipelinerun.yml) for reference

## Running the Connector

See the [sample manifest](./resources/connector-deployment.yml)