from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurriculumNode:
    key: str
    track_key: str
    stage_key: str
    order: int
    title: str
    objective: str
    prerequisites: tuple[str, ...]
    deliverable_kinds: tuple[str, ...]
    acceptance_types: tuple[str, ...]
    radar_keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurriculumTrack:
    key: str
    label: str
    weight: float
    nodes: tuple[CurriculumNode, ...]


@dataclass(frozen=True, slots=True)
class CurriculumCatalog:
    version: str
    tracks: tuple[CurriculumTrack, ...]

    def track(self, key: str) -> CurriculumTrack:
        return next(track for track in self.tracks if track.key == key)

    def node(self, key: str) -> CurriculumNode:
        return next(node for track in self.tracks for node in track.nodes if node.key == key)


class CurriculumSelector:
    def __init__(self, catalog: CurriculumCatalog) -> None:
        self.catalog = catalog

    def select(
        self,
        recent_track_keys: list[str],
        completed: set[str],
        remediation: CurriculumNode | None = None,
    ) -> CurriculumNode:
        if remediation is not None:
            return remediation

        candidates: dict[str, CurriculumNode] = {}
        for track in self.catalog.tracks:
            for node in track.nodes:
                if node.key in completed:
                    continue
                if all(key in completed for key in node.prerequisites):
                    candidates[track.key] = node
                    break
        if not candidates:
            raise ValueError("No unlocked curriculum node is available")

        window = recent_track_keys[-10:]
        next_total = len(window) + 1
        counts = {track.key: window.count(track.key) for track in self.catalog.tracks}
        ranked = sorted(
            self.catalog.tracks,
            key=lambda track: (
                -(track.weight * next_total - counts[track.key]),
                self.catalog.tracks.index(track),
            ),
        )
        selected_track = next(track for track in ranked if track.key in candidates)
        return candidates[selected_track.key]


