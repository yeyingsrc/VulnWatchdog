# 监控集成到主流程 - 详细设计方案

**功能名称**: 监控系统主流程集成
**优先级**: P0 ⭐⭐⭐⭐⭐
**预计工时**: 2小时
**状态**: 设计阶段

---

## 📋 功能概述

将已开发的监控模块（`libs/monitor.py`）完整集成到 `main.py` 主流程中，实现：
- 自动记录所有关键事件
- 实时统计运行指标
- 自动生成运行报告
- 健康状态检查和告警

---

## 🎯 设计目标

### 1. 零侵入性
- 不改变现有业务逻辑
- 仅添加监控调用
- 失败不影响主流程

### 2. 全面覆盖
- 覆盖所有关键操作点
- 记录成功和失败
- 捕获错误上下文

### 3. 易于使用
- 自动初始化和清理
- 自动生成报告
- 配置开关控制

---

## 🏗️ 架构设计

### 整体流程

```
程序启动
    ↓
初始化监控 (get_monitor())
    ↓
主流程执行
    ├── GitHub搜索 → record_*()
    ├── CVE信息获取 → record_*()
    ├── 仓库处理循环
    │   ├── 更新检测 → record_update_check()
    │   ├── GPT分析 → record_gpt_call()
    │   ├── 克隆仓库 → record_clone()
    │   ├── POC提取 → record_temp_dir_*()
    │   ├── 保存数据 → record_repo_new/updated/skipped()
    │   └── 错误处理 → record_error()
    ↓
程序结束 (finally块)
    ├── 打印监控摘要 → print_summary()
    ├── 保存监控数据 → save_to_file()
    ├── 健康检查 → check_health()
    └── 告警通知（可选）
```

---

## 💻 详细实现方案

### 1. 主流程改造

#### main.py 整体结构

