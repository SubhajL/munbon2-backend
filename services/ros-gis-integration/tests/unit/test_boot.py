import importlib
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[2]


def test_ros_boots_with_declared_networkx() -> None:
    requirements = (SERVICE_ROOT / "requirements.txt").read_text().splitlines()

    assert "networkx==3.2.1" in requirements

    optimizer_module = importlib.import_module("services.delivery_optimizer")
    main_module = importlib.import_module("main")

    assert optimizer_module.nx.DiGraph().is_directed()
    assert main_module.app.title == "ROS/GIS Integration Service"
