#!/usr/bin/env python
# coding: utf-8

# In[1]:


import json
import torch
from transformers import *
from transformers import AdamW
import torch.utils.data as Data
import collections
import os
import random
import tarfile
import torch
from torch import nn
import torchtext.vocab as Vocab
import pickle as pk
import copy
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import random
import torch.nn.functional as F
from IPython.display import display,HTML
import os
from torch.nn.utils.rnn import pad_sequence
from torch.nn.utils.rnn import pack_padded_sequence
from torch.nn.utils.rnn import pad_packed_sequence
from torch.nn.utils.rnn import pack_sequence
from torch.nn import CrossEntropyLoss, MSELoss
from torchcrf import CRF
from sklearn import metrics
import joblib
import math
device=torch.device("cuda:2" if torch.cuda.is_available() else "cpu")
import argparse
import glob
import json
import logging
import unicodedata
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler, TensorDataset
from torch.utils.data.distributed import DistributedSampler
from tqdm import tqdm_notebook as tqdm
import torch.utils.data as Data
import jieba
import jieba.posseg as pseg
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO 
)
ARG=collections.namedtuple('ARG',['train_batch_size',
 'eval_batch_size',
 'weight_decay',
 'learning_rate',
 'adam_epsilon',
 'num_train_epochs',
 'warmup_steps',
 'gradient_accumulation_steps',
 'save_steps',
 'max_grad_norm',
 'model_name_or_path',
 'output_dir',
 'seed',
 'device',
 'n_gpu',
 'max_steps',
 'output_mode',
'fp16_opt_level',
'fp16',
'card_list'])
parser = argparse.ArgumentParser()
parser.add_argument("-c","--card", help="feature",type=int,default=0)
parser.add_argument("-rnn","--rnn", help="feature",type=int,default=0)
parser.add_argument("-cnn","--cnn", help="feature",type=int,default=0)
parser.add_argument("-s","--split", help="feature",type=int,default=0)
# parser.add_argument("-plan","--use_plan", help="feature",type=int,default=0)
# parser.add_argument("-p","--p", help="feature",type=int,default=1)
args = parser.parse_args()
output_dir="./output_ner_"+str(args.rnn)+"_"+str(args.cnn)+"_"+str(args.split)+"/"
print(output_dir)
print("cuda:"+str(args.card))
need_rnn=bool(args.rnn)
need_cnn=bool(args.cnn)
# use_plan=bool(args.use_plan)
# p=args.p
print("need_rnn:",need_rnn)
print("need_cnn:",need_cnn)
# print("use_plan:",use_plan)
# print("p",p)
print("split:",args.split)
print("cuda:"+str(args.card))
device=torch.device("cuda:"+str(args.card) if torch.cuda.is_available() else "cpu")
if args.card==0:
    card_list=[0,1]
if args.card==2:
    card_list=[2,3]
print("card_list",card_list) 


# In[2]:


def convert_text_to_ids(tokenizer, text, max_len=100):
    if isinstance(text,str):
        output=tokenizer.encode_plus(text,max_length=max_len,pad_to_max_length=True,return_tensors="pt")
        input_ids=output["input_ids"].squeeze(0)
        token_type_ids=output["token_type_ids"].squeeze(0)
        attention_mask=output["attention_mask"].squeeze(0)
    elif isinstance(text,list):
        input_ids,token_type_ids,attention_mask=[],[],[]
        for e in text:
            output=tokenizer.encode_plus(e,max_length=max_len,pad_to_max_length=True,return_tensors="pt")
            input_ids.append(output["input_ids"].squeeze(0))
            token_type_ids.append(output["token_type_ids"].squeeze(0))
            attention_mask.append(output["attention_mask"].squeeze(0))
    else:
        raise Exception('type error')
    return torch.stack(input_ids).long(),torch.stack(token_type_ids).long(),torch.stack(attention_mask).long()        
class RelDataset(Data.Dataset):
    def __init__(self,examples):
        self.input_ids=torch.stack([e['input_ids'] for e in examples]).long()
        self.token_type_ids=torch.stack([e['token_type_ids'] for e in examples]).long()
        self.attention_mask=torch.stack([e['attention_mask'] for e in examples]).long()
        self.rel_label=torch.stack([e['rel_label'] for e in examples]).long()
        self.postag=torch.stack([e['postag'] for e in examples]).long()
        self.feature=torch.stack([e['feature'] for e in examples]).float()
        self.token_vec=np.stack([np.array(e['token_vec']) for e in examples])
        self.word_vec=np.stack([np.array(e['word_vec']) for e in examples])
        self.word_mask=np.stack([np.array(e['word_mask']) for e in examples])
        self.plan_label=np.stack([np.array(e['plan_label']) for e in examples])
        self.token2docs=[e["token2doc"] for e in examples]
    def __len__(self):
        return self.input_ids.shape[0]
    def __getitem__(self,idx):
        return self.input_ids[idx],self.attention_mask[idx],self.token_type_ids[idx],\
    self.rel_label[idx],self.postag[idx],self.feature[idx],self.token_vec[idx],self.word_vec[idx],\
    self.word_mask[idx],self.plan_label[idx],self.token2docs[idx]  
