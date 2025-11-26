#!/usr/bin/env python3
"""
重组目录结构：按CVE披露年份分类到 YYYY/ 目录
"""

import os
import re
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def extract_cve_year(cve_id):
    """从CVE编号提取年份"""
    match = re.match(r'CVE-(\d{4})-\d+', cve_id)
    if match:
        return match.group(1)
    return None

def reorganize_reports():
    """重组所有报告文件 - 按CVE年份"""

    logger.info("🚀 开始重组目录结构（按CVE年份）...\n")

    # 连接数据库
    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 查询所有仓库
    cursor.execute("""
        SELECT
            cve_id,
            name,
            url,
            gpt_analysis
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
        ORDER BY cve_id DESC
    """)

    stats = defaultdict(int)
    moved_count = 0
    skipped_count = 0
    error_count = 0

    for row in cursor.fetchall():
        cve_id, repo_name, repo_url, gpt_analysis = row

        # 从CVE编号提取年份
        cve_year = extract_cve_year(cve_id)
        if not cve_year:
            logger.warning(f"⚠️  无法解析CVE年份: {cve_id}")
            error_count += 1
            continue

        # 目标目录: data/YYYY/
        target_dir = Path(f'data/{cve_year}')
        target_dir.mkdir(parents=True, exist_ok=True)

        # 原文件名（从repo_url提取）
        repo_full_name = repo_url.replace('https://github.com/', '').replace('/', '_')

        # 查找现有文件（可能在不同位置）
        old_locations = [
            f"data/markdown/{cve_id}-{repo_full_name}.md",
        ]

        # 也检查旧的2025目录结构
        for year_dir in Path('data').glob('20*'):
            if year_dir.is_dir() and year_dir.name.isdigit():
                for month_dir in year_dir.glob('*'):
                    if month_dir.is_dir():
                        old_locations.append(str(month_dir / f"{cve_id}-{repo_full_name}.md"))

        new_filename = target_dir / f"{cve_id}-{repo_full_name}.md"

        # 查找并移动文件
        file_found = False
        for old_filename in old_locations:
            if os.path.exists(old_filename):
                file_found = True

                # 如果目标文件已存在且相同，跳过
                if new_filename.exists() and os.path.samefile(old_filename, new_filename):
                    stats[cve_year] += 1
                    skipped_count += 1
                    break

                # 如果目标位置有不同文件，先删除旧的
                if new_filename.exists():
                    new_filename.unlink()

                shutil.move(old_filename, new_filename)
                moved_count += 1
                stats[cve_year] += 1
                logger.info(f"✓ 移动: {cve_id} -> {cve_year}/")
                break

        if not file_found:
            logger.debug(f"⚠️  文件不存在: {cve_id}-{repo_full_name}.md")
            skipped_count += 1

    logger.info(f"\n✅ 文件移动完成!")
    logger.info(f"   移动: {moved_count} 个")
    logger.info(f"   跳过: {skipped_count} 个")
    logger.info(f"   错误: {error_count} 个")
    logger.info(f"\n📊 CVE年份分布:")
    for year, count in sorted(stats.items(), reverse=True):
        logger.info(f"   {year}: {count} 个漏洞")

    db.close()

    return stats

def create_cve_index():
    """创建CVE编号反向索引（符号链接）"""

    logger.info("\n🔗 创建CVE索引...")

    index_dir = Path('data/by-cve')
    index_dir.mkdir(exist_ok=True)

    created_count = 0

    # 遍历所有报告文件
    for md_file in Path('data').rglob('*.md'):
        if 'by-cve' in str(md_file) or md_file.name == 'README.md':
            continue

        # 提取CVE编号
        filename = md_file.name
        if filename.startswith('CVE-'):
            parts = filename.split('-')
            if len(parts) >= 3:
                cve_id = f"{parts[0]}-{parts[1]}-{parts[2]}"

                link_path = index_dir / f"{cve_id}.md"
                relative_target = os.path.relpath(md_file, index_dir)

                # 如果已存在，删除旧链接
                if link_path.exists() or link_path.is_symlink():
                    link_path.unlink()

                try:
                    os.symlink(relative_target, link_path)
                    created_count += 1
                except Exception as e:
                    logger.warning(f"⚠️  创建符号链接失败: {cve_id} ({e})")

    logger.info(f"✓ 创建索引: {created_count} 个CVE")

if __name__ == '__main__':
    stats = reorganize_reports()
    create_cve_index()
    logger.info("\n✅ 重组完成!")
