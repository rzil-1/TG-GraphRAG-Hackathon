#!/usr/bin/env python3
"""
Test script to run create_ingest function and see what it returns.
This demonstrates different configurations and their results.
"""


from pyTigerGraph import TigerGraphConnection
import json

def test_create_ingest_server_multi():
    """Test create_ingest with server multi-format data source."""
    print("=" * 60)
    print("Testing create_ingest with SERVER MULTI format")
    print("=" * 60)
    
    # Connect to TigerGraph
    conn = TigerGraphConnection(
        host="http://localhost",  # Docker internal network
        username="tigergraph", 
        password="tigergraph",
        gsPort="14240",
        restppPort="14240",
        graphname="test_graph"  # Will be created
    )
    conn.ai.configureGraphRAGHost("http://localhost:8000")

    conn.gsql(f"""CREATE GRAPH test_graph()""")

    conn.ai.initializeSupportAI()
    
    # Configure for server multi-format ingestion
    ingest_response = conn.ai.createDocumentIngest(
        data_source="server",
        data_source_config={"folder_path": "/data"},  # Docker volume mount path
        loader_config={},
        file_format="multi"  # Automatically uses direct loading (like Bedrock)
    )
    with open("ingest_response.json", "w") as f:
        json.dump(ingest_response, f, indent=4)
    print("Saved ingest_response to ingest_response.json")
    print(f"Load job ID: {ingest_response['load_job_id']}")
    print(f"Data path: {ingest_response['data_path']}")
    print(f"Data source ID type: {type(ingest_response['data_source_id'])}")
    print(f"Data source ID keys: {ingest_response['data_source_id'].keys() if isinstance(ingest_response['data_source_id'], dict) else 'N/A'}")
    
    print("\n=== Calling runDocumentIngest ===")
    try:
        # Since data_path doesn't start with "/", it will use the /ingest endpoint
        result = conn.ai.runDocumentIngest(
            ingest_response["load_job_id"],
            ingest_response["data_source_id"],
            ingest_response["data_path"]
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    result = conn.ai.forceConsistencyUpdate("graphrag")
    return "graphrag is ready"


test_create_ingest_server_multi()

