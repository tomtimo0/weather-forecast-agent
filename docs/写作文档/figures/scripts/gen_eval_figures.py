#!/usr/bin/env python3
"""
gen_eval_figures.py
===================

为本论文第 5 章实验验证生成 5 张统计图（导师意见 11）。

数据来源
--------

数据按论文 4.1/4.2/5.6 节中已确认表格硬编码到本脚本内部，与论文正文保持
严格一致。每张图的对应表如下：

* 图 5-1：tab:rag-weight-sweep        4.1 节 α 权重扫描
* 图 5-2：tab:bridge-ablation         4.1 节 通路 B 四档消融
* 图 5-3：tab:code-eval-overall       4.2 节 代码执行三档总表
* 图 5-4：tab:code-eval-category      4.2 节 代码执行按类别
* 图 5-5：tab:e2e-by-category         5.6 节 端到端按场景类别

输出
----

* docs/写作文档/figures/eval_5_1_rag_weight_sweep.png
* docs/写作文档/figures/eval_5_2_bridge_ablation.png
* docs/写作文档/figures/eval_5_3_code_overall.png
* docs/写作文档/figures/eval_5_4_code_by_category.png
* docs/写作文档/figures/eval_5_5_e2e_by_category.png

运行方式
--------

```bash
cd d:/毕设
python docs/写作文档/figures/scripts/gen_eval_figures.py
```

依赖：matplotlib >= 3.5。

@author 自动生成（按导师意见 11，2026-05-07）
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl

# ---------------------------------------------------------------------------
# 全局风格：中文字体 + 蓝橙双色 + 统一 dpi
# ---------------------------------------------------------------------------

plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["axes.grid"] = True
plt.rcParams["axes.axisbelow"] = True
plt.rcParams["grid.linestyle"] = ":"
plt.rcParams["grid.linewidth"] = 0.6
plt.rcParams["grid.alpha"] = 0.5
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["savefig.dpi"] = 300

# 与 drawio 出图统一的配色
COLOR_PRIMARY = "#1f77b4"   # 主色：蓝
COLOR_SECONDARY = "#ff7f0e"  # 对照色：橙
COLOR_NEUTRAL = "#7f7f7f"   # 灰
COLOR_HIGHLIGHT = "#d62728"  # 强调红（标注最优点）

# 项目相对路径
HERE = Path(__file__).resolve().parent
FIG_DIR = HERE.parent  # docs/写作文档/figures/

# ---------------------------------------------------------------------------
# 图 5-1  α 权重扫描折线图（双 y 轴：Top-1 命中率 + MRR）
# ---------------------------------------------------------------------------

def fig_5_1_rag_weight_sweep() -> Path:
    """对应论文 5.3 节，数据源 tab:rag-weight-sweep。"""
    alphas = [0.00, 0.50, 0.70, 0.80, 0.85, 0.90, 0.95, 1.00]
    top1 = [0.817, 0.783, 0.800, 0.817, 0.833, 0.850, 0.850, 0.817]
    mrr = [0.872, 0.851, 0.864, 0.872, 0.892, 0.908, 0.908, 0.872]

    fig, ax1 = plt.subplots(figsize=(7.0, 4.0))
    ax2 = ax1.twinx()

    line1, = ax1.plot(
        alphas, [v * 100 for v in top1],
        color=COLOR_PRIMARY, marker="o", linewidth=2,
        label="Top-1 命中率",
    )
    line2, = ax2.plot(
        alphas, mrr,
        color=COLOR_SECONDARY, marker="s", linewidth=2, linestyle="--",
        label="MRR",
    )

    # 标注最优点（α=0.9 与 α=0.95 并列最优；选 α=0.9 标注）
    best_alpha = 0.90
    best_top1 = 85.0
    best_mrr = 0.908
    ax1.annotate(
        f"最优 α = {best_alpha}\nTop-1 = {best_top1:.1f}%, MRR = {best_mrr:.3f}",
        xy=(best_alpha, best_top1),
        xytext=(0.55, 88.5),
        fontsize=10,
        arrowprops=dict(arrowstyle="->", color=COLOR_HIGHLIGHT, lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", fc="#fff7e6", ec=COLOR_HIGHLIGHT, lw=0.8),
    )

    ax1.set_xlabel(r"向量检索权重 $\alpha$（BM25 权重为 $1-\alpha$）", fontsize=11)
    ax1.set_ylabel("Top-1 命中率（%）", color=COLOR_PRIMARY, fontsize=11)
    ax2.set_ylabel("MRR", color=COLOR_SECONDARY, fontsize=11)
    ax1.tick_params(axis="y", colors=COLOR_PRIMARY)
    ax2.tick_params(axis="y", colors=COLOR_SECONDARY)
    ax1.set_ylim(75, 92)
    ax2.set_ylim(0.83, 0.93)
    ax1.set_xticks(alphas)
    ax1.set_xticklabels([f"{a:.2f}" for a in alphas], rotation=30, ha="right", fontsize=9)

    fig.legend(
        handles=[line1, line2],
        loc="lower right", bbox_to_anchor=(0.93, 0.20),
        frameon=True, framealpha=0.9, fontsize=10,
    )

    out = FIG_DIR / "eval_5_1_rag_weight_sweep.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 图 5-2  通路 B 语义桥接四档对比（多指标分组柱状图）
# ---------------------------------------------------------------------------

def fig_5_2_bridge_ablation() -> Path:
    """对应论文 5.4 节，数据源 tab:bridge-ablation。"""
    metrics = [
        "覆盖率",
        "分级 ID 准确率",
        "must_cite 全中",
        "citation 真实性",
    ]
    # 顺序：off / rule_only / rule_plus_rag / llm_baseline
    data = {
        "off":            [0.0,   5.6,   0.0,   0.0],
        "rule_only":      [100.0, 100.0, 0.0,   0.0],
        "rule_plus_rag":  [100.0, 100.0, 100.0, 100.0],
        "llm_baseline":   [74.6,  5.6,   25.4,  72.0],
    }
    colors = ["#bdbdbd", "#9ecae1", COLOR_PRIMARY, COLOR_SECONDARY]

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = list(range(len(metrics)))
    width = 0.20

    for i, (mode, vals) in enumerate(data.items()):
        offsets = [xi + (i - 1.5) * width for xi in x]
        bars = ax.bar(offsets, vals, width=width, color=colors[i], edgecolor="black",
                      linewidth=0.6, label=mode)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.2,
                    f"{v:.1f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel("准确率 / 命中率（%）", fontsize=11)
    ax.set_ylim(0, 118)
    ax.legend(loc="upper center", ncol=4, frameon=True, fontsize=9, bbox_to_anchor=(0.5, 1.10))

    out = FIG_DIR / "eval_5_2_bridge_ablation.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 图 5-3  代码执行三档对比（数值准确率 + 代码生成率/可执行率）
# ---------------------------------------------------------------------------

def fig_5_3_code_overall() -> Path:
    """对应论文 5.5 节，数据源 tab:code-eval-overall。"""
    modes = ["oracle", "llm_direct", "llm_with_code"]
    accuracy = [100.0, 66.7, 88.9]
    code_gen = [None, None, 94.4]
    code_run = [None, None, 94.4]

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    width = 0.25
    x = list(range(len(modes)))

    bars1 = ax.bar(
        [xi - width for xi in x], accuracy, width=width,
        color=COLOR_PRIMARY, edgecolor="black", linewidth=0.6,
        label="数值准确率",
    )
    # 后两档独有的代码生成率/可执行率
    bars2 = ax.bar(
        [x[2]], [code_gen[2]], width=width,
        color="#9ecae1", edgecolor="black", linewidth=0.6,
        label="代码生成率",
    )
    bars3 = ax.bar(
        [x[2] + width], [code_run[2]], width=width,
        color="#c6dbef", edgecolor="black", linewidth=0.6,
        label="代码可执行率",
    )

    for bars in (bars1, bars2, bars3):
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, v + 1.2,
                    f"{v:.1f}", ha="center", va="bottom", fontsize=9)

    # 标注三档差距
    ax.annotate(
        "+22.2 pp",
        xy=(2 - width, 88.9), xytext=(1.2, 75),
        fontsize=10, color=COLOR_HIGHLIGHT,
        arrowprops=dict(arrowstyle="->", color=COLOR_HIGHLIGHT, lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", fc="#fff7e6",
                  ec=COLOR_HIGHLIGHT, lw=0.8),
    )

    ax.set_xticks(x)
    ax.set_xticklabels(modes, fontsize=10)
    ax.set_ylabel("准确率 / 通过率（%）", fontsize=11)
    ax.set_ylim(0, 118)
    ax.legend(loc="upper center", ncol=3, frameon=True, fontsize=9,
              bbox_to_anchor=(0.5, 1.10))

    out = FIG_DIR / "eval_5_3_code_overall.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 图 5-4  代码执行按用例类别拆分（6 类 × 双档）
# ---------------------------------------------------------------------------

def fig_5_4_code_by_category() -> Path:
    """对应论文 5.5 节，数据源 tab:code-eval-category。"""
    categories = [
        "极值\nextreme",
        "计数\ncount",
        "平均\naverage",
        "求和\nsum",
        "排序\nsort",
        "差值\ndiff",
    ]
    direct = [0.0, 50.0, 80.0, 100.0, 100.0, 75.0]
    with_code = [66.7, 100.0, 100.0, 100.0, 100.0, 75.0]
    n_cases = [3, 2, 5, 2, 2, 4]

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = list(range(len(categories)))
    width = 0.36

    bars_direct = ax.bar(
        [xi - width / 2 for xi in x], direct, width=width,
        color=COLOR_NEUTRAL, edgecolor="black", linewidth=0.6,
        label="llm_direct",
    )
    bars_code = ax.bar(
        [xi + width / 2 for xi in x], with_code, width=width,
        color=COLOR_PRIMARY, edgecolor="black", linewidth=0.6,
        label="llm_with_code",
    )

    for bars in (bars_direct, bars_code):
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, v + 1.2,
                    f"{v:.0f}", ha="center", va="bottom", fontsize=8)

    # 类别下方加上用例数
    for xi, n in zip(x, n_cases):
        ax.text(xi, -10, f"n = {n}", ha="center", va="top", fontsize=8,
                color=COLOR_NEUTRAL)

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylabel("数值准确率（%）", fontsize=11)
    ax.set_ylim(-15, 115)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.legend(loc="lower right", frameon=True, fontsize=10)

    out = FIG_DIR / "eval_5_4_code_by_category.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 图 5-5  端到端 6 类场景双档对比
# ---------------------------------------------------------------------------

def fig_5_5_e2e_by_category() -> Path:
    """对应论文 5.6 节，数据源 tab:e2e-by-category。"""
    categories_zh = [
        "decision\n_support",
        "warning\n_extreme",
        "simple\n_query",
        "extreme\n_search",
        "trend\n_analysis",
        "multi\n_compare",
    ]
    ablated = [50.0, 50.0, 80.0, 80.0, 80.0, 100.0]
    full =    [100.0, 75.0, 80.0, 80.0, 80.0, 100.0]
    diff =    [50.0, 25.0, 0.0, 0.0, 0.0, 0.0]
    n_cases = [6, 4, 5, 5, 5, 5]

    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    x = list(range(len(categories_zh)))
    width = 0.36

    bars_a = ax.bar(
        [xi - width / 2 for xi in x], ablated, width=width,
        color=COLOR_NEUTRAL, edgecolor="black", linewidth=0.6,
        label="ablated（无 RAG）",
    )
    bars_f = ax.bar(
        [xi + width / 2 for xi in x], full, width=width,
        color=COLOR_PRIMARY, edgecolor="black", linewidth=0.6,
        label="full（含双通路 RAG）",
    )

    for bars in (bars_a, bars_f):
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5,
                    f"{v:.0f}", ha="center", va="bottom", fontsize=8)

    # 顶部标注差距
    for xi, d in zip(x, diff):
        if d > 0:
            ax.text(xi, 117, f"+{d:.0f} pp", ha="center", va="center",
                    fontsize=9, color=COLOR_HIGHLIGHT,
                    bbox=dict(boxstyle="round,pad=0.2",
                              fc="#fff7e6", ec=COLOR_HIGHLIGHT, lw=0.6))
        else:
            ax.text(xi, 117, "持平", ha="center", va="center",
                    fontsize=9, color=COLOR_NEUTRAL)

    # 类别下方加上用例数
    for xi, n in zip(x, n_cases):
        ax.text(xi, -8, f"n = {n}", ha="center", va="top", fontsize=8,
                color=COLOR_NEUTRAL)

    ax.set_xticks(x)
    ax.set_xticklabels(categories_zh, fontsize=9)
    ax.set_ylabel("端到端通过率（%）", fontsize=11)
    ax.set_ylim(-12, 130)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.legend(loc="upper center", ncol=2, frameon=True, fontsize=10,
              bbox_to_anchor=(0.5, 1.10))

    out = FIG_DIR / "eval_5_5_e2e_by_category.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"matplotlib: {mpl.__version__}")
    print(f"输出目录:   {FIG_DIR}")
    print()

    generators = [
        ("图 5-1 α 权重扫描", fig_5_1_rag_weight_sweep),
        ("图 5-2 通路 B 桥接四档", fig_5_2_bridge_ablation),
        ("图 5-3 代码执行三档", fig_5_3_code_overall),
        ("图 5-4 代码执行按类别", fig_5_4_code_by_category),
        ("图 5-5 端到端 6 类双档", fig_5_5_e2e_by_category),
    ]

    for name, fn in generators:
        out = fn()
        size_kb = out.stat().st_size / 1024
        print(f"  [OK] {name:<22} -> {out.name}  ({size_kb:.1f} KB)")

    print()
    print(f"共生成 {len(generators)} 张图。")


if __name__ == "__main__":
    main()
