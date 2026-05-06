# `figures/` 目录说明

本目录存放论文正文中所有矢量图源文件与编译用图片。

## 一、当前文件

| 文件名 | 说明 | 引用位置 |
|---|---|---|
| `dual_path_rag.svg` | 双通路 RAG 架构示意图，drawio 导出 | `\reffig{fig:dual-path-rag}`，4.1 节 |
| `code-gen-flow.svg` | 代码生成与受限沙箱执行流程图，drawio 导出 | `\reffig{fig:code-gen-flow}`，4.2 节 |

## 二、xelatex 与图片格式的兼容性

xelatex 默认仅支持 `.pdf / .png / .jpg / .jpeg / .eps`，不直接接受 `.svg`。
本论文 `4_1_语义桥接.tex` 与 `4_2_代码生成.tex` 中 `\includegraphics`
**不写后缀**，让 xelatex 按 `\DeclareGraphicsExtensions` 默认顺序自动选择
合适格式（`.pdf` 优先于 `.png`）。

> 注意：`.pdf` 优先意味着如果 drawio 导出失败留下 0 字节空 PDF，xelatex 会
> 报 `! Unable to load picture or PDF file` 而不是回退到 PNG。删除空 PDF
> 即可恢复 PNG 自动选择。

下面三种方式都能成功编译，按推荐顺序：

### 方案 0：drawio 直接导出 PNG（最简单）

1. drawio 中文件 → 导出 → PNG，缩放选 200% 或 300% 以保证打印清晰度，
   勾选「裁剪到图表大小」。
2. 保存为同名 PNG：

   ```
   figures/dual_path_rag.png
   figures/code-gen-flow.png
   ```

3. 不修改任何 `.tex` 文件，xelatex 会自动选 `.png`。
4. 缺点：位图，无限放大有锯齿；优点：导出无依赖，一次成功率高。

### 方案 1：drawio 直接导出 PDF（推荐）

drawio 处理自身导出的 `foreignObject + light-dark()` SVG 比 inkscape 更可靠
（不会丢失中文字体或样式）。步骤：

1. 在 drawio Desktop 或 [app.diagrams.net](https://app.diagrams.net/) 中
   打开 SVG（drawio SVG 自带 `<mxfile>` 元数据，可往返编辑）。
2. 文件 → 导出 → PDF，导出选项勾选「裁剪到图表大小」与「嵌入图片」，
   不勾选「页面页码」。
3. 保存为同名 PDF，与 SVG 并列：
   ```
   figures/dual_path_rag.pdf
   figures/code-gen-flow.pdf
   ```
4. 不需要修改 `论文.tex`，xelatex 会自动选择 `.pdf`。

### 方案 2：命令行 inkscape 转换（备选）

如果安装了 [Inkscape ≥ 1.0](https://inkscape.org/) 并加入 PATH：

```powershell
cd d:\毕设\docs\写作文档\figures
inkscape dual_path_rag.svg --export-type=pdf --export-text-to-path
inkscape code-gen-flow.svg --export-type=pdf --export-text-to-path
```

`--export-text-to-path` 把所有文字转换为路径，避免 PDF 字体缺失。
**注意**：drawio 的 SVG 用 `foreignObject` 嵌入 HTML 文本，老版本
inkscape 可能丢字。如出现文字缺失，请改用方案 1。

### 方案 3：导言区加载 svg 包（不推荐）

如果坚持只用 SVG，需要在 `论文.tex` 导言区加载：

```latex
\usepackage{svg}
```

并把 4.1/4.2 中的 `\includegraphics{figures/...}` 改为
`\includesvg[width=...]{figures/...}`，编译时启用：

```powershell
xelatex -shell-escape 论文.tex
```

且本机已安装 inkscape。该方案在 Windows + xelatex 上失败率较高，
故不推荐。

## 三、编译流程速记

```powershell
cd d:\毕设\docs\写作文档
xelatex 论文.tex
bibtex 论文
xelatex 论文.tex
xelatex 论文.tex
```

如果遇到「LaTeX Error: File `figures/dual_path_rag` not found.」，
说明对应的 PDF 还没生成，按方案 1 或方案 2 处理后再编译。