```python
# main.py
import logging
from datetime import datetime
from libs.monitor import get_monitor
from config import get_config

logger = logging.getLogger(__name__)

def main():
    """主函数 - 集成监控"""

    # ============================================
    # 1. 初始化监控
    # ============================================
    monitor = get_monitor()
    logger.info("监控系统已启动")

    # 获取配置
    enable_gpt = get_config('ENABLE_GPT')
    enable_notify = get_config('ENABLE_NOTIFY')
    enable_search = get_config('ENABLE_SEARCH')
    enable_extended = get_config('ENABLE_EXTENDED')
    enable_update_check = get_config('ENABLE_UPDATE_CHECK')
    enable_monitor_report = get_config('ENABLE_MONITOR_REPORT')  # 新增配置

    try:
        # ============================================
        # 2. GitHub仓库搜索
        # ============================================
        logger.info("开始搜索GitHub仓库...")

        try:
            cve_list, repo_list = search_github(query="CVE")

            # 记录发现
            monitor.record_cve_found(len(cve_list))
            monitor.record_repo_found(len(repo_list))
            monitor.record_github_api_call(success=True)

            logger.info(f"发现 {len(cve_list)} 个CVE, {len(repo_list)} 个仓库")

        except Exception as e:
            monitor.record_github_api_call(success=False)
            monitor.record_error('github_search_failed', str(e), {})
            logger.error(f"GitHub搜索失败: {e}")
            return

        # ============================================
        # 3. 扩展搜索（可选）
        # ============================================
        if enable_extended and enable_search:
            logger.info("执行扩展搜索...")

            for cve_id in cve_list:
                try:
                    search_results = search_searxng(cve_id)
                    # 扩展搜索不计入主要指标，但可以记录
                    logger.debug(f"{cve_id} 扩展搜索: {len(search_results)} 个结果")

                except Exception as e:
                    monitor.record_error('extended_search_failed', str(e), {'cve_id': cve_id})
                    logger.warning(f"扩展搜索失败 {cve_id}: {e}")

        # ============================================
        # 4. 处理每个仓库
        # ============================================
        logger.info(f"开始处理 {len(repo_list)} 个仓库...")

        for idx, repo_item in enumerate(repo_list, 1):
            cve_id = repo_item['cve_id']
            repo = repo_item['repo']
            repo_url = repo.get('html_url', '')

            logger.info(f"[{idx}/{len(repo_list)}] 处理仓库: {cve_id} - {repo_url}")

            try:
                # 调用处理函数（集成监控）
                result = process_repository_with_monitor(
                    cve_id=cve_id,
                    repo=repo,
                    enable_gpt=enable_gpt,
                    enable_update_check=enable_update_check,
                    enable_notify=enable_notify,
                    monitor=monitor
                )

                logger.info(f"处理完成: {cve_id} - {result.get('action', 'unknown')}")

            except Exception as e:
                # 记录处理失败
                monitor.record_repo_failed()
                monitor.record_error('repo_processing_failed', str(e), {
                    'cve_id': cve_id,
                    'repo_url': repo_url
                })
                logger.error(f"处理仓库失败 {cve_id}: {e}")
                continue

        logger.info("所有仓库处理完成")

    except KeyboardInterrupt:
        logger.warning("用户中断执行")
        monitor.record_error('user_interrupted', 'Keyboard interrupt', {})

    except Exception as e:
        logger.error(f"主流程异常: {e}")
        monitor.record_error('main_process_error', str(e), {})
        import traceback
        traceback.print_exc()

    finally:
        # ============================================
        # 5. 生成监控报告
        # ============================================
        logger.info("=" * 60)
        logger.info("生成监控报告...")

        # 打印到日志
        monitor.print_summary()

        # 保存到文件（可选）
        if enable_monitor_report:
            try:
                # 生成文件名（带时间戳）
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                report_file = f'logs/monitor_report_{timestamp}.json'

                monitor.save_to_file(report_file)
                logger.info(f"监控报告已保存: {report_file}")

            except Exception as e:
                logger.error(f"保存监控报告失败: {e}")

        # ============================================
        # 6. 健康检查
        # ============================================
        health = monitor.check_health()

        if health['status'] == 'healthy':
            logger.info(f"✅ 系统健康状态: {health['status']}")
        elif health['status'] == 'warning':
            logger.warning(f"⚠️  系统健康状态: {health['status']}")
            logger.warning(f"警告信息: {health['warnings']}")
        else:  # critical
            logger.error(f"❌ 系统健康状态: {health['status']}")
            logger.error(f"严重问题: {health['warnings']}")

        # ============================================
        # 7. 告警通知（可选）
        # ============================================
        if health['status'] in ['warning', 'critical'] and enable_notify:
            try:
                send_health_alert(health, monitor.get_summary())
            except Exception as e:
                logger.error(f"发送健康告警失败: {e}")

        logger.info("=" * 60)


def process_repository_with_monitor(
    cve_id: str,
    repo: dict,
    enable_gpt: bool,
    enable_update_check: bool,
    enable_notify: bool,
    monitor
) -> dict:
    """
    处理单个仓库（集成监控）

    参数:
        cve_id: CVE编号
        repo: 仓库信息
        enable_gpt: 是否启用GPT
        enable_update_check: 是否启用更新检测
        enable_notify: 是否启用通知
        monitor: 监控实例

    返回:
        处理结果字典
    """

    repo_url = repo.get('html_url', '')
    result = {
        'cve_id': cve_id,
        'repo_url': repo_url,
        'action': None,
        'success': False
    }

    db = next(get_db())

    try:
        # ============================================
        # 1. 检查仓库是否已存在
        # ============================================
        repo_data = db.query(Repository).filter_by(url=repo_url).first()

        # ============================================
        # 2. 更新检测
        # ============================================
        if repo_data and enable_update_check:
            logger.info(f"仓库已存在: {repo_url}")

            # 获取最新commit SHA
            try:
                latest_sha = get_latest_commit_sha(repo_url)
                monitor.record_github_api_call(success=latest_sha is not None)

                if not latest_sha:
                    logger.warning(f"无法获取commit SHA: {repo_url}")
                    monitor.record_error('sha_fetch_failed', 'Failed to get commit SHA', {
                        'repo_url': repo_url
                    })

                # 比对SHA
                has_update = (repo_data.latest_commit_sha != latest_sha)
                monitor.record_update_check(has_update=has_update)

                if not has_update:
                    logger.info(f"仓库无更新，跳过处理")
                    monitor.record_repo_skipped()
                    result['action'] = 'skipped'
                    result['success'] = True
                    return result
                else:
                    logger.info(f"仓库有更新，继续处理")
                    result['action'] = 'update'

            except Exception as e:
                monitor.record_github_api_call(success=False)
                monitor.record_error('update_check_error', str(e), {
                    'repo_url': repo_url
                })
                logger.warning(f"更新检测失败，继续处理: {e}")
        else:
            # 新仓库
            result['action'] = 'new'
            latest_sha = None

        # ============================================
        # 3. 获取CVE信息
        # ============================================
        cve_info = get_cve_info(cve_id)
        if not cve_info:
            logger.warning(f"未获取到CVE信息: {cve_id}")
            monitor.record_error('cve_info_not_found', f'CVE info not found: {cve_id}', {
                'cve_id': cve_id
            })

        # ============================================
        # 4. 克隆仓库并提取POC
        # ============================================
        poc_code = ''
        clone_path = None

        try:
            clone_path = __clone_repo(repo_url)
            monitor.record_clone(success=clone_path is not None)

            if clone_path:
                monitor.record_temp_dir_created()

                # 提取POC代码
                poc_code = get_github_poc_from_path(clone_path)
                logger.info(f"POC代码提取成功: {len(poc_code)} 字符")
            else:
                logger.error(f"克隆仓库失败: {repo_url}")
                monitor.record_error('clone_failed', 'Clone repository failed', {
                    'repo_url': repo_url
                })

        except Exception as e:
            monitor.record_clone(success=False)
            monitor.record_error('clone_error', str(e), {'repo_url': repo_url})
            logger.error(f"克隆仓库异常: {e}")

        finally:
            # 清理临时目录
            if clone_path:
                try:
                    import shutil
                    from pathlib import Path
                    if Path(clone_path).exists():
                        shutil.rmtree(clone_path)
                        monitor.record_temp_dir_cleaned(success=True)
                        logger.debug(f"临时目录已清理: {clone_path}")
                except Exception as e:
                    monitor.record_temp_dir_cleaned(success=False)
                    monitor.record_error('cleanup_failed', str(e), {
                        'clone_path': clone_path
                    })
                    logger.warning(f"清理临时目录失败: {e}")

        # ============================================
        # 5. GPT分析
        # ============================================
        gpt_results = None

        if enable_gpt and poc_code:
            try:
                # 构建提示词
                prompt = build_analysis_prompt(cve_info, poc_code)

                # 调用GPT
                gpt_results = ask_gpt(prompt)
                monitor.record_gpt_call(success=gpt_results is not None)

                if gpt_results:
                    logger.info(f"GPT分析成功: 风险等级 {gpt_results.get('risk', 'unknown')}")
                else:
                    logger.warning(f"GPT分析失败")
                    monitor.record_gpt_parsing_failure()
                    monitor.record_error('gpt_analysis_failed', 'GPT returned None', {
                        'cve_id': cve_id
                    })

            except Exception as e:
                monitor.record_gpt_call(success=False)
                monitor.record_error('gpt_call_error', str(e), {'cve_id': cve_id})
                logger.error(f"GPT调用异常: {e}")

        # ============================================
        # 6. 保存到数据库
        # ============================================
        try:
            if result['action'] == 'update' and repo_data:
                # 更新现有记录
                repo_data.latest_commit_sha = latest_sha
                repo_data.gpt_analysis = gpt_results
                repo_data.updated_at = datetime.now()
                db.commit()

                monitor.record_repo_updated()
                logger.info(f"仓库信息已更新: {repo_url}")

            else:
                # 插入新记录
                new_repo = Repository(
                    cve_id=cve_id,
                    url=repo_url,
                    latest_commit_sha=latest_sha,
                    gpt_analysis=gpt_results,
                    stars=repo.get('stargazers_count', 0),
                    created_at=datetime.now()
                )
                db.add(new_repo)
                db.commit()

                monitor.record_repo_new()
                logger.info(f"新仓库已保存: {repo_url}")

            result['success'] = True

        except Exception as e:
            db.rollback()
            monitor.record_repo_failed()
            monitor.record_error('database_save_error', str(e), {
                'cve_id': cve_id,
                'repo_url': repo_url
            })
            logger.error(f"保存数据库失败: {e}")
            raise

        # ============================================
        # 7. 生成Markdown报告
        # ============================================
        if result['success']:
            try:
                markdown_data = {
                    'cve_id': cve_id,
                    'repo_url': repo_url,
                    'gpt_analysis': gpt_results or {},
                    # ... 其他字段
                }

                # 生成文件名
                year = cve_id.split('-')[1]
                filename = f"data/{year}/{cve_id}_{repo['name']}.md"

                write_to_markdown(markdown_data, filename)
                logger.info(f"Markdown报告已生成: {filename}")

            except Exception as e:
                monitor.record_error('markdown_generation_error', str(e), {
                    'cve_id': cve_id
                })
                logger.warning(f"生成Markdown失败: {e}")

        # ============================================
        # 8. 发送通知（可选）
        # ============================================
        if result['success'] and enable_notify and result['action'] == 'new':
            try:
                send_webhook({
                    'cve': cve_info,
                    'repo': repo,
                    'gpt': gpt_results
                })
                logger.info(f"通知已发送: {cve_id}")

            except Exception as e:
                monitor.record_error('notification_error', str(e), {
                    'cve_id': cve_id
                })
                logger.warning(f"发送通知失败: {e}")

        return result

    except Exception as e:
        logger.error(f"处理仓库异常: {e}")
        monitor.record_repo_failed()
        monitor.record_error('repo_processing_error', str(e), {
            'cve_id': cve_id,
            'repo_url': repo_url
        })
        raise


def send_health_alert(health: dict, summary: dict):
    """
    发送健康状态告警

    参数:
        health: 健康检查结果
        summary: 监控摘要
    """

    alert_data = {
        'title': f"⚠️ VulnWatchdog健康告警 - {health['status'].upper()}",
        'status': health['status'],
        'warnings': health['warnings'],
        'timestamp': health['timestamp'],
        'summary': {
            'total_repos': summary['discovery']['total_repos'],
            'success_rate': summary['processing']['success_rate'],
            'failed': summary['processing']['failed'],
            'errors': summary['errors']['total']
        }
    }

    # 调用通知接口（需要实现）
    logger.info(f"发送健康告警: {alert_data}")
    # TODO: 实际发送告警通知


if __name__ == '__main__':
    main()
```

