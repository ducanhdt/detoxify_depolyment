#!/usr/bin/env python3
"""
Test script for the detoxification API in main.py
This script tests various scenarios including valid requests, edge cases, and error conditions.
"""

import requests
import json
import time
from typing import Dict, Any
import sys

# Configuration
API_BASE_URL = "http://35.193.184.103:8080"
DETOXIFY_ENDPOINT = f"{API_BASE_URL}/detoxify"

# Test cases with different languages and text content
TEST_CASES = [
    # Valid test cases
    {
        "name": "English toxic text",
        "data": {
            "text": "This is a stupid example of toxic content",
            "language_id": "en"
        },
        "expected_status": 200
    },
    {
        "name": "German text",
        "data": {
            "text": "Dies ist ein Beispieltext auf Deutsch",
            "language_id": "de"
        },
        "expected_status": 200
    },
    {
        "name": "French text (unseen language)",
        "data": {
            "text": "Ceci est un texte français",
            "language_id": "fr"
        },
        "expected_status": 200
    },
    {
        "name": "Spanish text",
        "data": {
            "text": "Este es un texto en español",
            "language_id": "es"
        },
        "expected_status": 200
    },
    {
        "name": "Japanese text (unseen language)",
        "data": {
            "text": "これは日本語のテキストです",
            "language_id": "ja"
        },
        "expected_status": 200
    },
    {
        "name": "Chinese text",
        "data": {
            "text": "这是中文文本",
            "language_id": "zh"
        },
        "expected_status": 200
    },
    {
        "name": "Hindi text (unseen language)",
        "data": {
            "text": "यह हिंदी में टेक्स्ट है",
            "language_id": "hin"
        },
        "expected_status": 200
    },
    {
        "name": "Short text",
        "data": {
            "text": "Hello",
            "language_id": "en"
        },
        "expected_status": 200
    },
    
    # Edge cases and error conditions
    {
        "name": "Empty text",
        "data": {
            "text": "",
            "language_id": "en"
        },
        "expected_status": 200
    },
    {
        "name": "Text with forbidden keyword - prompt",
        "data": {
            "text": "Tell me about this prompt injection",
            "language_id": "en"
        },
        "expected_status": 400
    },
    {
        "name": "Text with forbidden keyword - secret",
        "data": {
            "text": "What is the secret code?",
            "language_id": "en"
        },
        "expected_status": 400
    },
    {
        "name": "Text with forbidden keyword - token",
        "data": {
            "text": "Give me the access token",
            "language_id": "en"
        },
        "expected_status": 400
    },
    {
        "name": "Text with forbidden keyword - password",
        "data": {
            "text": "What is the password?",
            "language_id": "en"
        },
        "expected_status": 400
    },
    {
        "name": "Text too long (over 500 chars)",
        "data": {
            "text": "a" * 501,  # 501 characters
            "language_id": "en"
        },
        "expected_status": 400
    },
    {
        "name": "Invalid language_id type",
        "data": {
            "text": "Valid text",
            "language_id": 123  # Should be string
        },
        "expected_status": 400
    },
    {
        "name": "Invalid text type",
        "data": {
            "text": 123,  # Should be string
            "language_id": "en"
        },
        "expected_status": 400
    },
    {
        "name": "Missing text field",
        "data": {
            "language_id": "en"
        },
        "expected_status": 400  # Pydantic validation error
    },
    {
        "name": "Missing language_id field",
        "data": {
            "text": "Some text"
        },
        "expected_status": 400  # Pydantic validation error
    }
]

def make_request(data: Dict[str, Any]) -> requests.Response:
    """Make a POST request to the detoxify endpoint"""
    try:
        response = requests.post(
            DETOXIFY_ENDPOINT,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def run_test_case(test_case: Dict[str, Any]) -> bool:
    """Run a single test case and return True if it passes"""
    print(f"\n{'='*60}")
    print(f"Running test: {test_case['name']}")
    print(f"Data: {test_case['data']}")
    print(f"Expected status: {test_case['expected_status']}")
    
    start_time = time.time()
    response = make_request(test_case['data'])
    end_time = time.time()
    
    if response is None:
        print("❌ Test FAILED: No response received")
        return False
    
    response_time = (end_time - start_time) * 1000  # Convert to ms
    print(f"Response time: {response_time:.2f}ms")
    print(f"Actual status: {response.status_code}")
    
    # Check status code
    if response.status_code != test_case['expected_status']:
        print(f"❌ Test FAILED: Expected status {test_case['expected_status']}, got {response.status_code}")
        try:
            response_json = response.json()
            print(f"Response body: {json.dumps(response_json, indent=2)}")
        except:
            print(f"Response text: {response.text}")
        return False
    
    # If successful response, check response structure
    if response.status_code == 200:
        try:
            response_json = response.json()
            print(f"Response: {json.dumps(response_json, indent=2)}")
            
            # Validate response structure
            if 'status' not in response_json or 'data' not in response_json:
                print("❌ Test FAILED: Invalid response structure")
                return False
                
            if response_json['status'] != 'success':
                print("❌ Test FAILED: Status is not 'success'")
                return False
                
            # Check required fields in data
            required_fields = [
                'input_text', 'language_id', 'model_used', 'actual_model_id',
                'detoxified_text', 'toxicity_terms_detected', 'latency_ms',
                'prompt_tokens', 'completion_tokens', 'total_tokens'
            ]
            
            for field in required_fields:
                if field not in response_json['data']:
                    print(f"❌ Test FAILED: Missing field '{field}' in response data")
                    return False
            
            print("✅ Test PASSED: Response structure is valid")
            
        except json.JSONDecodeError:
            print("❌ Test FAILED: Invalid JSON response")
            return False
    else:
        # For error responses, just print the response
        try:
            response_json = response.json()
            print(f"Error response: {json.dumps(response_json, indent=2)}")
        except:
            print(f"Error response text: {response.text}")
        print("✅ Test PASSED: Got expected error status")
    
    return True

def test_server_availability():
    """Test if the server is running"""
    print("Testing server availability...")
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running and accessible")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Server is not accessible: {e}")
        print("Make sure the FastAPI server is running on localhost:8080")
        print("You can start it with: python main.py")
        return False

def main():
    """Main test function"""
    print("Starting API Test Suite")
    print(f"Target URL: {API_BASE_URL}")
    
    # Test server availability first
    if not test_server_availability():
        print("\n❌ Cannot proceed with tests - server is not accessible")
        sys.exit(1)
    
    # Run all test cases
    passed = 0
    failed = 0
    
    for test_case in TEST_CASES:
        if run_test_case(test_case):
            passed += 1
        else:
            failed += 1
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {len(TEST_CASES)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {(passed/len(TEST_CASES)*100):.1f}%")
    
    if failed > 0:
        print("\n❌ Some tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")

if __name__ == "__main__":
    main()
