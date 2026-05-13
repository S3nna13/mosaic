"""Transformer model tests — forward pass, attention, memory injection, verifier head."""

from __future__ import annotations

import torch
from mosaic.model.transformer import MosaicConfig, MosaicTransformer
from mosaic.model.verifier import VerifierHead


def test_transformer_forward_shape():
    cfg = MosaicConfig(vocab_size=1000, d_model=256, n_layers=4, n_heads=8)
    model = MosaicTransformer(cfg)
    batch, seq = 2, 32
    input_ids = torch.randint(0, cfg.vocab_size, (batch, seq))
    out = model(input_ids)
    assert out.shape == (batch, seq, cfg.d_model), f"unexpected shape {out.shape}"


def test_gqa_attention_uses_kv_heads():
    cfg = MosaicConfig(d_model=128, n_heads=8, n_kv_heads=2)
    model = MosaicTransformer(cfg)
    # GQA: 8 query heads, 2 key/value heads
    assert model.layers[0].attn.n_heads == 8


def test_verifier_head_scalar():
    cfg = MosaicConfig(d_model=256)
    verifier = VerifierHead(cfg.d_model)
    hidden = torch.randn(2, 16, cfg.d_model)  # [batch, seq, d_model]
    scores = verifier(hidden)  # [batch, seq]
    assert scores.shape == (2, 16)


def test_sinai_registers_trainable():
    cfg = MosaicConfig(d_model=256, n_registers=8)
    model = MosaicTransformer(cfg)
    reg = model.sinai_registers
    # Registers should be a Parameter (trainable)
    assert isinstance(reg, torch.nn.Parameter)
    assert reg.shape == (1, cfg.n_registers, cfg.d_model)


def test_memory_context_injection_shape():
    """Exodus memory context should be broadcast across batch dimension."""
    cfg = MosaicConfig(d_model=128, memory_slots=16)
    model = MosaicTransformer(cfg)
    batch, seq = 2, 8
    input_ids = torch.randint(0, cfg.vocab_size, (batch, seq))

    # Fake memory: (batch=1, slots, d_model) — should broadcast
    memory = torch.randn(1, cfg.memory_slots, cfg.d_model)

    out = model(input_ids, memory_context=memory)
    assert out.shape == (batch, seq, cfg.d_model)
