# VulnWatchdog 后续开发计划

**更新时间**: 2025-11-27
**当前版本**: v2.0
**规划周期**: 2025 Q4 - 2026 Q2

---

## 📊 当前状态评估

### ✅ 已完成功能

| 模块 | 功能 | 状态 | 版本 |
|------|------|------|------|
| **核心功能** | GitHub CVE仓库搜索 | ✅ | v1.0 |
| **核心功能** | CVE信息获取 | ✅ | v1.0 |
| **核心功能** | GPT漏洞分析 | ✅ | v1.0 |
| **核心功能** | POC代码提取 | ✅ | v1.0 |
| **核心功能** | Markdown报告生成 | ✅ | v1.0 |
| **核心功能** | 通知推送（飞书） | ✅ | v1.0 |
| **优化-P1** | 精确更新检测 | ✅ | v1.5 |
| **优化-P1** | 临时文件自动清理 | ✅ | v1.5 |
| **优化-P1** | GPT解析增强 | ✅ | v1.5 |
| **优化-P2** | POC提取效率优化 | ✅ | v2.0 |
| **优化-P2** | GitHub Token认证 | ✅ | v2.0 |
| **优化-P2** | 监控告警基础 | ✅ | v2.0 |

### 🔍 待改进的问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 监控未集成到主流程 | 无法实时查看运行状态 | P0 |
| 缺少并发处理 | 处理速度较慢 | P0 |
| 单一通知渠道（仅飞书） | 灵活性不足 | P1 |
| 缺少数据可视化 | 难以分析趋势 | P1 |
| 缺少增量更新机制 | 重复处理数据 | P1 |
| 缺少缓存机制 | API调用浪费 | P2 |
| 缺少异常恢复 | 中断后需重跑 | P1 |
| 缺少数据导出 | 数据利用率低 | P2 |

---

## 🎯 第三阶段优化 (P3) - 性能与稳定性

**目标**: 提升处理速度、系统稳定性和可靠性
**时间**: 2周
**优先级**: P0

### 3.1 监控集成到主流程 ⭐⭐⭐⭐⭐

**问题**:
- 监控模块已开发完成，但未集成到main.py
- 无法实时查看运行指标

**方案**:

```python
# main.py 改造
from libs.monitor import get_monitor

def main():
    monitor = get_monitor()

    try:
        # 搜索阶段
        cve_list, repo_list = search_github(query)
        monitor.record_cve_found(len(cve_list))
        monitor.record_repo_found(len(repo_list))

        # 处理阶段
        for repo in repo_list:
            try:
                # 更新检测
                if enable_update_check:
                    latest_sha = get_latest_commit_sha(repo_url)
                    monitor.record_github_api_call(success=True)
                    monitor.record_update_check(has_update=...)

                # GPT分析
                if enable_gpt:
                    result = ask_gpt(prompt)
                    monitor.record_gpt_call(success=result is not None)

                # 克隆
                clone_path = __clone_repo(repo_url)
                monitor.record_clone(success=clone_path is not None)
                monitor.record_temp_dir_created()

                # 清理
                monitor.record_temp_dir_cleaned(success=True)

                # 记录结果
                if action == 'new':
                    monitor.record_repo_new()
                elif action == 'update':
                    monitor.record_repo_updated()
                else:
                    monitor.record_repo_skipped()

            except Exception as e:
                monitor.record_error('processing_error', str(e), {'repo': repo_url})
                monitor.record_repo_failed()

    finally:
        # 打印摘要
        monitor.print_summary()
        # 保存到文件
        monitor.save_to_file('logs/monitor_report.json')
        # 健康检查
        health = monitor.check_health()
        if health['status'] != 'healthy':
            logger.warning(f"健康状态: {health['status']}, 警告: {health['warnings']}")
```

**改动文件**:
- `main.py` - 集成监控调用