class NerDataset(Data.Dataset):
    def __init__(self,examples):
        self.input_ids=torch.stack([e['input_ids'] for e in examples]).long()
        self.token_type_ids=torch.stack([e['token_type_ids'] for e in examples]).long()
        self.attention_mask=torch.stack([e['attention_mask'] for e in examples]).long()
        self.rel_label=torch.stack([e['rel_label'] for e in examples]).long()
        self.labels=torch.stack([e['labels'] for e in examples]).long()
        self.postag=torch.stack([e['postag'] for e in examples]).long()
        self.feature=torch.stack([e['feature'] for e in examples]).float()
        self.token2docs=[e["token2doc"] for e in examples]
    def __len__(self):
        return self.input_ids.shape[0]
    def __getitem__(self,idx):
        return self.input_ids[idx],self.attention_mask[idx],self.token_type_ids[idx],\
               self.rel_label[idx],self.labels[idx],self.postag[idx],self.feature[idx],self.token2docs[idx]  
import unicodedata
def _is_whitespace(char):
    """Checks whether `chars` is a whitespace character."""
    # \t, \n, and \r are technically contorl characters but we treat them
    # as whitespace since they are generally considered as such.
    if char == " " or char == "\t" or char == "\n" or char == "\r":
        return True
    cat = unicodedata.category(char)
    if cat == "Zs":
        return True
    return False
def is_chinese_char(cp):
    """Checks whether CP is the codepoint of a CJK character."""
    # This defines a "chinese character" as anything in the CJK Unicode block:
    #   https://en.wikipedia.org/wiki/CJK_Unified_Ideographs_(Unicode_block)
    #
    # Note that the CJK Unicode block is NOT all Japanese and Korean characters,
    # despite its name. The modern Korean Hangul alphabet is a different block,
    # as is Japanese Hiragana and Katakana. Those alphabets are used to write
    # space-separated words, so they are not treated specially and handled
    # like the all of the other languages.
    if (
        (cp >= 0x4E00 and cp <= 0x9FFF)
        or (cp >= 0x3400 and cp <= 0x4DBF)  #
        or (cp >= 0x20000 and cp <= 0x2A6DF)  #
        or (cp >= 0x2A700 and cp <= 0x2B73F)  #
        or (cp >= 0x2B740 and cp <= 0x2B81F)  #
        or (cp >= 0x2B820 and cp <= 0x2CEAF)  #
        or (cp >= 0xF900 and cp <= 0xFAFF)
        or (cp >= 0x2F800 and cp <= 0x2FA1F)  #
    ):  #
        return True

    return False
def is_punctuation(char):
    """Checks whether `chars` is a punctuation character."""
    cp = ord(char)
    # We treat all non-letter/number ASCII as punctuation.
    # Characters such as "^", "$", and "`" are not in the Unicode
    # Punctuation class but we treat them as punctuation anyways, for
    # consistency.
    if (cp >= 33 and cp <= 47) or (cp >= 58 and cp <= 64) or (cp >= 91 and cp <= 96) or (cp >= 123 and cp <= 126):
        return True
    cat = unicodedata.category(char)
    if cat.startswith("P"):
        return True
    return False
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
def cut_buff(info):
    buff=""
    tokens=[]
    for e in info:
        if (e.isdigit() and (buff.isdigit() or buff=='')):
            buff+=e
        elif (e.isalpha() and (buff.isalpha() or buff=='')):
            buff+=e
        else:
            if buff!="":
                tokens.append(buff)
            buff=""
            if not (e.isdigit() or e.isalpha()):
                tokens.append(e)
            else:
                buff+=e

    if buff!="":
        tokens.append(buff)
    return tokens
def build_tfidf_svd_matrix(texts,n_output,tfidf_vec=None,svd=None):
    corpus=[]
    for text in tqdm(texts):
#         print(text)
        words=word_segment(str(text['text']))
#         print(words)
        use_words=[]
        for word in words:
            if word in stop_words:
                continue
            use_words.append(word)
#         print(use_words)
        corpus.append(" ".join(use_words))
    print(len(corpus))
    print(corpus[0])
    if tfidf_vec is None:
        tfidf_vec=TfidfVectorizer()
        tfidf_matrix=tfidf_vec.fit_transform(corpus)
    else:
        tfidf_matrix=tfidf_vec.transform(corpus)
    if svd is None:
        svd=TruncatedSVD(n_components=n_output,n_iter=7,random_state=42)
        tf_idf_svd=svd.fit_transform(tfidf_matrix)
    else:
        tf_idf_svd=svd.transform(tfidf_matrix)
    return tf_idf_svd,tfidf_vec,svd
def word_segment(sentence):
    words=jieba.cut(sentence)
    return ",".join(words).split(",")
stop_words=set()
def load_stopwords():
    with open("./middle_data/stopwords.txt","r",encoding="UTF-8") as r:
        for line in r.readlines():
            stop_words.add(line.strip())
load_stopwords()
def remove_stopwords(word_list):
    res=[]
    for word in word_lists:
        if word not in stop_words:
            res.append(word)
    return ' '.join(res)
def clean_text(string):
    return string.replace(' ', '').replace('\n', '').replace('\u3000', '')
def index_token(text_raw):
    sub_text = []
    buff = ""
    for char in text_raw:
        if is_chinese_char(ord(char)) or is_punctuation(char):
            if buff != "":
                sub_text.append(buff)
                buff = ""
            sub_text.append(char)
        else:
            buff += char
    if buff != "":
        sub_text.append(buff)
    tok_to_orig_start_index = []
    tok_to_orig_end_index = []
    orig_to_tok_index = []
    tokens = []
    text_tmp = ''
    for (i, token) in enumerate(sub_text):
        orig_to_tok_index.append(len(tokens))
        sub_tokens = tokenizer.tokenize(token)
        text_tmp += token
        for sub_token in sub_tokens:
            tok_to_orig_start_index.append(len(text_tmp) - len(token))
            tok_to_orig_end_index.append(len(text_tmp) - 1)
            tokens.append(sub_token)
        else:
            continue
        break
    return tok_to_orig_start_index,tok_to_orig_end_index,orig_to_tok_index


