"""Exercise real stdio framing and actionable errors for legacy protocol clients."""
import asyncio
from contextlib import asynccontextmanager
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

import pytest

pytest.importorskip("mcp")
if tuple(map(int, version("mcp").split(".")[:2])) < (2, 2):
    pytest.skip("Requires the project's MCP 2.2 extra", allow_module_level=True)
from mcp import Client, StdioServerParameters


@asynccontextmanager
async def stdio_project_client(stderr):
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "tuba.mcp.server"],
                                      cwd=str(Path(__file__).resolve().parents[1]), env=dict(os.environ))
    from mcp.client.stdio import stdio_client
    async with Client(stdio_client(parameters, errlog=stderr), mode="legacy", read_timeout_seconds=30) as client:
        yield client


def tool_payload(result):
    return json.loads(next(item.text for item in result.content if item.type == "text"))


def is_error(result):
    return getattr(result, "is_error", getattr(result, "isError", False))


def test_stdio_tools_keep_schema_source_and_error_details(tmp_path, caplog):
    root = tmp_path / "project with space"
    root.mkdir()
    source = root / "model.py"
    source.write_text('from tuba import Model\nprint("project output")\nmodel = Model("stdio")\n', encoding="utf-8")
    original = source.read_bytes()

    async def check():
        with (tmp_path / "server-stderr.log").open("w", encoding="utf-8") as stderr:
            async with stdio_project_client(stderr) as client:
                tools = await client.list_tools()
                assert {"inspect_project_package", "generate_mesh", "run_mesh_convergence"} <= {tool.name for tool in tools.tools}
                tool = next(tool for tool in tools.tools if tool.name == "init_session")
                schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", None))
                assert "file_path" in schema["properties"]
                missing = await client.call_tool("inspect_model", {})
                assert is_error(missing) and "init_session" in missing.content[0].text
                initialized = await client.call_tool("init_session", {"file_path": str(source)})
                assert not is_error(initialized)
                assert source.read_bytes() == original
                inspected = await client.call_tool("inspect_model", {})
                assert tool_payload(inspected)["project_name"] == "stdio"
                archive = tmp_path / "shared.tubaproject"
                exported = await client.call_tool("export_project", {"output_path": str(archive)})
                assert not is_error(exported), exported
                assert tool_payload(exported)["include_results"] is False
                opened = await client.call_tool("open_project_package", {"file_path": str(archive), "destination": str(tmp_path / "opened")})
                assert not is_error(opened), opened
                assert (tmp_path / "opened" / "model.py").read_bytes() == original
                tgz = tmp_path / "shared.tgz"
                exported_tgz = await client.call_tool("export_project", {"output_path": str(tgz)})
                assert not is_error(exported_tgz), exported_tgz
                inspected_tgz = await client.call_tool("inspect_project_package", {"file_path": str(tgz)})
                assert not is_error(inspected_tgz), inspected_tgz
                assert tool_payload(inspected_tgz)["include_results"] is False
                opened_tgz = await client.call_tool("open_project_package", {"file_path": str(tgz), "destination": str(tmp_path / "opened-tgz")})
                assert not is_error(opened_tgz), opened_tgz
                assert (tmp_path / "opened-tgz" / "model.py").read_bytes() == original
                # Return to the original session for its outside-edit checks.
                await client.call_tool("init_session", {"file_path": str(source)})
                source.write_text("invalid Python!\n", encoding="utf-8")
                invalid_read = await client.call_tool("inspect_model", {})
                assert is_error(invalid_read) and "SyntaxError" in invalid_read.content[0].text
                refused = await client.call_tool("solve_model", {})
                assert is_error(refused)
                assert '"error_type": "SyntaxError"' in refused.content[0].text

    asyncio.run(check())
    assert source.read_text(encoding="utf-8") == "invalid Python!\n"
    assert "Failed to parse" not in caplog.text


def test_stdio_generates_real_unsolved_mesh(tmp_path):
    from tests.test_project_mesh import SCRIPT
    root = tmp_path / "native project"
    root.mkdir()
    (root / "model.py").write_text(SCRIPT, encoding="utf-8")
    async def check():
        with (tmp_path / "native-server.log").open("w", encoding="utf-8") as stderr:
            async with stdio_project_client(stderr) as client:
                initialized = await client.call_tool("init_session", {"file_path": str(root / "model.py")})
                assert not is_error(initialized), initialized
                result = await client.call_tool("generate_mesh", {"output_dir": str(tmp_path / "native mesh")})
                assert not is_error(result), result
                record = tool_payload(result)
                assert record["result_status"] == "mesh_only"
                assert (Path(record["directory"]) / "mesh.mail").is_file()
                assert not (root / "evidence").exists()
    asyncio.run(check())
