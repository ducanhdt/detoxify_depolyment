#!/usr/bin/env python3
"""
Simple test script for quick API testing
"""

import requests
import json

def test_detoxify_api():
    """Simple test for the detoxify API"""
    # url = "http://localhost:8080/detoxify"
    url = "http://35.193.184.103:8080/detoxify"
    
    # Test data
    test_data = {
        "text": "This is a test message with some bad words",
        "language_id": "en"
    }
    
    try:
        print("Sending request to:", url)
        print("Data:", json.dumps(test_data, indent=2))
        
        response = requests.post(url, json=test_data)
        
        print(f"\nResponse Status: {response.status_code}")
        print("Response Body:")
        print(json.dumps(response.json(), indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_detoxify_api()
