""" FalcorDB Adapter for Graph Database"""
import json
import logging
from typing import Optional, Any, List, Dict
from contextlib import asynccontextmanager


from falkordb.asyncio import FalkorDB
from cognee.infrastructure.databases.graph.graph_db_interface import GraphDBInterface

logger = logging.getLogger("FalcorDBAdapter")

class FalcorDBAdapter(GraphDBInterface):
    def __init__(
        self,
        graph_database_url: str,
        graph_database_username: str,
        graph_database_password: str,
        graph_database_port: int,
        driver: Optional[Any] = None,
        graph_name: str = "DefaultGraph",
    ):
        self.driver = FalkorDB(
            host = graph_database_url,
            port = graph_database_port)
        self.graph_name = graph_name



    async def query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        try:
                selected_graph = self.driver.select_graph(self.graph_name)

                result = await selected_graph.query(query)
                return result.result_set

        except Exception as error:
            logger.error("Falkor query error: %s", error, exc_info = True)
            raise error

    async def graph(self):
        return  self.driver

    async def add_node(self, node_id: str, node_properties: Dict[str, Any] = None):
        node_id = node_id.replace(":", "_")

        serialized_properties = self.serialize_properties(node_properties)

        if "name" not in serialized_properties:
            serialized_properties["name"] = node_id

        # serialized_properties["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # serialized_properties["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # properties = ", ".join(f"{property_name}: ${property_name}" for property_name in serialized_properties.keys())

        query = f"""MERGE (node:`{node_id}` {{id: $node_id}})
                ON CREATE SET node += $properties
                RETURN ID(node) AS internal_id, node.id AS nodeId"""

        params = {
            "node_id": node_id,
            "properties": serialized_properties,
        }

        return await self.query(query, params)

    async def add_nodes(self, nodes: list[tuple[str, dict[str, Any]]]) -> None:
        for node in nodes:
            node_id, node_properties = node
            node_id = node_id.replace(":", "_")

            await self.add_node(
                node_id = node_id,
                node_properties = node_properties,
            )



    async def extract_node_description(self, node_id: str):
        query = """MATCH (n)-[r]->(m)
                    WHERE n.id = $node_id
                    AND NOT m.id CONTAINS 'DefaultGraphModel'
                    RETURN m
                    """

        result = await self.query(query, dict(node_id = node_id))

        descriptions = []

        for node in result:
            # Assuming 'm' is a consistent key in your data structure
            attributes = node.get("m", {})

            # Ensure all required attributes are present
            if all(key in attributes for key in ["id", "layer_id", "description"]):
                descriptions.append({
                    "id": attributes["id"],
                    "layer_id": attributes["layer_id"],
                    "description": attributes["description"],
                })

        return descriptions

    async def get_layer_nodes(self):
        query = """MATCH (node) WHERE node.layer_id IS NOT NULL
        RETURN node"""

        return [result["node"] for result in (await self.query(query))]

    async def extract_node(self, node_id: str):
        results = self.extract_nodes([node_id])

        return results[0] if len(results) > 0 else None

    async def extract_nodes(self, node_ids: List[str]):
        query = """
        UNWIND $node_ids AS id
        MATCH (node {id: id})
        RETURN node"""

        params = {
            "node_ids": node_ids
        }

        results = await self.query(query, params)

        return results

    async def delete_node(self, node_id: str):
        node_id = id.replace(":", "_")

        query = f"MATCH (node:`{node_id}` {{id: $node_id}}) DETACH DELETE n"
        params = { "node_id": node_id }

        return await self.query(query, params)

    async def add_edge(self, from_node: str, to_node: str, relationship_name: str, edge_properties: Optional[Dict[str, Any]] = {}):
        serialized_properties = self.serialize_properties(edge_properties)
        from_node = from_node.replace(":", "_")
        to_node = to_node.replace(":", "_")

        query = f"""MATCH (from_node:`{from_node}` {{id: $from_node}}), (to_node:`{to_node}` {{id: $to_node}})
                MERGE (from_node)-[r:`{relationship_name}`]->(to_node)
                SET r += $properties
                RETURN r"""

        params = {
            "from_node": from_node,
            "to_node": to_node,
            "properties": serialized_properties
        }

        return await self.query(query, params)


    async def add_edges(self, edges: list[tuple[str, str, str, dict[str, Any]]]) -> None:
        # edges_data = []

        for edge in edges:
            from_node, to_node, relationship_name, edge_properties = edge
            from_node = from_node.replace(":", "_")
            to_node = to_node.replace(":", "_")

            await self.add_edge(
                from_node = from_node,
                to_node = to_node,
                relationship_name = relationship_name,
                edge_properties = edge_properties
            )



    async def filter_nodes(self, search_criteria):
        query = f"""MATCH (node)
                WHERE node.id CONTAINS '{search_criteria}'
                RETURN node"""


        return await self.query(query)


    async def delete_graph(self):
        query = """MATCH (node)
                DETACH DELETE node;"""

        return await self.query(query)

    def serialize_properties(self, properties = dict()):
        return {
            property_key: json.dumps(property_value)
            if isinstance(property_value, (dict, list))
            else property_value for property_key, property_value in properties.items()
        }
