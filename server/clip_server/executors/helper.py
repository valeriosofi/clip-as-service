from typing import Tuple, List, Callable

import numpy as np
from clip_server.model import clip
from docarray import Document, DocumentArray
from docarray.math.distance.numpy import cosine


def numpy_softmax(x: 'np.ndarray', axis: int = -1) -> 'np.ndarray':
    max = np.max(x, axis=axis, keepdims=True)
    e_x = np.exp(x - max)
    div = np.sum(e_x, axis=axis, keepdims=True)
    f_x = e_x / div
    return f_x


def preproc_image(
    da: 'DocumentArray',
    preprocess_fn: Callable,
    device: str = 'cpu',
    return_np: bool = False,
) -> 'DocumentArray':
    for d in da:
        if d.blob:
            d.convert_blob_to_image_tensor()
        elif d.tensor is None and d.uri:
            # in case user uses HTTP protocol and send data via curl not using .blob (base64), but in .uri
            d.load_uri_to_image_tensor()

        d.tensor = preprocess_fn(d.tensor).detach()

    if return_np:
        da.tensors = da.tensors.cpu().numpy().astype(np.float32)
    else:
        da.tensors = da.tensors.to(device)
    return da


def preproc_text(
    da: 'DocumentArray', device: str = 'cpu', return_np: bool = False
) -> Tuple['DocumentArray', List[str]]:
    texts = da.texts
    da.tensors = clip.tokenize(texts).detach()

    if return_np:
        da.tensors = da.tensors.cpu().numpy().astype(np.int64)
    else:
        da.tensors = da.tensors.to(device)

    da[:, 'mime_type'] = 'text'
    return da, texts


def split_img_txt_da(doc: 'Document', img_da: 'DocumentArray', txt_da: 'DocumentArray'):
    if doc.uri:
        img_da.append(doc)
    elif doc.blob or (doc.tensor is not None):
        img_da.append(doc)
    elif doc.text:
        txt_da.append(doc)


def set_rank(docs, _logit_scale=np.exp(4.60517)):
    queries = docs
    candidates = docs['@m']

    query_embeddings = queries.embeddings  # Q X D
    candidate_embeddings = candidates.embeddings  # C = Sum(C_q1, C_q2, C_q3,...) x D
    cosine_scores = 1 - cosine(
        query_embeddings, candidate_embeddings
    )  # Q x C Block matix
    start_idx = 0
    for q, _cosine_scores in zip(docs, cosine_scores):

        _candidates = q.matches

        end_idx = start_idx + len(_candidates)

        _candidate_cosines = _cosine_scores[start_idx:end_idx]
        _candidate_softmaxs = numpy_softmax(_logit_scale * _candidate_cosines)
        for c, _c_score, _s_score in zip(
            _candidates, _candidate_cosines, _candidate_softmaxs
        ):
            c.scores['clip_score'].value = _s_score
            c.scores['clip_score'].op_name = 'softmax'

            c.scores['clip_score_cosine'].value = _c_score
            c.scores['clip_score_cosine'].op_name = 'cosine'

        start_idx = end_idx

        final = sorted(
            _candidates, key=lambda _m: _m.scores['clip_score'].value, reverse=True
        )

        q.matches = final
