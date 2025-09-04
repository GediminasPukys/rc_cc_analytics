#!/usr/bin/env python3
"""
Very simple Gemini structured output example
Minimal Pydantic model to test basic functionality
"""

import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import google.generativeai as genai
import json

# Load environment variables
load_dotenv()


# VERY SIMPLE Pydantic model - no enums, no optional fields
class SimpleRecipe(BaseModel):
    """A simple recipe model"""
    recipe_name: str = Field(description="Name of the recipe")
    ingredients: str = Field(description="Comma-separated list of ingredients")
    prep_time_minutes: int = Field(description="Preparation time in minutes")
    difficulty: str = Field(description="Difficulty level: easy, medium, or hard")


def test_simplest_structure():
    """Test the simplest possible structured output"""
    print("=" * 60)
    print("SIMPLEST POSSIBLE STRUCTURED OUTPUT TEST")
    print("=" * 60)
    
    # Configure Gemini
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found")
        return
    
    print(f"✅ API key found: {api_key[:10]}...")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Test 1: JSON without schema
    print("\n📝 Test 1: JSON mode without schema constraint")
    print("-" * 40)
    
    generation_config = genai.GenerationConfig(
        temperature=0.3,
        response_mime_type="application/json"
    )
    
    prompt = """
    Create a simple recipe in JSON format with these fields:
    - recipe_name: string
    - ingredients: string (comma-separated)
    - prep_time_minutes: number
    - difficulty: string (easy, medium, or hard)
    
    Make it a chocolate chip cookie recipe.
    """
    
    try:
        response = model.generate_content(prompt, generation_config=generation_config)
        print("✅ Response received!")
        
        if hasattr(response, 'text'):
            print(f"Raw response: {response.text[:200]}...")
            data = json.loads(response.text)
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
    
    # Test 2: With Pydantic schema
    print("\n📝 Test 2: JSON mode WITH Pydantic schema")
    print("-" * 40)
    
    generation_config_with_schema = genai.GenerationConfig(
        temperature=0.3,
        response_mime_type="application/json",
        response_schema=SimpleRecipe  # Add the Pydantic model
    )
    
    prompt2 = "Create a recipe for chocolate chip cookies."
    
    try:
        print(f"Schema: {SimpleRecipe.model_json_schema()}")
        response = model.generate_content(prompt2, generation_config=generation_config_with_schema)
        print("✅ Response received!")
        
        if hasattr(response, 'text'):
            print(f"Raw response: {response.text[:200]}...")
            data = json.loads(response.text)
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
            
            # Create Pydantic instance
            recipe = SimpleRecipe(**data)
            print(f"\n✅ Valid SimpleRecipe created:")
            print(f"   Name: {recipe.recipe_name}")
            print(f"   Time: {recipe.prep_time_minutes} minutes")
            print(f"   Difficulty: {recipe.difficulty}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
        
        # If schema error, try to see what's wrong
        if "Unknown field" in str(e):
            print("\n⚠️  Schema issue detected. Checking schema...")
            schema = SimpleRecipe.model_json_schema()
            print(f"Schema keys: {list(schema.keys())}")
            if 'properties' in schema:
                for prop, details in schema['properties'].items():
                    print(f"  - {prop}: {list(details.keys())}")


if __name__ == "__main__":
    test_simplest_structure()