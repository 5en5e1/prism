#!/usr/bin/env python3
"""
Test the DOM manipulation feature with sample.html.

This script sends a real request to the backend to test the DOM manipulation
feature with the sample HTML file.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx


async def test_dom_manipulation():
    """Test DOM manipulation with sample.html."""
    
    # Read the sample HTML
    sample_html_path = Path(__file__).parent / "tests" / "fixtures" / "sample.html"
    
    if not sample_html_path.exists():
        print(f"❌ Error: Sample HTML not found at {sample_html_path}")
        return 1
    
    with open(sample_html_path, "r") as f:
        html_content = f.read()
    
    print("=" * 80)
    print("DOM MANIPULATION FEATURE TEST")
    print("=" * 80)
    print()
    
    # Prepare the request
    base_url = "http://localhost:8000"
    request_data = {
        "use_case": "dom_manipulation",
        "page_url": "https://example.com/test",
        "html": html_content,
        "user_prompt": "move the sidebar to the top right corner of the page while keeping everything else as it is",
        "params": {},
        "client_metadata": {
            "extension_version": "1.0.0"
        }
    }
    
    print("📄 Input HTML:")
    print(f"   File: {sample_html_path}")
    print(f"   Size: {len(html_content)} bytes")
    print()
    
    print("💬 User Prompt:")
    print(f'   "{request_data["user_prompt"]}"')
    print()
    
    print("🚀 Sending request to backend...")
    print(f"   Endpoint: POST {base_url}/api/v1/process")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/api/v1/process",
                json=request_data
            )
            
            print(f"📊 Response Status: {response.status_code}")
            print()
            
            if response.status_code != 200:
                print(f"❌ Error: Request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return 1
            
            data = response.json()
            
            # Print response details
            print("✅ Response received successfully!")
            print()
            
            print("🔍 Response Details:")
            print(f"   Trace ID: {data.get('trace_id')}")
            print(f"   Use Case: {data.get('use_case')}")
            print(f"   Status: {data.get('status')}")
            print()
            
            # Check for errors
            if data.get("status") == "error":
                error = data.get("error", {})
                print(f"❌ Error occurred:")
                print(f"   Code: {error.get('code')}")
                print(f"   Message: {error.get('message')}")
                print(f"   Stage: {error.get('stage')}")
                print(f"   Retryable: {error.get('retryable')}")
                return 1
            
            # Print warnings if any
            warnings = data.get("warnings", [])
            if warnings:
                print("⚠️  Warnings:")
                for warning in warnings:
                    print(f"   - {warning}")
                print()
            
            # Print usage statistics
            usage = data.get("usage")
            if usage:
                print("📈 Token Usage:")
                print(f"   Input Tokens: {usage.get('input_tokens')}")
                print(f"   Output Tokens: {usage.get('output_tokens')}")
                print(f"   Model: {usage.get('model')}")
                print()
            
            # Print timing information
            timing = data.get("timing_ms")
            if timing:
                print("⏱️  Timing (milliseconds):")
                print(f"   Preprocessing: {timing.get('preprocess_ms'):.2f}ms")
                print(f"   AI Call: {timing.get('ai_ms'):.2f}ms")
                print(f"   Postprocessing: {timing.get('postprocess_ms'):.2f}ms")
                print(f"   Total: {timing.get('total_ms'):.2f}ms")
                print()
            
            # Print patch operations
            result = data.get("result", {})
            patches = result.get("patches", [])
            
            print(f"🔧 Generated Patch Operations: {len(patches)}")
            print()
            
            if not patches:
                print("   ⚠️  No patch operations generated!")
                print("   This might indicate the AI didn't understand the prompt")
                print("   or couldn't find the sidebar element.")
            else:
                for i, patch in enumerate(patches, 1):
                    print(f"   {i}. Operation: {patch.get('op')}")
                    
                    # Print operation-specific details
                    if patch.get('op') == 'move':
                        print(f"      Selector: {patch.get('selector')}")
                        print(f"      Target: {patch.get('target_selector')}")
                        print(f"      Position: {patch.get('position')}")
                    elif patch.get('op') == 'insert':
                        print(f"      Target: {patch.get('target_selector')}")
                        print(f"      Position: {patch.get('position')}")
                        print(f"      HTML: {patch.get('html')[:100]}...")
                    elif patch.get('op') == 'replace':
                        print(f"      Selector: {patch.get('selector')}")
                        print(f"      HTML: {patch.get('html')[:100]}...")
                    elif patch.get('op') == 'delete':
                        print(f"      Selector: {patch.get('selector')}")
                    elif patch.get('op') in ['add_class', 'remove_class']:
                        print(f"      Selector: {patch.get('selector')}")
                        print(f"      Class: {patch.get('class_name')}")
                    elif patch.get('op') == 'set_attr':
                        print(f"      Selector: {patch.get('selector')}")
                        print(f"      Attribute: {patch.get('name')} = {patch.get('value')}")
                    elif patch.get('op') == 'wrap':
                        print(f"      Selector: {patch.get('selector')}")
                        print(f"      Wrapper: {patch.get('wrapper_html')}")
                    elif patch.get('op') == 'unwrap':
                        print(f"      Selector: {patch.get('selector')}")
                    
                    print()
            
            # Print metadata
            print("📋 Metadata:")
            print(f"   Element Count: {result.get('element_count')}")
            print(f"   Skeletonization Applied: {result.get('applied_skeletonization')}")
            print()
            
            # Save full response to file
            output_file = Path(__file__).parent / "test_dom_response.json"
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            
            print(f"💾 Full response saved to: {output_file}")
            print()
            
            print("=" * 80)
            print("✅ TEST COMPLETED SUCCESSFULLY")
            print("=" * 80)
            
            return 0
    
    except httpx.ConnectError:
        print("❌ Error: Could not connect to backend server")
        print("   Make sure the server is running at http://localhost:8000")
        print("   Start it with: python -m uvicorn app.main:app --reload")
        return 1
    
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(test_dom_manipulation()))

# Made with Bob
