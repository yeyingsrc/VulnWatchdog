#!/usr/bin/env python3
"""
生成所有README索引文件：
- 月度摘要 (data/YYYY/MM/README.md)
- 年度摘要 (data/YYYY/README.md)
- 主索引 (data/README.md)
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def generate_monthly_readmes():
    """生成每月的README摘要"""

    logger.info("\n📝 生成月度README...")

    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 获取所有年月
    cursor.execute("""
        SELECT DISTINCT
            strftime('%Y', created_at) as year,
            strftime('%m', created_at) as month
        FROM repositories
        WHERE created_at IS NOT NULL
          AND gpt_analysis IS NOT NULL
        ORDER BY year DESC, month DESC
    """)

    periods = cursor.fetchall()
    generated_count = 0

    for year, month in periods:
        if not year or not month:
            continue

        # 查询该月数据
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
            WHERE strftime('%Y', created_at) = '{year}'
              AND strftime('%m', created_at) = '{month}'
              AND gpt_analysis IS NOT NULL
            ORDER BY created_at DESC
        """)

        vulns = cursor.fetchall()
        count = len(vulns)

        # 统计分析
        type_counter = defaultdict(int)
        critical_count = 0

        for vuln in vulns:
            vuln_type = vuln[4] or '未知'
            type_counter[vuln_type] += 1

            risk = vuln[5] or ''
            if '高危' in risk or 'Critical' in risk or 'critical' in risk.lower():
                critical_count += 1

        # 生成README
        readme_path = Path(f'data/{year}/{month}/README.md')
        readme_path.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# {year}年{month}月漏洞情报汇总

> 📅 统计周期: {year}-{month}-01 ~ {year}-{month}-30
> 📊 新增漏洞: **{count}** 个
> 🔥 高危漏洞: **{critical_count}** 个

---

## 📊 漏洞类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
"""

        # 排序并生成表格
        for vuln_type, type_count in sorted(type_counter.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (type_count / count * 100) if count > 0 else 0
            content += f"| {vuln_type} | {type_count} | {percentage:.1f}% |\n"

        content += "\n---\n\n## 📋 详细列表\n\n"

        # 漏洞列表
        for vuln in vulns:
            cve_id, name, url, full_name, vuln_type, risk, poc_available, poison, created_at = vuln

            # 提取文件名
            repo_name = url.replace('https://github.com/', '').replace('/', '_')
            filename = f"{cve_id}-{repo_name}.md"

            # 格式化日期
            date = created_at[:10] if created_at else 'N/A'

            # 风险标记
            risk_badge = ""
            if risk and ('高危' in risk or 'Critical' in risk or 'critical' in risk.lower()):
                risk_badge = "🔴"
            elif risk and ('中危' in risk or 'High' in risk or 'medium' in risk.lower()):
                risk_badge = "🟡"

            # POC标记
            poc_badge = "✅" if poc_available == '是' else ""

            # 投毒风险
            poison_str = poison if poison else "N/A"

            content += f"### [{cve_id}]({filename}) {risk_badge} {poc_badge}\n\n"
            content += f"**名称:** {full_name or name or cve_id}  \n"
            content += f"**类型:** {vuln_type or '未知'}  \n"
            content += f"**风险:** {risk or '未评估'}  \n"
            content += f"**投毒风险:** {poison_str}  \n"
            content += f"**发现时间:** {date}  \n"
            content += f"**POC仓库:** [{url.split('/')[-1]}]({url})  \n\n"
            content += "---\n\n"

        content += f"""
## 🔍 快速查找

- [按CVE编号查找](../../by-cve/)
- [返回{year}年总览](../README.md)
- [返回总索引](../../README.md)

---

*本文档由 VulnWatchdog 自动生成 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

        # 写入文件
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

        generated_count += 1
        logger.info(f"✓ {year}/{month} - {count}个漏洞")

    db.close()
    logger.info(f"✅ 生成月度摘要: {generated_count} 个")


def generate_yearly_readmes():
    """生成每年的README摘要"""

    logger.info("\n📝 生成年度README...")

    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 获取所有年份
    cursor.execute("""
        SELECT DISTINCT strftime('%Y', created_at) as year
        FROM repositories
        WHERE created_at IS NOT NULL
          AND gpt_analysis IS NOT NULL
        ORDER BY year DESC
    """)

    years = [row[0] for row in cursor.fetchall()]
    generated_count = 0

    for year in years:
        if not year:
            continue

        # 查询该年数据
        cursor.execute(f"""
            SELECT
                strftime('%m', created_at) as month,
                COUNT(*) as count,
                SUM(CASE
                    WHEN json_extract(gpt_analysis, '$.risk') LIKE '%高危%'
                      OR json_extract(gpt_analysis, '$.risk') LIKE '%Critical%'
                      OR json_extract(gpt_analysis, '$.risk') LIKE '%critical%'
                    THEN 1 ELSE 0 END) as critical_count
            FROM repositories
            WHERE strftime('%Y', created_at) = '{year}'
              AND gpt_analysis IS NOT NULL
            GROUP BY month
            ORDER BY month
        """)

        monthly_stats = cursor.fetchall()
        total_count = sum(row[1] for row in monthly_stats)
        total_critical = sum(row[2] for row in monthly_stats)

        # 生成README
        readme_path = Path(f'data/{year}/README.md')
        readme_path.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# {year}年度漏洞情报汇总

> 📅 统计周期: {year}-01-01 ~ {year}-12-31
> 📊 年度新增: **{total_count}** 个漏洞
> 🔥 高危漏洞: **{total_critical}** 个

---

## 📊 月度统计

