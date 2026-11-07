# Watch 前端模块化与 Studio 工作舱实现

本文档说明 `watch.html` 的拆分结构、构建机制以及近期滚轮和卡顿问题的修复细节。

## 1. 为什么拆分

`orpath/web/watch.html` 之前把所有 CSS、HTML 模版、检视台逻辑和做题工作舱脚本堆在一个文件里，总行数超过 3300 行。
单文件过大导致几个实际问题：
- 修改做题工作舱样式时容易误伤检视台的 8 行网格布局。
- 门禁检查依赖特定 DOM id 和函数签名，直接在一个大文件里改动很难理清调用链。
- 难以针对独立模块做静态文件调试。

重构后，源码拆入 `orpath/web/src/`，并通过构建脚本统一打包为单文件 `watch.html`，既方便平时按模块维护，又确保对现有测试门禁零破坏。

## 2. 源码组织

```text
orpath/web/
├── src/
│   ├── css/
│   │   ├── base.css        # 全局变量、排版重置与 mode-studio / mode-inspector 容器布局
│   │   ├── studio.css      # 做题工作舱专属样式：卡片、滚动条、问答表单、成果下载
│   │   └── inspector.css   # 过程检视台样式：工具栏、阶段泳道、对话表单、模态框
│   ├── html/
│   │   ├── header.html     # 顶栏导航、双模式切换按钮与状态徽标
│   │   ├── studio.html     # 做题工作舱三步卡片结构
│   │   ├── inspector.html  # 专家检视台原生布局与底部栏
│   │   └── modals.html     # 题目导入弹窗与工件查看器
│   └── js/
│       ├── common.js       # 核心工具函数、状态字典与模式切换
│       ├── studio.js       # 做题舱前端逻辑：拖拽解析、API 配置、研判、确认求解
│       └── inspector.js    # 检视台前端逻辑：轮询/SSE 双轨、阶段渲染、Steer 表单
├── build.py                # 本地构建装配器（比对时间戳按需生成）
└── watch.html              # 最终生成的单文件（提交进仓库，供服务与门禁使用）
```

## 3. 构建与静态服务

打包由 `orpath/web/build.py` 负责：
- 依次读取 `src/css/`、`src/html/`、`src/js/` 下的文件，拼接成自包含的 `watch.html`。
- 如果文件无变化，跳过重新写入；加 `--force` 参数可强制全量刷新。
- `scripts/orpath_watch.py` 在收到根路径请求时会自动比对 `src/` 时间戳并按需编译。
- 服务端同时支持 `/static/css/*` 与 `/static/js/*` 路由，可以直接加载 `src/` 下的独立源文件进行断点调试。

验证构建与门禁：
```bash
python orpath/web/build.py --force
.venv/bin/python scripts/problem_workbench_gate.py
```

## 4. 缺陷根因与修复

### 4.1 鼠标滚轮无法向下滚动
- **根因**：页面根样式定义了 `body { height: 100vh; overflow: hidden; display: grid; }`，在做题模式下，容器 `#studioContainer` 没有设置自己的滚动属性和高度限制。当内容超过一屏时，溢出部分被 `body` 裁切，同时浏览器全局滚轮事件被吸收，导致无法向下滚动。
- **修复**：
  - 在 `base.css` 中将 `body.mode-studio` 改为垂直 flex 容器。
  - `#studioContainer` 设置 `flex: 1 1 auto; min-height: 0; overflow-y: auto !important;` 并配置自定义滚动条。
  - 检视台和页脚在做题模式下完全隐藏。切换模式时通过 `setAppMode` 切换 `document.body` 的类名，滚轮恢复正常。

### 4.2 文件上传后界面停留不前
- **根因**：
  - 卡片展开时原本调用 `scrollIntoView()`，但在外层容器死锁的情况下无法滚动，用户视野始终停留在第一步，看不到下方已经生成的第二步分析卡片。
  - 异常分支调用了系统原生的 `alert()`，在浏览器中弹窗会挂起事件循环，造成界面卡死的直观感受。
- **修复**：
  - 增加了容器级滚动平滑辅助函数 `scrollStudioToCard`，当分析或求解完成时，主动将 `#studioContainer` 滚动到对应的目标卡片顶部。
  - 移除所有阻塞式 `alert()`，改为卡片内嵌的错误提示条，并保留重试按钮。
  - 在文件拖拽区下方添加就绪状态栏与快捷启动按钮，文件加载完成后可直接点击进入研判。