**预期效果**:
- ✅ 实时监控运行状态
- ✅ 自动生成运行报告
- ✅ 健康状态自动检查
- ✅ 历史数据可追溯（JSON文件）

**工作量**: 2小时

---

### 3.2 并发处理优化 ⭐⭐⭐⭐⭐

**问题**:
- 当前串行处理，处理7680个仓库耗时过长
- CPU和网络资源利用率低

**方案**:

#### 方案A: 多线程 (推荐)

```python
# main.py
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 线程安全的监控
monitor_lock = threading.Lock()

def process_repo_with_monitor(repo_data):
    """线程安全的仓库处理"""
    result = process_repository(repo_data)

    # 线程安全记录
    with monitor_lock:
        if result['action'] == 'new':
            monitor.record_repo_new()
        elif result['action'] == 'update':
            monitor.record_repo_updated()
        # ...

    return result

def main():
    # 并发处理
    max_workers = 10  # 根据系统配置调整

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        futures = {
            executor.submit(process_repo_with_monitor, repo): repo
            for repo in repo_list
        }

        # 收集结果（带进度）
        for idx, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                logger.info(f"进度: {idx}/{len(repo_list)} - {result['cve_id']}")
            except Exception as e:
                repo = futures[future]
                logger.error(f"处理失败: {repo['cve_id']} - {e}")
```

**改动文件**:
- `main.py` - 添加并发处理逻辑
- `libs/utils.py` - 确保线程安全

**预期效果**:
- ✅ 处理速度提升 **5-10倍**
- ✅ 7680个仓库：1.5小时 → 15分钟
- ✅ 资源利用率提升

**配置项**:
```python
# config.py
MAX_WORKERS = 10  # 并发数（建议5-20）
```

**注意事项**:
- GitHub API限流（需Token认证）
- 数据库写入冲突（需加锁或使用连接池）
- GPT API限流（需控制并发）

**工作量**: 1天

---

### 3.3 异常恢复与断点续传 ⭐⭐⭐⭐

**问题**:
- 程序中断后需要从头开始
- 网络异常导致重复处理

**方案**:

```python
# 进度跟踪
class ProgressTracker:
    def __init__(self, checkpoint_file='progress.json'):
        self.checkpoint_file = checkpoint_file
        self.processed_repos = self._load_checkpoint()

    def _load_checkpoint(self):
        """加载已处理记录"""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file) as f:
                return set(json.load(f))
        return set()

    def mark_processed(self, repo_url):
        """标记已处理"""
        self.processed_repos.add(repo_url)
        self._save_checkpoint()

    def is_processed(self, repo_url):
        """检查是否已处理"""
        return repo_url in self.processed_repos

    def _save_checkpoint(self):
        """保存进度"""
        with open(self.checkpoint_file, 'w') as f:
            json.dump(list(self.processed_repos), f)

    def clear(self):
        """清除进度（新一轮运行）"""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)

# main.py 使用
def main():
    tracker = ProgressTracker()

    # 是否是新一轮运行
    if is_new_run():
        tracker.clear()

    for repo in repo_list:
        # 跳过已处理
        if tracker.is_processed(repo['html_url']):
            logger.info(f"跳过已处理仓库: {repo['html_url']}")
            continue

        try:
            result = process_repository(repo)
            tracker.mark_processed(repo['html_url'])
        except Exception as e:
            logger.error(f"处理失败: {e}")
            # 不标记为已处理，下次重试
```

**改动文件**:
- `libs/progress.py` - 新增进度跟踪模块
- `main.py` - 集成断点续传

**预期效果**:
- ✅ 中断后可继续运行
- ✅ 避免重复处理
- ✅ 提升稳定性

**工作量**: 4小时

---

### 3.4 增量更新机制 ⭐⭐⭐⭐

**问题**:
- 每次都搜索全部仓库
- 已处理的老仓库重复检查

**方案**:

