# V2 已验证案例与复用边界

证据来源：`<本地视频项目目录>` 的代码、教程、预览图与 MP4（迁移环境时项目路径只是定位线索，不是必须存在的依赖）。整理日期：2026-10-13。

## 已观察到的实现

- 初版 `replica/render.py` 用透明立绘的位移、缩放、旋转制作有限动画。
- V2 `replica/motion_assets.py` 保留原片的连续角色表演，两段 89、88 张透明帧。动作与眨眼、闭眼笑来自原片，不是单图生成。
- SIFT/RANSAC 负责配准；干净参考帧修补字幕；GrabCut 加针对原片的颜色阈值分离前景；道具与嘴部按需要局部跟踪。
- `replica/render_final.py` 用 DIS 光流补帧，透明图预乘 Alpha 插值；局部嘴部随 300～4000 Hz 语音能量开合。这不是逐音素同步。
- 声音复用原片，以 0.82 倍速保音高调整，延迟 0.12 秒；角色与口型共用相同时间映射。
- 背景、标题、Logo、字幕和装饰重新合成。每段 4 秒，合并 8 秒、1080×1920、30fps、H.264/AAC。
- 预览采用每段多个时刻，另有脸部、跟踪、嘴部检查图。代码能导出不等于动态和声音已验收。

## 可迁移的经验

1. 观感提升首先来自连续表演素材；背景动效只能辅助。
2. 分层降低改动互相影响：改字幕不必重做人物，修嘴部不应破坏眼睛。
3. 角色保持一致，信息分批出现，观众才知道先看哪里。
4. 干净帧修补、坐标一致、共用时间轴这些细节决定是否穿帮。
5. 先检查关键帧和短段，再批量渲染；把失败定位到具体层。
6. 向执行模型交付素材与可执行工具，效果比只给描述性的提示词更可控。

## 原样复现的真实入口

先读项目 `AGENTS.md`、`docs/video_tutorial.md`、`docs/agent_playbook.md`。在项目根目录每次运行一个阶段，检查成功后再继续：

```powershell
python replica/workflow.py init --job skill_replay01
python replica/workflow.py check --job skill_replay01
python replica/workflow.py motion --job skill_replay01
python replica/workflow.py preview --job skill_replay01
python replica/workflow.py render --job skill_replay01
python replica/workflow.py verify --job skill_replay01
```

输出隔离在 `replica/runs/skill_replay01/`。任务名已存在时先检查进度，或用新名字保留旧结果。不能并行向同一目录渲染。`motion_assets.py --preview` 不能代替完整提取。

`workflow.py` 会校验原片指纹与角色尺寸。不能绕过校验直接套新素材。不要运行底层脚本覆盖 `replica/v2/output/` 已验收产物；常规复现也不用重跑 `prepare_assets.py`。

## 没有被这个案例证明的能力

- 当前入口不接受任意主题、任意台词、任意角色 JSON。
- 原片文案中的产品与版本未由案例核实，不能复制到新主题事实脚本。
- 新台词需要新配音；新角色需要素材与标定；新动作需要动作库、绑定或生成工具。
- 此 skill 包含工作流和通用技术检查器，不内置角色素材、视频生成服务或新主题渲染器。
- 尚未用较弱模型完成多个新主题对照测试，不能声称已证明与强模型效果等同。