| 月份 | 新增漏洞 | 高危漏洞 | 环比 |
|------|---------|---------|------|
"""

        prev_count = 0
        for month, count, critical in monthly_stats:
            change = ""
            if prev_count > 0:
                diff = count - prev_count
                if diff > 0:
                    change = f"↑ +{diff}"
                elif diff < 0:
                    change = f"↓ {diff}"
                else:
                    change = "→"
            prev_count = count

            month_name = f"{year}-{month}"
            content += f"| [{month_name}]({month}/README.md) | {count} | {critical} | {change} |\n"

        content += f"""

---

## 📁 月度详情

"""

        for month, count, critical in monthly_stats:
            content += f"- [{year}-{month}]({month}/README.md) - {count}个漏洞 ({critical}个高危)\n"

        content += f"""

## 🔍 快速导航

- [按CVE编号查找](../by-cve/)
- [返回总索引](../README.md)

---

*本文档由 VulnWatchdog 自动生成 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

        generated_count += 1
        logger.info(f"✓ {year}年 - {total_count}个漏洞")

    db.close()
    logger.info(f"✅ 生成年度摘要: {generated_count} 个")


def generate_main_readme():
    """生成主README索引"""

    logger.info("\n📝 生成主索引README...")

    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 统计总数
    cursor.execute("SELECT COUNT(DISTINCT cve_id) FROM repositories WHERE gpt_analysis IS NOT NULL")
    total_cve = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM repositories WHERE gpt_analysis IS NOT NULL")
    total_repos = cursor.fetchone()[0]

    # 最近更新
    cursor.execute("""
        SELECT created_at
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    last_update = result[0][:10] if result else 'N/A'

    # 年度统计
    cursor.execute("""
        SELECT
            strftime('%Y', created_at) as year,
            COUNT(*) as count
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
        GROUP BY year
        ORDER BY year DESC
    """)

    yearly_stats = cursor.fetchall()

    # 本周新增
    cursor.execute("""
        SELECT
            cve_id,
            name,
            url,
            json_extract(gpt_analysis, '$.name') as full_name,
            json_extract(gpt_analysis, '$.type') as type,
            json_extract(gpt_analysis, '$.risk') as risk,
            created_at
        FROM repositories
        WHERE created_at >= date('now', '-7 days')
          AND gpt_analysis IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """)

    weekly_new = cursor.fetchall()

    # 生成README
    content = f"""# VulnWatchdog - 漏洞情报库

> 🤖 自动化CVE漏洞监控与分析系统
> 📅 最后更新: {last_update}
> 📊 已收录: **{total_cve}** 个CVE | **{total_repos}** 个POC仓库

---

## 🚀 快速开始

### 浏览方式
- 📅 **按时间浏览** - 查看最近发现的漏洞
  - [2025年](2025/README.md) | [2024年](2024/README.md) | [2023年](2023/README.md)
- 🔍 **按CVE编号查找** - 直接访问 `by-cve/CVE-XXXX-XXXXX.md`
- 📰 **订阅更新** - 见下方订阅方式

### 订阅方式
- 🔔 **GitHub Watch** - 点击右上角 ⭐ Star 和 👁️ Watch 接收更新通知
- 📡 **RSS订阅** - 添加到RSS阅读器:
  ```
  https://github.com/{Path.cwd().name}/VulnWatchdog/commits.atom
  ```
- 💬 **飞书通知** - Fork后配置Webhook接收实时推送

---

## 📊 数据统计

### 年度分布

| 年份 | 漏洞数量 | 占比 |
|------|---------|------|
"""

    for year, count in yearly_stats:
        if year:
            percentage = (count / total_repos * 100) if total_repos > 0 else 0
            content += f"| [{year}]({year}/README.md) | {count} | {percentage:.1f}% |\n"

    content += "\n---\n\n## 🚨 本周新增\n\n"

    if weekly_new:
        for vuln in weekly_new:
            cve_id, name, url, full_name, vuln_type, risk, created_at = vuln
            date = created_at[:10] if created_at else 'N/A'

            # 提取年月
            if created_at:
                year, month = created_at.split('-')[0:2]
                repo_name = url.replace('https://github.com/', '').replace('/', '_')
                file_path = f"{year}/{month}/{cve_id}-{repo_name}.md"

                risk_badge = "🔴" if (risk and ('高危' in risk or 'Critical' in risk)) else "🟡"

                content += f"### [{cve_id}]({file_path}) {risk_badge}\n\n"
                content += f"**名称:** {full_name or name or cve_id}  \n"
                content += f"**类型:** {vuln_type or '未知'} | **发现:** {date}  \n"
                content += f"**POC:** [{url.split('/')[-1]}]({url})  \n\n"
    else:
        content += "*暂无新增*\n\n"

    content += """---

## 📁 目录结构

```
data/
├── README.md          # 本文件
├── 2025/              # 2025年发现的漏洞
│   ├── 11/           # 11月
│   │   ├── README.md # 月度摘要
│   │   └── CVE-*.md  # 漏洞报告
│   ├── 10/           # 10月
│   └── README.md     # 年度摘要
├── 2024/              # 2024年发现的漏洞
│   └── ...
└── by-cve/            # CVE编号索引（符号链接）
    ├── CVE-2025-XXXXX.md
    └── ...
```

---

## 🔍 使用指南

### 查找漏洞
1. **最近漏洞:** 浏览最新年月目录
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

    with open('data/README.md', 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info("✓ 生成主索引: data/README.md")

    db.close()


if __name__ == '__main__':
    logger.info("🚀 开始生成所有索引...")
    generate_monthly_readmes()
    generate_yearly_readmes()
    generate_main_readme()
    logger.info("\n✅ 所有索引生成完成!")