```python
# config.py
INCREMENTAL_MODE = True  # 启用增量模式
INCREMENTAL_DAYS = 7     # 只处理最近7天更新的仓库

# main.py
def is_recently_updated(repo_data, days=7):
    """检查仓库是否最近更新"""
    updated_at = repo_data.get('updated_at')
    if not updated_at:
        return True  # 保险起见，包含未知时间的

    update_time = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%SZ')
    cutoff_time = datetime.now() - timedelta(days=days)
    return update_time >= cutoff_time

def main():
    if get_config('INCREMENTAL_MODE'):
        days = get_config('INCREMENTAL_DAYS')
        logger.info(f"增量模式：仅处理最近{days}天更新的仓库")

        # 过滤仓库
        repo_list = [
            repo for repo in all_repos
            if is_recently_updated(repo, days)
        ]
        logger.info(f"过滤后仓库数: {len(repo_list)}")
```

**改动文件**:
- `config.py` - 增量配置
- `main.py` - 增量逻辑

**预期效果**:
- ✅ 减少处理量 70-90%
- ✅ 运行时间缩短
- ✅ API调用减少

**工作量**: 2小时

---

## 🚀 第四阶段优化 (P4) - 功能扩展

**目标**: 增强系统功能和用户体验
**时间**: 3周
**优先级**: P1

### 4.1 多渠道通知支持 ⭐⭐⭐⭐

**问题**:
- 当前仅支持飞书
- 企业可能使用其他工具

**方案**:

新增通知渠道：
1. **钉钉** (DingTalk)
2. **企业微信** (WeChat Work)
3. **Slack**
4. **Email**
5. **Webhook** (通用)
6. **Telegram**

```python
# libs/notifier.py (重构)
class NotifierFactory:
    @staticmethod
    def create(notifier_type: str):
        if notifier_type == 'feishu':
            return FeishuNotifier()
        elif notifier_type == 'dingtalk':
            return DingTalkNotifier()
        elif notifier_type == 'wechat':
            return WeChatNotifier()
        elif notifier_type == 'slack':
            return SlackNotifier()
        elif notifier_type == 'email':
            return EmailNotifier()
        else:
            raise ValueError(f"未知通知类型: {notifier_type}")

# 支持多通道
# config.py
NOTIFY_CHANNELS = ['feishu', 'email']  # 多通道通知

# main.py
for channel in get_config('NOTIFY_CHANNELS'):
    notifier = NotifierFactory.create(channel)
    notifier.send(data)
```

**新增文件**:
- `libs/notifiers/base.py` - 通知基类
- `libs/notifiers/feishu.py` - 飞书
- `libs/notifiers/dingtalk.py` - 钉钉
- `libs/notifiers/wechat.py` - 企业微信
- `libs/notifiers/slack.py` - Slack
- `libs/notifiers/email.py` - 邮件
- `template/dingtalk.json`
- `template/wechat.json`
- `template/slack.json`

**工作量**: 3天

---

### 4.2 数据可视化面板 ⭐⭐⭐⭐

**问题**:
- 数据存储在数据库，缺少直观展示
- 难以分析趋势和统计

**方案**:

#### 方案A: Web仪表盘 (推荐)

使用 **Streamlit** 或 **Dash** 快速搭建：

