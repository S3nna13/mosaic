"""Local adapter — HuggingFace Transformers or local Mosaic weights."""

from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from mosaic.adapters.base import BaseAdapter, Message, ModelResponse


class LocalAdapter(BaseAdapter):
    name = "local"

    def __init__(
        self,
        model_path: str,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        use_mosaic_transformer: bool = False,
    ):
        self.model_path = model_path
        self.device = device
        self.use_mosaic = use_mosaic_transformer

        if self.use_mosaic:
            # Dynamically import late to avoid circular imports
            from mosaic.model.transformer import build_transformer_from_config

            # Load weights if checkpoint file provided
            self.model = build_transformer_from_config(self._infer_config())
            if model_path:
                state = torch.load(model_path, map_location=device)
                self.model.load_state_dict(state)
        else:
            self.model = AutoModelForCausalLM.from_pretrained(model_path).to(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.eval()

    def _infer_config(self):
        # Minimal AigisConfig sufficient for build_transformer_from_config
        from mosaic.core.schema import AigisConfig

        return AigisConfig()

    @torch.no_grad()
    def chat(self, messages: list[Message], **kwargs) -> ModelResponse:
        prompt = self._build_prompt(messages)
        inputs = self.tokenizer(prompt, return_tensors="pt", padding=True).to(
            self.device
        )

        gen_kwargs = {
            "max_new_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "do_sample": True,
        }
        output = self.model.generate(**inputs, **gen_kwargs)
        gen_tokens = output[0][inputs.input_ids.shape[1] :]
        text = self.tokenizer.decode(gen_tokens, skip_special_tokens=True)

        return ModelResponse(
            content=text,
            model=self.model_path,
            usage={
                "prompt_tokens": inputs.input_ids.shape[1],
                "completion_tokens": len(gen_tokens),
            },
            raw={},
        )

    def _build_prompt(self, messages: list[Message]) -> str:
        # ChatML-style: <|user|>…<|assistant|>…
        parts = []
        for m in messages:
            role = m.role
            if role == "user":
                parts.append(f"<|user|>\n{m.content}")
            elif role == "assistant":
                parts.append(f"<|assistant|>\n{m.content}")
            elif role == "system":
                parts.append(f"<|system|>\n{m.content}")
        parts.append("<|assistant|>")
        return "\n".join(parts)

    def health(self) -> bool:
        try:
            self.tokenizer("test")
            return True
        except Exception:
            return False
