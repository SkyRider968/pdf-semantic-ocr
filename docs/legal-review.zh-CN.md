# 许可与发布审查：0.1.0

核对日期：2026-10-11。范围：当前源码、README、SOP、skill、测试资料、选用的主要依赖和模型许可声明。
这是工程层面的许可筛查，不能替代特定司法辖区、部署方式和商业合同的法律意见。

## 判断

按当前 AGPL 开源方式发布工具、原创示例及对应源码，未发现明确禁止该发布方式的条款。
这不等于不存在法务风险。最需要管理的是 AGPL 集成义务和输入文档的版权；
当前版本不能直接作为“闭源商用集成无许可负担”的产品宣传。
GitHub 发布仍待账号认证；尚无公开仓库或远端 CI 验收结果。

## 代码许可

本项目为 AGPL-3.0-or-later，完整许可证在根目录 LICENSE，包元数据也声明该许可。
[PyMuPDF](https://github.com/pymupdf/PyMuPDF/blob/main/COPYING) 使用 AGPL-3.0；
[官方说明](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
同时提供 Artifex 商业许可路线。
[DocLayout-YOLO 代码](https://github.com/opendatalab/DocLayout-YOLO/blob/main/LICENSE) 使用 AGPL-3.0。

AGPL 允许商业使用，也允许收费；相关条件主要是许可证、版权声明和对应源码的提供。
若修改后的受覆盖程序供用户通过网络交互，AGPL 第 13 条要求向这些用户提供取得对应源码的机会。
闭源程序与这些依赖形成何种组合、哪些部分属于受覆盖作品，需要结合实际集成方式判断；
不能笼统断言“所有 SaaS 代码都要公开”，也不能以未修改依赖为由自动认定整套集成不受影响。
仅给自己写的封装换成 MIT 不能消除底层 AGPL 义务。

若将来做闭源分发或在线商业产品，应在架构确定前处理 PyMuPDF 商业许可或替代实现，
并单独解决 DocLayout 的许可或替代后端。不得认为购买 PyMuPDF 许可同时解决其他组件。
发布 wheel 时应同时提供同版本、包含必要构建材料的源码；当前已准备 sdist，
公开发布时还需核对源码与二进制对应并保持可获取。

宽松许可依赖已核对主要上游声明：
[RapidOCR](https://github.com/RapidAI/RapidOCR/blob/main/LICENSE)、
[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE)、
[OpenCV](https://github.com/opencv/opencv/blob/5.x/LICENSE) 为 Apache-2.0；
[ONNX Runtime](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) 和
[MLX-VLM](https://github.com/Blaizzy/mlx-vlm/blob/main/LICENSE) 为 MIT；
[NumPy 主项目](https://github.com/numpy/numpy/blob/main/LICENSE.txt) 为 BSD-3-Clause；
[PyObjC](https://github.com/ronaldoussoren/pyobjc/blob/main/pyobjc-core/License.txt) 为 MIT，但 Apple 框架另受 Apple 条款约束；
[当前 Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE) 为 MIT-CMU。
本次更正了原 notices 中仅写 Pillow HPND 的表述。
NumPy/Pillow 等二进制包还有内嵌组件许可，不能用主项目许可概括整个二进制包。
当前项目 wheel 不捆绑这些依赖；将来打包容器、桌面程序或完整运行时，应对锁定版本做传递依赖清单并保留其完整 notices。

## 模型权重：与代码分开核对

| 模型 | 本次证据 | 判断范围 |
| --- | --- | --- |
| DocLayout-DocStructBench | [固定 revision 的模型卡](https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench/blob/8c3299a30b8ff29a1503c4431b035b93220f7b11/README.md) 声明 `license: apache-2.0` | 权重声明为 Apache-2.0，推理库仍为 AGPL；模型卡非常简短 |
| PaddleOCR-VL-1.6 | [固定 revision 的完整 LICENSE](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/blob/c5630abae1d940eafe0697512a0325494b02ab42/LICENSE) | Apache-2.0 |
| MLX 4-bit 量化版 | [固定 revision 的模型卡](https://huggingface.co/mlx-community/PaddleOCR-VL-1.6-4bit/blob/c8987b277bdd8aaec8bd265d154f391bd03ad165/README.md) 声明 Apache-2.0 并标明上述基础模型 | 来源链和许可声明相符；未独立审计全部转换过程 |
| RapidOCR 选用的 ONNX 权重 | [ModelScope v3.10.0 README](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/README.md) 声明 Apache License 2.0；[托管 API](https://www.modelscope.cn/api/v1/models/RapidAI/RapidOCR) 的 License 字段一致 | 仓库级许可声明；请求该 revision 的独立 LICENSE 文件返回 404，不应称每个文件都已有单独完整许可证 |

选用 ONNX 文件名与 SHA-256 记录在 [models.md](models.md)。源码和发布包均不包含权重。
不捆绑权重不能免除下载、运行或再分发时的许可义务。上述声明也不能证明全部训练数据的权利来源。
当前 CLI 的模型下载未固定上述 HF revision，兼容版本范围也可能引入新的 RapidOCR 权重。
生产部署应保存固定本地模型快照、许可与 notices，再核对实际使用版本；本次日期核查不是永久许可保证。

## 示例、输入和输出内容

公开示例的文字、表格和图示为本项目生成的合成材料，gold 来自生成器的源声明。
用户提供的文档、提取文本、页图与修复记录不进入源码或发布包。
不以资料来源机构的官方身份或认证背书宣传该工具。

数字示例嵌入 Droid Sans Fallback Regular 字体；
[Android 源码 NOTICE](https://android.googlesource.com/platform/frameworks/base/+/android-4.0.1_r1/data/fonts/NOTICE)
提供 Apache-2.0 和 Android Open Source Project 的版权声明。
完整许可与版权声明已分别保留于 LICENSES/Apache-2.0.txt 和 LICENSES/Droid-font-NOTICE.txt。

工具的软件许可不会授予教材、讲义、题库或其提取结果的版权。
OCR 改变载体，不会把书籍内容变成可自由公开传播的作品。
个人学习、合理使用或法定例外的适用取决于地区、来源和使用范围，不能一概认定完整复制与分享合法。
后续上传他人书籍全文到公开仓库、销售提取结果或发布大量原文，需要另行核实授权。
发布工具与公开用户提供的资料应分别判断，输入内容授权应由使用者核实。

## 隐私与效果宣传

本项目的识别适配器调用本地推理，代码中没有源 PDF 上传 API；模型下载会访问 Hugging Face、ModelScope 等上游。
这不是对所有依赖版本与运行环境进行的网络出站审计，不能宣传“全栈零联网”。
若把 skill 接入云端 Agent，由 Agent 读取、发送文档内容的路径需要另行评估。
raw、完整页图、修复记录和候选结果也属于输入内容的副本，不能只删除最终 Markdown 就认定敏感内容已清除。

当前 [validation.md](validation.md) 限定了样本、环境和已知缺陷：小规模自制样本的 100% 不等于任意教材的 99%。
`engineering_status: PASS` 与语义认证分别报告，自动 audit 始终保留 `NOT_CERTIFIED`。
公开宣传应继续保留这些范围，不能改写为“全书保证准确”“每张图片完整提取”或“一键无需复核”。

## 本轮处理及剩余边界

已修正 Pillow 许可名称、增加代码/模型许可区分、记录已核对模型 revision/ONNX hash，
并在 README 明确文档版权不由工具许可覆盖。
基础 onboarding 已拆分为先跑数字/规则扫描示例，再按平台安装高级后端；skill 引导同步。
当前公开源码发布未发现明确许可阻断；闭源商业集成、完整运行时再分发、真实资料对外使用仍需各自核查。
没有完成全量传递依赖 SBOM、训练数据权利审计或针对所有部署模式的法律分析。
