# 抖音科普《微波炉热的饭菜有辐射吗》画面工程

写实信息图风，1080×1920 / 30fps，每个镜头一个 MP4，无声音。

- `lib/core.js`：全局风格（配色、字体、标注、动效节奏、微波炉组件）
- `lib/render.js`：Playwright 逐帧截图 → ffmpeg 编码
- `shots/sNN.js`：每个镜头
- 字体（不入库，需放到 `fonts/`）：思源黑体 NotoSansSC-Black/Bold（notofonts/noto-cjk，OFL）

```
node lib/render.js shots/s01.js frames/s01 --at 0,3,7   # 截关键帧
node lib/render.js shots/s01.js out/镜头01.mp4           # 渲染
```
