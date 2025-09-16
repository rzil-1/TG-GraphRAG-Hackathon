import os
import json
import uuid
import logging
import boto3
import time
import re

from pyTigerGraph import TigerGraphConnection

from common.config import embedding_dimension
from common.py_schemas.schemas import (
    # GraphRAGResponse,
    CreateIngestConfig,
    # LoadingInfo,
    # SupportAIInitConfig,
    # SupportAIMethod,
    # SupportAIQuestion,
)

logger = logging.getLogger(__name__)

def init_supportai(conn: TigerGraphConnection, graphname: str) -> tuple[dict, dict]:
    # need to open the file using the absolute path
    ver = conn.getVer().split(".")

    current_schema = conn.gsql("""USE GRAPH {}\n ls""".format(graphname))

    supportai_queries = [
        "common/gsql/supportai/Scan_For_Updates.gsql",
        "common/gsql/supportai/Update_Vertices_Processing_Status.gsql",
        "common/gsql/supportai/Selected_Set_Display.gsql",
        "common/gsql/supportai/retrievers/GraphRAG_Hybrid_Search_Display.gsql",
        "common/gsql/supportai/retrievers/GraphRAG_Community_Search_Display.gsql",
        "common/gsql/supportai/retrievers/Chunk_Sibling_Search.gsql",
        "common/gsql/supportai/retrievers/Content_Similarity_Search.gsql",
        "common/gsql/supportai/retrievers/GraphRAG_Hybrid_Search.gsql",
        "common/gsql/supportai/retrievers/GraphRAG_Community_Search.gsql",
    ]

    if "- VERTEX ResolvedEntity" in current_schema:
        schema_res="Schema already exists, skipped"
    else:
        file_path = "common/gsql/supportai/SupportAI_Schema.gsql"
        with open(file_path, "r") as f:
            schema = f.read()
        schema_res = conn.gsql(
            """USE GRAPH {}\n{}\nRUN SCHEMA_CHANGE JOB add_supportai_schema""".format(
                graphname, schema
            )
        )

    if "- embedding(Dimension=" in current_schema:
        schema_res+=" Embeddding schema already exists, skipped"
    else:
        if int(ver[0]) >= 4 and int(ver[1]) >= 2:
            file_path = "common/gsql/supportai/SupportAI_Schema_Native_Vector.gsql"
            with open(file_path, "r") as f:
                schema = f.read()
            if embedding_dimension != 1536:
                schema = schema.replace(
                    "dimension=1536",
                    f"dimension={embedding_dimension}",
                )
            schema_res += " "
            schema_res += conn.gsql(
                """USE GRAPH {}\n{}\nRUN SCHEMA_CHANGE JOB add_supportai_vector""".format(
                    graphname, schema
                )
            )

            logger.info(f"Installing GDS library")
            q_res = conn.gsql(
                """USE GLOBAL\nimport package gds\ninstall function gds.**"""
            )
            logger.info(f"Done installing GDS library with status {q_res}")

            supportai_queries.extend([
                "common/gsql/supportai/retrievers/Content_Similarity_Vector_Search.gsql",
                "common/gsql/supportai/retrievers/Chunk_Sibling_Vector_Search.gsql",
                "common/gsql/supportai/retrievers/GraphRAG_Community_Vector_Search.gsql",
                "common/gsql/supportai/retrievers/GraphRAG_Hybrid_Vector_Search.gsql",
            ])
        else:
            raise Exception(f"Vector feature is not supported by the current TigerGraph version: {ver}")

    if "- doc_chunk_epoch_processed_index" in current_schema:
        index_res="Index already exists, skipped"
    else:
        file_path = "common/gsql/supportai/SupportAI_IndexCreation.gsql"
        with open(file_path) as f:
            index = f.read()
        index_res = conn.gsql(
            """USE GRAPH {}\n{}\nRUN SCHEMA_CHANGE JOB add_supportai_indexes""".format(
                graphname, index
            )
        )

    for filename in supportai_queries:
        logger.info(f"Creating supportai query {filename}")
        with open(f"{filename}", "r") as f:
            q_body = f.read()
        q_name, extension = os.path.splitext(os.path.basename(filename))
        q_res = conn.gsql(
            """USE GRAPH {}\nBEGIN\n{}\nEND\n""".format(
                conn.graphname, q_body
            )
        )
        logger.info(f"Done creating supportai query {q_name} with status {q_res}")

    logger.info(f"Installing supportai queries all together")
    query_res = conn.gsql(
        """USE GRAPH {}\nINSTALL QUERY ALL\n""".format(
            conn.graphname
        )
    )
    logger.info(f"Done installing supportai query all with status {query_res}")

    return schema_res, index_res, query_res


