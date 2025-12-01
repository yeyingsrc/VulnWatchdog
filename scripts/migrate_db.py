#!/usr/bin/env python3
"""
数据库迁移脚本
用于更新数据库结构，添加缺失的字段
"""

import sqlite3
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_path():
    """从配置中获取数据库路径"""
    db_url = get_config('DB_URL')
    # 从 sqlite:///path 中提取路径
    if db_url.startswith('sqlite:///'):
        return db_url.replace('sqlite:///', '')
    return 'vulns.db'


def check_column_exists(cursor, table_name, column_name):
    """检查表中是否存在指定字段"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_add_latest_commit_sha(conn):
    """添加 latest_commit_sha 字段到 repositories 表"""
    cursor = conn.cursor()

    if check_column_exists(cursor, 'repositories', 'latest_commit_sha'):
        logger.info("✓ latest_commit_sha 字段已存在，跳过")
        return False

    logger.info("添加 latest_commit_sha 字段...")
    cursor.execute("ALTER TABLE repositories ADD COLUMN latest_commit_sha VARCHAR(40);")
    conn.commit()
    logger.info("✓ latest_commit_sha 字段添加成功")
    return True


def verify_schema(conn):
    """验证数据库结构"""
    cursor = conn.cursor()

    logger.info("\n验证数据库结构...")

    # 检查 repositories 表
    cursor.execute("PRAGMA table_info(repositories)")
    columns = cursor.fetchall()

    expected_columns = [
        'id', 'github_id', 'cve_id', 'name', 'description',
        'url', 'repo_data', 'repo_pushed_at', 'latest_commit_sha',
        'action_log', 'gpt_analysis', 'created_at', 'updated_at'
    ]

    actual_columns = [col[1] for col in columns]

    logger.info(f"repositories 表字段: {len(actual_columns)}")
    for col in actual_columns:
        status = "✓" if col in expected_columns else "✗"
        logger.info(f"  {status} {col}")

    missing = set(expected_columns) - set(actual_columns)
    if missing:
        logger.warning(f"缺失字段: {missing}")
        return False

    logger.info("✓ 数据库结构验证通过")
    return True


def get_statistics(conn):
    """获取数据库统计信息"""
    cursor = conn.cursor()

    logger.info("\n数据库统计信息:")

    # 总记录数
    cursor.execute("SELECT COUNT(*) FROM repositories")
    total = cursor.fetchone()[0]
    logger.info(f"  总仓库数: {total:,}")

    # 有 SHA 的记录数
    cursor.execute("SELECT COUNT(*) FROM repositories WHERE latest_commit_sha IS NOT NULL AND latest_commit_sha != ''")
    with_sha = cursor.fetchone()[0]
    logger.info(f"  有 SHA 的仓库: {with_sha:,} ({with_sha*100/total:.1f}%)")

    # CVE 数量
    cursor.execute("SELECT COUNT(DISTINCT cve_id) FROM repositories")
    cve_count = cursor.fetchone()[0]
    logger.info(f"  唯一 CVE 数: {cve_count:,}")

    # 2025年 CVE
    cursor.execute("SELECT COUNT(*) FROM repositories WHERE cve_id LIKE 'CVE-2025-%'")
    cve_2025 = cursor.fetchone()[0]
    logger.info(f"  2025年 CVE: {cve_2025:,}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("数据库迁移脚本")
    logger.info("=" * 60)

    db_path = get_db_path()
    logger.info(f"数据库路径: {db_path}")

    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        sys.exit(1)

    # 备份数据库
    import shutil
    from datetime import datetime

    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"创建备份: {backup_path}")
    shutil.copy2(db_path, backup_path)
    logger.info("✓ 备份完成")

    # 连接数据库
    conn = sqlite3.connect(db_path)

    try:
        # 执行迁移
        logger.info("\n执行数据库迁移...")
        migrations_applied = 0

        if migrate_add_latest_commit_sha(conn):
            migrations_applied += 1

        logger.info(f"\n✓ 应用了 {migrations_applied} 个迁移")

        # 验证结构
        if not verify_schema(conn):
            logger.error("数据库结构验证失败")
            sys.exit(1)

        # 显示统计
        get_statistics(conn)

        logger.info("\n" + "=" * 60)
        logger.info("✓ 数据库迁移完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"迁移失败: {str(e)}")
        logger.info(f"可以从备份恢复: {backup_path}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
