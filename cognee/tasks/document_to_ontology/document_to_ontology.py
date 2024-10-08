""" This module contains the TopologyEngine class which is responsible for adding graph topology from a JSON or CSV file. """

from cognee.infrastructure.databases.graph import get_graph_config
from cognee.modules.cognify.config import get_cognify_config
import csv
import json
import logging
from typing import Any, Dict, List, Optional, Union, Type

import aiofiles
import pandas as pd
from pydantic import BaseModel

from cognee.infrastructure.data.chunking.config import get_chunk_config
from cognee.infrastructure.data.chunking.get_chunking_engine import get_chunk_engine
from cognee.infrastructure.databases.graph.get_graph_engine import get_graph_engine
from cognee.infrastructure.files.utils.extract_text_from_file import extract_text_from_file
from cognee.infrastructure.files.utils.guess_file_type import guess_file_type, FileTypeException
from cognee.tasks.document_to_ontology.models.models import NodeModel

logger = logging.getLogger("topology")

from cognee.infrastructure.databases.graph.config import get_graph_config


from typing import Type
from pydantic import BaseModel
from cognee.infrastructure.llm.prompts import read_query_prompt
from cognee.infrastructure.llm.get_llm_client import get_llm_client


async def extract_topology(content: str, response_model: Type[BaseModel]):
    llm_client = get_llm_client()

    system_prompt = read_query_prompt("extract_topology.txt")

    llm_output = await llm_client.acreate_structured_output(content, system_prompt, response_model)

    return llm_output.model_dump()


async def infer_data_topology(content: str, graph_topology=None):
    if graph_topology is None:
        graph_config = get_graph_config()
        graph_topology = graph_config.graph_topology
    try:
        return (await extract_topology(
            content,
            graph_topology
        ))
    except Exception as error:
        logger.error("Error extracting topology from content: %s", error, exc_info = True)
        raise error

class TopologyEngine:
    def __init__(self, infer:bool) -> None:
        self.models: Dict[str, Type[BaseModel]] = {}
        self.infer = infer

    async def flatten_model(self, model: NodeModel, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Flatten the model to a dictionary."""
        result = model.dict()
        result["parent_id"] = parent_id
        if model.default_relationship:
            result.update({
                "relationship_type": model.default_relationship.type,
                "relationship_source": model.default_relationship.source,
                "relationship_target": model.default_relationship.target
            })
        return result

    async def recursive_flatten(self, items: Union[List[Dict[str, Any]], Dict[str, Any]], parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recursively flatten the items.  """
        flat_list = []

        if isinstance(items, list):
            for item in items:
                flat_list.extend(await self.recursive_flatten(item, parent_id))
        elif isinstance(items, dict):
            model = NodeModel.parse_obj(items)
            flat_list.append(await self.flatten_model(model, parent_id))
            for child in model.children:
                flat_list.extend(await self.recursive_flatten(child, model.node_id))
        return flat_list

    async def load_data(self, file_path: str) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Load data from a JSON or CSV file."""
        try:
            if file_path.endswith(".json"):
                async with aiofiles.open(file_path, mode="r") as f:
                    data = await f.read()
                    return json.loads(data)
            elif file_path.endswith(".csv"):
                async with aiofiles.open(file_path, mode="r") as f:
                    content = await f.read()
                    reader = csv.DictReader(content.splitlines())
                    return list(reader)
            else:
                raise ValueError("Unsupported file format")
        except Exception as e:
            raise RuntimeError(f"Failed to load data from {file_path}: {e}")

    async def add_graph_topology(self, file_path: str = None, files: list = None):
        """Add graph topology from a JSON or CSV file."""
        if self.infer:
            initial_chunks_and_ids = []

            chunk_config = get_chunk_config()
            chunk_engine = get_chunk_engine()
            chunk_strategy = chunk_config.chunk_strategy

            for base_file in files:
                with open(base_file["file_path"], "rb") as file:
                    try:
                        file_type = guess_file_type(file)
                        text = extract_text_from_file(file, file_type)

                        subchunks, chunks_with_ids = chunk_engine.chunk_data(chunk_strategy, text, chunk_config.chunk_size,
                                                                chunk_config.chunk_overlap)

                        if chunks_with_ids[0][0] == 1:
                            initial_chunks_and_ids.append({base_file["id"]: chunks_with_ids})

                    except FileTypeException:
                        logger.warning("File (%s) has an unknown file type. We are skipping it.", file["id"])


            topology = await infer_data_topology(str(initial_chunks_and_ids))
            graph_client = await get_graph_engine()

            await graph_client.add_nodes([(node["id"], node) for node in topology["nodes"]])
            await graph_client.add_edges((
                edge["source_node_id"],
                edge["target_node_id"],
                edge["relationship_name"],
                dict(relationship_name = edge["relationship_name"]),
            ) for edge in topology["edges"])

        else:
            dataset_level_information = files[0][1]

            # Extract the list of valid IDs from the explanations
            valid_ids = {item["id"] for item in dataset_level_information}
            try:
                data = await self.load_data(file_path)
                flt_topology = await self.recursive_flatten(data)
                df = pd.DataFrame(flt_topology)
                graph_client = await get_graph_engine()

                for _, row in df.iterrows():
                    node_data = row.to_dict()
                    node_id = node_data.pop("node_id", None)
                    if node_id in valid_ids:
                        await graph_client.add_node(node_id, node_data)
                    if node_id not in valid_ids:
                        raise ValueError(f"Node ID {node_id} not found in the dataset")
                    if pd.notna(row.get("relationship_source")) and pd.notna(row.get("relationship_target")):
                        await graph_client.add_edge(row["relationship_source"], row["relationship_target"], relationship_name=row["relationship_type"])

                return
            except Exception as e:
                raise RuntimeError(f"Failed to add graph topology from {file_path}: {e}") from e





async def document_to_ontology(data, root_node_id):
    cognee_config = get_cognify_config()
    graph_config = get_graph_config()
    root_node_id = None
    if graph_config.infer_graph_topology and graph_config.graph_topology_task:
        topology_engine = TopologyEngine(infer=graph_config.infer_graph_topology)
        root_node_id = await topology_engine.add_graph_topology(files=data)
    elif graph_config.infer_graph_topology and not graph_config.infer_graph_topology:

        topology_engine = TopologyEngine(infer=graph_config.infer_graph_topology)
        await topology_engine.add_graph_topology(graph_config.topology_file_path)
    elif not graph_config.graph_topology_task:
        root_node_id = "ROOT"

    yield (data, root_node_id)