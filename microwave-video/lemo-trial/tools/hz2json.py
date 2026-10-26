"""把板上要写的汉字的笔画中线（Make Me a Hanzi / hanzi-writer-data，Arphic Public License）抽成 fonts/hanzi.json。
用法：python tools/hz2json.py <hanzi-writer-data 的 package 目录>"""
import json, sys, os
CHARS = '家务小组作业我干了一整份丈夫妻子超出撒谎你在场洗碗拖地衣服对方的做饭倒垃圾交水电费先想别人再估自己高'
src = sys.argv[1]; out = {}
for ch in dict.fromkeys(CHARS):
    d = json.load(open(os.path.join(src, ch + '.json')))
    out[ch] = d['medians']
os.makedirs('fonts', exist_ok=True)
json.dump(out, open('fonts/hanzi.json', 'w'), separators=(',', ':'))
print(len(out), 'glyphs')
