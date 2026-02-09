"""Kimi K2 Thinking API Client"""
import os
import json
import re
from typing import Dict, Any, List, Optional
import structlog
from openai import OpenAI

logger = structlog.get_logger()


class KimiClient:
    """Client for Kimi K2 Thinking via OpenRouter"""
    
    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2-thinking")
        self.temperature = float(os.getenv("KIMI_TEMPERATURE", "1.0"))
    
    def _clean_json_response(self, response: str) -> str:
        """Strip markdown code blocks from JSON responses"""
        # Remove ```json and ``` wrappers
        cleaned = re.sub(r'^```json\s*', '', response, flags=re.MULTILINE)
        cleaned = re.sub(r'^```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return cleaned.strip()
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096
    ) -> str:
        """Send completion request to Kimi K2 Thinking"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=self.temperature
            )
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error("Kimi API error", error=str(e))
            raise
    
    async def structured_completion(
        self,
        messages: List[Dict[str, str]],
        response_format: Dict[str, Any],
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Get structured JSON response"""
        try:
            # Enhance system message for JSON compliance
            json_instruction = {
                "role": "system",
                "content": f"""You must respond with ONLY valid JSON matching this exact schema.
Do not include any markdown formatting, code blocks, or explanatory text.
Output raw JSON only.

Required schema:
{json.dumps(response_format, indent=2)}

CRITICAL: Your entire response must be parseable by json.loads(). 
Do NOT wrap in ```json or ``` tags.
Output ONLY the raw JSON object."""
            }
            
            # Add instruction at the beginning
            enhanced_messages = [json_instruction] + messages
            
            response_text = await self.complete(enhanced_messages, max_tokens)
            
            # Clean markdown code blocks if present
            cleaned_response = self._clean_json_response(response_text)
            
            # Parse JSON
            parsed = json.loads(cleaned_response)
            
            logger.debug(
                "Structured completion succeeded",
                response_length=len(response_text),
                cleaned_length=len(cleaned_response)
            )
            
            return parsed
        
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON response",
                error=str(e),
                response_content=response_text[:1000]  # Log first 1000 chars
            )
            # Re-raise with original response for debugging
            raise ValueError(f"JSON parse error: {e}\nResponse: {response_text[:500]}")
        
        except Exception as e:
            logger.error("Structured completion error", error=str(e))
            raise