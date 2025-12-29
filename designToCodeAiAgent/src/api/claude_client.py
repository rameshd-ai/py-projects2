"""
Claude/Anthropic API Client
Handles all interactions with Anthropic Claude API:
- Generate HTML from screenshots
- Analyze HTML structure
- Extract component definitions
- Create Handlebars templates
"""
import base64
from anthropic import Anthropic, AsyncAnthropic
from typing import Dict, List, Optional, Union
import asyncio
from datetime import datetime

from src.config import settings


class ClaudeAPIError(Exception):
    """Raised when Claude API returns an error"""
    pass


class ClaudeClient:
    """
    Client for interacting with Anthropic Claude API
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude client
        
        Args:
            api_key: Anthropic API key (from settings if not provided)
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.model = settings.anthropic_model
        self.max_tokens = settings.anthropic_max_tokens
        self.temperature = settings.anthropic_temperature
        self.rate_limit = settings.claude_rate_limit
        
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
        
        # Initialize async client
        self.client = AsyncAnthropic(api_key=self.api_key)
        
        # Rate limiting
        self._last_request_time = None
        self._request_interval = 60.0 / self.rate_limit
    
    async def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self._request_interval:
                await asyncio.sleep(self._request_interval - elapsed)
        self._last_request_time = datetime.now()
    
    def _encode_image(self, image_data: bytes) -> str:
        """
        Encode image to base64
        
        Args:
            image_data: Image bytes
            
        Returns:
            Base64 encoded string
        """
        return base64.b64encode(image_data).decode('utf-8')
    
    async def _create_message(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Create Claude API message
        
        Args:
            messages: List of message dicts
            system: System prompt
            max_tokens: Max tokens to generate
            temperature: Temperature for generation
            
        Returns:
            Response text
        """
        await self._wait_for_rate_limit()
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                system=system,
                messages=messages
            )
            
            # Extract text from response
            return response.content[0].text
            
        except Exception as e:
            raise ClaudeAPIError(f"Claude API error: {str(e)}") from e
    
    async def generate_html_from_screenshot(
        self,
        screenshot: bytes,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Generate HTML from screenshot
        
        Args:
            screenshot: Screenshot image bytes
            additional_context: Additional context/requirements
            
        Returns:
            Generated HTML code
        """
        # Encode image
        image_b64 = self._encode_image(screenshot)
        
        # Construct prompt
        system_prompt = """You are an expert web developer. Your task is to generate clean, semantic HTML from design screenshots.

Requirements:
- Use modern HTML5 semantic tags
- Include appropriate class names (use utility classes when applicable)
- Preserve the visual hierarchy and structure
- Use descriptive element IDs and classes
- Do NOT include CSS or JavaScript
- Return ONLY the HTML code, no explanations"""
        
        user_message = "Generate HTML for this design screenshot."
        if additional_context:
            user_message += f"\n\nAdditional context: {additional_context}"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": user_message
                    }
                ]
            }
        ]
        
        html = await self._create_message(messages, system=system_prompt)
        
        # Clean up response (remove markdown code blocks if present)
        html = html.strip()
        if html.startswith("```html"):
            html = html[7:]
        if html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        
        return html.strip()
    
    async def analyze_html_structure(
        self,
        html: str,
        return_json: bool = True
    ) -> Union[str, Dict]:
        """
        Analyze HTML structure and identify components
        
        Args:
            html: HTML code to analyze
            return_json: Return as JSON dict
            
        Returns:
            Analysis of HTML structure
        """
        system_prompt = """You are an expert at analyzing HTML structure.
Identify the component hierarchy, semantic sections, and relationships between elements."""
        
        messages = [
            {
                "role": "user",
                "content": f"""Analyze this HTML and identify:
1. Main component structure (parent/children)
2. Semantic sections (header, nav, main, etc.)
3. Repeating patterns
4. Data-driven elements (lists, cards, etc.)

Return as {"JSON" if return_json else "structured text"}.

HTML:
```html
{html}
```"""
            }
        ]
        
        response = await self._create_message(messages, system=system_prompt)
        
        if return_json:
            # Try to parse as JSON
            import json
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    response = response[start:end].strip()
                elif "```" in response:
                    start = response.find("```") + 3
                    end = response.find("```", start)
                    response = response[start:end].strip()
                
                return json.loads(response)
            except json.JSONDecodeError:
                # Return as text if JSON parsing fails
                return {"analysis": response}
        
        return response
    
    async def extract_component_definitions(
        self,
        html: str,
        config_structure: Dict,
        format_example: Optional[str] = None
    ) -> Dict:
        """
        Extract component definitions from HTML
        Maps HTML elements to CMS definition structure
        
        Args:
            html: HTML code
            config_structure: Example config structure to follow
            format_example: Example format template
            
        Returns:
            Component definitions
        """
        system_prompt = """You are an expert at mapping HTML to CMS component definitions.
Create a structured definition following the MiBlock format."""
        
        example_info = ""
        if format_example:
            example_info = f"\n\nFormat example:\n{format_example}"
        
        messages = [
            {
                "role": "user",
                "content": f"""Map this HTML to component definitions following this structure:

Config Structure:
{config_structure}
{example_info}

HTML to map:
```html
{html}
```

Return a JSON object with:
- Component hierarchy (Level0, Level1, etc.)
- PropertyName and PropertyAliasName for each element
- ControlId (1=Text, 7=Image, 8=Boolean, etc.)
- Parent-child relationships"""
            }
        ]
        
        response = await self._create_message(messages, system=system_prompt)
        
        # Parse JSON response
        import json
        try:
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ClaudeAPIError(f"Failed to parse component definitions: {e}")
    
    async def create_handlebars_template(
        self,
        html: str,
        definitions: Dict
    ) -> str:
        """
        Convert HTML to Handlebars template
        
        Args:
            html: Original HTML
            definitions: Component definitions
            
        Returns:
            Handlebars template (FormatContent)
        """
        system_prompt = """You are an expert at creating Handlebars templates.
Convert static HTML to dynamic Handlebars templates with {{data.xxx}} placeholders."""
        
        messages = [
            {
                "role": "user",
                "content": f"""Convert this HTML to a Handlebars template.

Replace content with:
- {{{{data.PropertyName}}}} for text content
- {{{{#each Child.ComponentName}}}} for repeating sections
- Keep all HTML structure and attributes

Definitions to use:
{definitions}

HTML:
```html
{html}
```

Return ONLY the Handlebars template, no explanations."""
            }
        ]
        
        template = await self._create_message(messages, system=system_prompt)
        
        # Clean up response
        template = template.strip()
        if template.startswith("```handlebars") or template.startswith("```hbs"):
            template = template[template.find("\n") + 1:]
        if template.startswith("```html"):
            template = template[7:]
        if template.startswith("```"):
            template = template[3:]
        if template.endswith("```"):
            template = template[:-3]
        
        return template.strip()
    
    async def validate_html_match(
        self,
        original_screenshot: bytes,
        generated_html: str,
        threshold: float = 0.85
    ) -> Dict:
        """
        Validate if generated HTML matches screenshot
        (Visual validation via Claude)
        
        Args:
            original_screenshot: Original screenshot bytes
            generated_html: Generated HTML
            threshold: Match threshold
            
        Returns:
            Dict with match result and suggestions
        """
        image_b64 = self._encode_image(original_screenshot)
        
        system_prompt = """You are an expert at comparing designs and HTML output.
Analyze if the HTML accurately represents the design screenshot."""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""Compare this design screenshot with the generated HTML.

Generated HTML:
```html
{generated_html}
```

Analyze:
1. Does the HTML structure match the visual design?
2. Are all major sections present?
3. Is the hierarchy correct?
4. What's missing or incorrect?

Return JSON:
{{
  "matches": true/false,
  "confidence": 0.0-1.0,
  "issues": ["list of issues"],
  "suggestions": ["list of improvements"]
}}"""
                    }
                ]
            }
        ]
        
        response = await self._create_message(messages, system=system_prompt)
        
        # Parse JSON
        import json
        try:
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            return {
                "matches": False,
                "confidence": 0.0,
                "issues": ["Failed to validate"],
                "suggestions": []
            }


# Example usage
if __name__ == "__main__":
    async def test_claude_client():
        """Test Claude client functionality"""
        client = ClaudeClient()
        
        # Test with dummy screenshot
        dummy_screenshot = b"dummy_image_data"
        
        try:
            html = await client.generate_html_from_screenshot(dummy_screenshot)
            print("Generated HTML:")
            print(html[:200])
        except Exception as e:
            print(f"Error: {e}")
    
    # Run test
    # asyncio.run(test_claude_client())


