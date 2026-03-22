import asyncio
import logging
from pathlib import Path
from threading import Lock

import numpy as np
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

from core.config import (
    HF_TOKEN,
    STT_MODEL_ID,
    STT_MAX_NEW_TOKENS,
    STT_MODELS_DIR,
    STT_NOISE_GATE_THRESHOLD,
    STT_MIN_VOICED_RATIO,
    STT_WHISPER_SOURCE_LANGUAGE,
    STT_WHISPER_TASK,
)


logger = logging.getLogger(__name__)


def _safe_model_dir_name(model_id: str) -> str:
    return model_id.replace('/', '--')


class SpeechToTextService:
    def __init__(self, model_id: str = STT_MODEL_ID, models_dir: str = STT_MODELS_DIR):
        self.model_id = model_id
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.local_model_dir = self.models_dir / _safe_model_dir_name(model_id)
        self._load_lock = Lock()
        self._model_lock = Lock()
        self._processor = None
        self._model = None
        self._device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._torch_dtype = torch.float16 if self._device == 'cuda' else torch.float32
        self._default_prompt = '<|audio|>can you transcribe the speech into a written format?'
        self._is_whisper = 'whisper' in model_id.lower()
        self._whisper_task = STT_WHISPER_TASK or 'translate'
        self._whisper_source_language = STT_WHISPER_SOURCE_LANGUAGE or None
        self._max_new_tokens = max(16, STT_MAX_NEW_TOKENS)
        self._noise_gate_threshold = max(0.0, float(STT_NOISE_GATE_THRESHOLD))
        self._min_voiced_ratio = min(1.0, max(0.0, float(STT_MIN_VOICED_RATIO)))

    def _prepare_audio(self, audio_samples: np.ndarray) -> np.ndarray:
        if audio_samples.size == 0:
            return audio_samples

        samples = np.asarray(audio_samples, dtype=np.float32).copy()
        abs_samples = np.abs(samples)
        voiced_mask = abs_samples >= self._noise_gate_threshold
        voiced_ratio = float(np.mean(voiced_mask)) if voiced_mask.size else 0.0
        if voiced_ratio < self._min_voiced_ratio:
            logger.info(
                'STT skipped transcription due to low voiced ratio: voiced_ratio=%.4f threshold=%.4f',
                voiced_ratio,
                self._min_voiced_ratio,
            )
            return np.array([], dtype=np.float32)

        samples[~voiced_mask] = 0.0
        voiced_indices = np.flatnonzero(voiced_mask)
        if voiced_indices.size == 0:
            return np.array([], dtype=np.float32)

        start = int(voiced_indices[0])
        end = int(voiced_indices[-1]) + 1
        trimmed = samples[start:end]
        peak = float(np.max(np.abs(trimmed))) if trimmed.size else 0.0
        if peak > 0.0:
            trimmed = np.clip(trimmed / peak, -1.0, 1.0)
        return trimmed

    def _call_generate(self, model, model_inputs: dict, *, max_new_tokens: int, task: str | None = None, language: str | None = None):
        generation_config = model.generation_config
        original_values = {
            'max_length': getattr(generation_config, 'max_length', None),
            'max_new_tokens': getattr(generation_config, 'max_new_tokens', None),
            'do_sample': getattr(generation_config, 'do_sample', None),
            'num_beams': getattr(generation_config, 'num_beams', None),
            'task': getattr(generation_config, 'task', None),
            'language': getattr(generation_config, 'language', None),
            'forced_decoder_ids': getattr(generation_config, 'forced_decoder_ids', None),
        }
        try:
            generation_config.max_length = None
            generation_config.max_new_tokens = max_new_tokens
            generation_config.do_sample = False
            generation_config.num_beams = 1
            if hasattr(generation_config, 'task'):
                generation_config.task = task
            if hasattr(generation_config, 'language'):
                generation_config.language = language
            if hasattr(generation_config, 'forced_decoder_ids'):
                generation_config.forced_decoder_ids = None
            with torch.inference_mode():
                return model.generate(**model_inputs)
        finally:
            for key, value in original_values.items():
                if hasattr(generation_config, key):
                    setattr(generation_config, key, value)

    def _ensure_local_model(self) -> Path:
        config_path = self.local_model_dir / 'config.json'
        if config_path.exists():
            return self.local_model_dir

        snapshot_download(
            repo_id=self.model_id,
            local_dir=str(self.local_model_dir),
            token=HF_TOKEN or None,
        )
        return self.local_model_dir

    def _load_model_sync(self) -> None:
        with self._load_lock:
            if self._model is not None and self._processor is not None:
                return

            local_dir = self._ensure_local_model()
            self._processor = AutoProcessor.from_pretrained(str(local_dir))
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                str(local_dir),
                dtype=self._torch_dtype,
            )
            self._model.to(self._device)
            self._model.eval()
            logger.info(
                'Loaded STT model `%s` from `%s` on `%s`.',
                self.model_id,
                self.local_model_dir,
                self._device,
            )

    async def ensure_loaded(self) -> None:
        await asyncio.to_thread(self._load_model_sync)

    def _transcribe_sync(self, audio_samples: np.ndarray, sample_rate: int) -> str:
        self._load_model_sync()
        prepared_audio = self._prepare_audio(audio_samples)
        if prepared_audio.size == 0:
            return ''
        logger.info(
            'STT transcription started: samples=%s sample_rate=%s duration_sec=%.2f',
            prepared_audio.size,
            sample_rate,
            prepared_audio.size / max(sample_rate, 1),
        )

        processor = self._processor
        model = self._model
        assert processor is not None
        assert model is not None

        with self._model_lock:
            if self._is_whisper:
                model_inputs = processor(
                    audio=prepared_audio,
                    sampling_rate=sample_rate,
                    return_tensors='pt',
                    return_attention_mask=True,
                )
                input_features = model_inputs.get('input_features')
                if input_features is None:
                    raise RuntimeError('Whisper processor did not return input_features.')
                generate_inputs = {
                    'input_features': input_features.to(self._device),
                }
                attention_mask = model_inputs.get('attention_mask')
                if attention_mask is not None:
                    generate_inputs['attention_mask'] = attention_mask.to(self._device)
                max_target_positions = getattr(model.config, 'max_target_positions', None)
                decoder_input_len = 2
                if max_target_positions:
                    if hasattr(processor, 'get_decoder_prompt_ids'):
                        prompt_ids = processor.get_decoder_prompt_ids(
                            language=self._whisper_source_language,
                            task=self._whisper_task,
                        )
                        if prompt_ids:
                            decoder_input_len = len(prompt_ids) + 2
                    safe_max_new_tokens = max(
                        1,
                        min(
                            int(self._max_new_tokens),
                            int(max_target_positions) - int(decoder_input_len) - 1,
                        ),
                    )
                else:
                    safe_max_new_tokens = self._max_new_tokens
                generated_ids = self._call_generate(
                    model,
                    generate_inputs,
                    max_new_tokens=safe_max_new_tokens,
                    task=self._whisper_task,
                    language=self._whisper_source_language,
                )
                text = processor.batch_decode(
                    generated_ids,
                    skip_special_tokens=True,
                )[0]
            else:
                tokenizer = processor.tokenizer
                chat = [{'role': 'user', 'content': self._default_prompt}]
                prompt = tokenizer.apply_chat_template(
                    chat,
                    tokenize=False,
                    add_generation_prompt=True,
                )
                model_inputs = processor(
                    prompt,
                    prepared_audio,
                    sampling_rate=sample_rate,
                    return_tensors='pt',
                )
                model_inputs = {
                    key: value.to(self._device)
                    for key, value in model_inputs.items()
                }
                generated_ids = self._call_generate(
                    model,
                    model_inputs,
                    max_new_tokens=self._max_new_tokens,
                )

                input_ids = model_inputs.get('input_ids')
                if input_ids is not None:
                    num_input_tokens = input_ids.shape[-1]
                    generated_ids = generated_ids[:, num_input_tokens:]

                text = tokenizer.batch_decode(
                    generated_ids,
                    skip_special_tokens=True,
                )[0]
        final_text = text.strip()
        logger.info(
            'STT transcription completed: model_type=%s whisper_task=%s text_length=%s preview=%r',
            'whisper' if self._is_whisper else 'granite',
            self._whisper_task if self._is_whisper else 'n/a',
            len(final_text),
            final_text[:120],
        )
        return final_text

    async def transcribe_pcm16(self, pcm_bytes: bytes, sample_rate: int) -> str:
        if not pcm_bytes:
            return ''
        pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        if pcm_int16.size == 0:
            return ''
        audio = pcm_int16.astype(np.float32) / 32768.0
        return await asyncio.to_thread(self._transcribe_sync, audio, sample_rate)


stt_service = SpeechToTextService()