```python
# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from models.models import get_db, CVE, Repository

st.set_page_config(page_title="VulnWatchdog Dashboard", layout="wide")

# 标题
st.title("🐕 VulnWatchdog 监控面板")

# 数据加载
@st.cache_data(ttl=600)  # 缓存10分钟
def load_data():
    db = next(get_db())
    cves = db.query(CVE).all()
    repos = db.query(Repository).all()
    return cves, repos

cves, repos = load_data()

# 统计卡片
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("CVE总数", len(cves))
with col2:
    st.metric("仓库总数", len(repos))
with col3:
    new_count = len([r for r in repos if r.created_at > datetime.now() - timedelta(days=7)])
    st.metric("本周新增", new_count)
with col4:
    high_risk = len([c for c in cves if c.cvss_score >= 7.0])
    st.metric("高危漏洞", high_risk)

# 图表1: CVE年份分布
st.subheader("📊 CVE年份分布")
cve_years = [cve.id.split('-')[1] for cve in cves]
year_counts = pd.Series(cve_years).value_counts().sort_index()
fig1 = px.bar(x=year_counts.index, y=year_counts.values, labels={'x': '年份', 'y': '数量'})
st.plotly_chart(fig1, use_container_width=True)

# 图表2: 风险等级分布
st.subheader("⚠️ 风险等级分布")
risk_levels = [cve.cvss_score for cve in cves if cve.cvss_score]
risk_df = pd.DataFrame({
    'level': ['低危', '中危', '高危', '严重'],
    'count': [
        len([s for s in risk_levels if s < 4.0]),
        len([s for s in risk_levels if 4.0 <= s < 7.0]),
        len([s for s in risk_levels if 7.0 <= s < 9.0]),
        len([s for s in risk_levels if s >= 9.0])
    ]
})
fig2 = px.pie(risk_df, names='level', values='count')
st.plotly_chart(fig2, use_container_width=True)

# 图表3: 每日新增趋势
st.subheader("📈 每日新增趋势")
daily_data = pd.DataFrame([
    {'date': r.created_at.date(), 'count': 1}
    for r in repos if r.created_at
])
daily_counts = daily_data.groupby('date').count().reset_index()
fig3 = px.line(daily_counts, x='date', y='count', labels={'date': '日期', 'count': '新增数量'})
st.plotly_chart(fig3, use_container_width=True)

# 数据表格
st.subheader("📋 最近仓库")
recent_repos = sorted(repos, key=lambda r: r.created_at, reverse=True)[:20]
st.dataframe([
    {
        'CVE': r.cve_id,
        '仓库': r.url,
        '发现时间': r.created_at.strftime('%Y-%m-%d %H:%M'),
        '更新时间': r.updated_at.strftime('%Y-%m-%d %H:%M') if r.updated_at else '-'
    }
    for r in recent_repos
])
```

**运行**:
```bash
streamlit run dashboard.py
# 访问 http://localhost:8501
```

**新增依赖**:
```bash
pip install streamlit plotly pandas
```

**工作量**: 2天

---

### 4.3 API接口开发 ⭐⭐⭐

**问题**:
- 数据无法被其他系统访问
- 缺少程序化查询方式

**方案**:

使用 **FastAPI** 提供RESTful API：

```python
# api.py
from fastapi import FastAPI, Query, HTTPException
from typing import List, Optional
from models.models import get_db, CVE, Repository
from pydantic import BaseModel

app = FastAPI(title="VulnWatchdog API", version="2.0")

class CVEResponse(BaseModel):
    id: str
    title: str
    cvss_score: Optional[float]
    description: Optional[str]

    class Config:
        from_attributes = True

@app.get("/api/cves", response_model=List[CVEResponse])
async def list_cves(
    year: Optional[int] = None,
    min_score: Optional[float] = None,
    limit: int = Query(100, le=1000)
):
    """获取CVE列表"""
    db = next(get_db())
    query = db.query(CVE)

    if year:
        query = query.filter(CVE.id.like(f'CVE-{year}-%'))
    if min_score:
        query = query.filter(CVE.cvss_score >= min_score)

    return query.limit(limit).all()

@app.get("/api/cves/{cve_id}")
async def get_cve(cve_id: str):
    """获取CVE详情"""
    db = next(get_db())
    cve = db.query(CVE).filter(CVE.id == cve_id).first()
    if not cve:
        raise HTTPException(status_code=404, detail="CVE not found")
    return cve

@app.get("/api/repositories")
async def list_repos(cve_id: Optional[str] = None, limit: int = 100):
    """获取仓库列表"""
    db = next(get_db())
    query = db.query(Repository)

    if cve_id:
        query = query.filter(Repository.cve_id == cve_id)

    return query.limit(limit).all()

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    db = next(get_db())
    return {
        'total_cves': db.query(CVE).count(),
        'total_repos': db.query(Repository).count(),
        'recent_cves': db.query(CVE).filter(
            CVE.created_at > datetime.now() - timedelta(days=7)
        ).count()
    }
```

