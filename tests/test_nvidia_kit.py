# tests/test_nvidia_kit.py

import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aether.nvidia_kit import NVIDIAKit, ModelResponse

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "test_api_key"}):
        yield

@pytest.mark.asyncio
async def test_nvidia_kit_initialization(mock_env):
    """Test NVIDIAKit initialization"""
    kit = NVIDIAKit()
    assert kit.config.api_key == "test_api_key"
    await kit.close()

@pytest.mark.asyncio
async def test_nvidia_kit_completion(mock_env):
    """Test successful completion call"""
    async with NVIDIAKit() as kit:
        with patch.object(kit, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.content.iter_any.return_value = [
                b"data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}], \"usage\": {\"total_tokens\": 10}}\n\n",
                b"data: [DONE]"
            ]
            mock_request.return_value = mock_response

            response = await kit.complete(messages=[{"role": "user", "content": "Hi"}])

            assert isinstance(response, ModelResponse)
            assert response.content == "Hello"
            assert response.usage["total_tokens"] == 10

@pytest.mark.asyncio
async def test_nvidia_kit_thinking_mode(mock_env):
    """Test thinking mode"""
    async with NVIDIAKit() as kit:
        with patch.object(kit, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.content.iter_any.return_value = [
                b"data: {\"choices\": [{\"delta\": {\"thinking\": \"Step 1\"}}], \"usage\": {\"total_tokens\": 20}}\n\n",
                b"data: {\"choices\": [{\"delta\": {\"content\": \"Result\"}}], \"usage\": {\"total_tokens\": 20}}\n\n",
                b"data: [DONE]"
            ]
            mock_request.return_value = mock_response

            response = await kit.complete(messages=[{"role": "user", "content": "Solve 1+1"}], thinking=True)

            assert response.thinking == "Step 1"
            assert response.content == "Result"

@pytest.mark.asyncio
async def test_nvidia_kit_vision(mock_env):
    """Test vision (multimodal) call"""
    with patch("builtins.open", new_callable=MagicMock) as mock_open, \
         patch("base64.b64encode", return_value=b"encoded_image") as mock_b64encode:
        
        mock_open.return_value.__enter__.return_value.read.return_value = b"image_data"

        async with NVIDIAKit() as kit:
            with patch.object(kit, "complete", new_callable=AsyncMock) as mock_complete:
                mock_complete.return_value = ModelResponse(content="Image recognized")

                response = await kit.complete_with_vision(
                    messages=[{"role": "user", "content": "What is this?"}],
                    images=["test_image.jpg"]
                )

                assert response.content == "Image recognized"
                mock_complete.assert_called_once()
                call_args = mock_complete.call_args[1]
                assert "data:image/jpeg;base64,encoded_image" in str(call_args["messages"])