---

### 2. 配置文件改造

#### config.py 新增配置

```python
# config.py

# 监控配置
ENABLE_MONITOR_REPORT = True  # 是否保存监控报告到文件
MONITOR_REPORT_DIR = 'logs'   # 监控报告保存目录

def get_config(env: str):
    config = {
        # ... 现有配置 ...

        # 监控配置
        'ENABLE_MONITOR_REPORT': os.environ.get('ENABLE_MONITOR_REPORT', ENABLE_MONITOR_REPORT),
        'MONITOR_REPORT_DIR': os.environ.get('MONITOR_REPORT_DIR', MONITOR_REPORT_DIR),
    }
    return config.get(env, '')
```

---

### 3. 辅助函数改造

#### libs/utils.py 暴露内部函数

```python
# libs/utils.py

def get_github_poc_from_path(clone_path: str) -> str:
    """
    从已克隆的路径提取POC代码

    参数:
        clone_path: 克隆目录路径

    返回:
        POC代码内容
    """

    # 原 get_github_poc 函数的核心逻辑
    ignore_patterns = [
        # ... 现有的忽略规则 ...
    ]

    outputs = process_path(
        path=clone_path,
        extensions=None,
        include_hidden=False,
        ignore_files_only=False,
        ignore_gitignore=True,
        gitignore_rules=[],
        ignore_patterns=ignore_patterns,
        claude_xml=False,
        markdown=False,
        line_numbers=False
    )

    logger.info(f"成功提取POC代码: {len(outputs)} 行")
    return '\n'.join(outputs)


# 重构 get_github_poc 使用新函数
def get_github_poc(github_link: str) -> str:
    """获取GitHub仓库中的POC代码"""
    clone_path = None

    try:
        clone_path = __clone_repo(github_link)
        if not clone_path:
            return ''

        return get_github_poc_from_path(clone_path)

    finally:
        if clone_path and Path(clone_path).exists():
            shutil.rmtree(clone_path)
```

