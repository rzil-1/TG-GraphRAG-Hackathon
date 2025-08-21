import json
import boto3
import uuid
import time


def lambda_handler(event, context):

    s3 = boto3.client('s3')
    bda_client = boto3.client('bedrock-data-automation')
    bda_runtime_client = boto3.client('bedrock-data-automation-runtime')
    bucket_name = 'barclays-poc-source-data'
    output_bucket = 'barclays-output'

    try:
        # Delete existing project if it exists
        existing_projects = bda_client.list_data_automation_projects()[
            "projects"]
        print("Existing projects:")
        print(f"{existing_projects}")
        for project in existing_projects:
            if project["projectName"] == "barclays-preprocessing-project":
                print(f"Deleting existing project: {project['projectName']}")
                bda_client.delete_data_automation_project(
                    projectArn=project["projectArn"])
                time.sleep(2)
                break

        # Create BDA project
        project_response = bda_client.create_data_automation_project(
            projectName='barclays-preprocessing-project6',
            projectDescription='Preprocessing project for Barclays data',
            projectStage='DEVELOPMENT',
            standardOutputConfiguration={
                "document": {
                    "extraction": {
                        "granularity": {"types": ["DOCUMENT", "PAGE", "ELEMENT", "LINE", "WORD"]},
                        "boundingBox": {"state": "ENABLED"}
                    },
                    "generativeField": {"state": "ENABLED"},
                    "outputFormat": {
                        "textFormat": {"types": ["PLAIN_TEXT", "MARKDOWN", "HTML", "CSV"]},
                        "additionalFileFormat": {"state": "ENABLED"}
                    }
                }}
        )
        project_arn = project_response['projectArn']

        # Get file names from S3
        response = s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get('Contents', [])

        job_results = []

        # Create BDA job for each file
        for obj in objects:
            time.sleep(2)
            file_key = obj['Key']
            input_s3_uri = f's3://{bucket_name}/{file_key}'
            output_s3_uri = f's3://{output_bucket}/bda/output/{file_key}'

            bda_response = bda_runtime_client.invoke_data_automation_async(

                inputConfiguration={
                    's3Uri': input_s3_uri
                },
                outputConfiguration={
                    's3Uri': output_s3_uri
                },
                dataAutomationConfiguration={
                    'dataAutomationProjectArn': project_arn,
                    'stage': 'DEVELOPMENT'
                },
                dataAutomationProfileArn=f'arn:aws:bedrock:us-west-2:734036167395:data-automation-profile/us.data-automation-v1'
            )

            job_results.append({
                'file': file_key,
                'jobId': bda_response.get('invocationArn')
            })

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Created {len(job_results)} BDA jobs',
                'jobs': job_results
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
