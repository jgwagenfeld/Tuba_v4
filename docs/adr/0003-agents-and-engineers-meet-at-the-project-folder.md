---
status: accepted
---

# Agents and engineers meet at the project folder

An authoring session is shared between processes only through the project folder on disk. The MCP server and the studio each run the same session code in their own process and learn of each other's work from the model script and the evidence written there, so a project also carries its evidence with it (`<project>/evidence/<operation>/`). Tools rewrite only generated model scripts; authored model scripts are read, solved and reviewed but never rewritten.

We chose this over a studio-hosted session that agents call over HTTP, which would make agent editing depend on a running studio and bypass every other editor, and over editing authored scripts as source text, which is a hard problem of its own that can be added later behind the same session. As a consequence the MCP process sends no viewer events: a viewer sees an agent's change when the studio watching the folder picks it up.

This assumes both processes run on one machine, in the same environment (both Windows or both WSL), against a project folder on a local disk; network shares and synced folders weaken the file locking and change detection it relies on. Authoring across machines, such as a remote agent editing a project viewed in a local studio, is out of scope and would reopen the studio-hosted alternative.
