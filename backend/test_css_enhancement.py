#!/usr/bin/env python3
"""
Test script to verify that LLM can generate CSS positioning patches.

Note: This test now expects the LLM to generate CSS patches, not the backend.
The backend no longer automatically adds CSS enhancement - that's the LLM's job.
"""
import asyncio
import json
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.handlers.dom_manipulation import DOMManipulationHandler
from app.schemas.dom_manipulation import DOMManipulationRequest


async def test_css_enhancement():
    """
    Test that the system can handle CSS patches from the LLM.
    
    Note: The LLM is responsible for generating CSS patches when needed.
    This test simulates an LLM response that includes CSS positioning.
    """
    
    # Load sample HTML
    sample_html_path = Path(__file__).parent / "tests" / "fixtures" / "sample.html"
    with open(sample_html_path, 'r') as f:
        html = f.read()
    
    print("=" * 80)
    print("Testing CSS Enhancement in Backend")
    print("=" * 80)
    
    # Create handler
    handler = DOMManipulationHandler()
    
    # Create request
    request = DOMManipulationRequest(
        page_url="https://example.com",
        html=html,
        user_prompt="move the sidebar to the top right corner",
        params={}
    )
    
    print(f"\nðŸ“„ Input HTML length: {len(html)} chars")
    print(f"ðŸ“ User prompt: {request.user_prompt}")
    
    # Preprocess
    print("\nðŸ”„ Preprocessing HTML...")
    context = await handler.preprocess(html, request)
    print(f"   âœ… Processed HTML length: {len(context.processed_html)} chars")
    print(f"   âœ… Element count: {len(context.element_id_map)}")
    
    # Build messages
    print("\nðŸ’¬ Building AI messages...")
    messages = await handler.build_messages(context, request, request.user_prompt)
    print(f"   âœ… Created {len(messages)} messages")
    
    # Simulate AI response (we'll create a mock response)
    print("\nðŸ¤– Simulating AI response...")
    # Find the sidebar element ID from element map
    sidebar_elem_id = None
    body_elem_id = None
    for elem_id, css_selector in context.element_id_map.items():
        if 'sidebar' in css_selector.lower() or 'aside' in css_selector.lower():
            sidebar_elem_id = elem_id
            print(f"   Found sidebar: {elem_id} -> {css_selector}")
        if css_selector == 'body':
            body_elem_id = elem_id
    
    # Build proper element ID selectors
    if sidebar_elem_id:
        sidebar_selector = f"[data-element-id='{sidebar_elem_id}']"
    else:
        print("   âš ï¸  Warning: Could not find sidebar in element map, using CSS fallback")
        sidebar_selector = "aside.sidebar"
    
    if body_elem_id:
        body_selector = f"[data-element-id='{body_elem_id}']"
    else:
        body_selector = "body"
    
    # Simulate LLM response with CSS positioning (LLM's responsibility now)
    mock_ai_response = json.dumps({
        "patches": [
            {
                "op": "move",
                "selector": sidebar_selector,
                "target_selector": body_selector,
                "position": "prepend"
            },
            {
                "op": "set_attr",
                "selector": sidebar_selector,
                "name": "style",
                "value": "position: fixed; top: 20px; right: 20px; width: 250px; background: #f5f5f5; padding: 15px; border: 1px solid #ddd; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); z-index: 1000;"
            }
        ],
        "element_count": len(context.element_id_map),
        "applied_skeletonization": context.metadata.get("applied_skeletonization", False)
    })
    
    # Parse response
    print("\nðŸ“Š Parsing AI response...")
    parsed = await handler.parse_response(mock_ai_response, context)
    print(f"   âœ… Parsed {len(parsed.patches)} patches")
    for i, patch in enumerate(parsed.patches, 1):
        print(f"   {i}. {patch.op}: {getattr(patch, 'element_id', 'N/A')}")
    
    # Postprocess (this is where CSS enhancement happens)
    print("\nðŸŽ¨ Postprocessing (CSS enhancement)...")
    result = await handler.postprocess(parsed, context)
    
    print(f"\nâœ… Final result has {len(result.patches)} patches:")
    for i, patch in enumerate(result.patches, 1):
        patch_dict = patch.dict()
        print(f"\n{i}. Operation: {patch_dict['op']}")
        if patch_dict['op'] == 'move':
            print(f"   Selector: {patch_dict.get('selector')}")
            print(f"   Target: {patch_dict.get('target_selector')}")
            print(f"   Position: {patch_dict.get('position')}")
        elif patch_dict['op'] == 'set_attr':
            print(f"   Selector: {patch_dict.get('selector')}")
            print(f"   Attribute: {patch_dict.get('name')}")
            value = patch_dict.get('value', '')
            if len(value) > 100:
                print(f"   Value: {value[:100]}...")
            else:
                print(f"   Value: {value}")
    
    # Check if CSS positioning was added
    has_css_patch = any(
        p.op == 'set_attr' and p.name == 'style' 
        for p in result.patches
    )
    
    print("\n" + "=" * 80)
    if has_css_patch:
        print("âœ… SUCCESS: LLM-generated CSS positioning patch found!")
        print("   (Note: CSS is now LLM's responsibility, not backend enhancement)")
    else:
        print("âŒ FAILURE: No CSS positioning patch found")
        print("   (This would mean the LLM didn't generate CSS when it should have)")
    print("=" * 80)
    
    return result


if __name__ == "__main__":
    asyncio.run(test_css_enhancement())