# In[3]:



do_lower_case=True
max_len=256
# bert_dir="./bert-pytorch-chinese/"
# vocab="bert-base-chinese-vocab.txt"
# config_file="bert_config.json"
bert_dir="./roberta-zh-wwm-pytorch/"
vocab="vocab.txt"
config_file="bert_config.json"
tokenizer=BertTokenizer.from_pretrained(os.path.join(bert_dir,vocab),do_lower_case=do_lower_case)


# In[4]:


text_data=[]
with open("./dataset/train_data/new_train_data.json","r") as r:
    raw_data=r.readlines()
    for d in raw_data:
        text_data.append(json.loads(d))
test_text_data=[]
with open("./dataset/test1_data/new_test1_data.json","r") as r:
    raw_data=r.readlines()
    for d in raw_data:
        test_text_data.append(json.loads(d))
schema=[]
with open("./dataset/schema.json","r") as r:
    raw_schema=r.readlines()
    for d in raw_schema:
        schema.append(json.loads(d))
rels=set()
special_rels=set()
for e in schema:
        if len(e['object_type'].keys())==1:
            rels.add(e["predicate"])
        else:
            special_rels.add(e["predicate"])
            for key in e['object_type'].keys():
                rels.add(e['predicate']+"_"+key)
if not os.path.exists("./dataset/dict.pk"):
    special_rels=list(special_rels)
    id2rels=list(rels)
    rels2id=dict([(rel,idx) for idx,rel in enumerate(id2rels)])
    id2labels=["O","B-OBJ","I-OBJ","B-SUB","I-SUB","[category]","[SEP]","[CLS]","[PAD]"]
    label2ids=dict([ (label,idx) for idx,label in enumerate(id2labels)])
    pk.dump([special_rels,id2rels,rels2id,id2labels,label2ids],open("./dataset/dict.pk","wb"))
else:
    print("loading dict...")
    special_rels,id2rels,rels2id,id2labels,label2ids=pk.load(open("./dataset/dict.pk","rb"))
id2kglabels=['O','I']+['B-'+e+"-SUB" for e in id2rels]+['B-'+e+"-OB" for e in id2rels]
kglabels2id=dict([ (label,idx) for idx,label in enumerate(id2kglabels)])
new_id2labels=["O","B-OBJ","E-OBJ","B-SUB","E-SUB","[category]","[SEP]","[CLS]","[PAD]"]
new_label2ids=dict([ (label,idx) for idx,label in enumerate(new_id2labels)])
new_id2kglabels=['O']+['B-'+e+"-SUB" for e in id2rels]+['B-'+e+"-OB" for e in id2rels]+['E-'+e+"-SUB" for e in id2rels]+['E-'+e+"-OB" for e in id2rels]
new_kglabels2id=dict([ (label,idx) for idx,label in enumerate(new_id2kglabels)])
id2reltype=[[] for i in range(len(id2rels))]
for e in schema:
    if len(e['object_type'].keys())==1:
        rel=e["predicate"]
        ids=rels2id[rel]
        id2reltype[ids].append(e)
    else:
        for key in e['object_type'].keys():
            rel=e['predicate']+"_"+key
            ids=rels2id[rel]
            temp_e=copy.deepcopy(e)
            poped_keys=[]
            for k in temp_e['object_type'].keys():
                if k!=key:
                    poped_keys.append(k)
            for k in poped_keys:
                 temp_e['object_type'].pop(k)
            id2reltype[ids].append(temp_e)
id2schema=[e[0] for e in id2reltype]
id2rel_text=[[] for i in range(len(id2rels))]
id2rel_rawtext=[[] for i in range(len(id2rels))]
id2rel_token2text=[[] for i in range(len(id2rels))]
for rel in range(len(id2rels)):
    if id2rels[rel].split("_")[0] not in special_rels:
        cls_text=id2schema[rel]['subject_type']+","+id2schema[rel]['predicate']+","+id2schema[rel]['object_type']['@value']
    else:
        cls_text=id2schema[rel]['subject_type']+","+id2schema[rel]['predicate']+","+id2schema[rel]['object_type'][id2rels[rel].split("_")[1]]
    id2rel_text[rel]=tokenizer.tokenize(cls_text)
    id2rel_rawtext[rel]=cls_text
    id2rel_token2text[rel]=index_token(cls_text)[0]
    assert len(id2rel_token2text[rel])==len(id2rel_text[rel])
