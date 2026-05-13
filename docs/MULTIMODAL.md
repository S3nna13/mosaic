# Multi-Modal Usage — Image Inputs

MOSAIC supports vision-language tasks through provider-native vision APIs.

## OpenAI GPT-4o Example

```python
from mosaic.adapters import build_adapter
from mosaic.multimodal.vision import ImageInput, MultiModalMessage

adapter = build_adapter(provider="openai", model="gpt-4o")
msg = MultiModalMessage(
    role="user",
    content="What is shown in this image?",
    images=[ImageInput(source="https://example.com/diagram.png")]
)
resp = adapter.chat([msg])
print(resp.content)
```

## Claude 3.5 Sonnet Example

```python
adapter = build_adapter(provider="anthropic", model="claude-3-5-sonnet-20241022")
msg = MultiModalMessage(
    role="user",
    content="Analyze this screenshot",
    images=[ImageInput(source="/tmp/screenshot.png", mime_type="image/png")]
)
resp = adapter.chat([msg])
```

## API Endpoints

Send a POST to `/chat/completions` with an `images` field:

```json
{
  "messages": [
    {"role": "user", "content": "Describe this", "images": [{"source": "file:///tmp/pic.jpg"}]}
  ],
  "adapter": "openai"
}
```