TRACK_DEFINITIONS: tuple[
    tuple[str, str, float, tuple[tuple[str, str, str, tuple[str, ...]], ...]], ...
] = (
    (
        "ai",
        "AI/LLM 工程",
        0.40,
        (
            (
                "foundation",
                "model-io",
                "掌握 OpenAI 兼容模型请求、响应与错误边界",
                ("OpenAI API", "LLM request"),
            ),
            (
                "foundation",
                "prompt-contracts",
                "用明确输入输出契约设计可测试提示词",
                ("structured output", "prompt engineering"),
            ),
            (
                "foundation",
                "embedding-retrieval",
                "构建可度量的向量检索最小闭环",
                ("embedding", "vector search"),
            ),
            (
                "practice",
                "rag-grounding",
                "实现带引用的检索增强回答",
                ("RAG", "grounded generation"),
            ),
            (
                "practice",
                "tool-boundaries",
                "为 Agent 工具定义权限与参数边界",
                ("tool calling", "agent safety"),
            ),
            (
                "practice",
                "langgraph-state",
                "实现可恢复的 LangGraph 状态工作流",
                ("LangGraph", "state graph"),
            ),
            (
                "production",
                "eval-dataset",
                "建立固定样本与可重复的模型评测",
                ("LLM evaluation", "dataset"),
            ),
            (
                "production",
                "observability",
                "记录模型延迟、token、引用与失败原因",
                ("LLM observability", "tracing"),
            ),
            (
                "production",
                "guardrails",
                "验证提示注入防护和敏感信息边界",
                ("prompt injection", "guardrails"),
            ),
            (
                "architecture",
                "routing",
                "设计多模型路由与可降级策略",
                ("model routing", "fallback"),
            ),
            (
                "architecture",
                "memory",
                "区分会话、长期记忆和证据存储",
                ("agent memory", "context engineering"),
            ),
            (
                "architecture",
                "agent-system",
                "完成有权限、评测和审计的 Agent 系统设计",
                ("agent architecture", "AI system design"),
            ),
        ),
    ),
    (
        "backend",
        "后端与架构",
        0.25,
        (
            (
                "foundation",
                "api-contract",
                "用 Schema 和状态码定义稳定 API 契约",
                ("API design", "OpenAPI"),
            ),
            (
                "foundation",
                "database-modeling",
                "为业务约束设计关系模型和索引",
                ("PostgreSQL", "data modeling"),
            ),
            (
                "foundation",
                "transactions",
                "验证事务、并发更新和幂等边界",
                ("transaction", "idempotency"),
            ),
            ("practice", "async-io", "实现有超时和取消语义的异步 I/O", ("asyncio", "httpx")),
            ("practice", "cache-consistency", "选择缓存策略并处理失效", ("cache", "consistency")),
            (
                "practice",
                "background-jobs",
                "构建可补跑的后台任务",
                ("scheduler", "background jobs"),
            ),
            (
                "production",
                "rate-limits",
                "实现面向用户和依赖的限流",
                ("rate limiting", "backpressure"),
            ),
            (
                "production",
                "migration-safety",
                "设计向后兼容的数据迁移",
                ("Alembic", "zero downtime migration"),
            ),
            (
                "production",
                "service-observability",
                "用指标、日志和追踪定位请求故障",
                ("observability", "distributed tracing"),
            ),
            (
                "architecture",
                "service-boundaries",
                "按变化原因划分服务边界",
                ("service boundaries", "DDD"),
            ),
            (
                "architecture",
                "resilience",
                "设计重试、熔断和降级策略",
                ("resilience", "circuit breaker"),
            ),
            (
                "architecture",
                "capacity",
                "根据负载模型完成容量与瓶颈分析",
                ("capacity planning", "performance"),
            ),
        ),
    ),
    (
        "quality",
        "工程质量",
        0.20,
        (
            (
                "foundation",
                "unit-tests",
                "编写能捕获真实回归的单元测试",
                ("unit testing", "pytest"),
            ),
            (
                "foundation",
                "static-analysis",
                "建立格式、Lint 和类型检查门禁",
                ("ruff", "type checking"),
            ),
            ("foundation", "git-practice", "用小提交和清晰历史支持审阅", ("Git", "code review")),
            (
                "practice",
                "integration-tests",
                "验证数据库与外部依赖边界",
                ("integration testing", "test containers"),
            ),
            (
                "practice",
                "contract-tests",
                "用契约测试保护服务集成",
                ("contract testing", "OpenAPI"),
            ),
            (
                "practice",
                "property-tests",
                "用性质和不变量覆盖输入空间",
                ("property testing", "Hypothesis"),
            ),
            ("production", "ci-gates", "配置可重复且有失败门禁的 CI", ("GitHub Actions", "CI")),
            (
                "production",
                "security-tests",
                "自动检查鉴权、注入和密钥泄漏",
                ("security testing", "secret scanning"),
            ),
            (
                "production",
                "performance-tests",
                "建立性能基线与回归阈值",
                ("load testing", "benchmark"),
            ),
            (
                "architecture",
                "test-strategy",
                "按风险设计测试金字塔",
                ("test strategy", "risk based testing"),
            ),
            (
                "architecture",
                "quality-metrics",
                "选择能驱动决策的质量指标",
                ("quality metrics", "DORA"),
            ),
            (
                "architecture",
                "evolution",
                "安全重构遗留系统并控制兼容性",
                ("refactoring", "legacy modernization"),
            ),
        ),
    ),
    (
        "devops",
        "云与 DevOps",
        0.15,
        (
            (
                "foundation",
                "containers",
                "构建最小且可复现的容器镜像",
                ("Docker", "container image"),
            ),
            (
                "foundation",
                "compose-network",
                "隔离 Compose 服务网络和端口",
                ("Docker Compose", "networking"),
            ),
            (
                "foundation",
                "linux-ops",
                "使用日志、进程和资源工具定位故障",
                ("Linux", "operations"),
            ),
            ("practice", "https-proxy", "部署自动 HTTPS 与反向代理", ("Caddy", "TLS")),
            (
                "practice",
                "backup-restore",
                "完成数据库备份与恢复演练",
                ("PostgreSQL backup", "restore"),
            ),
            ("practice", "deployment", "实现带健康检查的可回滚部署", ("deployment", "rollback")),
            ("production", "monitoring", "建立服务与主机告警", ("monitoring", "alerting")),
            ("production", "secrets", "管理运行时密钥与轮换", ("secret management", "rotation")),
            (
                "production",
                "supply-chain",
                "扫描依赖、镜像与构建来源",
                ("SBOM", "container scanning"),
            ),
            (
                "architecture",
                "cloud-resilience",
                "设计单机故障和区域故障恢复",
                ("disaster recovery", "cloud resilience"),
            ),
            (
                "architecture",
                "delivery-strategy",
                "比较滚动、蓝绿与金丝雀发布",
                ("progressive delivery", "canary"),
            ),
            ("architecture", "cost-capacity", "平衡云成本、容量和可靠性", ("FinOps", "capacity")),
        ),
    ),
)


def _build_catalog() -> CurriculumCatalog:
    tracks: list[CurriculumTrack] = []
    for track_key, label, weight, definitions in TRACK_DEFINITIONS:
        nodes: list[CurriculumNode] = []
        previous: str | None = None
        for order, (stage, slug, objective, keywords) in enumerate(definitions, start=1):
            key = f"{track_key}-{stage}-{slug}"
            nodes.append(
                CurriculumNode(
                    key=key,
                    track_key=track_key,
                    stage_key=stage,
                    order=order,
                    title=objective,
                    objective=objective,
                    prerequisites=(previous,) if previous else (),
                    deliverable_kinds=("commit", "report"),
                    acceptance_types=("command", "inspection"),
                    radar_keywords=keywords,
                )
            )
            previous = key
        tracks.append(CurriculumTrack(track_key, label, weight, tuple(nodes)))
    return CurriculumCatalog("v1", tuple(tracks))


CURRICULUM = _build_catalog()
