#!/usr/bin/env python3
"""
数据迁移脚本: 为现有仓库记录填充 latest_commit_sha
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import get_db, Repository
from libs.utils import get_latest_commit_sha

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_commit_sha():
    """
    为所有缺少commit SHA的仓库记录填充SHA值
    """
    logger.info("🚀 开始迁移commit SHA数据...")

    engine = get_db()

    # 查询所有缺少commit SHA的记录
    repos = engine.query(Repository).filter(
        Repository.latest_commit_sha.is_(None)
    ).all()

    total = len(repos)
    logger.info(f"📊 找到 {total} 条需要迁移的记录")

    if total == 0:
        logger.info("✅ 所有记录已有commit SHA,无需迁移")
        return

    success_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, repo in enumerate(repos, 1):
        try:
            logger.info(f"[{idx}/{total}] 处理仓库: {repo.url}")

            # 获取最新commit SHA
            latest_sha = get_latest_commit_sha(repo.url)

            if latest_sha:
                repo.latest_commit_sha = latest_sha
                engine.commit()
                success_count += 1
                logger.info(f"  ✓ 填充SHA成功: {latest_sha[:8]}...")
            else:
                failed_count += 1
                logger.warning(f"  ✗ 获取SHA失败")

            # 避免GitHub API限流,每10个请求暂停1秒
            if idx % 10 == 0:
                logger.info(f"  💤 暂停1秒 (已处理 {idx}/{total})...")
                time.sleep(1)

        except Exception as e:
            logger.error(f"  ✗ 处理异常: {str(e)}")
            failed_count += 1
            engine.rollback()
            continue

    logger.info("\n" + "="*60)
    logger.info("📊 迁移完成统计:")
    logger.info(f"  总计:   {total} 条")
    logger.info(f"  成功:   {success_count} 条")
    logger.info(f"  失败:   {failed_count} 条")
    logger.info(f"  成功率: {success_count/total*100:.1f}%")
    logger.info("="*60)

    # 验证迁移结果
    remaining = engine.query(Repository).filter(
        Repository.latest_commit_sha.is_(None)
    ).count()

    logger.info(f"\n✅ 验证: 剩余 {remaining} 条记录未填充SHA")

    engine.close()


if __name__ == '__main__':
    try:
        migrate_commit_sha()
    except KeyboardInterrupt:
        logger.warning("\n⚠️  用户中断迁移")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ 迁移失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