if not os.path.exists("./middle_data/rel_data_postag.pk"):
    jieba.enable_paddle() 
    jieba.enable_parallel(8)
    rel_cut_words=[]
    rel_cut_tags=[]
    for idx in tqdm(range(len(id2rel_rawtext))):
        words = pseg.lcut(id2rel_rawtext[idx],use_paddle=True) #jieba默认模式
        new_words=[w for w,t in words]
        new_tags=[t for w,t in words]
        rel_cut_words.append([idx,new_words])
        rel_cut_tags.append([idx,new_tags])
    rel_cut_words=[e[1] for e in sorted(rel_cut_words,key=lambda x:x[0])]
    rel_cut_tags=[e[1] for e in sorted(rel_cut_tags,key=lambda x:x[0])]
    rel_data_postag=[]
    for idx in tqdm(range(len(id2rel_rawtext))):
        assert len(id2rel_rawtext[idx].strip())==len("".join(rel_cut_words[idx]))
        indexs=[]
        cur_length=0
        for e in rel_cut_words[idx]:
            indexs.append([cur_length,cur_length+len(e)-1])
            cur_length+=len(e)
        pos_label=np.zeros(len(id2rel_rawtext[idx])).astype(np.int8)
        for i,(b,e) in enumerate(indexs):
            assert (id2rel_rawtext[idx][b]==rel_cut_words[idx][i][0] or _is_whitespace(id2rel_rawtext[idx].strip()[b])                   or _is_whitespace(rel_cut_words[idx][i][0]))                     and (id2rel_rawtext[idx].strip()[e]==rel_cut_words[idx][i][-1]                          or _is_whitespace(id2rel_rawtext[idx].strip()[e])  or _is_whitespace(rel_cut_words[idx][i][-1]))
            pos_label[b+1:e+1]=pos2id_BIO['I-'+rel_cut_tags[idx][i]]
            pos_label[b]=pos2id_BIO['B-'+rel_cut_tags[idx][i]]
        rel_data_postag.append(pos_label)
    pk.dump(rel_data_postag,open("./middle_data/rel_data_postag.pk","wb"))
else:
    print("loading...")
    rel_data_postag=pk.load(open("./middle_data/rel_data_postag.pk","rb"))
special_major_idx=[2,4,22,32,54]
special_affilate_idx=[[] for i in range(len(id2rels))]
special_affilate_idx[2]=[5]
special_affilate_idx[4]=[0]
special_affilate_idx[22]=[51]
special_affilate_idx[32]=[8]
special_affilate_idx[54]=[6,11,14]
special_pass_idx=[0,5,6,8,11,14,51]
padding_O=[0]*len(new_id2labels)
padding_O[0]=1
padding_category=[0]*len(new_id2labels)
padding_category[5]=1
padding_SEP=[0]*len(new_id2labels)
padding_SEP[6]=1
padding_CLS=[0]*len(new_id2labels)
padding_CLS[7]=1
padding_PAD=[0]*len(new_id2labels)
padding_PAD[8]=1 #for pointer ner


# In[8]:


if not os.path.exists("./middle_data/train_postag.pk"):
    postag_set=set()
    jieba.enable_paddle() 
    jieba.enable_parallel(8)
    train_cut_words=[]
    train_cut_tags=[]
    for idx in tqdm(range(len(text_data))):
        words = pseg.lcut(text_data[idx]['text'],use_paddle=True) #jieba默认模式
        new_words=[w for w,t in words]
        new_tags=[t for w,t in words]
        postag_set.update(new_tags)
        train_cut_words.append([idx,new_words])
        train_cut_tags.append([idx,new_tags])
    train_cut_words=[e[1] for e in sorted(train_cut_words,key=lambda x:x[0])]
    train_cut_tags=[e[1] for e in sorted(train_cut_tags,key=lambda x:x[0])]
    id2pos=list(postag_set)
    pos2id=dict([(pos,idx) for idx,pos in enumerate(id2pos)])
    jieba.enable_parallel(16)
    for idx in tqdm(range(len(text_data))):
        words = pseg.lcut(text_data[idx]['text'],use_paddle=True) #jieba默认模式
        new_words=[w for w,t in words]
        assert new_words==train_cut_words[idx]
    pk.dump([id2pos,pos2id,train_cut_words,train_cut_tags],open("./middle_data/train_postag.pk","wb"))
else:
    print("loading...")
    id2pos,pos2id,train_cut_words,train_cut_tags=pk.load(open("./middle_data/train_postag.pk","rb"))
if not os.path.exists("./middle_data/train_postag_BIO.pk"):
    id2pos_BIO=['B-'+e for e in id2pos]+['I-'+e for e in id2pos]
    id2pos_BIO.extend(['[CLS]','[SEP]','[PAD]'])
    pos2id_BIO=dict([(pos,idx) for idx,pos in enumerate(id2pos_BIO)])

    text_data_postag=[]
    for idx in tqdm(range(len(text_data))):
        assert len(text_data[idx]['text'].strip())==len("".join(train_cut_words[idx]))
        indexs=[]
        cur_length=0
        for e in train_cut_words[idx]:
            indexs.append([cur_length,cur_length+len(e)-1])
            cur_length+=len(e)
        pos_label=np.zeros(len(text_data[idx]['text'])).astype(np.int8)
        for i,(b,e) in enumerate(indexs):
            assert (text_data[idx]['text'].strip()[b]==train_cut_words[idx][i][0] or _is_whitespace(text_data[idx]['text'].strip()[b])                   or _is_whitespace(train_cut_words[idx][i][0]))                     and (text_data[idx]['text'].strip()[e]==train_cut_words[idx][i][-1]                          or _is_whitespace(text_data[idx]['text'].strip()[e])  or _is_whitespace(train_cut_words[idx][i][-1]))
            pos_label[b+1:e+1]=pos2id_BIO['I-'+train_cut_tags[idx][i]]
            pos_label[b]=pos2id_BIO['B-'+train_cut_tags[idx][i]]
        text_data_postag.append(pos_label)
    pk.dump([id2pos_BIO,pos2id_BIO,text_data_postag],open("./middle_data/train_postag_BIO.pk","wb"))
else:
    print("loading...")
    id2pos_BIO,pos2id_BIO,text_data_postag=pk.load(open("./middle_data/train_postag_BIO.pk","rb"))


# In[5]:


