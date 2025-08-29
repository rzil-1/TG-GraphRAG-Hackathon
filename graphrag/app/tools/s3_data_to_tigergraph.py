import json
import boto3
import uuid
from urllib.parse import unquote_plus
import pyTigerGraph as tg
import re


def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    bucket_name = "barclays-output"
    TG_instance_payloads = []


    # Initialize connection
    conn = tg.TigerGraphConnection(host="http://172.31.18.14", 
                                   graphname="BarClaysGraphRAG", 
                                   username="tigergraph", 
                                   password="tigergraph",
                                   restppPort="14240")

    # List objects with the specific prefix pattern
    prefix = 'bda/output/BarclaysDocs/'
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        processed_files = []
        
        for page in pages:
            if 'Contents' not in page: 
                continue
                
            for obj in page['Contents']:
                key = obj['Key']
                
                # Check if it matches our pattern: */*/0/standard_output/0/results.md
                if key.endswith('/0/standard_output/0/result.md'):
                    # Extract pdfName and UUID from path
                    path_parts = key.split('/')
                    print(f"Path parts: {path_parts}")
                    if len(path_parts) >= 7:
                        pdf_name = path_parts[3]  # barclays-output/bda/output/BarclaysDocs/pdfName/...
                        file_uuid = path_parts[4] if len(path_parts) <=9 else "/".join(path_parts[4:-4])  # .../UUID/...
                        
                        # Get file content
                        response = s3_client.get_object(Bucket=bucket_name, Key=key)
                        content = response['Body'].read().decode('utf-8')
                        
                        # Replace image paths with S3 URI
                        base_path = f"bda/output/BarclaysDocs/{pdf_name}/{file_uuid}/0/standard_output/0/assets/"
                       
                        # Find and log image matches before replacement
                        matches = re.findall(r'!\[([^\]]*)\]\(\./([^)]+)\)', content)
                       
                        content = re.sub(r'!\[([^\]]*)\]\(\./([^)]+)\)', lambda m: f'![{m.group(1)}](s3://{bucket_name}/{base_path}{m.group(2)})', content)

                        # Create document ID (you can modify this logic as needed)
                        doc_id = f"{pdf_name}"
                        
                        # Prepare API payload
                        payload = json.dumps({"doc_id": doc_id, "doc_type": "markdown", "content": content})
                        
                        # Call API
                        conn.runLoadingJobWithData(payload, "DocumentContent", "load_documents_content_json", None, None, 16000, 128000000)
                        
                        processed_files.append({
                            'file_path': key,
                            'doc_id': doc_id,
                        })
        

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(processed_files)} files',
                'processed_files': processed_files
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }