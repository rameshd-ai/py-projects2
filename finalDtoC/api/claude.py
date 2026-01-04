"""
Claude AI Client
Handles HTML generation from screenshots using Claude AI
"""
import os
import base64
from typing import Optional
from anthropic import Anthropic


class ClaudeClient:
    """Client for interacting with Claude AI"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude client
        
        Args:
            api_key: Claude API key (from .env)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        self.client = Anthropic(api_key=self.api_key)
    
    def encode_image(self, image_path: str) -> str:
        """
        Encode image to base64 for API
        
        Args:
            image_path: Path to image file
        
        Returns:
            Base64 encoded image string
        """
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def generate_html(self, screenshot_path: str, additional_context: Optional[str] = None) -> str:
        """
        Generate HTML from Figma screenshot using Claude
        
        Args:
            screenshot_path: Path to screenshot image
            additional_context: Optional additional context/prompts
        
        Returns:
            Generated HTML string
        """
        # Encode image
        image_data = self.encode_image(screenshot_path)
        
        # Build prompt
        prompt = """Analyze this Figma design screenshot and generate clean, semantic HTML code that matches the design.

Requirements:
1. Use semantic HTML5 elements (header, nav, main, section, article, footer, etc.)
2. Include proper heading hierarchy (h1, h2, h3)
3. Use appropriate HTML elements for images, buttons, links, etc.
4. Add meaningful class names that describe the component structure
5. Include inline CSS for styling to match the design
6. Make the HTML responsive and accessible
7. Preserve the visual layout and structure

Generate only the HTML code, no markdown formatting."""
        
        if additional_context:
            prompt += f"\n\nAdditional context: {additional_context}"
        
        # Call Claude API
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
        
        # Extract HTML from response
        html_content = message.content[0].text
        
        # Clean up if wrapped in markdown code blocks
        if html_content.startswith('```html'):
            html_content = html_content[7:]
        if html_content.startswith('```'):
            html_content = html_content[3:]
        if html_content.endswith('```'):
            html_content = html_content[:-3]
        
        return html_content.strip()