if not os.path.exists("./middle_data/texts_tfidf_svd.pk"):
    texts_tfidf_svd,tfidf_vectorizer,svd_vectorizer=build_tfidf_svd_matrix(text_data,16)
    joblib.dump(tfidf_vectorizer,"./middle_data/tfidf_vectorizer.sk.model")
    joblib.dump(svd_vectorizer,"./middle_data/svd_vectorizer.sk.model")
    pk.dump(texts_tfidf_svd,open("./middle_data/texts_tfidf_svd.pk","wb"))
else:
    print("loading...")
    texts_tfidf_svd=pk.load(open("./middle_data/texts_tfidf_svd.pk","rb"))





if not os.path.exists("./middle_data/ner_examples_ner.pk"):
    ner_examples=[]
    example2doc=[]
    doc2example=[[] for i in range(len(ner_doc_tokens))]
    for idx,(tokens,rel,labels,token2doc) in tqdm(enumerate(zip(ner_doc_tokens,ner_doc_rels,ner_doc_token_labels,ner_token2doc))):
        tfidf_svd=texts_tfidf_svd[ner_doc2doc[idx]]
        postag=text_data_postag[ner_doc2doc[idx]]
        cur_idx=0
        rel_text=id2rel_text[rel]
        rel_postag=rel_data_postag[rel]
        rel_token2doc=id2rel_token2text[rel]
        while len(tokens)-cur_idx> (max_len-3-len(rel_text)):
            temp_tokens=tokens[cur_idx:cur_idx+max_len-3-len(rel_text)]
            temp_labels=labels[cur_idx:cur_idx+max_len-3-len(rel_text)]
            temp_token2doc=[e[cur_idx:cur_idx+max_len-3-len(rel_text)] if ind<2 else e for ind,e in enumerate(token2doc)]
            #训练时把这些label里面妹有 3 4 1 2 的样本去掉
            if (1 in  temp_labels) or (2 in  temp_labels) or (3 in  temp_labels) or (4 in  temp_labels):
                example2doc.append(idx)
                ner_examples.append(create_example(temp_tokens,rel,temp_labels,temp_token2doc,tokenizer,rel_text,tfidf_svd,postag,rel_postag,rel_token2doc))
                doc2example[idx].append(len(ner_examples)-1)
            cur_idx+=max_len-3-len(rel_text)
        if cur_idx<len(tokens):
            temp_tokens=tokens[cur_idx:]
            temp_labels=labels[cur_idx:]
            temp_token2doc=[e[cur_idx:cur_idx+max_len-3-len(rel_text)] if ind<2 else e for ind,e in enumerate(token2doc)]
            if (1 in  temp_labels) or (2 in  temp_labels) or (3 in  temp_labels) or (4 in  temp_labels):
                example2doc.append(idx)
                ner_examples.append(create_example(temp_tokens,rel,temp_labels,temp_token2doc,tokenizer,rel_text,tfidf_svd,postag,rel_postag,rel_token2doc))    
                doc2example[idx].append(len(ner_examples)-1)

    pk.dump([doc2example,example2doc,ner_examples],open("./middle_data/ner_examples_ner.pk","wb"))
else:
    print("loading example..")
    doc2example,example2doc,ner_examples=pk.load(open("./middle_data/ner_examples_ner.pk","rb"))


# In[7]:


# pk.dump([doc2example,example2doc,ner_examples[:10000]+ner_examples[-1000:]],open("./middle_data/ner_debug_examples_pointer.pk","wb"))


# In[6]:


# ner_train_dataset=NerDataset(ner_examples[:10000])
# ner_val_dataset=NerDataset(ner_examples[-1000:])

from sklearn.model_selection import KFold

ner_examples=np.array(ner_examples)
spliter=KFold(n_splits=3,shuffle=True,random_state=20)
for idx,(train_index,val_index) in enumerate(spliter.split(ner_examples)):
    if idx==args.split:
        print("split!!",idx)
        break
ner_train_dataset=NerDataset(ner_examples[train_index])
ner_val_dataset=NerDataset(ner_examples[val_index[:1000]])

# In[7]:


hidden_dropout_prob = 0.1
num_rel_labels = len(id2rels)
num_token_labels=len(id2labels)
learning_rate = 2.917e-06
weight_decay = 0
epochs = 12
batch_size = 16
adam_epsilon=1e-8




class GCNN_block(nn.Module):
    def __init__(self,input_channel,output_channel,kernel_size,padding,dilation=1):
        super(GCNN_block,self).__init__()
        self.input_channel=input_channel
        self.output_channel=output_channel
        self.conv1=nn.Conv1d(input_channel,output_channel,kernel_size,padding=padding,dilation=dilation)
        self.conv2=nn.Conv1d(input_channel,output_channel,kernel_size,padding=padding,dilation=dilation)
        if input_channel !=output_channel:
            self.trans=nn.Conv1d(input_channel,output_channel,1)
    def forward(self,args):
        X,attention_mask=args[0],args[1]
        X=X*attention_mask.unsqueeze(1).float()
        gate=torch.sigmoid(self.conv2(X))
        if self.input_channel==self.output_channel:
            Y=X*(1-gate)+self.conv1(X)*gate
        else:
            Y=self.trans(X)*(1-gate)+self.conv1(X)*gate
        Y=Y*attention_mask.unsqueeze(1).float()
        return Y,attention_mask
