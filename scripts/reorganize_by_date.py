#!/usr/bin/env python3
"""
重组目录结构：按发现时间（created_at）分类到 YYYY/MM/ 目录
"""

import os
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def reorganize_reports():
    """重组所有报告文件"""

    logger.info("🚀 开始重组目录结构...\n")

    # 连接数据库
    db = sqlite3.connect('vulns.db')
    cursor = db.cursor()

    # 查询所有仓库及其创建时间
    cursor.execute("""
        SELECT
            cve_id,
            name,
            url,
            created_at,
            gpt_analysis
        FROM repositories
        WHERE gpt_analysis IS NOT NULL
        ORDER BY created_at DESC
    """)

    stats = defaultdict(int)
    moved_count = 0
    skipped_count = 0

    for row in cursor.fetchall():
        cve_id, repo_name, repo_url, created_at, gpt_analysis = row

        # 解析时间
        try:
            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"⚠️  时间格式异常: {cve_id}, 跳过 ({e})")
            skipped_count += 1
            continue

        # 目标目录: data/YYYY/MM/
        year = created_date.strftime('%Y')
        month = created_date.strftime('%m')
        target_dir = Path(f'data/{year}/{month}')
        target_dir.mkdir(parents=True, exist_ok=True)

        # 原文件名（从repo_url提取）
        repo_full_name = repo_url.replace('https://github.com/', '').replace('/', '_')
        old_filename = f"data/markdown/{cve_id}-{repo_full_name}.md"
        new_filename = target_dir / f"{cve_id}-{repo_full_name}.md"

        # 移动文件
        if os.path.exists(old_filename):
            # 如果目标文件已存在，跳过
            if new_filename.exists():
                logger.debug(f"⏭️  已存在: {new_filename}")
                stats[f"{year}/{month}"] += 1
                skipped_count += 1
                continue

            shutil.move(old_filename, new_filename)
            moved_count += 1
            stats[f"{year}/{month}"] += 1
            logger.info(f"✓ 移动: {cve_id} -> {year}/{month}/")
        else:
            logger.debug(f"⚠️  文件不存在: {old_filename}")
            skipped_count += 1

    logger.info(f"\n✅ 文件移动完成!")
    logger.info(f"   新移动: {moved_count} 个")
    logger.info(f"   跳过: {skipped_count} 个")
    logger.info(f"\n📊 分布统计:")
    for period, count in sorted(stats.items(), reverse=True)[:10]:
        logger.info(f"   {period}: {count} 个漏洞")

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
