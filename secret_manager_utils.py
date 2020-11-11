import logging
import os

from google.cloud import secretmanager


logging.basicConfig(level=logging.INFO)

PROJECT_ID = os.environ.get("GCP_PROJECT", "projectoceanis")


class SecretsManagerUtils:
    def __init__(self, project_id, ):
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()

    def get_secret_version(self, secret_id, version_id="latest"):
        # Build the resource name of the secret version.
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"

        # Access the secret version.
        response = self.client.access_secret_version(name=name)

        # Return the decoded payload.
        logging.info(f"Got secret version {response.name}")
        return response.payload.data.decode('UTF-8')

    def add_secret_version(self, secret_id, secret_value):
        # Build the resource name of the parent secret.
        parent = f"projects/{self.project_id}/secrets/{secret_id}"

        # Convert the string payload into a bytes.
        payload = {"data": secret_value.encode('UTF-8')}

        # Add the secret version.
        response = self.client.add_secret_version(parent=parent, payload=payload)

        # Print the new secret version name.
        logging.info(f'Added secret version: {response.name}')
        return response.name

    def destroy_secret_version(self, secret_id, version_id):
        # Create the Secret Manager client.
        client = secretmanager.SecretManagerServiceClient()

        # Build the resource name of the secret version
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"

        # Destroy the secret version.
        response = client.destroy_secret_version(request={"name": name})

        logging.info("Destroyed secret version: {}".format(response.name))