class BERT_BiLSTM_CRF(nn.Module):
    def __init__(self,bert_dir,config_file,num_rel_labels,num_token_labels,hidden_dropout_prob,need_birnn=True,need_cnn=False,rnn_dim=128):
        super(BERT_BiLSTM_CRF, self).__init__()
        self.num_rel_labels = num_rel_labels
        self.num_token_labels= num_token_labels
        self.bert =BertModel.from_pretrained(bert_dir,config=os.path.join(bert_dir,config_file),                                              hidden_dropout_prob=hidden_dropout_prob,output_hidden_states=True, output_attentions=True)
        self.dropout = nn.Dropout(hidden_dropout_prob)
        out_dim =self.bert.pooler.dense.out_features
        hidden_size=out_dim
        self.rel_classifier = nn.Linear(out_dim, self.num_rel_labels)
        self.need_birnn = need_birnn
        self.need_cnn=need_cnn
        # 如果为False，则不要BiLSTM层
        if need_birnn:
            self.birnn = nn.LSTM(out_dim, rnn_dim, num_layers=1, bidirectional=True, batch_first=True)
            out_dim = rnn_dim*2
        if need_cnn:
            self.DGCNN=nn.Sequential(GCNN_block(hidden_size,hidden_size,1,padding=0,dilation=1),
                       GCNN_block(hidden_size,hidden_size,3,padding=1,dilation=1),
                       GCNN_block(hidden_size,hidden_size,3,padding=2,dilation=2),
                       GCNN_block(hidden_size,hidden_size,3,padding=4,dilation=4))
            out_dim=hidden_size
            #attention/batch norm+relu/ pooling/什么都不用
        
        self.hidden2tag = nn.Linear(out_dim, self.num_token_labels)
        self.crf = CRF(self.num_token_labels, batch_first=True)
    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        labels=None,
        label_tokens=None
    ):

        outputs = self.bert(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids)

        seq_output,pooled_output = outputs[0],outputs[1]
        pooled_output = self.dropout(pooled_output)
        emissions=self.tag_outputs(seq_output,attention_mask)
        rel_logits = self.rel_classifier(pooled_output)
        seq_logits = emissions
        outputs = (rel_logits,seq_logits) + outputs[2:]  # add hidden states and attention if they are here
        loss_full=None
        if labels is not None:
            loss_rel = nn.BCEWithLogitsLoss(reduction="none")
            l_r = ((loss_rel(rel_logits.view(-1, self.num_rel_labels), labels.view(-1,self.num_rel_labels).float())).sum(dim=-1)).mean()
            loss_full=l_r

        if label_tokens is not None:
            l_t = -1*self.crf(emissions, label_tokens, mask=attention_mask.byte(),reduction='mean')
            loss_full+=l_t
        if loss_full is not None:
            outputs = (loss_full,) + outputs
        return outputs  # (loss), logits, (hidden_states), (attentions)

    def tag_outputs(self, sequence_output,attention_mask):
        if self.need_birnn:
            sequence_output, _ = self.birnn(sequence_output)
        if self.need_cnn:
            sequence_output=self.DGCNN([sequence_output.permute(0,2,1),attention_mask])[0].permute(0,2,1)
        sequence_output = self.dropout(sequence_output)
        emissions = self.hidden2tag(sequence_output)
        return emissions
    
    def predict(self, input_ids,attention_mask=None,token_type_ids=None):
        outputs = self.bert(input_ids, attention_mask=attention_mask,token_type_ids=token_type_ids )
        sequence_output = outputs[0]
        emissions = self.tag_outputs(sequence_output,attention_mask)
        return self.crf.decode(emissions, attention_mask.byte())

def set_seed(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.n_gpu > 0:
        torch.cuda.manual_seed_all(args.seed)
def train(args, train_dataset,val_dataset, model, tokenizer):
#     """ Train the model """
#     if args.local_rank in [-1, 0]:
#         tb_writer = SummaryWriter()

#     args.train_batch_size = args.per_gpu_train_batch_size * max(1, args.n_gpu)
    train_sampler = RandomSampler(train_dataset) # if args.local_rank == -1 else DistributedSampler(train_dataset)
    train_dataloader = DataLoader(train_dataset, sampler=train_sampler, batch_size=args.train_batch_size)

    if args.max_steps > 0:
        t_total = args.max_steps
        args.num_train_epochs = args.max_steps // (len(train_dataloader) // args.gradient_accumulation_steps) + 1
    else:
        t_total = len(train_dataloader) // args.gradient_accumulation_steps * args.num_train_epochs

    # Prepare optimizer and schedule (linear warmup and decay)
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {
            "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
            "weight_decay": args.weight_decay,
        },
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ]

    optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=args.adam_epsilon)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=args.warmup_steps, num_training_steps=t_total
    )

    # Check if saved optimizer or scheduler states exist
    if os.path.isfile(os.path.join(args.model_name_or_path, "optimizer.pt")) and os.path.isfile(
        os.path.join(args.model_name_or_path, "scheduler.pt")
    ):
        logger.info("  loading optimizer and scheduler...")
        # Load in optimizer and scheduler states
        optimizer.load_state_dict(torch.load(os.path.join(args.model_name_or_path, "optimizer.pt")))
#         scheduler.load_state_dict(torch.load(os.path.join(args.model_name_or_path, "scheduler.pt")))
    else:
        logger.info("  No optimizer and scheduler,we build a new one")        

    if args.fp16:
        try:
            from apex import amp
        except ImportError:
            raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use fp16 training.")
        model, optimizer = amp.initialize(model, optimizer, opt_level=args.fp16_opt_level)

    # multi-gpu training (should be after apex fp16 initialization)
    if args.n_gpu > 1:
        model = torch.nn.DataParallel(model,device_ids=args.card_list)


    # Train!
    logger.info("***** Running training *****")
    logger.info("  Num examples = %d", len(train_dataset))
    logger.info("  Num Epochs = %d", args.num_train_epochs)
