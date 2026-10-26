# Lemo-Opuscar 白板讲解试片：家务百分比

在 [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar)（MIT）的克隆里，按它的 AGENTS/DIRECTOR/TECHNIQUE 流程做的 31 秒试片。
`engine/wb.js` 复制自它的 `styles/whiteboard/demo/engine/`（MIT）。板上汉字的笔画中线来自 hanzi-writer-data（Make Me a Hanzi，Arphic Public License，见 fonts/）。

放到库里的 `films/jiawu/` 下运行：events.mjs → mix.py → video.mjs → 两遍 loudnorm 封装（mux.sh 在 ffmpeg 6.1 上会误判音频长度，见对话记录）。
