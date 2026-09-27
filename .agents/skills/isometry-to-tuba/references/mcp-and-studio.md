# MCP and Studio procedure

Use the active checkout's tool schemas and implementation as authority. The following entry points are verified against Tuba v4; inspect them again if the checkout differs:

- `tuba/mcp/server.py`: `init_session`, `inspect_model`, `check_clashes`, `verify_model`, `solve_model`.
- `tuba/model.py`: `Support.restraint()` and native fitting/support records.
- `tuba/project/script.py`: authored-script loading/preservation.
- `tuba/cli_studio.py`: project launch and actual server URL.

## Connect

Discover an existing Tuba MCP connection first. Otherwise launch the local stdio server through an MCP client using the project's Python environment:

```text
<project-python> -m tuba.mcp.server
```

Set the process working directory to the intended checkout and ensure Python imports Tuba from that checkout. Use an absolute interpreter path where environments differ. In Windows environments with the documented nested-uv NumPy DLL issue, use the established environment directly or `UV_NO_SYNC=1` with `uv run`; verify the import before launching.

Starting the process alone does not verify MCP. Perform the MCP initialization handshake, list tools, call tools through the transport, and check `isError` and the returned payload. If no connected client tools are available, the installed Python MCP SDK provides `mcp.ClientSession`, `mcp.StdioServerParameters` and `mcp.client.stdio.stdio_client` for this fallback. Keep the server's stdout reserved for protocol traffic and close a temporary session after use. Do not silently install dependencies or change global client configuration merely to avoid reporting a blocker.

Check that the selected environment includes the repository's optional `mcp` extra. If importing `mcp` fails, report the missing dependency and use the repository's declared extra when environment setup is authorized. The server module has a fallback decorator for local imports; successfully importing or calling its Python functions does not prove an operational MCP transport.

## Load and inspect

Call `init_session(file_path=<absolute model.py>, load_existing=True)`. Confirm it loaded the expected project and reports the authored-script state. **Initialization can create or synchronize `study.py` beside the model.** For a strictly read-only review, use an owned copy of the project with its relative dependencies, or inspect through an already initialized session. Loading Python also executes that project's code; only execute source within the user's authorized scope.

Call `inspect_model()` to obtain elements, routes, groups, actual supports and load cases. Reconcile these entities with the drawing table. Its support count does not establish correct directions, stiffnesses, source coverage or boundary-condition completeness. For facts omitted by a tool response, inspect the authored model/current API separately and identify that evidence as a local check.

After editing `model.py`, reload with `init_session(..., load_existing=True)` before further checks. An existing MCP session holds an in-memory model and may otherwise inspect stale state. Keep authored scripts procedural; do not use generated-script mutations to replace them.

Call `check_clashes(include_self=True, include_duplicate_nodes=True)` with the project's required clearance. Use returned element references, routes/groups and assembly provenance to investigate. Retain unresolved candidates and geometric closure errors. A returned `status: success` means the tool ran; inspect `passed` and individual findings.

Run `verify_model()` for the cold-model gate when preparing evaluation. Read blockers and advisories. This gate does not know whether every drawing support was imported, so source reconciliation remains mandatory. Do not change clearance or omit self/duplicate checks merely to suppress failures.

Save concise verification evidence with the project: checkout/import path, source fingerprint or revision, tool names/arguments, findings and unresolved source entries. Avoid embedding complete flat node dumps in authored code or the handoff.

## Studio and evaluation

```text
<project-python> -m tuba.cli_studio <project-directory> --port <available-port> --no-open
```

Read the actual startup URL and open it in the browser. Studio is a separate service; launching it does not start or prove MCP use. Verify it serves the intended project and current source. Inspect the specific reported junction and representative supports in the live viewport before making visual claims.

Use `solve_model` only when evaluation is in scope and the model is ready. Read its current schema, qualify Code_Aster availability, and require real solved/imported artifacts before reporting stress, displacement, reaction, compliance or operating-state results. Stop evaluation with the concrete blocker if any required step fails.