#     logger.info("  Instantaneous batch size per GPU = %d", args.per_gpu_train_batch_size)
    logger.info(
        "  Total train batch size (w. parallel, distributed & accumulation) = %d",
        args.train_batch_size
        * args.gradient_accumulation_steps
#         * (torch.distributed.get_world_size() if args.local_rank != -1 else 1),
    )
    logger.info("  Gradient Accumulation steps = %d", args.gradient_accumulation_steps)
    logger.info("  Total optimization steps = %d", t_total)

    global_step = 0
    epochs_trained = 0
    steps_trained_in_current_epoch = 0
    # Check if continuing training from a checkpoint
    if os.path.exists(args.model_name_or_path):
        # set global_step to global_step of last saved checkpoint from model path
        try:
            global_step = int(args.model_name_or_path.split("-")[-1].split("/")[0])
        except ValueError:
            global_step = 0
        epochs_trained = global_step // (len(train_dataloader) // args.gradient_accumulation_steps)
        steps_trained_in_current_epoch = global_step % (len(train_dataloader) // args.gradient_accumulation_steps)

        logger.info("  Continuing training from checkpoint, will skip to saved global_step")
        logger.info("  Continuing training from epoch %d", epochs_trained)
        logger.info("  Continuing training from global step %d", global_step)
        logger.info("  Will skip the first %d steps in the first epoch", steps_trained_in_current_epoch)

    tr_loss, logging_loss = 0.0, 0.0
    model.zero_grad()
    train_iterator = tqdm(range(
        epochs_trained, int(args.num_train_epochs)), desc="Epoch")
    set_seed(args)  # Added here for reproductibility
    for _ in train_iterator:
        epoch_iterator = tqdm(train_dataloader, desc="Iteration")
        for step, batch in enumerate(epoch_iterator):

            # Skip past any already trained steps if resuming training
            if steps_trained_in_current_epoch > 0:
                if  (step + 1) % args.gradient_accumulation_steps == 0: 
                        steps_trained_in_current_epoch -= 1
                continue

            model.train()
            batch = tuple(t.to(args.device) for t in batch[:-1])
            inputs = {"input_ids": batch[0], "attention_mask": batch[1], "labels": batch[3],"label_tokens":batch[4]}
            inputs["token_type_ids"]=batch[2]
#             if args.model_type != "distilbert":
#                 inputs["token_type_ids"] = (
#                     batch[2] if args.model_type in ["bert", "xlnet", "albert"] else None
#                 )  # XLM, DistilBERT, RoBERTa, and XLM-RoBERTa don't use segment_ids
            outputs = model(**inputs)
            loss = outputs[0]  # model outputs are always tuple in transformers (see doc)

            if args.n_gpu > 1:
                loss = loss.mean()  # mean() to average on multi-gpu parallel training
            if args.gradient_accumulation_steps > 1:
                loss = loss / args.gradient_accumulation_steps

            if args.fp16:
                with amp.scale_loss(loss, optimizer) as scaled_loss:
                    scaled_loss.backward()
            else:
                loss.backward()
            logger.info("  step:%d loss %.3f", step,loss.item())

            tr_loss += loss.item()
            if (step + 1) % args.gradient_accumulation_steps == 0:
                if args.fp16:
                    torch.nn.utils.clip_grad_norm_(amp.master_params(optimizer), args.max_grad_norm)
                else:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)

                optimizer.step()
                scheduler.step()  # Update learning rate schedule
                model.zero_grad()
                global_step += 1

                if  args.save_steps > 0 and global_step % args.save_steps == 0:
                    # Save model checkpoint
                    results = evaluate(args, val_dataset,model, tokenizer)
                    output_dir = os.path.join(args.output_dir, "checkpoint-{}".format(global_step))
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    model_to_save = (
                        model.module if hasattr(model, "module") else model
                    )  # Take care of distributed/parallel training
                    torch.save(model_to_save.state_dict(),os.path.join(output_dir,"model.pt"))
                    tokenizer.save_pretrained(output_dir)

                    torch.save(args, os.path.join(output_dir, "training_args.bin"))
                    logger.info("Saving model checkpoint to %s", output_dir)
                    if args.fp16:
                        torch.save(amp.state_dict(),os.path.join(output_dir, "amp.pt"))
                    torch.save(optimizer.state_dict(), os.path.join(output_dir, "optimizer.pt"))
                    torch.save(scheduler.state_dict(), os.path.join(output_dir, "scheduler.pt"))
                    logger.info("Saving optimizer and scheduler states to %s", output_dir)

            if args.max_steps > 0 and global_step > args.max_steps:
                epoch_iterator.close()
                break
        if args.max_steps > 0 and global_step > args.max_steps:
            train_iterator.close()
            break


    return global_step, tr_loss / global_step
def evaluate(args, eval_dataset,model, tokenizer, prefix=""):
    eval_output_dir = args.output_dir 

    results = {}

    if not os.path.exists(eval_output_dir) :
        os.makedirs(eval_output_dir)

    eval_sampler = SequentialSampler(eval_dataset)
    eval_dataloader = DataLoader(eval_dataset, sampler=eval_sampler, batch_size=args.eval_batch_size,num_workers=0)

    # multi-gpu eval
