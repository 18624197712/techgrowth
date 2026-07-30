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


LEGACY_CURRICULUM = _build_catalog()


V2_TRACK_TOPICS: tuple[tuple[str, str, tuple[tuple[str, str, str, tuple[str, ...]], ...]], ...] = (
    (
        "java",
        "Java + Spring Cloud",
        (
            (
                "foundation",
                "java-core",
                "掌握 Java 类型系统、集合与异常边界",
                ("Java", "collections"),
            ),
            ("foundation", "spring-ioc", "理解 Spring IoC、配置与生命周期", ("Spring", "IoC")),
            (
                "foundation",
                "spring-web",
                "实现有明确契约的 Spring Web API",
                ("Spring Boot", "REST"),
            ),
            (
                "practice",
                "data-transactions",
                "使用持久化与事务实现一致业务规则",
                ("JPA", "transaction"),
            ),
            (
                "practice",
                "service-integration",
                "实现有超时和降级的服务调用",
                ("OpenFeign", "resilience"),
            ),
            ("practice", "messaging", "实现可验证的异步消息和幂等消费", ("Kafka", "idempotency")),
            ("production", "testing", "建立分层自动化测试和契约门禁", ("JUnit", "Testcontainers")),
            (
                "production",
                "observability",
                "用日志、指标与追踪定位服务故障",
                ("Micrometer", "tracing"),
            ),
            (
                "production",
                "security-performance",
                "验证服务安全与性能基线",
                ("Spring Security", "performance"),
            ),
            (
                "architecture",
                "distributed-consistency",
                "设计分布式一致性和失败恢复",
                ("distributed transaction", "Saga"),
            ),
            (
                "architecture",
                "service-governance",
                "设计注册发现、配置与流量治理",
                ("Spring Cloud", "governance"),
            ),
            (
                "architecture",
                "platform-architecture",
                "完成可演进的 Java 服务平台架构",
                ("platform engineering", "DDD"),
            ),
        ),
    ),
    (
        "python_ai",
        "Python + FastAPI/AI",
        (
            (
                "foundation",
                "python-core",
                "掌握 Python 类型、数据模型与异常边界",
                ("Python", "typing"),
            ),
            (
                "foundation",
                "fastapi-contract",
                "实现 Pydantic 驱动的 FastAPI 契约",
                ("FastAPI", "Pydantic"),
            ),
            (
                "foundation",
                "model-api",
                "正确处理模型 API、流式响应与错误",
                ("OpenAI compatible", "SSE"),
            ),
            (
                "practice",
                "async-data",
                "实现异步 I/O、数据库事务与任务边界",
                ("asyncio", "SQLAlchemy"),
            ),
            ("practice", "rag", "构建带引用和检索评测的 RAG 闭环", ("RAG", "pgvector")),
            (
                "practice",
                "agents",
                "实现有权限和状态边界的 Agent 工具调用",
                ("LangGraph", "tool calling"),
            ),
            (
                "production",
                "evaluation",
                "建立固定数据集和模型质量评测",
                ("LLM evaluation", "dataset"),
            ),
            (
                "production",
                "observability",
                "记录模型 token、延迟、引用与失败",
                ("LLM observability", "tracing"),
            ),
            (
                "production",
                "security-cost",
                "控制提示注入、敏感数据与模型成本",
                ("prompt injection", "cost control"),
            ),
            (
                "architecture",
                "model-routing",
                "设计多模型路由、降级与容量策略",
                ("model routing", "fallback"),
            ),
            (
                "architecture",
                "knowledge-platform",
                "设计知识摄取、索引与治理平台",
                ("knowledge platform", "retrieval"),
            ),
            (
                "architecture",
                "ai-platform",
                "完成可评测、可审计的 AI 平台架构",
                ("AI platform", "governance"),
            ),
        ),
    ),
    (
        "go",
        "Go",
        (
            ("foundation", "language-core", "掌握 Go 类型、接口与错误模型", ("Go", "interfaces")),
            (
                "foundation",
                "concurrency",
                "正确使用 goroutine、channel 与 context",
                ("goroutine", "context"),
            ),
            (
                "foundation",
                "toolchain",
                "建立模块、测试、Lint 与基准工具链",
                ("go test", "benchmark"),
            ),
            (
                "practice",
                "http-service",
                "实现有契约和中间件的 HTTP 服务",
                ("net/http", "middleware"),
            ),
            (
                "practice",
                "data-access",
                "实现事务化数据访问与连接池治理",
                ("database/sql", "transaction"),
            ),
            (
                "practice",
                "distributed-client",
                "实现有超时、重试和限流的服务客户端",
                ("gRPC", "rate limiting"),
            ),
            (
                "production",
                "testing",
                "验证并发、竞态与集成边界",
                ("race detector", "integration test"),
            ),
            ("production", "profiling", "使用 pprof 定位 CPU、内存和阻塞", ("pprof", "profiling")),
            (
                "production",
                "operations",
                "建立可观测、安全且可回滚的服务",
                ("OpenTelemetry", "deployment"),
            ),
            (
                "architecture",
                "high-concurrency",
                "设计高并发服务的背压与容量",
                ("backpressure", "capacity"),
            ),
            (
                "architecture",
                "distributed-systems",
                "处理分布式一致性与故障模型",
                ("consensus", "distributed systems"),
            ),
            (
                "architecture",
                "cloud-platform",
                "完成 Go 云原生平台架构",
                ("Kubernetes", "platform engineering"),
            ),
        ),
    ),
    (
        "node_ts",
        "Node.js + TypeScript",
        (
            (
                "foundation",
                "typescript",
                "掌握 TypeScript 类型系统和边界验证",
                ("TypeScript", "type system"),
            ),
            ("foundation", "node-runtime", "理解事件循环、流与错误传播", ("Node.js", "event loop")),
            ("foundation", "api-contract", "实现有 Schema 的 Node API", ("Fastify", "OpenAPI")),
            (
                "practice",
                "data-transactions",
                "实现数据访问、事务与迁移",
                ("PostgreSQL", "migration"),
            ),
            ("practice", "events-jobs", "实现幂等事件和可补跑后台任务", ("event driven", "jobs")),
            ("practice", "testing", "建立单元、集成和契约测试", ("Vitest", "contract testing")),
            (
                "production",
                "performance",
                "分析事件循环延迟、内存和吞吐",
                ("profiling", "performance"),
            ),
            ("production", "security", "验证鉴权、输入和供应链安全", ("OWASP", "supply chain")),
            (
                "production",
                "observability",
                "建立日志、指标、追踪和发布门禁",
                ("OpenTelemetry", "CI"),
            ),
            (
                "architecture",
                "service-boundaries",
                "划分模块与服务演进边界",
                ("modular monolith", "DDD"),
            ),
            (
                "architecture",
                "event-architecture",
                "设计可靠事件驱动和一致性策略",
                ("event sourcing", "outbox"),
            ),
            (
                "architecture",
                "platform",
                "完成 TypeScript 服务平台架构",
                ("platform engineering", "governance"),
            ),
        ),
    ),
    (
        "algorithms",
        "数据结构与算法",
        (
            ("foundation", "complexity", "分析时间和空间复杂度", ("complexity", "Big O")),
            ("foundation", "arrays", "使用数组和双指针解决边界问题", ("array", "two pointers")),
            (
                "foundation",
                "linked-lists",
                "实现链表操作并验证指针不变量",
                ("linked list", "pointer"),
            ),
            ("foundation", "stacks-queues", "用栈和队列建模顺序约束", ("stack", "queue")),
            ("foundation", "hashing", "使用哈希结构优化查找和计数", ("hash map", "set")),
            (
                "foundation",
                "binary-search",
                "为单调空间实现无越界二分",
                ("binary search", "boundary"),
            ),
            ("practice", "trees", "实现树遍历并维护递归不变量", ("tree", "traversal")),
            ("practice", "heaps", "使用堆解决动态 Top K 问题", ("heap", "priority queue")),
            ("practice", "graphs", "使用 BFS 和 DFS 处理图可达性", ("graph", "BFS")),
            ("practice", "sorting", "比较排序算法和稳定性边界", ("sorting", "stability")),
            ("practice", "recursion", "用递归和分治缩小问题规模", ("recursion", "divide conquer")),
            ("practice", "backtracking", "用剪枝控制回溯搜索空间", ("backtracking", "pruning")),
            ("production", "greedy", "证明贪心选择的正确性边界", ("greedy", "proof")),
            (
                "production",
                "dynamic-programming",
                "定义状态和转移解决优化问题",
                ("dynamic programming", "state"),
            ),
            (
                "production",
                "shortest-path",
                "选择合适的最短路径算法",
                ("Dijkstra", "shortest path"),
            ),
            ("production", "union-find", "用并查集维护动态连通性", ("union find", "connectivity")),
            (
                "production",
                "string-matching",
                "实现并验证高效字符串匹配",
                ("KMP", "string matching"),
            ),
            (
                "production",
                "range-query",
                "使用树状数组或线段树处理区间查询",
                ("segment tree", "range query"),
            ),
            (
                "architecture",
                "algorithm-selection",
                "根据约束选择算法和数据结构",
                ("algorithm design", "tradeoff"),
            ),
            (
                "architecture",
                "concurrency-structures",
                "分析并发数据结构的正确性",
                ("concurrent data structure", "linearizability"),
            ),
            (
                "architecture",
                "distributed-algorithms",
                "理解一致性、选举和逻辑时钟",
                ("consensus", "logical clock"),
            ),
            (
                "architecture",
                "index-design",
                "把树、哈希和过滤器用于存储索引",
                ("B-tree", "Bloom filter"),
            ),
            (
                "architecture",
                "scheduling",
                "用算法权衡调度公平性和吞吐",
                ("scheduling", "fairness"),
            ),
            (
                "architecture",
                "system-problem",
                "完成从业务约束到算法方案的系统设计",
                ("system algorithm", "optimization"),
            ),
        ),
    ),
)


def _build_v2_catalog() -> CurriculumCatalog:
    tracks: list[CurriculumTrack] = []
    for track_key, label, definitions in V2_TRACK_TOPICS:
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
                    deliverable_kinds=("commit", "report", "answer"),
                    acceptance_types=("command", "inspection", "answer"),
                    radar_keywords=keywords,
                )
            )
            previous = key
        weight = 0.0 if track_key == "algorithms" else 0.25
        tracks.append(CurriculumTrack(track_key, label, weight, tuple(nodes)))
    return CurriculumCatalog("v2", tuple(tracks))


CURRICULUM = _build_v2_catalog()
