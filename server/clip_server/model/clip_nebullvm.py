import os
from pathlib import Path

import numpy as np
import torch.cuda

from .clip import _download, available_models

_S3_BUCKET = 'https://clip-as-service.s3.us-east-2.amazonaws.com/models/onnx/'
_MODELS = {
    'RN50': ('RN50/textual.onnx', 'RN50/visual.onnx'),
    'RN101': ('RN101/textual.onnx', 'RN101/visual.onnx'),
    'RN50x4': ('RN50x4/textual.onnx', 'RN50x4/visual.onnx'),
    'RN50x16': ('RN50x16/textual.onnx', 'RN50x16/visual.onnx'),
    'RN50x64': ('RN50x64/textual.onnx', 'RN50x64/visual.onnx'),
    'ViT-B/32': ('ViT-B-32/textual.onnx', 'ViT-B-32/visual.onnx'),
    'ViT-B/16': ('ViT-B-16/textual.onnx', 'ViT-B-16/visual.onnx'),
    'ViT-L/14': ('ViT-L-14/textual.onnx', 'ViT-L-14/visual.onnx'),
    'ViT-L/14@336px': ('ViT-L-14@336px/textual.onnx', 'ViT-L-14@336px/visual.onnx'),
}


class CLIPNebullvmModel:
    def __init__(self, name: str = None, pixel_size: int = 224):
        self.pixel_size = pixel_size
        if name in _MODELS:
            cache_dir = os.path.expanduser(f'~/.cache/clip/{name.replace("/", "-")}')
            self._textual_path = _download(_S3_BUCKET + _MODELS[name][0], cache_dir)
            self._visual_path = _download(_S3_BUCKET + _MODELS[name][1], cache_dir)
        else:
            raise RuntimeError(
                f'Model {name} not found; available models = {available_models()}'
            )

    def optimize_models(
        self,
        **kwargs,
    ):
        from nebullvm.api.functions import optimize_model

        general_kwargs = {}
        general_kwargs.update(kwargs)

        dynamic_info = {
            "inputs": [
                {0: 'batch', 1: 'num_channels', 2: 'pixel_size', 3: 'pixel_size'}
            ],
            "outputs": [{0: 'batch'}],
        }

        self._visual_model = optimize_model(
            self._visual_path,
            input_data=[
                (
                    (
                        np.random.randn(1, 3, self.pixel_size, self.pixel_size).astype(
                            np.float32
                        ),
                    ),
                    0,
                )
            ],
            dynamic_info=dynamic_info,
            **general_kwargs,
        )

        dynamic_info = {
            "inputs": [
                {0: 'batch', 1: 'num_tokens'},
            ],
            "outputs": [
                {0: 'batch'},
            ],
        }

        self._textual_model = optimize_model(
            self._textual_path,
            input_data=[((np.random.randint(0, 100, (1, 77)),), 0)],
            dynamic_info=dynamic_info,
            **general_kwargs,
        )

    def encode_image(self, onnx_image):
        (visual_output,) = self._visual_model(onnx_image)
        return visual_output

    def encode_text(self, onnx_text):
        (textual_output,) = self._textual_model(onnx_text)
        return textual_output


class EnvRunner:
    def __init__(self, device: str, num_threads: int = None):
        self.device = device
        self.cuda_str = None
        self.rm_cuda_flag = False
        self.num_threads = num_threads

    def __enter__(self):
        if self.device == "cpu" and torch.cuda.is_available():
            self.cuda_str = os.environ.get("CUDA_VISIBLE_DEVICES")
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"
            self.rm_cuda_flag = self.cuda_str is None
        if self.num_threads is not None:
            os.environ["NEBULLVM_THREADS_PER_MODEL"] = f"{self.num_threads}"

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cuda_str is not None:
            os.environ["CUDA_VISIBLE_DEVICES"] = self.cuda_str
        elif self.rm_cuda_flag:
            os.environ.pop("CUDA_VISIBLE_DEVICES")
        if self.num_threads is not None:
            os.environ.pop("NEBULLVM_THREADS_PER_MODEL")
