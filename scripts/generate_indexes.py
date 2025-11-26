#!/usr/bin/env python3
"""
生成所有README索引文件：
- 年度摘要 (data/YYYY/README.md)
- 主索引 (data/README.md)
"""

import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def extract_cve_year(cve_id):
    """从CVE编号提取年份"""
    match = re.match(r'CVE-(\d{4})-\d+', cve_id)
    if match:
        return match.group(1)
    return None


def generate_yearly_readmes():
    """生成每年的README摘要"""

    logger.info("\n📝 生成年度README...")

    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 获取所有CVE年份
    cursor.execute("""
        SELECT DISTINCT cve_id
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
    """)

    years_set = set()
    for (cve_id,) in cursor.fetchall():
        year = extract_cve_year(cve_id)
        if year:
            years_set.add(year)

    years = sorted(years_set, reverse=True)
    generated_count = 0

    for year in years:
        # 查询该年数据
        cursor.execute(f"""
            SELECT
                cve_id,
                name,
                url,
                json_extract(gpt_analysis, '$.name') as full_name,
                json_extract(gpt_analysis, '$.type') as type,
                json_extract(gpt_analysis, '$.risk') as risk,
                json_extract(gpt_analysis, '$.poc_available') as poc_available,
                json_extract(gpt_analysis, '$.poison') as poison,
                created_at
            FROM repositories
            WHERE cve_id LIKE 'CVE-{year}-%'
              AND gpt_analysis IS NOT NULL
            ORDER BY cve_id DESC
        """)

        vulns = cursor.fetchall()
        count = len(vulns)

        if count == 0:
            continue

        # 统计分析
        type_counter = defaultdict(int)
        critical_count = 0
        poison_high_count = 0

        for vuln in vulns:
            vuln_type = vuln[4] or '未知'
            type_counter[vuln_type] += 1

            risk = vuln[5] or ''
            if '高危' in risk or 'Critical' in risk or '远程代码执行' in risk or 'RCE' in risk.upper():
                critical_count += 1

            poison = vuln[7] or '0%'
            try:
                poison_pct = int(poison.replace('%', ''))
                if poison_pct >= 70:
                    poison_high_count += 1
            except:
                pass

        # 生成README
        readme_path = Path(f'data/{year}/README.md')
        readme_path.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# {year}年CVE漏洞情报汇总

> 📅 CVE年份: **{year}**
> 📊 漏洞总数: **{count}** 个
> 🔥 高危漏洞: **{critical_count}** 个 ({critical_count/count*100:.1f}%)
> ⚠️ 高投毒风险: **{poison_high_count}** 个

---

## 📊 漏洞类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
"""

        # 排序并生成表格
        for vuln_type, type_count in sorted(type_counter.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (type_count / count * 100) if count > 0 else 0
            content += f"| {vuln_type} | {type_count} | {percentage:.1f}% |\n"

        content += f"""
---

## 🔍 漏洞详情列表

"""

        # 生成详细列表
        for idx, vuln in enumerate(vulns[:500], 1):  # 限制500个
            cve_id, repo_name, repo_url, full_name, vuln_type, risk, poc_available, poison, created_at = vuln

            # 计算风险标签
            risk_badge = ""
            if critical_count and ('高危' in (risk or '') or 'RCE' in (risk or '').upper()):
                risk_badge = " 🔴"

            # 计算投毒标签
            poison_badge = ""
            try:
                poison_pct = int((poison or '0%').replace('%', ''))
                if poison_pct >= 70:
                    poison_badge = " ⚠️"
            except:
                pass

            # 从URL提取repo_full_name用于文件名
            repo_full_name = repo_url.replace('https://github.com/', '').replace('/', '_')
            filepath = f"{cve_id}-{repo_full_name}.md"

            content += f"""### [{cve_id}]({filepath}){risk_badge}{poison_badge}

**名称:** {full_name or cve_id}
**类型:** {vuln_type or '未知'} | **POC:** {poc_available or '未知'} | **投毒风险:** {poison or '未知'}
**仓库:** [{repo_name}]({repo_url})

"""

        content += """
---

## 📖 说明

- 🔴 标记为高危漏洞
- ⚠️ 标记为高投毒风险（≥70%）
- 漏洞按CVE编号降序排列
- 点击CVE编号查看详细分析报告

