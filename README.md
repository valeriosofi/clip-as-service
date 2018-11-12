# bert-as-service

[![Python: 3.6](https://img.shields.io/badge/Python-3.6-brightgreen.svg)](https://opensource.org/licenses/MIT)    [![Tensorflow: 1.10](https://img.shields.io/badge/Tensorflow-1.10-brightgreen.svg)](https://opensource.org/licenses/MIT)  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Using BERT model as a sentence encoding service, i.e. mapping a variable length sentence to a fixed length vector.

Author: Han Xiao [https://hanxiao.github.io](https://hanxiao.github.io)


## What is it?

[Developed by Google](https://github.com/google-research/bert), BERT is a method of pre-training language representations. It leverages an enormous amount of plain text data publicly available on the web and is trained in an unsupervised manner. Pre-training a BERT model is a fairly expensive yet one-time procedure for each language. Fortunately, Google released several pre-trained models where [you can download from here](https://github.com/google-research/bert#pre-trained-models).


On the other hand, sentence encoding is a upstream task required in many NLP applications, e.g. sentiment analysis, text classification. The goal is to represent a variable length sentence into a fixed length vector, each element of which should "encode" some semantics of the original sentence.

This repo uses BERT as the sentence encoder and allows you to convert sentences into fixed length representations in just two lines of code. 

## Usage

#### 1. Download the Pre-trained BERT Model
Download it from [here](https://github.com/google-research/bert#pre-trained-models), then uncompress the zip file into some folder, say `/tmp/english_L-12_H-768_A-12/`


#### 2. Start a BERT service
```bash
python app.py -num_worker=4 -model_dir /tmp/english_L-12_H-768_A-12/
```
This will start a service with four workers, meaning that it can handel up to four **concurrent** requests. (These workers are behind a simple load balancer.)

#### 3. Use Client to Encode Sentences
Now you can use pretrained BERT to encode sentences in your Python code simply as follows:
```python
ec = BertClient()
ec.encode(['abc', 'defg', 'uwxyz'])
```
This will return a python object with type `List[List[float]]`, each element of the outer `List` is the fixed representation of a sentence.

### Using BERT Service Remotely
One can also start the service on one (GPU) machine and call it from another (CPU) machine as follows

```python
# on another CPU machine
ec = BertClient(ip='xx.xx.xx.xx', port=5555)  # ip address of the GPU machine
ec.encode(['abc', 'defg', 'uwxyz'])
```
 
## QA on Technical Details

**Q:** Where do you get the fixed representation? Did you do pooling or something?

**A:** I take the second-to-last hidden layer of all of the tokens in the sentence and do average pooling. See [the function I added to the modeling.py](bert/modeling.py#L236)

**Q:** Why not use the hidden state of the first token, i.e. the `[CLS]`?

**A:** Because a pre-trained model is not fine-tuned on any downstream tasks yet. In this case, the hidden state of `[CLS]` is not a good sentence representation. If later you fine-tune the model, you may [use `get_pooled_output()` to get the fixed length representation](bert/modeling.py#L224) as well.

**Q:** Why not the last hidden layer? Why second-to-last?

**A:** The last layer is too closed to the target functions (i.e. masked language model and next sentence prediction) during pre-training, therefore may be biased to those targets.

**Q:** Could I use other pooling techniques?

**A:** For sure. Just follows [`get_sentence_encoding()` I added to the modeling.py](bert/modeling.py#L236). Note that, if you introduce new `tf.variables` to the graph, then you need to train those variables before using the model.

**Q:** How many requests can a service handle concurrently?

**A:** The maximum number of concurrent requests is determined by `num_worker` in `app.py`. If you a sending more than `num_worker` requests concurrently, the new requests will be temporally stored in a queue until a free worker becomes available.

**Q:** So one request means one sentence?

**A:** No. One request means a list of sentences sent from a client. A request may contain 256, 512 or 1024 sentences. The optimal size of a request is often determined empirically. One large request can certainly  improve the GPU utilization, yet it also increases the overhead of transmission. You may run `python client_example.py` for a simple benchmark.

 





