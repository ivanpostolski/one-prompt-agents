import json
import boto3
import requests
import tempfile
import zipfile
import os
import shutil

def get_config():
    """Reads the configuration from config.json."""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found. Please copy config.json.template and fill it out.")
        exit(1)

def get_credentials_and_settings(api_endpoint, api_key):
    """Fetches temporary credentials and settings from the auth API."""
    print("--> Authenticating with deployment service...")
    try:
        response = requests.post(
            api_endpoint,
            headers={"Content-Type": "application/json"},
            json={"api_key": api_key}
        )
        response.raise_for_status()
        print("Authentication successful.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error authenticating: {e}")
        print(f"Response body: {e.response.text if e.response else 'No response body'}")
        exit(1)

def create_deployment_package(temp_dir, notification_email):
    """Creates a zip file containing the application source and scripts."""
    print("--> Creating deployment package...")
    shutil.copytree("src", os.path.join(temp_dir, "src"))
    shutil.copytree("scripts", os.path.join(temp_dir, "scripts"))
    shutil.copy("appspec.yml", temp_dir)
    
    # Create deployment metadata file for notification script
    meta_path = os.path.join(temp_dir, "deployment_meta.json")
    with open(meta_path, "w") as f:
        json.dump({"notification_email": notification_email}, f)
    
    zip_path = os.path.join(temp_dir, "deployment.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file != "deployment.zip":
                    zipf.write(os.path.join(root, file), 
                               os.path.relpath(os.path.join(root, file), temp_dir))
    print("Deployment package created.")
    return zip_path

def upload_to_s3(creds, region, bucket, package_path):
    """Uploads the deployment package to S3."""
    print(f"--> Uploading package to s3://{bucket}...")
    s3 = boto3.client(
        's3',
        aws_access_key_id=creds['accessKeyId'],
        aws_secret_access_key=creds['secretAccessKey'],
        aws_session_token=creds['sessionToken'],
        region_name=region
    )
    key = os.path.basename(package_path)
    s3.upload_file(package_path, bucket, key)
    print("Upload successful.")
    return key

def update_customer_parameters(creds, region, customer_name, parameters):
    """Writes customer-defined parameters to SSM Parameter Store."""
    if not parameters:
        print("--> No parameters to update.")
        return

    print("--> Updating customer parameters in SSM Parameter Store...")
    ssm = boto3.client(
        'ssm',
        aws_access_key_id=creds['accessKeyId'],
        aws_secret_access_key=creds['secretAccessKey'],
        aws_session_token=creds['sessionToken'],
        region_name=region
    )
    for key, value in parameters.items():
        param_name = f"/{customer_name}/app/{key}"
        print(f"  - Setting parameter: {param_name}")
        ssm.put_parameter(
            Name=param_name,
            Value=value,
            Type='SecureString', # Use SecureString for all params for simplicity and security
            Overwrite=True
        )
    print("Parameter update successful.")

def start_deployment(creds, region, app_name, dg_name, bucket, key):
    """Triggers a new CodeDeploy deployment."""
    print("--> Starting CodeDeploy deployment...")
    codedeploy = boto3.client(
        'codedeploy',
        aws_access_key_id=creds['accessKeyId'],
        aws_secret_access_key=creds['secretAccessKey'],
        aws_session_token=creds['sessionToken'],
        region_name=region
    )
    response = codedeploy.create_deployment(
        applicationName=app_name,
        deploymentGroupName=dg_name,
        revision={
            'revisionType': 'S3',
            's3Location': {
                'bucket': bucket,
                'key': key,
                'bundleType': 'zip'
            }
        }
    )
    deploy_id = response['deploymentId']
    print(f"Deployment successfully started with ID: {deploy_id}")
    print("You will receive an email notification with the deployment status.")

def main():
    config = get_config()
    auth_data = get_credentials_and_settings(config["api_endpoint_url"], config["api_key"])
    
    creds = auth_data["credentials"]
    settings = auth_data["config"]
    customer_name = settings.get("customer_name") # The API should return the customer's name

    if not customer_name:
        print("Error: Did not receive 'customer_name' from API. Cannot set parameters.")
        exit(1)

    # Update SSM parameters before deploying
    customer_params = config.get("parameters", {})
    update_customer_parameters(creds, settings["aws_region"], customer_name, customer_params)

    with tempfile.TemporaryDirectory() as temp_dir:
        package_path = create_deployment_package(temp_dir, settings.get("notification_email"))
        s3_key = upload_to_s3(creds, settings["aws_region"], settings["artefact_bucket"], package_path)
        start_deployment(creds, settings["aws_region"], settings["codedeploy_app_name"], 
                         settings["codedeploy_deployment_group"], settings["artefact_bucket"], s3_key)

if __name__ == "__main__":
    main() 