---

## 📊 监控指标映射

### 指标记录时机表

| 操作 | 成功时记录 | 失败时记录 |
|------|-----------|-----------|
| **GitHub搜索** | `record_cve_found()`<br>`record_repo_found()`<br>`record_github_api_call(True)` | `record_github_api_call(False)`<br>`record_error()` |
| **更新检测** | `record_github_api_call(True)`<br>`record_update_check(has_update)` | `record_github_api_call(False)`<br>`record_error()` |
| **克隆仓库** | `record_clone(True)`<br>`record_temp_dir_created()` | `record_clone(False)`<br>`record_error()` |
| **临时目录清理** | `record_temp_dir_cleaned(True)` | `record_temp_dir_cleaned(False)`<br>`record_error()` |
| **GPT分析** | `record_gpt_call(True)` | `record_gpt_call(False)`<br>`record_gpt_parsing_failure()`<br>`record_error()` |
| **仓库处理** | `record_repo_new()`<br>或 `record_repo_updated()`<br>或 `record_repo_skipped()` | `record_repo_failed()`<br>`record_error()` |

---

## 📁 文件变更清单

### 需要修改的文件

1. **main.py**
   - 导入监控模块
   - 初始化监控实例
   - 添加监控调用
   - 添加finally报告生成

2. **config.py**
   - 新增监控配置项
   - 更新get_config函数