"""

        readme_path.write_text(content, encoding='utf-8')
        generated_count += 1
        logger.info(f"  ✓ {year}/README.md ({count} 个漏洞)")

    db.close()
    logger.info(f"✅ 生成 {generated_count} 个年度README")

    return generated_count


def generate_main_readme():
    """生成主README"""

    logger.info("\n📝 生成主README...")

    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 统计总数
    cursor.execute("""
        SELECT COUNT(DISTINCT cve_id)
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
    """)
    total_cves = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT github_id)
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
    """)
    total_repos = cursor.fetchone()[0]

    # 按CVE年份统计
    cursor.execute("""
        SELECT cve_id
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
    """)

    year_counter = defaultdict(int)
    for (cve_id,) in cursor.fetchall():
        year = extract_cve_year(cve_id)
        if year:
            year_counter[year] += 1

    # 获取本周新增（按创建时间）
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute(f"""
        SELECT
            cve_id,
            url,
            json_extract(gpt_analysis, '$.name') as full_name,
            json_extract(gpt_analysis, '$.type') as type,
            json_extract(gpt_analysis, '$.risk') as risk,
            created_at
        FROM repositories
        WHERE created_at >= '{week_ago}'
          AND gpt_analysis IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """)

    weekly_vulns = cursor.fetchall()

    # 生成主README
    content = f"""# VulnWatchdog - 漏洞情报库

> 🤖 自动化CVE漏洞监控与分析系统
> 📅 最后更新: {datetime.now().strftime('%Y-%m-%d')}
> 📊 已收录: **{total_cves}** 个CVE | **{total_repos}** 个POC仓库

---

## 🚀 快速开始

### 浏览方式
- 📅 **按年份浏览** - 查看特定年份的CVE漏洞
"""

    # 添加年份链接
    for year in sorted(year_counter.keys(), reverse=True)[:5]:
        content += f"  - [{year}年]({year}/README.md) ({year_counter[year]} 个)\n"

    content += f"""- 🔍 **按CVE编号查找** - 直接访问 `by-cve/CVE-XXXX-XXXXX.md`
- 📰 **订阅更新** - 见下方订阅方式

### 订阅方式
- 🔔 **GitHub Watch** - 点击右上角 ⭐ Star 和 👁️ Watch 接收更新通知
- 📡 **RSS订阅** - 添加到RSS阅读器:
  ```
  https://github.com/VulnWatchdog/VulnWatchdog/commits.atom
  ```
- 💬 **飞书通知** - Fork后配置Webhook接收实时推送

---

## 📊 数据统计

### 年度分布

| 年份 | 漏洞数量 | 占比 |
|------|---------|------|
"""

    # 生成年度统计表
    for year in sorted(year_counter.keys(), reverse=True):
        count = year_counter[year]
        percentage = (count / total_repos * 100) if total_repos > 0 else 0
        content += f"| [{year}]({year}/README.md) | {count} | {percentage:.1f}% |\n"

    content += """
---

## 🚨 本周新增

"""

    # 添加本周新增
    if weekly_vulns:
        for vuln in weekly_vulns:
            cve_id, repo_url, full_name, vuln_type, risk, created_at = vuln

            # 风险标记
            risk_badge = ""
            if risk and ('高危' in risk or 'RCE' in risk.upper() or 'Critical' in risk):
                risk_badge = " 🔴"

            # 提取CVE年份
            cve_year = extract_cve_year(cve_id)
            if not cve_year:
                continue

            # 构建文件路径
            repo_full_name = repo_url.replace('https://github.com/', '').replace('/', '_')
            filepath = f"{cve_year}/{cve_id}-{repo_full_name}.md"

            # 格式化日期
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except:
                created_date = created_at[:10]

            content += f"""### [{cve_id}]({filepath}){risk_badge}

**名称:** {full_name or cve_id}
**类型:** {vuln_type or '未知'} | **发现:** {created_date}
**POC:** [{repo_url.split('/')[-1]}]({repo_url})

"""
    else:
        content += "_本周暂无新增漏洞_\n\n"

    content += """---

## 📁 目录结构

```
data/
├── README.md          # 本文件
├── 2025/              # 2025年CVE漏洞
│   ├── README.md     # 年度摘要
│   └── CVE-*.md      # 漏洞报告
├── 2024/              # 2024年CVE漏洞
│   └── ...
└── by-cve/            # CVE编号索引（符号链接）
    ├── CVE-2025-XXXXX.md
    └── ...
```

---

## 🔍 使用指南

### 查找漏洞
1. **特定年份:** 访问对应年份目录 (如 `2024/`)
2. **指定CVE:** 访问 `by-cve/CVE-XXXX-XXXXX.md`
3. **搜索关键词:** 使用GitHub搜索功能

### 报告格式
每个报告包含：
- ✅ 漏洞类型、影响应用、危害等级
- ✅ POC可用性、投毒风险评估
- ✅ 详细分析、利用条件
- ✅ 相关链接（POC仓库、NVD）

---

## 🤝 贡献

欢迎通过以下方式参与：
- 🐛 [报告问题](../../issues) - GPT误判、投毒误报
- 💡 [提出建议](../../discussions) - 功能改进
- ⭐ **Star本项目** - 支持项目发展

---

## 📜 许可证

MIT License

---

## 致谢

- 感谢 [Poc-Monitor](https://github.com/sari3l/Poc-Monitor) 项目提供的思路
- 感谢 [SearXNG](https://github.com/searxng/searxng) 项目提供的搜索引擎

---

*🤖 本仓库由 VulnWatchdog 自动维护 | 最后生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    readme_path = Path('data/README.md')
    readme_path.write_text(content, encoding='utf-8')

    db.close()
    logger.info("✅ 生成主README")


if __name__ == '__main__':
    logger.info("🚀 开始生成所有索引...")

    # 生成年度README
    yearly_count = generate_yearly_readmes()

    # 生成主README
    generate_main_readme()

    logger.info(f"\n✅ 索引生成完成! 共{yearly_count + 1}个文件")
