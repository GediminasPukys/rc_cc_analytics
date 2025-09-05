#!/usr/bin/env python3
"""Check analysis data for a specific session"""

import os
import json
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize GCS client
client = storage.Client(project=os.getenv("GCS_PROJECT_ID"))
bucket = client.bucket(os.getenv("GCS_BUCKET_NAME"))

# Session to check
session_id = "20250904_180344_custom_empathy"

print(f"\n=== Checking analysis for session: {session_id} ===\n")

# Check if analysis file exists
analysis_blob = bucket.blob(f"sessions/{session_id}/conversation_analysis.json")

if analysis_blob.exists():
    print("✅ Analysis file found")
    
    # Download and parse the analysis
    analysis_data = json.loads(analysis_blob.download_as_text())
    
    # Check review-related fields
    print("\n=== Review Information ===")
    print(f"requires_review: {analysis_data.get('requires_review')}")
    print(f"review_priority: {analysis_data.get('review_priority')}")
    print(f"review_reasons: {analysis_data.get('review_reasons', [])}")
    
    # Also check what's being stored in metadata about this session
    print("\n=== Checking Session Metadata ===")
    
    # List all files in session
    blobs = bucket.list_blobs(prefix=f"sessions/{session_id}/")
    files = []
    for blob in blobs:
        files.append(blob.name.split('/')[-1])
    
    print(f"Files in session: {files}")
    
    # Check if metadata exists
    metadata_blob = bucket.blob(f"sessions/{session_id}/metadata.json")
    if metadata_blob.exists():
        metadata = json.loads(metadata_blob.download_as_text())
        print(f"\nMetadata content:")
        print(json.dumps(metadata, indent=2))
else:
    print("❌ No analysis file found for this session")

print("\n=== Expected Behavior ===")
print("If review_priority is 'high', the master table should show 🟠 High")
print("If review_priority is 'medium', the master table should show 🟡 Medium")
print("Currently, it seems to be showing the wrong color/priority")