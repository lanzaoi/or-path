# 带外目录（Out-of-band）

下列路径**不属于** OR-Path 产品源码导航，默认勿当业务代码读写。

| 路径 | 性质 | Git |
|------|------|-----|
| `vendor/` | 上游镜像 | **忽略** |
| `openpi/` | 已移除 | **忽略** |
| `pi-main/` | Pi 上游树 | **忽略** |
| `runtime/node_modules/` | Pi npm（L2 zip 可含；git 忽略） | **忽略** |
| `.venv-314/` | Python 环境 | **忽略** |
| `.hermes/` | Hermes IDE 本机区（含赛题附件风险） | **整棵忽略** |
| `inbox/*` | 本地题面投放 | **忽略**（保留 `inbox/README.md`） |
| `/outputs` `/runs` `/notes` `/papers` | 运行产物（根目录） | **忽略**（`demo/seed/**` 例外） |
| `dist/` | 打包输出 | **忽略** |

## 历史文档

可公开的历史在 **`docs/archive/`**（plans / closeouts / tickets / design-notes / evidence）。  
不要把新的施工长文堆回 `docs/` 顶层。

## 产品入口（对照）

| 路径 | 性质 |
|------|------|
| `orpath/` `tools/` `scripts/` `specs/` | **产品** |
| `START-*.bat` `orpath.bat` | **入口** |
| `demo/seed/` | **默认可分发脸** |
| `docs/*.md`（顶层少数） | **活文档** |
