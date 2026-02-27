"""
Graph Service — Neo4j Ontology Management & Query.

Full ontology graph:
  (:Method)-[:APPLIED_IN]->(:Case)
  (:Director)-[:PREFERS {weight}]->(:Method)
  (:Case)-[:SIMILAR_TO {score, reason}]-(:Case)
  (:Method)-[:RELATED_TO {reason}]-(:Method)
  (:Case)-[:IN_INDUSTRY]->(:Industry)

Provides:
- Full graph build from PostgreSQL data (seed_full_graph)
- Query methods: traversal, path finding, subgraph extraction
- Graph statistics & health monitoring
"""
from __future__ import annotations

import logging
from typing import Any

from app.db.database import get_neo4j_driver

logger = logging.getLogger(__name__)


class GraphService:
    def __init__(self):
        self.driver = get_neo4j_driver()

    # ══════════════════════════════════════════════════════════════════
    #  GRAPH BUILD — 전체 온톨로지 구축
    # ══════════════════════════════════════════════════════════════════

    def create_constraints(self):
        """Create uniqueness constraints and indexes for performance."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Method) REQUIRE m.method_name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Case) REQUIRE c.case_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Director) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (c:Case) ON (c.industry)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Case) ON (c.budget_tier)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Method) ON (m.category)",
        ]
        with self.driver.session() as session:
            for q in constraints:
                try:
                    session.run(q)
                except Exception as e:
                    logger.warning(f"Constraint skip: {e}")
        logger.info("Neo4j constraints/indexes created")

    def seed_methods(self, methods: list[dict]) -> int:
        """Upsert Method nodes with full properties."""
        count = 0
        with self.driver.session() as session:
            for m in methods:
                session.run(
                    """
                    MERGE (method:Method {method_name: $method_name})
                    SET method.category       = $category,
                        method.sig_question   = $sig_question,
                        method.core_principle = $core_principle,
                        method.apply_when     = $apply_when,
                        method.avoid_when     = $avoid_when,
                        method.risk_factors   = $risk_factors,
                        method.pg_id          = $pg_id
                    """,
                    method_name=m["method_name"],
                    category=m.get("category"),
                    sig_question=m.get("signature_question"),
                    core_principle=m.get("core_principle"),
                    apply_when=m.get("apply_when"),
                    avoid_when=m.get("avoid_when"),
                    risk_factors=m.get("risk_factors"),
                    pg_id=m.get("id"),
                )
                count += 1
        return count

    def seed_cases(self, cases: list[dict]) -> int:
        """Upsert Case nodes + Industry nodes + APPLIED_IN edges."""
        case_count = 0
        edge_count = 0
        with self.driver.session() as session:
            for c in cases:
                case_id = c["case_id"]

                # Case node
                session.run(
                    """
                    MERGE (case:Case {case_id: $case_id})
                    SET case.brand          = $brand,
                        case.campaign_title = $title,
                        case.industry       = $industry,
                        case.target         = $target,
                        case.problem        = $problem,
                        case.insight        = $insight,
                        case.solution       = $solution,
                        case.outcomes       = $outcomes,
                        case.budget_tier    = $budget_tier,
                        case.key_channels   = $channels
                    """,
                    case_id=case_id,
                    brand=c.get("brand"),
                    title=c.get("campaign_title"),
                    industry=c.get("industry"),
                    target=c.get("target"),
                    problem=c.get("problem"),
                    insight=c.get("insight"),
                    solution=c.get("solution"),
                    outcomes=c.get("outcomes"),
                    budget_tier=c.get("budget_tier"),
                    channels=c.get("key_channels"),
                )
                case_count += 1

                # Industry node + edge
                industry = c.get("industry")
                if industry:
                    session.run(
                        """
                        MERGE (i:Industry {name: $industry})
                        WITH i
                        MATCH (case:Case {case_id: $case_id})
                        MERGE (case)-[:IN_INDUSTRY]->(i)
                        """,
                        industry=industry,
                        case_id=case_id,
                    )

                # APPLIED_IN edges
                applied = c.get("applied_methods") or []
                for method_name in applied:
                    method_name = method_name.strip()
                    if not method_name:
                        continue
                    session.run(
                        """
                        MERGE (m:Method {method_name: $method_name})
                        WITH m
                        MATCH (case:Case {case_id: $case_id})
                        MERGE (m)-[:APPLIED_IN]->(case)
                        """,
                        method_name=method_name,
                        case_id=case_id,
                    )
                    edge_count += 1

        logger.info(f"Seeded {case_count} cases, {edge_count} APPLIED_IN edges")
        return case_count

    def seed_directors(self, directors: list[dict]) -> int:
        """Upsert Director nodes."""
        count = 0
        with self.driver.session() as session:
            for d in directors:
                session.run(
                    """
                    MERGE (dir:Director {name: $name})
                    SET dir.tagline       = $tagline,
                        dir.archetype     = $archetype,
                        dir.description   = $description,
                        dir.w_logic       = $w_logic,
                        dir.w_emotion     = $w_emotion,
                        dir.w_culture     = $w_culture,
                        dir.w_action      = $w_action,
                        dir.w_performance = $w_performance
                    """,
                    name=d["name"],
                    tagline=d.get("tagline"),
                    archetype=d.get("archetype"),
                    description=d.get("description"),
                    w_logic=d.get("w_logic", 0),
                    w_emotion=d.get("w_emotion", 0),
                    w_culture=d.get("w_culture", 0),
                    w_action=d.get("w_action", 0),
                    w_performance=d.get("w_performance", 0),
                )
                count += 1
        return count

    def build_director_method_preferences(self, directors: list[dict], methods: list[dict]) -> int:
        """
        Build Director-[:PREFERS]->Method edges based on weight heuristics.

        Logic: Method.category의 특성과 Director의 weight 프로필을 매칭하여
        각 Director가 선호하는 Method에 가중치를 부여.
        """
        # Category → 관련 weight dimension 매핑
        CATEGORY_WEIGHT_MAP = {
            "감성소구": "w_emotion",
            "사회적증거": "w_culture",
            "문제해결": "w_logic",
            "대비효과": "w_logic",
            "스토리텔링": "w_emotion",
            "행동유도": "w_action",
            "파격적접근": "w_culture",
            "반복/일관성": "w_performance",
            "데이터기반": "w_performance",
            "트렌드활용": "w_culture",
            "브랜딩": "w_emotion",
            "퍼포먼스": "w_performance",
        }

        edge_count = 0
        with self.driver.session() as session:
            for d in directors:
                for m in methods:
                    category = m.get("category", "")
                    weight_key = None
                    for cat_keyword, wk in CATEGORY_WEIGHT_MAP.items():
                        if cat_keyword in category:
                            weight_key = wk
                            break

                    if not weight_key:
                        weight_key = "w_logic"  # default

                    weight_value = d.get(weight_key, 0)
                    if weight_value <= 0:
                        continue

                    # Normalize weight to 0~1 scale (assuming max weight ~5)
                    normalized = min(weight_value / 5.0, 1.0)
                    if normalized < 0.2:
                        continue  # Skip weak preferences

                    session.run(
                        """
                        MATCH (dir:Director {name: $dir_name})
                        MATCH (m:Method {method_name: $method_name})
                        MERGE (dir)-[r:PREFERS]->(m)
                        SET r.weight = $weight,
                            r.dimension = $dimension
                        """,
                        dir_name=d["name"],
                        method_name=m["method_name"],
                        weight=round(normalized, 3),
                        dimension=weight_key,
                    )
                    edge_count += 1

        logger.info(f"Built {edge_count} Director-PREFERS->Method edges")
        return edge_count

    def build_case_similarity(self) -> int:
        """
        Build Case-[:SIMILAR_TO]-Case edges based on shared attributes.

        Similarity score computed from:
        - Same industry (+0.3)
        - Same budget_tier (+0.2)
        - Shared applied_methods (Jaccard * 0.5)
        """
        count = 0
        with self.driver.session() as session:
            # Get all case pairs that share at least one Method
            result = session.run(
                """
                MATCH (c1:Case)<-[:APPLIED_IN]-(m:Method)-[:APPLIED_IN]->(c2:Case)
                WHERE c1.case_id < c2.case_id
                WITH c1, c2, collect(DISTINCT m.method_name) AS shared_methods
                RETURN c1.case_id AS id1, c2.case_id AS id2,
                       c1.industry AS ind1, c2.industry AS ind2,
                       c1.budget_tier AS bud1, c2.budget_tier AS bud2,
                       shared_methods,
                       size(shared_methods) AS shared_count
                """
            )

            for r in result:
                score = 0.0
                reasons = []

                # Shared methods (Jaccard approximation)
                shared_count = r["shared_count"]
                if shared_count > 0:
                    score += min(shared_count * 0.15, 0.5)
                    reasons.append(f"shared_methods:{shared_count}")

                # Same industry
                if r["ind1"] and r["ind2"] and r["ind1"] == r["ind2"]:
                    score += 0.3
                    reasons.append("same_industry")

                # Same budget tier
                if r["bud1"] and r["bud2"] and r["bud1"] == r["bud2"]:
                    score += 0.2
                    reasons.append("same_budget")

                if score < 0.2:
                    continue  # Skip weak similarities

                session.run(
                    """
                    MATCH (c1:Case {case_id: $id1})
                    MATCH (c2:Case {case_id: $id2})
                    MERGE (c1)-[r:SIMILAR_TO]-(c2)
                    SET r.score = $score,
                        r.reason = $reason,
                        r.shared_methods = $shared_methods
                    """,
                    id1=r["id1"],
                    id2=r["id2"],
                    score=round(score, 3),
                    reason="|".join(reasons),
                    shared_methods=r["shared_methods"],
                )
                count += 1

        logger.info(f"Built {count} Case-SIMILAR_TO-Case edges")
        return count

    def build_method_relatedness(self) -> int:
        """
        Build Method-[:RELATED_TO]-Method edges based on co-occurrence in cases.
        Two methods that are frequently applied together in cases are related.
        """
        count = 0
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (m1:Method)-[:APPLIED_IN]->(c:Case)<-[:APPLIED_IN]-(m2:Method)
                WHERE m1.method_name < m2.method_name
                WITH m1, m2, collect(DISTINCT c.case_id) AS shared_cases
                WHERE size(shared_cases) >= 1
                RETURN m1.method_name AS name1, m2.method_name AS name2,
                       shared_cases, size(shared_cases) AS co_count
                """
            )
            for r in result:
                session.run(
                    """
                    MATCH (m1:Method {method_name: $name1})
                    MATCH (m2:Method {method_name: $name2})
                    MERGE (m1)-[rel:RELATED_TO]-(m2)
                    SET rel.co_occurrence = $co_count,
                        rel.shared_cases = $cases
                    """,
                    name1=r["name1"],
                    name2=r["name2"],
                    co_count=r["co_count"],
                    cases=r["shared_cases"],
                )
                count += 1

        logger.info(f"Built {count} Method-RELATED_TO-Method edges")
        return count

    def clear_graph(self):
        """Remove all nodes and relationships."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Graph cleared")

    # ══════════════════════════════════════════════════════════════════
    #  QUERY METHODS — 온톨로지 기반 검색
    # ══════════════════════════════════════════════════════════════════

    def find_methods_for_case(self, case_id: str) -> list[dict[str, Any]]:
        """Find all Methods applied in a given Case."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (m:Method)-[:APPLIED_IN]->(c:Case {case_id: $case_id})
                RETURN m.method_name AS method_name,
                       m.category AS category,
                       m.core_principle AS core_principle,
                       m.pg_id AS pg_id
                """,
                case_id=case_id,
            )
            return [dict(r) for r in result]

    def find_cases_by_method(self, method_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find Cases that applied a given Method."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (m:Method {method_name: $method_name})-[:APPLIED_IN]->(c:Case)
                RETURN c.case_id AS case_id,
                       c.brand AS brand,
                       c.campaign_title AS campaign_title,
                       c.industry AS industry,
                       c.problem AS problem,
                       c.insight AS insight,
                       c.solution AS solution
                LIMIT $limit
                """,
                method_name=method_name,
                limit=limit,
            )
            return [dict(r) for r in result]

    def find_preferred_methods(self, director_archetype: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find Methods preferred by a Director archetype, ordered by weight."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (d:Director {archetype: $archetype})-[r:PREFERS]->(m:Method)
                RETURN m.method_name AS method_name,
                       m.category AS category,
                       m.core_principle AS core_principle,
                       r.weight AS weight,
                       r.dimension AS dimension
                ORDER BY r.weight DESC
                LIMIT $limit
                """,
                archetype=director_archetype,
                limit=limit,
            )
            return [dict(r) for r in result]

    def find_similar_cases(self, case_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find Cases similar to a given Case."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c1:Case {case_id: $case_id})-[r:SIMILAR_TO]-(c2:Case)
                RETURN c2.case_id AS case_id,
                       c2.brand AS brand,
                       c2.campaign_title AS campaign_title,
                       c2.industry AS industry,
                       c2.problem AS problem,
                       r.score AS score,
                       r.reason AS reason
                ORDER BY r.score DESC
                LIMIT $limit
                """,
                case_id=case_id,
                limit=limit,
            )
            return [dict(r) for r in result]

    def find_related_methods(self, method_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find Methods related to a given Method (co-occurrence)."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (m1:Method {method_name: $method_name})-[r:RELATED_TO]-(m2:Method)
                RETURN m2.method_name AS method_name,
                       m2.category AS category,
                       r.co_occurrence AS co_occurrence,
                       r.shared_cases AS shared_cases
                ORDER BY r.co_occurrence DESC
                LIMIT $limit
                """,
                method_name=method_name,
                limit=limit,
            )
            return [dict(r) for r in result]

    def find_strategy_path(
        self, from_method: str, to_case: str, max_depth: int = 4
    ) -> list[dict[str, Any]]:
        """Find shortest path from a Method to a Case through the graph."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = shortestPath(
                    (m:Method {method_name: $from_method})-[*1..$depth]-(c:Case {case_id: $to_case})
                )
                RETURN [n IN nodes(path) |
                    CASE
                        WHEN 'Method' IN labels(n) THEN {type: 'Method', name: n.method_name}
                        WHEN 'Case' IN labels(n) THEN {type: 'Case', name: n.case_id, brand: n.brand}
                        WHEN 'Director' IN labels(n) THEN {type: 'Director', name: n.name}
                        WHEN 'Industry' IN labels(n) THEN {type: 'Industry', name: n.name}
                        ELSE {type: 'Unknown'}
                    END
                ] AS path_nodes,
                length(path) AS path_length
                """,
                from_method=from_method,
                to_case=to_case,
                depth=max_depth,
            )
            paths = [dict(r) for r in result]
            return paths

    def get_method_case_subgraph(self, method_name: str) -> dict[str, Any]:
        """Get full subgraph around a Method: cases, related methods, directors."""
        with self.driver.session() as session:
            # Cases using this method
            cases_result = session.run(
                """
                MATCH (m:Method {method_name: $name})-[:APPLIED_IN]->(c:Case)
                RETURN c.case_id AS case_id, c.brand AS brand,
                       c.campaign_title AS title, c.industry AS industry
                """,
                name=method_name,
            )
            cases = [dict(r) for r in cases_result]

            # Related methods
            related_result = session.run(
                """
                MATCH (m:Method {method_name: $name})-[r:RELATED_TO]-(m2:Method)
                RETURN m2.method_name AS method_name, m2.category AS category,
                       r.co_occurrence AS co_occurrence
                ORDER BY r.co_occurrence DESC LIMIT 5
                """,
                name=method_name,
            )
            related = [dict(r) for r in related_result]

            # Directors preferring this method
            directors_result = session.run(
                """
                MATCH (d:Director)-[r:PREFERS]->(m:Method {method_name: $name})
                RETURN d.name AS director, d.archetype AS archetype,
                       r.weight AS weight
                ORDER BY r.weight DESC
                """,
                name=method_name,
            )
            directors = [dict(r) for r in directors_result]

            return {
                "method": method_name,
                "cases": cases,
                "related_methods": related,
                "preferred_by_directors": directors,
            }

    # ══════════════════════════════════════════════════════════════════
    #  GRAPH STATISTICS — 모니터링
    # ══════════════════════════════════════════════════════════════════

    def get_stats(self) -> dict[str, Any]:
        """Return graph node/relationship counts."""
        with self.driver.session() as session:
            stats = {}
            for label in ["Method", "Case", "Director", "Industry"]:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                stats[f"{label.lower()}_nodes"] = result.single()["cnt"]

            for rel_type in ["APPLIED_IN", "PREFERS", "SIMILAR_TO", "RELATED_TO", "IN_INDUSTRY"]:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
                stats[f"{rel_type.lower()}_edges"] = result.single()["cnt"]

            return stats