**运行**:
```bash
uvicorn api:app --reload
# 访问 http://localhost:8000/docs (Swagger UI)
```

**新增依赖**:
```bash
pip install fastapi uvicorn[standard]
```

**工作量**: 1天

---

### 4.4 数据导出功能 ⭐⭐⭐

**问题**:
- 数据锁定在数据库
- 无法导出用于分析

**方案**:

```python
# scripts/export_data.py
import csv
import json
import argparse
from models.models import get_db, CVE, Repository

def export_to_csv(output_file='export.csv'):
    """导出为CSV"""
    db = next(get_db())
    repos = db.query(Repository).all()

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'cve_id', 'repo_url', 'stars', 'created_at', 'updated_at',
            'risk_level', 'cvss_score'
        ])
        writer.writeheader()

        for repo in repos:
            writer.writerow({
                'cve_id': repo.cve_id,
                'repo_url': repo.url,
                'stars': repo.stars,
                'created_at': repo.created_at,
                'updated_at': repo.updated_at,
                'risk_level': repo.gpt_analysis.get('risk') if repo.gpt_analysis else '',
                'cvss_score': repo.cve.cvss_score if repo.cve else ''
            })

def export_to_json(output_file='export.json'):
    """导出为JSON"""
    db = next(get_db())
    repos = db.query(Repository).all()

    data = []
    for repo in repos:
        data.append({
            'cve_id': repo.cve_id,
            'repo_url': repo.url,
            'gpt_analysis': repo.gpt_analysis,
            'created_at': repo.created_at.isoformat(),
            'updated_at': repo.updated_at.isoformat() if repo.updated_at else None
        })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', choices=['csv', 'json'], default='csv')
    parser.add_argument('--output', default='export')
    args = parser.parse_args()

    output_file = f"{args.output}.{args.format}"

    if args.format == 'csv':
        export_to_csv(output_file)
    else:
        export_to_json(output_file)

    print(f"数据已导出到: {output_file}")
```

**使用**:
```bash
# 导出CSV
python scripts/export_data.py --format csv --output data_export

# 导出JSON
python scripts/export_data.py --format json --output data_export
```

**工作量**: 4小时

---

## 🔧 第五阶段优化 (P5) - 性能调优

**目标**: 进一步优化性能和成本
**时间**: 2周
**优先级**: P2

### 5.1 缓存机制 ⭐⭐⭐

**问题**:
- CVE信息重复查询
- GitHub API重复调用

**方案**:

```python
# libs/cache.py
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

class SimpleCache:
    def __init__(self, cache_dir='.cache', ttl=3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = ttl  # 秒

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str):
        """获取缓存"""
        cache_file = self._get_cache_path(key)

        if not cache_file.exists():
            return None

        # 检查过期
        with open(cache_file) as f:
            cache_data = json.load(f)

        cached_time = datetime.fromisoformat(cache_data['timestamp'])
        if datetime.now() - cached_time > timedelta(seconds=self.ttl):
            cache_file.unlink()  # 删除过期缓存
            return None

        return cache_data['value']

    def set(self, key: str, value):
        """设置缓存"""
        cache_file = self._get_cache_path(key)
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'value': value
        }

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)

    def clear(self):
        """清空缓存"""
        for cache_file in self.cache_dir.glob('*.json'):
            cache_file.unlink()

# libs/utils.py 使用缓存
from libs.cache import SimpleCache

cve_cache = SimpleCache(cache_dir='.cache/cve', ttl=86400)  # 24小时
github_cache = SimpleCache(cache_dir='.cache/github', ttl=3600)  # 1小时

def get_cve_info(cve_id: str) -> Dict:
    # 先查缓存
    cached = cve_cache.get(cve_id)
    if cached:
        logger.debug(f"命中CVE缓存: {cve_id}")
        return cached

    # 未命中，查询API
    data = _fetch_cve_from_api(cve_id)

    # 存入缓存
    if data:
        cve_cache.set(cve_id, data)

    return data
```

