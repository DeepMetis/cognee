
import os
import pytest

@pytest.fixture(autouse=True, scope="session")
def copy_cognee_db_to_target_location():
    os.system("mv cognee/tests/integration/run_toy_tasks/data/cognee_db cognee/.cognee_system/databases")
