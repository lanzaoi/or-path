# Feynman 源码深层复验 → OR-Path P0/P1（第二轮）

**日期：** 2026-07-29  
**方法：** 读 `vendor/feynman/src/**` 运行时（非只 prompts），对照 OR-Path 已实现 P0/P1。  
**原则：** 学协议与数据结构，**不**文件级照抄 TS。

---

## 1. Feynman 源码里「论文/证据」真正深的地方

### 1.1 Prompt 层（表面，上一轮已对齐大半）

| 机制 | 源 | OR 现状 |
|------|----|---------|
| `.drafts` draft/cited/revised | `prompts/deepresearch.md`, `pi/runtime.ts` scaffold | ✅ |
| on-disk 证明再声称 fixed | deepresearch 172 行协议 | ✅ 薄：`revise-proof.md`（needle），非通用 `rg` 工具链 |
| final candidate = revised else cited | deepresearch | ✅ **本轮补** `select_final_candidate` + provenance 提升 |
| failFast:false 子代理 | deepresearch | ⚪ Pi 配置层，非 LG 硬门 |
| verification.md | deepresearch | ✅ **本轮补** `.drafts/<slug>-verification.md` |

### 1.2 Workbench 运行时（深层，上一轮几乎没搬）

| 机制 | 源码 | 深度含义 | OR 现状 |
|------|------|----------|---------|
| **Claim marker 抽取** | `workbench/claims.ts` `CLAIM_MARKER` | 只有 `Claim:`/`Finding:`/`Conclusion:`/`Verified:` 行进账本；普通段落不进 | ✅ **本轮补** `orpath/claim_ledger.py` |
| **稳定 claimId** | `claimIdForText` = sha256(scope:norm)[:16] | UI/检查可链到同一 claim | ✅ **本轮补** `claim:<hex>` |
| **status 合并** failed>verified>unverified | `mergeCandidate` | verification check 可把 artifact 声明升级为 verified/failed | ✅ **本轮补** |
| **checks ↔ claimId** | `verification_checks` + claims test | 门禁结果是一等公民，不是散文 | ✅ **本轮补** gates→checks |
| **ResearchRun v1 schema** | `research/contracts.ts` + `validateResearchRun` | 全 run 状态机 + artifacts primary + 禁 rawFullTextStored | ❌ 未搬（P2/产品面） |
| **artifact versions + dependency** | `artifact-versions` / `artifact-provenance-ledgers` | 版本图：inputPaths→dependsOn | ❌ 未搬（有 LG checkpoint + hashes，但无版本依赖图） |
| **content snapshots before/after** | `artifact-snapshots` | 编辑可回放 | ❌ 未搬（P2） |
| **annotations 锚点** | `annotations.ts` | 选区/矩形批注反馈环 | ❌ 未搬；我们只有 review markdown inline |
| **PaperRank 排序包** | `rank/paper-rank.ts` | 文献 triage，**不是**写论文流水线 | ❌ 故意不搬（OR 知识轨另有 LightRAG） |
| **org DB ledgers** | `org-database.ts` | 多租户 SQLite 账本 | ❌ 不需要 |

### 1.3 测试钉死的行为（Feynman 自己当契约）

`tests/workbench-claims.test.ts`：

1. `Claim:` / `Finding:` 必须变成 structured claims  
2. verification 文件里的 `Verified:` 与 claim **同 id 合并为 verified**  
3. plain paragraphs **不**进 claims  

→ 我们的 `claim_ledger` 按此契约实现（Python）。

---

## 2. 上一轮 P0/P1 哪些是「表面对齐」

| 项 | 表面 | 深层缺口（已/未） |
|----|------|-------------------|
| draft→cite→review | 图节点有 | final candidate 规则本轮才钉死 |
| claim_map | 数字/URL 契约 | **不是** claimId 账本；两者互补 |
| inline review | markdown 批注 | 无 anchor/offset 存储 |
| plan ledger | 追加 stage 行 | 无 ResearchRun schema 校验 |
| revise-proof | needle ABSENT | 无 snapshot 版本链 |
| provenance | PASS/BLOCKED 文 | 本轮加 verificationState + final_candidate + claimCount |

---

## 3. 本轮补强（仍属 P0/P1 深度，不碰 P2 技术栈）

| 文件 | 作用 |
|------|------|
| `orpath/claim_ledger.py` | marker 抽取、claimId、merge、checks、verificationState、final candidate |
| `nodes_t2` cite_pack / provenance | 写 ledger + verification.md；提升 final→papers/ |
| `paper_workflow` Results | 主动写 `Claim:`/`Finding:` 行，便于账本捕获 |
| `scripts/paper_gate.py` | 校验 ledger schema / claim: ids / verification.md / final_candidate |

**明确仍不搬（非 1.0 论文硬核 / 属 P2）：**

- Workbench UI + annotations 存库  
- artifact snapshot/version graph  
- ResearchRun 全量 manifest validator  
- PaperRank / OpenAlex 深检索  
- failFast 子代理编排语义（Pi 侧）

---

## 4. 诚实结论

1. **之前不是抄源码**，主要是 prompt 协议 + OR 门禁自研。  
2. **深层源码**里，论文相关最该学的是 **`claims.ts` 账本模型** 与 **final candidate / verification 制品**，不是 PaperRank 几千行。  
3. 复验后：**P0/P1 协议层已从「像」加深到「有 claimId 账本 + verification 制品 + final 提升」**；与 Feynman 完整 workbench 仍有版本图/批注/ResearchRun 差距，那些标为 **P2/产品面**，不阻塞「可验证论文环 1.0」。

---

## 5. 验收命令

```bat
orpath.bat paper-gate
python -c "from orpath.claim_ledger import claim_id_for_text; print(claim_id_for_text('x','s'))"
```

期望：`P0_PAPER_GATE_PASS`，且存在  
`outputs/.drafts/<slug>-claim-ledger.json`、`*-verification.md`，provenance 含 `final_candidate` / `verificationState`。