**配置**:
```python
# config.py
CACHE_ENABLED = True
CACHE_TTL_CVE = 86400      # CVE信息缓存24小时
CACHE_TTL_GITHUB = 3600    # GitHub信息缓存1小时
```

**预期效果**:
- ✅ API调用减少 50-80%
- ✅ 响应速度提升
- ✅ 成本降低

**工作量**: 1天

---

### 5.2 数据库索引优化 ⭐⭐⭐

**问题**:
- 查询速度慢（7680条记录）
- 缺少合适索引

**方案**:

```python
# models/models.py
from sqlalchemy import Index

class Repository(Base):
    __tablename__ = 'repositories'

    id = Column(Integer, primary_key=True)
    cve_id = Column(String(50), nullable=False, index=True)  # 添加索引
    url = Column(String(255), unique=True, index=True)       # 添加索引
    latest_commit_sha = Column(String(40), index=True)       # 添加索引
    created_at = Column(DateTime, default=datetime.now, index=True)  # 添加索引
    updated_at = Column(DateTime, onupdate=datetime.now, index=True) # 添加索引

    # 复合索引
    __table_args__ = (
        Index('idx_cve_created', 'cve_id', 'created_at'),
        Index('idx_url_sha', 'url', 'latest_commit_sha'),
    )

# 迁移脚本
# scripts/add_indexes.py
from models.models import engine
from sqlalchemy import text

def add_indexes():
    with engine.connect() as conn:
        # 添加索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_repo_cve_id ON repositories(cve_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_repo_url ON repositories(url)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_repo_sha ON repositories(latest_commit_sha)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_repo_created ON repositories(created_at)"))
        conn.commit()
    print("索引创建完成")

if __name__ == '__main__':
    add_indexes()
```

**工作量**: 2小时

---

### 5.3 GPT提示词优化 ⭐⭐⭐

**问题**:
- 当前提示词可能不够精确
- GPT响应质量有待提升

**方案**:

```python
# 优化提示词模板
OPTIMIZED_PROMPT_TEMPLATE = """
你是一名专业的网络安全分析师。请分析以下CVE漏洞及其POC代码，提供精确的风险评估。

# 任务要求
1. 简洁明了（避免冗余）
2. 突出关键技术细节
3. 提供可操作的建议

# 输出格式（严格JSON）
{{
    "risk": "低危|中危|高危|严重",
    "type": "RCE|XSS|SQL注入|权限提升|...",
    "affected_version": "受影响版本",
    "exploit_difficulty": "简单|中等|困难",
    "summary": "一句话总结（20字内）",
    "technical_details": "技术细节（50字内）",
    "mitigation": "缓解措施（30字内）"
}}

# 输入数据
## CVE信息
{cve_info}

## POC代码
{poc_code}

# 重要提示
- 仅返回JSON，无其他内容
- 确保所有字段都存在
- risk必须是四个等级之一
"""

def ask_gpt_optimized(cve_info: Dict, poc_code: str) -> Optional[Dict]:
    """优化的GPT调用"""
    prompt = OPTIMIZED_PROMPT_TEMPLATE.format(
        cve_info=json.dumps(cve_info, indent=2),
        poc_code=poc_code[:5000]  # 限制长度
    )

    # 使用优化的参数
    data = {
        "model": get_config('GPT_MODEL'),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,  # 降低随机性，提升一致性
        "max_tokens": 500,   # 限制输出长度
        "response_format": {"type": "json_object"}  # 强制JSON输出（如果模型支持）
    }

    # ... 其余逻辑
```

