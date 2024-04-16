import yaml
import boto3

def expandyaml(data):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            current = result
            sub_keys = key.split(".")
            for sub_key in sub_keys[:-1]:
                current = current.setdefault(sub_key, {})
            current[sub_keys[-1]] = expandyaml(value)
        return result
    if isinstance(data, list):
        return [uvexpandyaml(item) for item in data]
    else:
        return data


def read_configuration(path):
    with open(path, "r") as file:
        return expandyaml(yaml.safe_load(file))


def deploy_function(lambda_client, manifest, zipfile):
    try:
        lambda_client.update_function_code(
            ZipFile=zipfile, FunctionName=manifest["FunctionName"]
        )
        print("Function code updated")
    except lambda_client.exceptions.ResourceNotFoundException:
        lambda_client.create_function(Code={'ZipFile': zipfile}, PackageType='Zip', **manifest)
        print("Function created")
    lambda_client.get_waiter('function_updated').wait(FunctionName=manifest['FunctionName'])
    print('Done')

def get_function_arn(lambda_client, function_name):
    return lambda_client.get_function(FunctionName=function_name)['Configuration']['FunctionArn']

def create_s3_trigger(s3_client, function_arn, trigger_config):
    print(trigger_config)
    for configs in trigger_config['NotificationConfiguration']['LambdaFunctionConfigurations']:
        configs['LambdaFunctionArn'] = function_arn
    s3_client.put_bucket_notification_configuration(Bucket=trigger_config['Bucket'], NotificationConfiguration=trigger_config['NotificationConfiguration'])

def invoke_function(lambda_client, function_manifest):
    response = lambda_client.invoke(FunctionName=function_manifest['FunctionName'])
    print(response)
    print(response['Payload'].read())

def main():
    try:
        with open('function.zip', 'rb') as file:
            zipfile=file.read()
        function_manifest = read_configuration('manifest.yaml')['FunctionConfiguration']
        environment_config = read_configuration('manifest.yaml')['Environments'][0]

        lambda_client = boto3.client('lambda')
        deploy_function(lambda_client, function_manifest, zipfile)
        invoke_function(lambda_client, function_manifest)
        deploy_function(lambda_client, function_manifest, zipfile)
        invoke_function(lambda_client, function_manifest)
        function_arn = get_function_arn(lambda_client, function_manifest['FunctionName'])

        s3_client = boto3.client('s3')
        create_s3_trigger(s3_client, function_arn, environment_config['Triggers'][0])

    finally:
        print("Cleaning up function")
        # lambda_client.delete_function(FunctionName=function_manifest['FunctionName'])
        print('Done')

if __name__ == "__main__":
    main()
