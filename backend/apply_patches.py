#!/usr/bin/env python3
"""
Apply patch operations to HTML file.

This script takes the JSON response from the backend and applies the patch
operations to the original HTML file, generating a modified HTML file.

Usage:
    python apply_patches.py --input sample.html --patches response.json --output modified.html
    
Or run the full test:
    python apply_patches.py --test
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag


def add_element_ids(html: str) -> tuple[str, dict[str, str]]:
    """
    Add data-element-id attributes to HTML elements.
    This mimics what the backend does during preprocessing.
    """
    soup = BeautifulSoup(html, 'lxml')
    element_id_map = {}
    counter = 0
    
    # Add IDs to all meaningful elements
    for element in soup.find_all(True):
        if not isinstance(element, Tag):
            continue
        
        # Skip script, style, head, meta, link tags
        if element.name in ['script', 'style', 'head', 'meta', 'link']:
            continue
        
        # Generate element ID
        element_id = f"e{counter}"
        counter += 1
        
        # Add ID attribute
        element['data-element-id'] = element_id
        element_id_map[element_id] = element_id
    
    return str(soup), element_id_map


class PatchApplicator:
    """Applies patch operations to HTML."""
    
    def __init__(self, html: str, preprocess: bool = True):
        """
        Initialize with HTML content.
        
        Args:
            html: HTML content
            preprocess: If True, add element IDs like the backend does
        """
        if preprocess:
            html, self.element_id_map = add_element_ids(html)
            print(f"   ℹ️  Added {len(self.element_id_map)} element IDs during preprocessing")
        
        self.soup = BeautifulSoup(html, 'lxml')
    
    def apply_patches(self, patches: list) -> str:
        """
        Apply all patch operations and return modified HTML.
        
        Args:
            patches: List of patch operations
        """
        print(f"\n📝 Applying {len(patches)} patch operations...")
        
        for i, patch in enumerate(patches, 1):
            op = patch.get('op')
            print(f"\n{i}. Applying {op} operation...")
            
            try:
                if op == 'move':
                    self._apply_move(patch)
                elif op == 'insert':
                    self._apply_insert(patch)
                elif op == 'replace':
                    self._apply_replace(patch)
                elif op == 'delete':
                    self._apply_delete(patch)
                elif op == 'set_attr':
                    self._apply_set_attr(patch)
                elif op == 'add_class':
                    self._apply_add_class(patch)
                elif op == 'remove_class':
                    self._apply_remove_class(patch)
                elif op == 'wrap':
                    self._apply_wrap(patch)
                elif op == 'unwrap':
                    self._apply_unwrap(patch)
                else:
                    print(f"   ⚠️  Unknown operation: {op}")
                
                print(f"   ✅ Applied successfully")
            
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        return str(self.soup)
    
    def _find_element(self, selector: str):
        """Find element by selector."""
        # Handle data-element-id selectors
        if 'data-element-id' in selector:
            # Extract ID from selector like [data-element-id='e5']
            import re
            match = re.search(r"data-element-id=['\"](\w+)['\"]", selector)
            if match:
                element_id = match.group(1)
                return self.soup.find(attrs={'data-element-id': element_id})
        
        # Try CSS selector
        return self.soup.select_one(selector)
    
    def _apply_move(self, patch: dict):
        """Apply move operation."""
        element = self._find_element(patch['selector'])
        target = self._find_element(patch['target_selector'])
        position = patch['position']
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        if not target:
            raise ValueError(f"Target not found: {patch['target_selector']}")
        
        # Extract the element
        element.extract()
        
        # Insert at new position
        if position == 'before':
            target.insert_before(element)
        elif position == 'after':
            target.insert_after(element)
        elif position == 'prepend':
            target.insert(0, element)
        elif position == 'append':
            target.append(element)
        
        print(f"   Moved element to {position} target")
    
    def _apply_insert(self, patch: dict):
        """Apply insert operation."""
        target = self._find_element(patch['target_selector'])
        position = patch['position']
        html = patch['html']
        
        if not target:
            raise ValueError(f"Target not found: {patch['target_selector']}")
        
        # Parse the HTML to insert
        new_element = BeautifulSoup(html, 'lxml').body
        if new_element:
            # Get the actual content (skip body wrapper)
            content = list(new_element.children)
            
            if position == 'before':
                for item in reversed(content):
                    target.insert_before(item)
            elif position == 'after':
                for item in content:
                    target.insert_after(item)
            elif position == 'prepend':
                for i, item in enumerate(content):
                    target.insert(i, item)
            elif position == 'append':
                for item in content:
                    target.append(item)
        
        print(f"   Inserted HTML at {position} target")
    
    def _apply_replace(self, patch: dict):
        """Apply replace operation."""
        element = self._find_element(patch['selector'])
        html = patch['html']
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        # Parse replacement HTML
        new_element = BeautifulSoup(html, 'lxml').body
        if new_element:
            content = list(new_element.children)
            # Replace with new content
            for item in content:
                element.insert_before(item)
            element.decompose()
        
        print(f"   Replaced element")
    
    def _apply_delete(self, patch: dict):
        """Apply delete operation."""
        element = self._find_element(patch['selector'])
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        element.decompose()
        print(f"   Deleted element")
    
    def _apply_set_attr(self, patch: dict):
        """Apply set_attr operation."""
        element = self._find_element(patch['selector'])
        name = patch['name']
        value = patch['value']
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        if value is None:
            # Remove attribute
            if name in element.attrs:
                del element.attrs[name]
                print(f"   Removed attribute: {name}")
        else:
            # Set attribute
            element[name] = value
            print(f"   Set attribute: {name}={value}")
    
    def _apply_add_class(self, patch: dict):
        """Apply add_class operation."""
        element = self._find_element(patch['selector'])
        class_name = patch['class_name']
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        # Get current classes
        classes = element.get('class', [])
        if isinstance(classes, str):
            classes = classes.split()
        
        if class_name not in classes:
            classes.append(class_name)
            element['class'] = classes
        
        print(f"   Added class: {class_name}")
    
    def _apply_remove_class(self, patch: dict):
        """Apply remove_class operation."""
        element = self._find_element(patch['selector'])
        class_name = patch['class_name']
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        # Get current classes
        classes = element.get('class', [])
        if isinstance(classes, str):
            classes = classes.split()
        
        if class_name in classes:
            classes.remove(class_name)
            element['class'] = classes if classes else None
        
        print(f"   Removed class: {class_name}")
    
    def _apply_wrap(self, patch: dict):
        """Apply wrap operation."""
        element = self._find_element(patch['selector'])
        wrapper_html = patch['wrapper_html']
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        # Parse wrapper HTML
        wrapper = BeautifulSoup(wrapper_html, 'lxml').body
        if wrapper and wrapper.contents:
            wrapper_element = wrapper.contents[0]
            element.wrap(wrapper_element)
        
        print(f"   Wrapped element")
    
    def _apply_unwrap(self, patch: dict):
        """Apply unwrap operation."""
        element = self._find_element(patch['selector'])
        
        if not element:
            raise ValueError(f"Element not found: {patch['selector']}")
        
        element.unwrap()
        print(f"   Unwrapped element")


async def test_full_workflow():
    """Run full test: call API, get patches, apply them."""
    print("=" * 80)
    print("FULL DOM MANIPULATION TEST")
    print("=" * 80)
    
    # Read sample HTML
    sample_path = Path(__file__).parent / "tests" / "fixtures" / "sample.html"
    if not sample_path.exists():
        print(f"❌ Error: {sample_path} not found")
        return 1
    
    with open(sample_path, 'r') as f:
        original_html = f.read()
    
    print(f"\n📄 Input: {sample_path}")
    print(f"   Size: {len(original_html)} bytes")
    
    # Call backend API
    print("\n🚀 Calling backend API...")
    request_data = {
        "use_case": "dom_manipulation",
        "page_url": "https://example.com/test",
        "html": original_html,
        "user_prompt": "move the sidebar to the top right corner of the page while keeping everything else as it is",
        "params": {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:8000/api/v1/process",
                json=request_data
            )
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                print(response.text)
                return 1
            
            data = response.json()
            
            if data.get('status') == 'error':
                print(f"❌ Backend Error: {data.get('error')}")
                return 1
            
            print("✅ API call successful")
            
            # Get patches
            result = data.get('result', {})
            patches = result.get('patches', [])
            
            print(f"\n📋 Received {len(patches)} patch operations")
            
            if not patches:
                print("⚠️  No patches to apply")
                return 0
            
            # Apply patches
            applicator = PatchApplicator(original_html)
            modified_html = applicator.apply_patches(patches)
            
            # Save modified HTML
            output_path = Path(__file__).parent / "sample_modified.html"
            with open(output_path, 'w') as f:
                f.write(modified_html)
            
            print(f"\n💾 Modified HTML saved to: {output_path}")
            print(f"   Size: {len(modified_html)} bytes")
            
            # Save patches JSON
            patches_path = Path(__file__).parent / "patches.json"
            with open(patches_path, 'w') as f:
                json.dump(patches, f, indent=2)
            
            print(f"💾 Patches saved to: {patches_path}")
            
            print("\n" + "=" * 80)
            print("✅ TEST COMPLETED SUCCESSFULLY")
            print("=" * 80)
            print(f"\nOpen {output_path} in a browser to see the result!")
            
            return 0
    
    except httpx.ConnectError:
        print("❌ Error: Could not connect to backend")
        print("   Make sure server is running: python -m uvicorn app.main:app --reload")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def apply_from_files(input_path: str, patches_path: str, output_path: str):
    """Apply patches from JSON file to HTML file."""
    print("=" * 80)
    print("APPLYING PATCHES FROM FILES")
    print("=" * 80)
    
    # Read input HTML
    print(f"\n📄 Reading HTML from: {input_path}")
    with open(input_path, 'r') as f:
        html = f.read()
    
    # Read patches
    print(f"📋 Reading patches from: {patches_path}")
    with open(patches_path, 'r') as f:
        patches = json.load(f)
    
    # Apply patches
    applicator = PatchApplicator(html)
    modified_html = applicator.apply_patches(patches)
    
    # Save result
    print(f"\n💾 Saving modified HTML to: {output_path}")
    with open(output_path, 'w') as f:
        f.write(modified_html)
    
    print("\n✅ Done!")
    print(f"Open {output_path} in a browser to see the result!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Apply DOM manipulation patches to HTML")
    parser.add_argument('--test', action='store_true', help='Run full test workflow')
    parser.add_argument('--input', help='Input HTML file')
    parser.add_argument('--patches', help='Patches JSON file')
    parser.add_argument('--output', help='Output HTML file')
    
    args = parser.parse_args()
    
    if args.test:
        return asyncio.run(test_full_workflow())
    elif args.input and args.patches and args.output:
        apply_from_files(args.input, args.patches, args.output)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