**工作量**: 4小时

---

## 📅 开发时间表

### 近期 (1个月内)

| 周次 | 任务 | 优先级 | 预计工时 |
|------|------|--------|---------|
| **Week 1** | 监控集成到主流程 | P0 | 2h |
| **Week 1** | 并发处理优化 | P0 | 8h |
| **Week 1** | 异常恢复与断点续传 | P0 | 4h |
| **Week 2** | 增量更新机制 | P0 | 2h |
| **Week 2** | 多渠道通知支持 | P1 | 16h |
| **Week 3** | 数据可视化面板 | P1 | 16h |
| **Week 4** | API接口开发 | P1 | 8h |
| **Week 4** | 数据导出功能 | P1 | 4h |

### 中期 (2-3个月)

| 任务 | 优先级 | 预计工时 |
|------|--------|---------|
| 缓存机制 | P2 | 8h |
| 数据库索引优化 | P2 | 2h |
| GPT提示词优化 | P2 | 4h |
| 日志系统优化 | P2 | 4h |
| 配置管理优化 | P2 | 4h |

### 长期 (3-6个月)

| 任务 | 优先级 |
|------|--------|
| 漏洞预测模型 | P3 |
| 自动化修复建议 | P3 |
| 社区贡献机制 | P3 |
| 多语言支持 | P3 |

---

## 🎯 关键里程碑

### v2.1 (1个月后)
- ✅ 监控全面集成
- ✅ 并发处理上线
- ✅ 异常恢复机制
- ✅ 增量更新模式

**预期效果**:
- 处理速度提升 **5-10倍**
- 稳定性显著提升
- 运行时间: 15分钟完成全量扫描

### v2.5 (2个月后)
- ✅ 多渠道通知
- ✅ 数据可视化面板
- ✅ RESTful API
- ✅ 数据导出

**预期效果**:
- 用户体验大幅提升
- 数据利用率提升
- 支持第三方集成

### v3.0 (3个月后)
- ✅ 缓存系统
- ✅ 性能全面优化
- ✅ 企业级特性

**预期效果**:
- 生产级稳定性
- 成本降低 50%
- 支持大规模部署

---

## 💡 创新性功能（探索）

### 1. 漏洞预测模型
基于历史数据，预测哪些仓库可能发布POC

### 2. 自动化修复建议
基于POC代码，自动生成修复建议

### 3. 社区贡献平台
允许安全研究者提交和分享分析

### 4. 威胁情报联动
与其他威胁情报平台集成

---

## 📊 成功指标

| 指标 | 当前 | v2.1目标 | v3.0目标 |
|------|------|---------|---------|
| 处理速度 | 1.5小时 | 15分钟 | 5分钟 |
| 成功率 | ~95% | >98% | >99% |
| API调用数 | 基准 | -50% | -70% |
| GPT成本 | 基准 | -20% | -40% |
| 监控覆盖 | 部分 | 100% | 100% |
| 系统可用性 | - | 95% | 99% |

---

## 🔄 迭代原则

1. **小步快跑**: 每次迭代1-2周，快速交付
2. **数据驱动**: 基于监控数据指导优化方向
3. **用户反馈**: 持续收集使用反馈
4. **兼容优先**: 保持向后兼容
5. **文档同步**: 代码和文档同步更新

---

## 📚 参考资源

- [Streamlit文档](https://docs.streamlit.io/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [GitHub API文档](https://docs.github.com/en/rest)
- [OpenAI API最佳实践](https://platform.openai.com/docs/guides/prompt-engineering)

---

**更新日期**: 2025-11-27
**维护者**: VulnWatchdog Team
**版本**: v1.0