def trigger_bedrock_bda(bucket_name, output_bucket, region):
    s3 = boto3.client('s3', region_name=region)
    bda_client = boto3.client('bedrock-data-automation', region_name=region)
    bda_runtime_client = boto3.client('bedrock-data-automation-runtime', region_name=region)
    

    try:
        # there is a bug in AWS bedrock, it does not delete projects properly, so here 
        # we generate random project name each time below
        # Delete existing project if it exists
        # existing_projects = bda_client.list_data_automation_projects()["projects"]
        # for project in existing_projects:
        #     if project["projectName"] == "barclays-preprocessing-project":
        #         bda_client.delete_data_automation_project(projectArn=project["projectArn"])
        #         time.sleep(2)
        #         break

        # Create BDA project
        project_name = f"bda-preprocessing-{uuid.uuid4().hex[:6]}"
        project_response = bda_client.create_data_automation_project(
            projectName=project_name,
            projectDescription='Preprocessing multi data formats using bedrock data automation',
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
                dataAutomationProfileArn='arn:aws:bedrock:us-west-2:734036167395:data-automation-profile/us.data-automation-v1'
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


def create_ingest(
    graphname: str,
    ingest_config: CreateIngestConfig,
    conn: TigerGraphConnection,
):
    # Check for invalid combination of multi format and non-s3 data source
    if ingest_config.file_format.lower() == "multi" and ingest_config.data_source.lower() != "s3":
        raise Exception(
            "AWS Bedrock BDA preprocessing with 'multi' file format is only supported for S3 data sources.")

    if ingest_config.file_format.lower() == "json":
        file_path = "common/gsql/supportai/SupportAI_InitialLoadJSON.gsql"

        with open(file_path) as f:
            ingest_template = f.read()
        ingest_template = ingest_template.replace("@uuid@", str(uuid.uuid4().hex))
        doc_id = ingest_config.loader_config.get("doc_id_field", "doc_id")
        doc_text = ingest_config.loader_config.get("content_field", "content")
        doc_type = ingest_config.loader_config.get("doc_type", "")
        ingest_template = ingest_template.replace('"doc_id"', '"{}"'.format(doc_id))
        ingest_template = ingest_template.replace('"content"', '"{}"'.format(doc_text))
        ingest_template = ingest_template.replace('"doc_type"', '"{}"'.format(doc_type))

    if ingest_config.file_format.lower() == "csv":
        file_path = "common/gsql/supportai/SupportAI_InitialLoadCSV.gsql"

        with open(file_path) as f:
            ingest_template = f.read()
        ingest_template = ingest_template.replace("@uuid@", str(uuid.uuid4().hex))
        separator = ingest_config.get("separator", "|")
        header = ingest_config.get("header", "true")
        eol = ingest_config.get("eol", "\n")
        quote = ingest_config.get("quote", "double")
        ingest_template = ingest_template.replace('"|"', '"{}"'.format(separator))
        ingest_template = ingest_template.replace('"true"', '"{}"'.format(header))
        ingest_template = ingest_template.replace('"\\n"', '"{}"'.format(eol))
        ingest_template = ingest_template.replace('"double"', '"{}"'.format(quote))

    file_path = "common/gsql/supportai/SupportAI_DataSourceCreation.gsql"

    with open(file_path) as f:
        data_stream_conn = f.read()

    # assign unique identifier to the data stream connection

    data_stream_conn = data_stream_conn.replace(
        "@source_name@", "SupportAI_" + graphname + "_" + str(uuid.uuid4().hex)
    )

    # check the data source and create the appropriate connection
    res = {"data_source": ingest_config.data_source.lower()}

    if ingest_config.data_source.lower() == "s3":
        data_conn = ingest_config.data_source_config
        if (
            data_conn.get("aws_access_key") is None
            or data_conn.get("aws_secret_key") is None
        ):
            raise Exception("AWS credentials not provided")
        connector = {
            "type": "s3",
            "access.key": data_conn["aws_access_key"],
            "secret.key": data_conn["aws_secret_key"],
        }

        data_stream_conn = data_stream_conn.replace(
            "@source_config@", json.dumps(connector)
        )

        if ingest_config.file_format.lower() == "multi":
           
            bucket_name = data_conn["bucket_name"]
            output_bucket = data_conn["output_bucket"]
            region_name = data_conn["region_name"]

            try:
                bedrock_bda_result = trigger_bedrock_bda(
                    bucket_name, output_bucket, region_name)
                if bedrock_bda_result.get("statusCode") != 200:
                    raise Exception(f"Bedrock BDA failed: {bedrock_bda_result}")
                body = bedrock_bda_result.get("body")
                if not body:
                    raise Exception("Bedrock BDA response missing 'body'")
                jobs = json.loads(body).get("jobs")
                if not jobs or not jobs[0].get("output_json_path"):
                    raise Exception(
                        "No output_json_path found in Bedrock BDA result")
                output_json_path = jobs[0]["output_json_path"]
                ingest_config.data_source_config["data_path"] = output_json_path
                ingest_config.file_format = "json"

                # --- Begin: S3 markdown extraction and TigerGraph loading ---
                s3_client = boto3.client('s3')
                bucket_name = output_bucket
                # Use the folder containing the output
                prefix = output_json_path.rsplit('/', 1)[0] + '/'
                processed_files = []

                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

                for page in pages:
                    if 'Contents' not in page:
                        continue
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('/0/standard_output/0/result.md'):
                            path_parts = key.split('/')
                            print(f"Path parts: {path_parts}")
                            if len(path_parts) >= 7:
                                pdf_name = path_parts[3]
                                file_uuid = path_parts[4] if len(path_parts) <= 9 else "/".join(path_parts[4:-4])
                                response = s3_client.get_object(Bucket=bucket_name, Key=key)
                                content = response['Body'].read().decode('utf-8')
                                base_path = f"bda/output/BarclaysDocs/{pdf_name}/{file_uuid}/0/standard_output/0/assets/"
                                
                                # Find and log image matches before replacement
                                matches = re.findall(r'!\[([^\]]*)\]\(\./([^)]+)\)', content)
                                content = re.sub(r'!\[([^\]]*)\]\(\./([^)]+)\)', lambda m: f'![{m.group(1)}](s3://{bucket_name}/{base_path}{m.group(2)})', content)
                                doc_id = f"{pdf_name}"
                                processed_files.append({
                                    'file_path': key,
                                    'doc_id': doc_id,
                                })
                                # payload = json.dumps({"doc_id": doc_id, "doc_type": "markdown", "content": content})
                                # Loading into TigerGraph is now handled elsewhere.
                logger.info(
                    f"Processed {len(processed_files)} markdown files from S3 and loaded into TigerGraph.")
                # --- End: S3 markdown extraction and TigerGraph loading ---
            except Exception as e:
                logger.error(f"Error during Bedrock BDA preprocessing: {e}")
                return {"error": str(e), "stage": "bedrock_bda_preprocessing"}
                
    elif ingest_config.data_source.lower() == "azure":
        if ingest_config.data_source_config.get("account_key") is not None:
            connector = {
                "type": "abs",
                "account.key": ingest_config.data_source_config["account_key"],
            }
        elif ingest_config.data_source_config.get("client_id") is not None:
            # verify that the client secret is also provided
            if ingest_config.data_source_config.get("client_secret") is None:
                raise Exception("Client secret not provided")
            # verify that the tenant id is also provided
            if ingest_config.data_source_config.get("tenant_id") is None:
                raise Exception("Tenant id not provided")
            connector = {
                "type": "abs",
                "client.id": ingest_config.data_source_config["client_id"],
                "client.secret": ingest_config.data_source_config["client_secret"],
                "tenant.id": ingest_config.data_source_config["tenant_id"],
            }
        else:
            raise Exception("Azure credentials not provided")
        data_stream_conn = data_stream_conn.replace(
            "@source_config@", json.dumps(connector)
        )
    elif ingest_config.data_source.lower() == "gcs":
        # verify that the correct fields are provided
        if ingest_config.data_source_config.get("project_id") is None:
            raise Exception("Project id not provided")
        if ingest_config.data_source_config.get("private_key_id") is None:
            raise Exception("Private key id not provided")
        if ingest_config.data_source_config.get("private_key") is None:
            raise Exception("Private key not provided")
        if ingest_config.data_source_config.get("client_email") is None:
            raise Exception("Client email not provided")
        connector = {
            "type": "gcs",
            "project_id": ingest_config.data_source_config["project_id"],
            "private_key_id": ingest_config.data_source_config["private_key_id"],
            "private_key": ingest_config.data_source_config["private_key"],
            "client_email": ingest_config.data_source_config["client_email"],
        }
        data_stream_conn = data_stream_conn.replace(
            "@source_config@", json.dumps(connector)
        )
    elif ingest_config.data_source.lower() == "local":
        pass
    else:
        raise Exception("Data source not implemented")

    load_job_created = conn.gsql("USE GRAPH {}\n".format(graphname) + ingest_template)

    res["load_job_id"] = load_job_created.split(":")[1].strip(" [").strip(" ").strip(".").strip("]")
    if ingest_config.data_source_config:
        res["data_path"] = ingest_config.data_source_config.get("data_path", "")

    if ingest_config.data_source.lower() == "local":
        res["data_source_id"] = "DocumentContent"
    else:
        
        data_source_created = conn.gsql(
            "USE GRAPH {}\n".format(graphname) + data_stream_conn
        )
        res["data_source_id"] = data_source_created.split(":")[1].strip(" [").strip(" ").strip(".").strip("]")

    return res