#         if args.n_gpu > 1 and not isinstance(model, torch.nn.DataParallel):
#             model = torch.nn.DataParallel(model)

    # Eval!
    logger.info("***** Running evaluation {} *****".format(prefix))
    logger.info("  Num examples = %d", len(eval_dataset))
    logger.info("  Batch size = %d", args.eval_batch_size)
    eval_loss = 0.0
    nb_eval_steps = 0
    rel_preds=None
    rel_labels=None
    token_preds=None
    token_labels=None
    for batch in tqdm(eval_dataloader, desc="Evaluating"):
        model.eval()
        batch = tuple(t.to(args.device) for t in batch[:-1])

        with torch.no_grad():
            inputs = {"input_ids": batch[0], "attention_mask": batch[1], "labels": batch[3],"label_tokens":batch[4]}
            inputs["token_type_ids"]=batch[2]
            temp_inputs={"input_ids": batch[0], "attention_mask": batch[1],"token_type_ids":batch[2]}
#                 if args.model_type != "distilbert":
#                     inputs["token_type_ids"] = (
#                         batch[2] if args.model_type in ["bert", "xlnet", "albert"] else None
#                     )  # XLM, DistilBERT, RoBERTa, and XLM-RoBERTa don't use segment_ids
            outputs = model(**inputs)
            model_to_predict = (
                model.module if hasattr(model, "module") else model
            )  # Take care of distributed/parallel training
            token_pred=model_to_predict.predict(**temp_inputs)
            tmp_eval_loss, rel_logits, token_logits = outputs[:3]
            
            eval_loss += tmp_eval_loss.mean().item()
        nb_eval_steps += 1
        mask=batch[1].view(-1).detach().cpu().numpy()
        rel_pred = F.softmax(rel_logits,dim=-1)
        rel_pred =torch.argmax(rel_pred,dim=-1).detach().cpu().numpy()
        rel_label=torch.argmax(inputs["labels"],dim=-1).detach().cpu().numpy()
        if rel_preds is None:
            rel_preds=rel_pred
        else:
            rel_preds=np.append(rel_preds,rel_pred,axis=0)
        if rel_labels is None:
            rel_labels=rel_label
        else:
            rel_labels=np.append(rel_labels,rel_label,axis=0)     

            
        #token classify
#         token_pred = F.softmax(token_logits,dim=-1)
#         token_pred =torch.argmax(token_pred,dim=-1).view(-1).detach().cpu().numpy()*mask
        for i in range(len(token_pred)):
            token_pred[i]+=[label2ids['[PAD]']]*(max_len-len(token_pred[i]))
        token_pred=np.array(token_pred).reshape(-1)*mask
        token_label=inputs["label_tokens"].view(-1).detach().cpu().numpy()*mask
        if token_preds is None:
            token_preds=token_pred
        else:
            token_preds=np.append(token_preds,token_pred,axis=0)
        if token_labels is None:
            token_labels=token_label
        else:
            token_labels=np.append(token_labels,token_label,axis=0) 
        


    eval_loss = eval_loss / nb_eval_steps
    print("准召报告：")
    df_precison_recall_f1=pd.DataFrame(list(metrics.precision_recall_fscore_support(rel_labels,rel_preds)),index=['precison','recall','f1','number'])
    display(HTML(df_precison_recall_f1.to_html()))
    df_precison_recall_f2=pd.DataFrame(list(metrics.precision_recall_fscore_support(token_labels,token_preds)),index=['precison','recall','f1','number'])
    display(HTML(df_precison_recall_f2.to_html()))
    result = {"cls":    df_precison_recall_f1,'ner':    df_precison_recall_f2}
    results.update(result)

    output_eval_file = os.path.join(eval_output_dir, prefix, "eval_results.txt")
    with open(output_eval_file, "a") as writer:
        logger.info("***** Eval results {} *****".format(prefix))
        for key in sorted(result.keys()):
            logger.info("  %s = %s", key, str(result[key]))
            writer.write("%s = %s\n" % (key, str(result[key])))

    return rel_labels,rel_preds,token_preds,token_labels



# In[9]:
args=ARG(train_batch_size=batch_size*2,eval_batch_size=batch_size*2,weight_decay=weight_decay,learning_rate=learning_rate,
         adam_epsilon=adam_epsilon,num_train_epochs=epochs,warmup_steps=0,gradient_accumulation_steps=1,save_steps=int(len(ner_train_dataset)//(batch_size*2)),
         max_grad_norm=1.0,model_name_or_path=os.path.join(output_dir,"checkpoint-29840"),output_dir=output_dir,seed=42,device=device,n_gpu=len(card_list),
        max_steps=0,output_mode="classification",fp16=False,fp16_opt_level='O1',card_list=card_list)

# model=BertSeqLabeling(bert_dir,config_file,num_rel_labels=num_rel_labels,num_token_labels=num_token_labels,
#                                      hidden_dropout_prob=hidden_dropout_prob)
model=BERT_BiLSTM_CRF(bert_dir,config_file,num_rel_labels=num_rel_labels,num_token_labels=num_token_labels,
                                     hidden_dropout_prob=hidden_dropout_prob,need_birnn=need_rnn,need_cnn=need_cnn)
# model=BERT_BiLSTM_POINTER(bert_dir,config_file,num_rel_labels=num_rel_labels,num_token_labels=num_token_labels,
#                          hidden_dropout_prob=hidden_dropout_prob,need_birnn=need_rnn,need_cnn=need_cnn\
#                           ,use_plan=use_plan,p=p)
model_path=os.path.join(args.model_name_or_path,"model.pt")
print("model_path",model_path)
print("save steps",args.save_steps)
ckpt=torch.load(model_path, map_location=lambda storage, loc: storage)
model.load_state_dict(ckpt)

# In[10]:



# In[11]:


set_seed(args)
model.to(args.device)
global_step, tr_loss = train(args,ner_train_dataset,ner_val_dataset, model, tokenizer)