3. **libs/utils.py**
   - 暴露 `get_github_poc_from_path()` 函数
   - 确保线程安全（为并发准备）

4. **logs/** 目录
   - 确保目录存在
   - 添加到.gitignore

---

## 🧪 测试方案

### 测试用例

#### 1. 基础功能测试

```bash
# 运行主程序，观察监控输出
python main.py 2>&1 | tee test_monitor_integration.log

# 检查日志
grep "监控系统已启动" test_monitor_integration.log
grep "运行监控摘要" test_monitor_integration.log
grep "系统健康状态" test_monitor_integration.log
```

#### 2. 监控报告测试

```bash
# 检查报告文件生成
ls -lh logs/monitor_report_*.json

# 查看报告内容
cat logs/monitor_report_*.json | python -m json.tool
```

#### 3. 指标准确性测试

```python
# test_monitor_integration.py
def test_monitor_metrics():
    """测试监控指标记录准确性"""

    # 运行主程序（小规模）
    # 验证指标

    monitor = get_monitor()
    summary = monitor.get_summary()

    # 检查CVE发现数
    assert summary['discovery']['total_cves'] > 0

    # 检查仓库处理数
    total_processed = (
        summary['processing']['new'] +
        summary['processing']['updated'] +
        summary['processing']['skipped']
    )
    assert total_processed > 0

    # 检查成功率
    success_rate = float(summary['processing']['success_rate'].rstrip('%'))
    assert success_rate >= 80.0

    print("✅ 监控指标准确性测试通过")
```

---

## 📈 预期效果

### 运行日志示例

```
2025-11-27 10:00:00 INFO 监控系统已启动
2025-11-27 10:00:01 INFO 开始搜索GitHub仓库...
2025-11-27 10:00:05 INFO 发现 25 个CVE, 48 个仓库
2025-11-27 10:00:05 INFO 开始处理 48 个仓库...
2025-11-27 10:00:06 INFO [1/48] 处理仓库: CVE-2025-1234 - https://github.com/...
2025-11-27 10:00:07 INFO 仓库已存在: https://github.com/...
2025-11-27 10:00:08 INFO 仓库无更新，跳过处理
2025-11-27 10:00:08 INFO 处理完成: CVE-2025-1234 - skipped
...
2025-11-27 10:15:30 INFO 所有仓库处理完成
2025-11-27 10:15:30 INFO ============================================================
2025-11-27 10:15:30 INFO 生成监控报告...
2025-11-27 10:15:30 INFO ============================================================
2025-11-27 10:15:30 INFO 运行监控摘要
2025-11-27 10:15:30 INFO ============================================================
2025-11-27 10:15:30 INFO 运行时长: 15分30秒
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO 发现统计:
2025-11-27 10:15:30 INFO   CVE总数: 25
2025-11-27 10:15:30 INFO   仓库总数: 48
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO 处理统计:
2025-11-27 10:15:30 INFO   新仓库: 5
2025-11-27 10:15:30 INFO   更新仓库: 3
2025-11-27 10:15:30 INFO   跳过（无更新）: 40
2025-11-27 10:15:30 INFO   成功: 8
2025-11-27 10:15:30 INFO   失败: 0
2025-11-27 10:15:30 INFO   成功率: 100.0%
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO GitHub API统计:
2025-11-27 10:15:30 INFO   调用次数: 49
2025-11-27 10:15:30 INFO   失败次数: 0
2025-11-27 10:15:30 INFO   成功率: 100.0%
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO GPT分析统计:
2025-11-27 10:15:30 INFO   调用次数: 8
2025-11-27 10:15:30 INFO   失败次数: 0
2025-11-27 10:15:30 INFO   解析失败: 0
2025-11-27 10:15:30 INFO   成功率: 100.0%
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO 克隆统计:
2025-11-27 10:15:30 INFO   克隆次数: 8
2025-11-27 10:15:30 INFO   失败次数: 0
2025-11-27 10:15:30 INFO   成功率: 100.0%
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO 更新检测统计:
2025-11-27 10:15:30 INFO   检测次数: 43
2025-11-27 10:15:30 INFO   发现更新: 3
2025-11-27 10:15:30 INFO   更新率: 7.0%
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO 临时文件清理:
2025-11-27 10:15:30 INFO   创建: 8
2025-11-27 10:15:30 INFO   清理: 8
2025-11-27 10:15:30 INFO   失败: 0
2025-11-27 10:15:30 INFO   清理率: 100.0%
2025-11-27 10:15:30 INFO
2025-11-27 10:15:30 INFO ============================================================
2025-11-27 10:15:30 INFO 监控报告已保存: logs/monitor_report_20251127_101530.json
2025-11-27 10:15:30 INFO ✅ 系统健康状态: healthy
2025-11-27 10:15:30 INFO ============================================================
```

### 监控报告JSON示例

```json
{
  "runtime": {
    "seconds": 930.5,
    "formatted": "15分30秒"
  },
  "discovery": {
    "total_cves": 25,
    "total_repos": 48
  },
  "processing": {
    "new": 5,
    "updated": 3,
    "skipped": 40,
    "success": 8,
    "failed": 0,
    "success_rate": "100.0%"
  },
  "github_api": {
    "calls": 49,
    "failures": 0,
    "success_rate": "100.0%"
  },
  "gpt": {
    "calls": 8,
    "failures": 0,
    "parsing_failures": 0,
    "success_rate": "100.0%"
  },
  "clone": {
    "count": 8,
    "failures": 0,
    "success_rate": "100.0%"
  },
  "update_check": {
    "total": 43,
    "updates_found": 3,
    "detection_rate": "7.0%"
  },
  "temp_cleanup": {
    "created": 8,
    "cleaned": 8,
    "failures": 0,
    "cleanup_rate": "100.0%"
  },
  "errors": {
    "total": 0,
    "by_type": {},
    "recent": []
  }
}
```

---

## ✅ 验收标准

### 功能验收

- [ ] 监控系统自动初始化
- [ ] 所有关键操作都有监控记录
- [ ] 运行结束自动生成摘要
- [ ] 监控报告保存到文件
- [ ] 健康检查正常工作
- [ ] 错误追踪完整

### 性能验收

- [ ] 监控开销 < 5%（运行时间）
- [ ] 内存占用增加 < 10MB
- [ ] 不影响主流程性能

### 质量验收

- [ ] 所有测试用例通过
- [ ] 代码注释完整
- [ ] 无明显Bug

---

## 🚀 实施步骤

### Phase 1: 基础集成（30分钟）
1. 修改 main.py，添加监控初始化
2. 添加基本监控调用（GitHub搜索、仓库处理）
3. 添加finally报告生成
4. 测试基本功能

### Phase 2: 完善监控（30分钟）
5. 添加详细监控点（克隆、GPT、更新检测）
6. 添加错误追踪
7. 实现监控报告保存
8. 测试完整功能

### Phase 3: 优化和文档（60分钟）
9. 添加健康检查和告警
10. 优化代码和注释
11. 编写测试用例
12. 更新文档

---

## 📚 参考资料

- `libs/monitor.py` - 监控模块实现
- `test_monitor.py` - 监控测试用例
- `OPTIMIZATION_PHASE2_COMPLETE.md` - 监控系统文档

---

**设计完成时间**: 2025-11-27
**预计实施时间**: 2小时
**优先级**: P0
